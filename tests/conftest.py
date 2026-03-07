import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tests.factories import UserFactory, DocumentFactory, CompletedDocumentFactory


@pytest.fixture
def api_client():
    """Plain unauthenticated API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """A regular user in the DB."""
    return UserFactory()


@pytest.fixture
def other_user(db):
    """A second user — for ownership/isolation tests."""
    return UserFactory()


@pytest.fixture
def auth_client(db, user):
    """
    API client pre-authenticated as `user`.
    Uses JWT — same as real requests.
    """
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def other_auth_client(db, other_user):
    """API client authenticated as `other_user`."""
    client = APIClient()
    refresh = RefreshToken.for_user(other_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


@pytest.fixture
def document(db, user):
    """A pending document owned by `user`."""
    return DocumentFactory(owner=user)


@pytest.fixture
def completed_document(db, user):
    """A completed document owned by `user`."""
    return CompletedDocumentFactory(owner=user)


@pytest.fixture
def celery_eager(settings):
    """
    Makes Celery tasks execute synchronously in tests.
    No worker needed — task runs inline when .delay() is called.
    Critical for testing the full upload → process flow.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True  # Raises exceptions instead of swallowing
    yield


@pytest.fixture
def mock_groq_summarize(mocker):
    """Mocks the summarize_document function."""
    return mocker.patch(
        "apps.documents.ai.summarize_document",
        return_value="• Test summary point one.\n• Test summary point two.",
    )


@pytest.fixture
def mock_groq_entities(mocker):
    """Mocks the extract_entities function."""
    return mocker.patch(
        "apps.documents.ai.extract_entities",
        return_value={
            "people": ["Jane Doe"],
            "organizations": ["Test Corp"],
            "dates": ["2024-01-01"],
            "locations": ["London"],
            "key_topics": ["testing", "django"],
        },
    )


@pytest.fixture
def mock_groq_qa(mocker):
    """Mocks the answer_question function."""
    return mocker.patch(
        "apps.documents.ai.answer_question",
        return_value="This is a test answer based on the document.",
    )


@pytest.fixture
def mock_extract_text(mocker):
    """Mocks file text extraction — avoids reading real files in task tests."""
    return mocker.patch(
        "apps.documents.utils.extract_text_from_document",
        return_value="This is the extracted text content of the test document.",
    )