import magic
from django.conf import settings
from django.core.exceptions import ValidationError


def validate_file_size(file):
    """
    Rejects files over MAX_UPLOAD_SIZE_MB.
    We check size before reading content — fail fast.
    """
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(
            f"File size {file.size / (1024*1024):.1f}MB exceeds "
            f"the {settings.MAX_UPLOAD_SIZE_MB}MB limit."
        )


def validate_file_type(file):
    """
    Validates the REAL file type by reading the first 2048 bytes
    (the 'magic bytes') rather than trusting the file extension.

    Why: A user can rename 'malware.exe' to 'report.pdf'.
    python-magic catches this by reading the actual file signature.
    """
    file.seek(0)  # Ensure we're reading from the beginning
    mime_type = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)  # Reset for subsequent reads

    if mime_type not in settings.ALLOWED_DOCUMENT_TYPES:
        raise ValidationError(
            f"File type '{mime_type}' is not supported. "
            f"Allowed types: PDF, JPEG, PNG, WebP."
        )
    return mime_type  # Return so the model can store it