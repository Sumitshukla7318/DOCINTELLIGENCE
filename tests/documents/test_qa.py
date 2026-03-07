import pytest
from django.urls import reverse
from tests.factories import DocumentFactory, CompletedDocumentFactory


@pytest.mark.django_db
class TestDocumentQA:

    def test_qa_success(self, auth_client, completed_document, mock_groq_qa):
        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        response = auth_client.post(url, {"question": "What is this document about?"})

        assert response.status_code == 200
        assert response.data["question"] == "What is this document about?"
        assert response.data["answer"] == "This is a test answer based on the document."
        assert str(response.data["document_id"]) == str(completed_document.id)

    def test_qa_on_pending_document_rejected(self, auth_client, document):
        url = reverse("document-qa", kwargs={"pk": document.id})
        response = auth_client.post(url, {"question": "Any question?"})
        assert response.status_code == 400
        assert "not ready" in response.data["detail"]

    def test_qa_requires_auth(self, api_client, completed_document):
        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        response = api_client.post(url, {"question": "Question?"})
        assert response.status_code == 401

    def test_qa_wrong_user_gets_404(self, other_auth_client, completed_document):
        """Other user should get 404, not 403 — don't leak document existence."""
        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        response = other_auth_client.post(url, {"question": "Question?"})
        assert response.status_code == 404

    def test_qa_empty_question_rejected(self, auth_client, completed_document):
        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        response = auth_client.post(url, {"question": ""})
        assert response.status_code == 400

    def test_qa_question_too_short(self, auth_client, completed_document):
        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        response = auth_client.post(url, {"question": "Hi"})  # min_length is 3
        assert response.status_code == 400

    def test_qa_groq_failure_returns_503(self, auth_client, completed_document, mocker):
        mocker.patch(
            "apps.documents.ai.answer_question",
            side_effect=Exception("Groq is down"),
        )
        mocker.patch(
            "apps.documents.utils.extract_text_from_document",
            return_value="Some text",
        )
        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        response = auth_client.post(url, {"question": "What is this about?"})
        assert response.status_code == 503