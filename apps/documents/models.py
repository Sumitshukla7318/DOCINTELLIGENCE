import uuid
import os
from django.conf import settings
from django.db import models


def document_upload_path(instance, filename):
    """
    Generates a unique upload path per user:
    documents/user-uuid/doc-uuid/filename

    Why per-user folders? Makes it trivial to list or delete
    all documents for a specific user in S3.
    """
    ext = os.path.splitext(filename)[1].lower()
    return f"documents/{instance.owner_id}/{instance.id}{ext}"


class Document(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"        # Just uploaded, not yet processed
        PROCESSING = "processing", "Processing"  # Celery task running
        COMPLETED = "completed", "Completed"  # AI processing done
        FAILED = "failed", "Failed"           # Something went wrong

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    # File metadata
    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=document_upload_path)
    file_size = models.PositiveBigIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100)

    # Processing state
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,    # We'll filter by status often
    )
    error_message = models.TextField(blank=True)  # Store failure reason

    # AI results (Phase 3 will populate these)
    summary = models.TextField(blank=True)
    extracted_entities = models.JSONField(default=dict, blank=True)

    # Webhook (Phase 5)
    webhook_url = models.URLField(blank=True)
    webhook_delivered = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.status})"

    @property
    def file_size_display(self) -> str:
        """Human-readable file size."""
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class QAHistory(models.Model):
    """
    Stores every Q&A interaction on a document.

    Why a separate model and not JSONField on Document?
    - Each Q&A is independently queryable
    - You can paginate history
    - You can delete individual entries
    - You can add per-entry feedback later (thumbs up/down)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="qa_history",
    )
    question = models.TextField()
    answer = models.TextField()
    asked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-asked_at"]
        indexes = [
            models.Index(fields=["document", "asked_at"]),
        ]

    def __str__(self):
        return f"Q: {self.question[:50]} — {self.document.title}"