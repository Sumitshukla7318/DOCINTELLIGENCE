import pytest
from django.urls import reverse
from apps.documents.models import Document
from tests.factories import DocumentFactory, CompletedDocumentFactory


@pytest.mark.django_db
class TestDocumentRetry:

    def test_retry_failed_document_success(self, auth_client, user, mocker):
        document = DocumentFactory(
            owner=user,
            status=Document.Status.FAILED,
            error_message="Groq API was down",
        )
        mocker.patch("apps.documents.tasks.process_document.delay")

        url = reverse("document-retry", kwargs={"pk": document.id})
        response = auth_client.post(url)

        assert response.status_code == 200
        assert response.data["status"] == "pending"
        assert response.data["error_message"] == ""

    def test_retry_resets_error_message(self, auth_client, user, mocker):
        document = DocumentFactory(
            owner=user,
            status=Document.Status.FAILED,
            error_message="Some previous error",
        )
        mocker.patch("apps.documents.tasks.process_document.delay")

        url = reverse("document-retry", kwargs={"pk": document.id})
        auth_client.post(url)

        document.refresh_from_db()
        assert document.error_message == ""
        assert document.status == Document.Status.PENDING

    def test_retry_triggers_celery_task(self, auth_client, user, mocker):
        document = DocumentFactory(
            owner=user,
            status=Document.Status.FAILED,
        )
        mock_task = mocker.patch("apps.documents.tasks.process_document.delay")

        url = reverse("document-retry", kwargs={"pk": document.id})
        auth_client.post(url)

        mock_task.assert_called_once_with(str(document.id))

    def test_retry_completed_document_rejected(self, auth_client, user):
        document = CompletedDocumentFactory(owner=user)

        url = reverse("document-retry", kwargs={"pk": document.id})
        response = auth_client.post(url)

        assert response.status_code == 400
        assert "failed documents" in response.data["detail"]

    def test_retry_pending_document_rejected(self, auth_client, user):
        document = DocumentFactory(
            owner=user,
            status=Document.Status.PENDING,
        )
        url = reverse("document-retry", kwargs={"pk": document.id})
        response = auth_client.post(url)

        assert response.status_code == 400

    def test_retry_wrong_user_gets_404(self, other_auth_client, user):
        document = DocumentFactory(
            owner=user,
            status=Document.Status.FAILED,
        )
        url = reverse("document-retry", kwargs={"pk": document.id})
        response = other_auth_client.post(url)

        assert response.status_code == 404

    def test_retry_requires_auth(self, api_client, user):
        document = DocumentFactory(
            owner=user,
            status=Document.Status.FAILED,
        )
        url = reverse("document-retry", kwargs={"pk": document.id})
        response = api_client.post(url)

        assert response.status_code == 401