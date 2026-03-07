import hashlib
import hmac
import json
import logging
import time
import uuid
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def build_webhook_payload(document) -> dict:
    """
    Builds the standardized payload sent to webhook URLs.
    We include enough info that the receiver doesn't need
    to call our API again to get basic document info.
    """
    return {
        "event": "document.processed",
        "timestamp": document.processed_at.isoformat() if document.processed_at else None,
        "delivery_id": str(uuid.uuid4()),   # Unique per delivery attempt
        "data": {
            "document_id": str(document.id),
            "title": document.title,
            "status": document.status,
            "mime_type": document.mime_type,
            "processed_at": document.processed_at.isoformat() if document.processed_at else None,
            "summary_available": bool(document.summary),
            "entities_available": bool(document.extracted_entities),
        },
    }


def generate_webhook_signature(payload_json: str, secret: str) -> str:
    """
    Generates an HMAC-SHA256 signature of the payload.

    Why signatures? The receiver needs to verify the request
    actually came from us — not an attacker who knows their webhook URL.
    The receiver computes the same HMAC with their secret and compares.

    This is exactly how GitHub, Stripe, and Shopify webhooks work.
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def deliver_webhook(document) -> bool:
    """
    Delivers a webhook notification to the document's webhook_url.

    Returns True if delivery succeeded, False otherwise.
    Handles timeouts and connection errors gracefully.
    """
    if not document.webhook_url:
        return False

    payload = build_webhook_payload(document)
    payload_json = json.dumps(payload, default=str)

    # Use document ID as signing secret — in production you'd
    # store a per-user webhook secret on the User model
    signature = generate_webhook_signature(
        payload_json,
        str(document.owner_id),
    )

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Event": "document.processed",
        "User-Agent": "DocumentIntelligence-Webhook/1.0",
    }

    timeout = getattr(settings, "WEBHOOK_TIMEOUT_SECONDS", 10)

    try:
        response = requests.post(
            document.webhook_url,
            data=payload_json,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        logger.info(
            "Webhook delivered for document %s → %s (HTTP %s)",
            document.id, document.webhook_url, response.status_code,
        )
        return True

    except requests.exceptions.Timeout:
        logger.warning("Webhook timed out for document %s", document.id)
        raise

    except requests.exceptions.ConnectionError as exc:
        logger.warning("Webhook connection error for document %s: %s", document.id, exc)
        raise

    except requests.exceptions.HTTPError as exc:
        logger.warning(
            "Webhook HTTP error for document %s: %s",
            document.id, exc.response.status_code,
        )
        raise

    except Exception as exc:
        logger.exception("Unexpected webhook error for document %s: %s", document.id, exc)
        raise