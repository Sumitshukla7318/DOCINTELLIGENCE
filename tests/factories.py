import factory
from faker import Faker
from django.core.files.base import ContentFile
from apps.users.models import User
from apps.documents.models import Document

fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    """
    Creates a real User in the test DB.
    Each call generates unique email/name so tests don't collide.
    """
    class Meta:
        model = User

    email = factory.LazyFunction(lambda: fake.unique.email())
    first_name = factory.LazyFunction(lambda: fake.first_name())
    last_name = factory.LazyFunction(lambda: fake.last_name())
    is_active = True
    daily_upload_limit = 20

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Use our custom manager so password is hashed correctly
        password = kwargs.pop("password", "TestPass123!")
        user = model_class.objects.create_user(*args, password=password, **kwargs)
        return user


class DocumentFactory(factory.django.DjangoModelFactory):
    """
    Creates a Document with a real (tiny) in-memory PDF file.
    Avoids hitting disk or S3 in tests.
    """
    class Meta:
        model = Document

    owner = factory.SubFactory(UserFactory)
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=4))
    original_filename = factory.LazyFunction(lambda: f"{fake.word()}.pdf")
    mime_type = "application/pdf"
    file_size = 1024
    status = Document.Status.PENDING
    webhook_url = ""

    # Minimal valid PDF bytes — just enough for the file field
    file = factory.LazyAttribute(
        lambda obj: ContentFile(
            b"%PDF-1.4 1 0 obj<</Type /Catalog>>endobj",
            name=obj.original_filename,
        )
    )


class CompletedDocumentFactory(DocumentFactory):
    """A document that has already been processed — for Q&A tests."""
    status = Document.Status.COMPLETED
    summary = "• This is a test summary.\n• It has two bullet points."
    extracted_entities = {
        "people": ["John Doe"],
        "organizations": ["Acme Corp"],
        "dates": ["2024-01-01"],
        "locations": ["New York"],
        "key_topics": ["testing"],
    }