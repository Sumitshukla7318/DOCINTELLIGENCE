from rest_framework import serializers
from .models import Document,QAHistory
from .validators import validate_file_size, validate_file_type


class DocumentUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField()
    webhook_url = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = Document
        fields = ("id", "title", "file", "webhook_url")
        read_only_fields = ("id",)

    def validate_file(self, file):
        validate_file_size(file)
        mime_type = validate_file_type(file)
        self._mime_type = mime_type
        return file

    def create(self, validated_data):
        file = validated_data["file"]
        return Document.objects.create(
            owner=self.context["request"].user,
            title=validated_data["title"],
            original_filename=file.name,
            file=file,
            file_size=file.size,
            mime_type=getattr(self, "_mime_type", file.content_type or ""),
            webhook_url=validated_data.get("webhook_url", ""),
            status=Document.Status.PENDING,
        )


class DocumentListSerializer(serializers.ModelSerializer):
    file_size_display = serializers.CharField(read_only=True)

    class Meta:
        model = Document
        fields = (
            "id", "title", "original_filename", "mime_type",
            "status", "file_size_display", "created_at",
        )


class DocumentDetailSerializer(serializers.ModelSerializer):
    file_size_display = serializers.CharField(read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            "id", "title", "original_filename", "mime_type",
            "status", "error_message", "file_size_display",
            "file_url", "summary", "extracted_entities",
            "webhook_url", "webhook_delivered",
            "created_at", "updated_at", "processed_at",
        )

    def get_file_url(self, obj) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url
    

    
    
class DocumentQASerializer(serializers.Serializer):
    """Request serializer for document Q&A endpoint."""
    question = serializers.CharField(
        min_length=3,
        max_length=500,
        trim_whitespace=True,
    )


class DocumentQAResponseSerializer(serializers.Serializer):
    """Response serializer — for Swagger docs only."""
    question = serializers.CharField()
    answer = serializers.CharField()
    document_id = serializers.UUIDField()


class QAHistorySerializer(serializers.ModelSerializer):
    """Serializer for Q&A history entries."""

    class Meta:
        model = QAHistory
        fields = ("id", "question", "answer", "asked_at")
        read_only_fields = ("id", "asked_at")