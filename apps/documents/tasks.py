import logging
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    time_limit=1800,
    soft_time_limit=1500,
    name="documents.process_document",
)
def process_document(self, document_id: str):
    """
    Orchestrates full AI processing pipeline for a document:
    1. Extract raw text from file
    2. Summarize with OpenAI
    3. Extract entities with OpenAI
    4. Mark COMPLETED
    5. Trigger webhook (Phase 5)
    """
    from .models import Document
    from .utils import extract_text_from_document, truncate_text
    from .ai import summarize_document, extract_entities

    logger.info("Starting processing for document: %s", document_id)

    try:
        # --- Load document ---
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            logger.warning("Document %s not found, skipping.", document_id)
            return

        if document.status == Document.Status.COMPLETED:
            logger.info("Document %s already completed, skipping.", document_id)
            return

        # --- Mark PROCESSING ---
        document.status = Document.Status.PROCESSING
        document.save(update_fields=["status", "updated_at"])

        # --- Extract text ---
        file_path = document.file.path
        raw_text = extract_text_from_document(file_path, document.mime_type)
        text_for_ai = truncate_text(raw_text)

        # --- Summarize ---
        logger.info("Running summarization for document %s", document_id)
        summary = summarize_document(text_for_ai)

        # --- Extract entities ---
        logger.info("Running entity extraction for document %s", document_id)
        entities = extract_entities(text_for_ai)

        # --- Mark COMPLETED ---
        document.status = Document.Status.COMPLETED
        document.summary = summary
        document.extracted_entities = entities
        document.processed_at = timezone.now()
        document.error_message = ""
        document.save(update_fields=[
            "status", "summary", "extracted_entities",
            "processed_at", "error_message", "updated_at",
        ])

        logger.info("Document %s processed successfully.", document_id)

        # Phase 5: trigger_webhook.delay(document_id) goes here

    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded for document %s", document_id)
        _mark_failed(document_id, "Processing timed out.")
        raise

    except Exception as exc:
        logger.exception("Error processing document %s: %s", document_id, exc)
        if self.request.retries >= self.max_retries:
            _mark_failed(document_id, str(exc))
        raise


def _mark_failed(document_id: str, error_message: str):
    from .models import Document
    try:
        Document.objects.filter(id=document_id).update(
            status=Document.Status.FAILED,
            error_message=error_message,
            updated_at=timezone.now(),
        )
    except Exception as exc:
        logger.exception("Failed to mark document %s as failed: %s", document_id, exc)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    name="documents.trigger_webhook",
)
def trigger_webhook(self, document_id: str):
    """
    Delivers a webhook notification after document processing completes.

    Separated from process_document intentionally:
    - Webhook failure should never affect document processing status
    - Webhook retries are independent of processing retries
    - Clean separation of concerns
    """
    from .models import Document
    from .webhooks import deliver_webhook

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.warning("Webhook: document %s not found.", document_id)
        return

    if not document.webhook_url:
        logger.info("No webhook URL for document %s, skipping.", document_id)
        return

    if document.webhook_delivered:
        logger.info("Webhook already delivered for document %s, skipping.", document_id)
        return

    try:
        deliver_webhook(document)
        # Mark as delivered so we don't re-send on task replay
        Document.objects.filter(id=document_id).update(
            webhook_delivered=True,
        )
        logger.info("Webhook marked as delivered for document %s.", document_id)

    except Exception as exc:
        logger.warning(
            "Webhook delivery failed for document %s (attempt %s/%s): %s",
            document_id, self.request.retries + 1, self.max_retries + 1, exc,
        )
        raise  # Celery handles retry