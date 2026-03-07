import logging
from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
    OpenApiParameter,
   
)
from drf_spectacular.types import OpenApiTypes
from django_ratelimit.decorators import ratelimit

from .models import Document,QAHistory
from .serializers import (
    DocumentUploadSerializer,
    DocumentListSerializer,
    DocumentDetailSerializer,
    DocumentQASerializer,
    DocumentQAResponseSerializer,
    QAHistorySerializer,
)
from common.ratelimit import check_daily_upload_limit

logger = logging.getLogger(__name__)


@method_decorator(
    ratelimit(key="user", rate="10/m", method="POST", block=True),
    name="post",
)
class DocumentUploadView(generics.CreateAPIView):
    serializer_class = DocumentUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=["Documents"],
        summary="Upload a document",
        description=(
            "Upload a PDF or image file for AI processing. "
            "Processing happens asynchronously — the response returns immediately "
            "with `status: pending`. Poll `GET /documents/{id}/` to check progress.\n\n"
            "**Supported formats:** PDF, JPEG, PNG, WebP\n"
            "**Max file size:** 20MB\n"
            "**Rate limit:** 10 uploads/minute, 20 uploads/day"
        ),
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Human-readable document title"},
                    "file": {"type": "string", "format": "binary"},
                    "webhook_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "Optional URL to notify when processing completes",
                    },
                },
                "required": ["title", "file"],
            }
        },
        responses={
            201: DocumentDetailSerializer,
            400: OpenApiResponse(description="Invalid file type, size exceeded, or missing fields"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
    )
    def post(self, request, *args, **kwargs):
        is_allowed, current_count, limit = check_daily_upload_limit(request.user)
        if not is_allowed:
            return Response(
                {
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": (
                            f"Daily upload limit reached. "
                            f"You have uploaded {current_count}/{limit} documents today."
                        ),
                        "details": {
                            "current_count": current_count,
                            "limit": limit,
                            "resets_at": "midnight UTC",
                        },
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()

        from apps.documents.tasks import process_document
        process_document.delay(str(document.id))

        return Response(
            DocumentDetailSerializer(document, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentListView(generics.ListAPIView):
    serializer_class = DocumentListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Document.objects.filter(owner=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter in Document.Status.values:
            qs = qs.filter(status=status_filter)
        return qs

    @extend_schema(
        tags=["Documents"],
        summary="List my documents",
        description="Returns all documents belonging to the authenticated user. Supports filtering by status and ordering.",
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by processing status",
                enum=["pending", "processing", "completed", "failed"],
                required=False,
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Sort field. Prefix with `-` for descending.",
                enum=["created_at", "-created_at", "title", "-title"],
                required=False,
            ),
        ],
        responses={200: DocumentListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DocumentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = DocumentDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    @extend_schema(
        tags=["Documents"],
        summary="Get document details",
        description=(
            "Returns full document details including AI results. "
            "Poll this endpoint after upload to check when `status` becomes `completed`."
        ),
        responses={
            200: DocumentDetailSerializer,
            404: OpenApiResponse(description="Document not found or doesn't belong to you"),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Documents"],
        summary="Delete a document",
        description="Permanently deletes the document and its file from storage.",
        responses={
            204: OpenApiResponse(description="Document deleted"),
            404: OpenApiResponse(description="Document not found"),
        },
    )
    def delete(self, request, *args, **kwargs):
        document = self.get_object()
        if document.file:
            document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentQAView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Documents"],
        summary="Ask a question about a document",
        description=(
            "Ask any natural language question and get an answer grounded strictly "
            "in the document's content. The AI will not hallucinate — if the answer "
            "isn't in the document, it says so.\n\n"
            "Document must have `status: completed` before Q&A is available."
        ),
        request=DocumentQASerializer,
        responses={
            200: DocumentQAResponseSerializer,
            400: OpenApiResponse(description="Document not yet processed or invalid question"),
            404: OpenApiResponse(description="Document not found"),
            503: OpenApiResponse(description="AI service temporarily unavailable"),
        },
        examples=[
            OpenApiExample(
                "Ask about document content",
                value={"question": "What are the main conclusions of this document?"},
                request_only=True,
            ),
            OpenApiExample(
                "Ask about a specific entity",
                value={"question": "Who are the key people mentioned?"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, pk):
        try:
            document = Document.objects.get(id=pk, owner=request.user)
        except Document.DoesNotExist:
            return Response(
                {"detail": "Document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if document.status != Document.Status.COMPLETED:
            return Response(
                {
                    "detail": (
                        f"Document is not ready for Q&A. "
                        f"Current status: {document.status}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DocumentQASerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["question"]

        try:
            from .utils import extract_text_from_document, truncate_text
            from .ai import answer_question
            raw_text = extract_text_from_document(document.file.path, document.mime_type)
            text_for_ai = truncate_text(raw_text)
            answer = answer_question(text_for_ai, question)
        except Exception as exc:
            logger.exception("Q&A failed for document %s: %s", pk, exc)
            return Response(
                {"detail": "Failed to process your question. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        
        QAHistory.objects.create(
            document=document,
            question=question,
            answer=answer,
        )


        return Response({
            "document_id": str(document.id),
            "question": question,
            "answer": answer,
        })


def handle_ratelimited(request, exception):
    from rest_framework.response import Response
    return Response(
        {
            "error": {
                "code": "rate_limit_exceeded",
                "message": "Too many requests. Maximum 10 uploads per minute.",
                "details": {},
            }
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )


class DocumentRetryView(APIView):
    """
    POST /api/v1/documents/<id>/retry/

    Re-queues a FAILED document for AI processing.
    Only works on documents with status: "failed".
    No file re-upload needed — uses the existing file.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Documents"],
        summary="Retry processing a failed document",
        description=(
            "Re-queues a failed document for AI processing. "
            "Only documents with `status: failed` can be retried. "
            "The original file is reused — no re-upload needed."
        ),
        responses={
            200: DocumentDetailSerializer,
            400: OpenApiResponse(description="Document is not in failed state"),
            404: OpenApiResponse(description="Document not found"),
        },
    )
    def post(self, request, pk):
        # Ownership check
        try:
            document = Document.objects.get(id=pk, owner=request.user)
        except Document.DoesNotExist:
            return Response(
                {"detail": "Document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Only FAILED documents can be retried
        if document.status != Document.Status.FAILED:
            return Response(
                {
                    "detail": (
                        f"Only failed documents can be retried. "
                        f"Current status: {document.status}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reset document state before re-queuing
        document.status = Document.Status.PENDING
        document.error_message = ""
        document.summary = ""
        document.extracted_entities = {}
        document.processed_at = None
        document.save(update_fields=[
            "status", "error_message", "summary",
            "extracted_entities", "processed_at", "updated_at",
        ])

        # Re-queue the Celery task
        from apps.documents.tasks import process_document
        process_document.delay(str(document.id))

        logger.info(
            "Document %s re-queued for processing by user %s",
            document.id, request.user.id,
        )

        return Response(
            DocumentDetailSerializer(document, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

class DocumentQAHistoryView(generics.ListAPIView):
    """
    GET /api/v1/documents/<id>/qa/history/

    Returns all Q&A interactions on a document,
    most recent first.

    Why this is useful:
    - User asked the same question twice — they can see
      the previous answer without hitting Groq again
    - Audit trail of what was asked about a document
    - Foundation for a "suggested questions" feature later
    """
    serializer_class = QAHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Documents"],
        summary="Get Q&A history for a document",
        description=(
            "Returns all questions and answers for a document, "
            "ordered most recent first. "
            "Only the document owner can view history."
        ),
        responses={
            200: QAHistorySerializer(many=True),
            404: OpenApiResponse(description="Document not found"),
        },
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # Ownership check — verify document belongs to user
        try:
            document = Document.objects.get(
                id=self.kwargs["pk"],
                owner=self.request.user,
            )
        except Document.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound("Document not found.")

        return QAHistory.objects.filter(document=document)