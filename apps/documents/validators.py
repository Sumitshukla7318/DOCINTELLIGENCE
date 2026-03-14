from django.conf import settings
from django.core.exceptions import ValidationError


def validate_file_size(file):
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(
            f"File size {file.size / (1024*1024):.1f}MB exceeds "
            f"the {settings.MAX_UPLOAD_SIZE_MB}MB limit."
        )


def validate_file_type(file):
    try:
        import magic
        file.seek(0)
        mime_type = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)
    except Exception:
        # libmagic not available — fall back to extension check
        import os
        ext = os.path.splitext(file.name)[1].lower()
        ext_map = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime_type = ext_map.get(ext)
        if not mime_type:
            raise ValidationError(
                f"File type not supported. "
                f"Allowed types: PDF, JPEG, PNG, WebP."
            )

    if mime_type not in settings.ALLOWED_DOCUMENT_TYPES:
        raise ValidationError(
            f"File type '{mime_type}' is not supported. "
            f"Allowed types: PDF, JPEG, PNG, WebP."
        )
    return mime_type