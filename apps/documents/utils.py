import re
import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


def extract_text_from_document(file_path: str, mime_type: str) -> str:
    try:
        if mime_type == "application/pdf":
            return _extract_from_pdf(file_path)
        elif mime_type.startswith("image/"):
            return _extract_from_image(file_path)
        else:
            logger.warning("Unsupported mime type for extraction: %s", mime_type)
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
            logger.warning("PDF is encrypted, skipping: %s", file_path)
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
    """
    Cleans common PDF extraction artifacts:

    1. Standalone line numbers (code listing PDFs)
       "2\n3\n4\n91\n91\n92" → removed entirely

    2. Inline numbers between content lines
       "some text\n42\nmore text" → "some text\nmore text"

    3. Single character garbage lines
       "त र  क  र ा" style lines → removed
       (symptom of bad font encoding in scanned PDFs)

    4. Excessive whitespace and control characters
    """

    # Remove lines that are ONLY a number (standalone line numbers)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Remove inline line numbers — single numbers between content
    text = re.sub(r'\n\d+\n', '\n', text)

    # Collapse 3+ newlines into 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Process line by line — remove garbage lines
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        words = line.split()
        if words:
            # If more than 70% of words are single characters
            # it's a garbage line (bad encoding artifact)
            single_char_count = sum(1 for w in words if len(w) == 1)
            ratio = single_char_count / len(words)
            if ratio > 0.7:
                continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)

    # Normalize multiple spaces to single space
    cleaned = re.sub(r' {2,}', ' ', cleaned)

    # Remove null bytes and control characters
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

    return cleaned


def _is_garbage_text(text: str) -> bool:
    """
    Detects if extracted text is unreadable garbage.

    Checks:
    - Too short to be meaningful (under 50 chars)
    - High ratio of single chars to total words
      → symptom of bad font encoding
    """
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
    """
    Truncates text to fit within Groq's context window.
    Truncates at a word boundary to avoid cutting mid-word.
    """
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.9:
        truncated = truncated[:last_space]
    return truncated + "\n\n[Content truncated for processing...]"
