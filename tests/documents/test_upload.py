import pytest
import io
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.documents.models import Document


def make_pdf_file(name="test.pdf", size_bytes=1024):
    """Creates a minimal in-memory PDF file for upload tests."""
    content = b"%PDF-1.4 " + b"A" * size_bytes
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def make_image_file(name="test.jpg"):
    """Creates a minimal JPEG file."""
    # Minimal JPEG magic bytes
    content = bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"\x00" * 100
    return SimpleUploadedFile(name, content, content_type="image/jpeg")


@pytest.mark.django_db
class TestDocumentUpload:

    def test_upload_pdf_success(self, auth_client, mocker):
        mocker.patch("apps.documents.tasks.process_document.delay")
        url = reverse("document-upload")
        response = auth_client.post(url, {
            "title": "My Test Document",
            "file": make_pdf_file(),
        }, format="multipart")

        assert response.status_code == 201
        assert response.data["status"] == "pending"
        assert response.data["title"] == "My Test Document"
        assert response.data["mime_type"] == "application/pdf"
        assert Document.objects.count() == 1

    def test_upload_triggers_celery_task(self, auth_client, mocker):
        mock_task = mocker.patch("apps.documents.tasks.process_document.delay")
        url = reverse("document-upload")
        auth_client.post(url, {
            "title": "Test",
            "file": make_pdf_file(),
        }, format="multipart")

        # Verify the task was called with the document's ID
        assert mock_task.called
        document = Document.objects.first()
        mock_task.assert_called_once_with(str(document.id))

    def test_upload_requires_auth(self, api_client):
        url = reverse("document-upload")
        response = api_client.post(url, {
            "title": "Test",
            "file": make_pdf_file(),
        }, format="multipart")
        assert response.status_code == 401

    def test_upload_file_too_large(self, auth_client, settings):
        settings.MAX_UPLOAD_SIZE_MB = 1   # Set 1MB limit for this test
        large_content = b"%PDF-1.4 " + b"A" * (2 * 1024 * 1024)  # 2MB
        large_file = SimpleUploadedFile("big.pdf", large_content, content_type="application/pdf")

        url = reverse("document-upload")
        response = auth_client.post(url, {
            "title": "Big File",
            "file": large_file,
        }, format="multipart")
        assert response.status_code == 400

    def test_upload_wrong_file_type(self, auth_client):
        # .exe file disguised as PDF
        fake_file = SimpleUploadedFile(
            "malware.pdf",
            b"MZ\x90\x00\x03",   # Real EXE magic bytes
            content_type="application/pdf",
        )
        url = reverse("document-upload")
        response = auth_client.post(url, {
            "title": "Definitely Not Malware",
            "file": fake_file,
        }, format="multipart")
        assert response.status_code == 400

    def test_upload_missing_title(self, auth_client):
        url = reverse("document-upload")
        response = auth_client.post(url, {
            "file": make_pdf_file(),
        }, format="multipart")
        assert response.status_code == 400

    def test_daily_limit_enforced(self, auth_client, user, mocker, settings):
        settings.DAILY_UPLOAD_LIMIT = 2
        user.daily_upload_limit = 2
        user.save()

        mocker.patch("apps.documents.tasks.process_document.delay")
        url = reverse("document-upload")

        # First two uploads succeed
        for _ in range(2):
            resp = auth_client.post(url, {
                "title": "Doc",
                "file": make_pdf_file(),
            }, format="multipart")
            assert resp.status_code == 201

        # Third upload is blocked
        response = auth_client.post(url, {
            "title": "One Too Many",
            "file": make_pdf_file(),
        }, format="multipart")
        assert response.status_code == 429
        assert response.data["error"]["code"] == "rate_limit_exceeded"

    def test_users_cannot_see_each_others_documents(
        self, auth_client, other_auth_client, user, other_user, mocker
    ):
        mocker.patch("apps.documents.tasks.process_document.delay")
        url = reverse("document-upload")

        # User uploads a document
        auth_client.post(url, {"title": "Private", "file": make_pdf_file()}, format="multipart")

        # Other user's list is empty
        list_url = reverse("document-list")
        response = other_auth_client.get(list_url)
        assert response.status_code == 200
        assert len(response.data) == 0