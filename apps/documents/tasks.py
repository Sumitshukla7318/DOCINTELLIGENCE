import os
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
    1. Download file (from Cloudinary in production, local path in dev)
    2. Extract raw text
    3. Summarize with Groq
    4. Extract entities with Groq
    5. Mark COMPLETED
    6. Trigger webhook if configured
    """
    from .models import Document
    from .utils import extract_text_from_document, truncate_text, download_file_to_temp
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

        # --- Download file to temp (handles both local + Cloudinary) ---
        temp_path = download_file_to_temp(document.file)

        try:
            # --- Extract text ---
            raw_text = extract_text_from_document(temp_path, document.mime_type)
            text_for_ai = truncate_text(raw_text)

            # --- Summarize ---
            logger.info("Running summarization for document %s", document_id)
            summary = summarize_document(text_for_ai)

            # --- Extract entities ---
            logger.info("Running entity extraction for document %s", document_id)
            entities = extract_entities(text_for_ai)

        finally:
            # Always clean up temp file whether success or failure
            _cleanup_temp_file(document, temp_path)

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

        # --- Trigger webhook if configured ---
        if document.webhook_url:
            trigger_webhook.delay(document_id)

    except SoftTimeLimitExceeded:
        logger.error("Soft time limit exceeded for document %s", document_id)
        _mark_failed(document_id, "Processing timed out.")
        raise

    except Exception as exc:
        logger.exception("Error processing document %s: %s", document_id, exc)
        if self.request.retries >= self.max_retries:
            _mark_failed(document_id, str(exc))
        raise


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
    Delivers webhook notification after document processing completes.
    Separated from process_document so webhook failures never
    affect document processing status.
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
        Document.objects.filter(id=document_id).update(
            webhook_delivered=True,
        )
        logger.info("Webhook marked as delivered for document %s.", document_id)

    except Exception as exc:
        logger.warning(
            "Webhook delivery failed for document %s (attempt %s/%s): %s",
            document_id, self.request.retries + 1, self.max_retries + 1, exc,
        )
        raise


def _mark_failed(document_id: str, error_message: str):
    """Marks a document as FAILED with error message."""
    from .models import Document
    try:
        Document.objects.filter(id=document_id).update(
            status=Document.Status.FAILED,
            error_message=error_message,
            updated_at=timezone.now(),
        )
        logger.info("Marked document %s as FAILED: %s", document_id, error_message)
    except Exception as exc:
        logger.exception(
            "Failed to mark document %s as failed: %s", document_id, exc
        )


def _cleanup_temp_file(document, temp_path: str):
    """
    Cleans up temp file if it was downloaded from Cloudinary.
    For local storage, file.path == temp_path so nothing to delete.
    """
    try:
        local_path = document.file.path
        if local_path != temp_path:
            os.unlink(temp_path)
            logger.debug("Cleaned up temp file: %s", temp_path)
    except NotImplementedError:
        # Cloudinary — no local path, always clean up temp
        try:
            os.unlink(temp_path)
            logger.debug("Cleaned up Cloudinary temp file: %s", temp_path)
        except Exception as exc:
            logger.warning("Failed to clean up temp file %s: %s", temp_path, exc)
    except Exception as exc:
        logger.warning("Failed to clean up temp file %s: %s", temp_path, exc)