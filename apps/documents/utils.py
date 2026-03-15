import re
import logging
import tempfile
import requests
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

def download_file_to_temp(file_field) -> str:
    """
    Downloads file from Cloudinary to temp or returns local path.
    """
    try:
        # Try local path first (development)
        path = file_field.path
        logger.info("Using local file path: %s", path)
        return path
    except NotImplementedError:
        # Cloudinary — download to temp file
        url = file_field.url
        logger.info("Downloading from Cloudinary URL: %s", url)

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.exception("Failed to download file from Cloudinary: %s", exc)
            raise Exception(f"Could not download file for processing: {exc}")

        # Detect extension
        ext = ".pdf"
        if "image" in file_field.name:
            ext = ".jpg"
        name = file_field.name
        if "." in name:
            ext = "." + name.rsplit(".", 1)[-1]

        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=ext,
        )
        tmp.write(response.content)
        tmp.flush()
        tmp.close()

        logger.info(
            "Downloaded %d bytes to temp file: %s",
            len(response.content),
            tmp.name,
        )
        return tmp.name


def extract_text_from_document(file_path: str, mime_type: str) -> str:
    try:
        if mime_type == "application/pdf":
            return _extract_from_pdf(file_path)
        elif mime_type.startswith("image/"):
            return _extract_from_image(file_path)
        else:
            logger.warning("Unsupported mime type: %s", mime_type)
            return ""
    except Exception as exc:
        logger.exception("Text extraction failed for %s: %s", file_path, exc)
        return ""


def _extract_from_pdf(file_path: str) -> str:
    import pypdf

    text_parts = []

    with open(file_path, "rb") as f:
        reader = pypdf.PdfReader(f)

        if reader.is_encrypted:
            logger.warning("PDF is encrypted: %s", file_path)
            return ""

        for page_num, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text(
                    extraction_mode="layout",
                ) or ""
                page_text = _clean_text(page_text)
                if page_text.strip():
                    text_parts.append(page_text)
            except Exception as exc:
                logger.warning("Failed to extract page %d: %s", page_num, exc)
                continue

    full_text = "\n".join(text_parts).strip()

    if _is_garbage_text(full_text):
        logger.warning("PDF appears scanned or unreadable: %s", file_path)
        return (
            "This document appears to be a scanned PDF or contains "
            "non-extractable text. Please upload a text-based PDF."
        )

    logger.info("Extracted %d characters from PDF: %s", len(full_text), file_path)
    return full_text


def _clean_text(text: str) -> str:
    # Remove standalone line numbers
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Remove inline line numbers
    text = re.sub(r'\n\d+\n', '\n', text)

    # Collapse 3+ newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        words = line.split()
        if words:
            single_char_count = sum(1 for w in words if len(w) == 1)
            ratio = single_char_count / len(words)
            if ratio > 0.7:
                continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

    return cleaned


def _is_garbage_text(text: str) -> bool:
    if not text or len(text.strip()) < 50:
        return True
    words = text.split()
    if not words:
        return True
    single_chars = sum(1 for w in words if len(w) == 1)
    if len(words) > 10 and single_chars / len(words) > 0.5:
        return True
    return False


def _extract_from_image(file_path: str) -> str:
    try:
        with Image.open(file_path) as img:
            img.verify()
        return (
            f"[Image file: {Path(file_path).name} "
            f"— text extraction via AI in processing]"
        )
    except Exception as exc:
        logger.exception("Image validation failed: %s", exc)
        return ""


def truncate_text(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.9:
        truncated = truncated[:last_space]
    return truncated + "\n\n[Content truncated for processing...]"