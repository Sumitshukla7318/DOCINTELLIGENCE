import pytest
from unittest.mock import patch
from apps.documents.models import Document
from apps.documents.tasks import process_document
from tests.factories import DocumentFactory


@pytest.mark.django_db
class TestProcessDocumentTask:

    def test_task_marks_document_completed(
        self, db, mock_extract_text, mock_groq_summarize, mock_groq_entities
    ):
        document = DocumentFactory()

        process_document(str(document.id))

        document.refresh_from_db()
        assert document.status == Document.Status.COMPLETED
        assert document.summary != ""
        assert document.processed_at is not None

    def test_task_saves_summary_and_entities(
        self, db, mock_extract_text, mock_groq_summarize, mock_groq_entities
    ):
        document = DocumentFactory()

        process_document(str(document.id))

        document.refresh_from_db()
        assert "Test summary" in document.summary
        assert document.extracted_entities["people"] == ["Jane Doe"]
        assert document.extracted_entities["organizations"] == ["Test Corp"]

    def test_task_skips_nonexistent_document(self, db, mock_extract_text):
        """Task should exit gracefully if document was deleted before processing."""
        import uuid
        # Should not raise
        process_document(str(uuid.uuid4()))

    def test_task_skips_already_completed_document(
        self, db, mock_extract_text, mock_groq_summarize
    ):
        document = DocumentFactory(status=Document.Status.COMPLETED)

        process_document(str(document.id))

        # Summarize should never be called for already-completed docs
        mock_groq_summarize.assert_not_called()

    def test_task_marks_failed_after_max_retries(self, db, mock_extract_text, mocker):
        document = DocumentFactory()

        mocker.patch(
            "apps.documents.ai.summarize_document",
            side_effect=Exception("Groq API down"),
        )

        # Simulate task with retries exhausted
        with patch.object(process_document, "max_retries", 0):
            with pytest.raises(Exception):
                process_document(str(document.id))

        document.refresh_from_db()
        assert document.status == Document.Status.FAILED
        assert "Groq API down" in document.error_message

    def test_task_triggers_webhook_if_configured(
        self, db, mock_extract_text, mock_groq_summarize, mock_groq_entities, mocker
    ):
        document = DocumentFactory(webhook_url="https://example.com/hook")
        mock_webhook = mocker.patch("apps.documents.tasks.trigger_webhook")

        process_document(str(document.id))

        mock_webhook.delay.assert_called_once_with(str(document.id))


    def test_task_does_not_trigger_webhook_if_not_configured(
        self, db, mock_extract_text, mock_groq_summarize, mock_groq_entities, mocker
    ):
        document = DocumentFactory(webhook_url="")
        mock_webhook = mocker.patch("apps.documents.tasks.trigger_webhook")

        process_document(str(document.id))

        mock_webhook.assert_not_called()