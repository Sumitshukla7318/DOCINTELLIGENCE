import pytest
from django.urls import reverse
from apps.documents.models import QAHistory
from tests.factories import DocumentFactory, CompletedDocumentFactory


@pytest.mark.django_db
class TestQAHistory:

    def test_qa_saves_to_history(self, auth_client, completed_document, mocker):
        mocker.patch(
            "apps.documents.ai.answer_question",
            return_value="Test answer",
        )
        mocker.patch(
            "apps.documents.utils.extract_text_from_document",
            return_value="Some text",
        )

        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        auth_client.post(url, {"question": "What is this about?"})

        assert QAHistory.objects.count() == 1
        entry = QAHistory.objects.first()
        assert entry.question == "What is this about?"
        assert entry.answer == "Test answer"
        assert entry.document == completed_document

    def test_qa_history_multiple_entries(self, auth_client, completed_document, mocker):
        mocker.patch(
            "apps.documents.ai.answer_question",
            return_value="Some answer",
        )
        mocker.patch(
            "apps.documents.utils.extract_text_from_document",
            return_value="Some text",
        )

        url = reverse("document-qa", kwargs={"pk": completed_document.id})
        auth_client.post(url, {"question": "First question?"})
        auth_client.post(url, {"question": "Second question?"})
        auth_client.post(url, {"question": "Third question?"})

        assert QAHistory.objects.count() == 3

    def test_get_qa_history_success(self, auth_client, completed_document, db):
        # Create history entries directly
        QAHistory.objects.create(
            document=completed_document,
            question="What is this?",
            answer="It is a test document.",
        )
        QAHistory.objects.create(
            document=completed_document,
            question="Who wrote it?",
            answer="A test author.",
        )

        url = reverse("document-qa-history", kwargs={"pk": completed_document.id})
        response = auth_client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 2
        # Most recent first
        assert response.data[0]["question"] == "Who wrote it?"
        assert response.data[1]["question"] == "What is this?"

    def test_get_qa_history_empty(self, auth_client, completed_document):
        url = reverse("document-qa-history", kwargs={"pk": completed_document.id})
        response = auth_client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 0

    def test_get_qa_history_requires_auth(self, api_client, completed_document):
        url = reverse("document-qa-history", kwargs={"pk": completed_document.id})
        response = api_client.get(url)
        assert response.status_code == 401

    def test_get_qa_history_wrong_user_gets_404(
        self, other_auth_client, completed_document
    ):
        QAHistory.objects.create(
            document=completed_document,
            question="Secret question?",
            answer="Secret answer.",
        )
        url = reverse("document-qa-history", kwargs={"pk": completed_document.id})
        response = other_auth_client.get(url)
        assert response.status_code == 404

    def test_history_isolated_between_documents(self, auth_client, user, db):
        doc1 = CompletedDocumentFactory(owner=user)
        doc2 = CompletedDocumentFactory(owner=user)

        QAHistory.objects.create(
            document=doc1, question="Doc1 question?", answer="Doc1 answer."
        )
        QAHistory.objects.create(
            document=doc2, question="Doc2 question?", answer="Doc2 answer."
        )

        url = reverse("document-qa-history", kwargs={"pk": doc1.id})
        response = auth_client.get(url)

        assert len(response.data) == 1
        assert response.data[0]["question"] == "Doc1 question?"