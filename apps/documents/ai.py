import logging
from groq import Groq, RateLimitError, APITimeoutError, APIConnectionError
from django.conf import settings

logger = logging.getLogger(__name__)


def get_groq_client() -> Groq:
    return Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=60.0,
        max_retries=2,
    )


def summarize_document(text: str) -> str:
    if not text.strip():
        return "No text content available for summarization."

    client = get_groq_client()

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional document analyst. "
                        "Summarize documents accurately and concisely. "
                        "Only use information explicitly present in the document. "
                        "Never invent or infer facts not stated in the text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Please summarize the following document in 3-5 bullet points. "
                        f"Each bullet point should capture a key idea.\n\n"
                        f"Document:\n{text}"
                    ),
                },
            ],
        )
        summary = response.choices[0].message.content.strip()
        logger.info("Summarization completed. Tokens used: %s", response.usage.total_tokens)
        return summary

    except RateLimitError:
        logger.warning("Groq rate limit hit during summarization.")
        raise
    except (APITimeoutError, APIConnectionError) as exc:
        logger.error("Groq connectivity error during summarization: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected error during summarization: %s", exc)
        raise


def extract_entities(text: str) -> dict:
    if not text.strip():
        return {}

    client = get_groq_client()

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an information extraction system. "
                        "Extract entities from documents and return ONLY valid JSON. "
                        "No explanations, no markdown, no code blocks — raw JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Extract all named entities from this document. "
                        "Return a JSON object with these exact keys: "
                        "people, organizations, dates, locations, key_topics. "
                        "Each value must be a list of strings. "
                        "If none found for a category, return an empty list.\n\n"
                        f"Document:\n{text}"
                    ),
                },
            ],
        )
        raw = response.choices[0].message.content.strip()
        logger.info("Entity extraction completed. Tokens used: %s", response.usage.total_tokens)
        return _safe_parse_json(raw)

    except RateLimitError:
        logger.warning("Groq rate limit hit during entity extraction.")
        raise
    except (APITimeoutError, APIConnectionError) as exc:
        logger.error("Groq connectivity error during entity extraction: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected error during entity extraction: %s", exc)
        raise


def answer_question(text: str, question: str) -> str:
    if not text.strip():
        return "This document has no extractable text content to answer questions from."
    if not question.strip():
        return "Please provide a question."

    client = get_groq_client()

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                         "You are a precise document Q&A assistant. "
                         "Answer questions using the information in the provided document. "
                         "If the answer is explicitly stated, quote or paraphrase it directly. "
                         "If the answer can be reasonably inferred from the document content, "
                         "summarize what the document implies. "
                         "Only say 'This information is not available in the provided document' "
                         "if the topic is completely absent from the document. "
                         "Never use outside knowledge or facts not related to the document."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Document:\n{text}\n\n"
                        f"Question: {question}"
                    ),
                },
            ],
        )
        answer = response.choices[0].message.content.strip()
        logger.info("Q&A completed. Tokens used: %s", response.usage.total_tokens)
        return answer

    except RateLimitError:
        logger.warning("Groq rate limit hit during Q&A.")
        raise
    except (APITimeoutError, APIConnectionError) as exc:
        logger.error("Groq connectivity error during Q&A: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected error during Q&A: %s", exc)
        raise


def _safe_parse_json(raw: str) -> dict:
    import json
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    try:
        parsed = json.loads(raw)
        for key in ["people", "organizations", "dates", "locations", "key_topics"]:
            if key not in parsed:
                parsed[key] = []
        return parsed
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from Groq response: %s", raw[:200])
        return {
            "people": [], "organizations": [],
            "dates": [], "locations": [], "key_topics": [],
            "parse_error": True,
        }