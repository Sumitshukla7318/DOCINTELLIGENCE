import pytest
import responses as responses_mock
from apps.documents.webhooks import deliver_webhook, generate_webhook_signature, build_webhook_payload
from apps.documents.tasks import trigger_webhook
from tests.factories import CompletedDocumentFactory


class TestWebhookSignature:
    """Pure unit tests — no DB."""

    def test_signature_is_deterministic(self):
        sig1 = generate_webhook_signature('{"key": "value"}', "secret")
        sig2 = generate_webhook_signature('{"key": "value"}', "secret")
        assert sig1 == sig2

    def test_different_secrets_produce_different_signatures(self):
        sig1 = generate_webhook_signature('{"key": "value"}', "secret1")
        sig2 = generate_webhook_signature('{"key": "value"}', "secret2")
        assert sig1 != sig2

    def test_different_payloads_produce_different_signatures(self):
        sig1 = generate_webhook_signature('{"key": "value1"}', "secret")
        sig2 = generate_webhook_signature('{"key": "value2"}', "secret")
        assert sig1 != sig2


@pytest.mark.django_db
class TestWebhookDelivery:

    @responses_mock.activate
    def test_webhook_delivered_successfully(self, db):
        document = CompletedDocumentFactory(webhook_url="https://example.com/hook")
        responses_mock.add(
            responses_mock.POST,
            "https://example.com/hook",
            status=200,
        )

        result = deliver_webhook(document)

        assert result is True
        assert len(responses_mock.calls) == 1

    @responses_mock.activate
    def test_webhook_payload_structure(self, db):
        document = CompletedDocumentFactory(webhook_url="https://example.com/hook")
        responses_mock.add(responses_mock.POST, "https://example.com/hook", status=200)

        deliver_webhook(document)

        import json
        payload = json.loads(responses_mock.calls[0].request.body)
        assert payload["event"] == "document.processed"
        assert "timestamp" in payload
        assert "delivery_id" in payload
        assert payload["data"]["document_id"] == str(document.id)
        assert payload["data"]["status"] == "completed"

    @responses_mock.activate
    def test_webhook_includes_signature_header(self, db):
        document = CompletedDocumentFactory(webhook_url="https://example.com/hook")
        responses_mock.add(responses_mock.POST, "https://example.com/hook", status=200)

        deliver_webhook(document)

        headers = responses_mock.calls[0].request.headers
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")

    @responses_mock.activate
    def test_webhook_raises_on_timeout(self, db):
        import requests
        document = CompletedDocumentFactory(webhook_url="https://example.com/hook")
        responses_mock.add(
            responses_mock.POST,
            "https://example.com/hook",
            body=requests.exceptions.Timeout(),
        )

        with pytest.raises(requests.exceptions.Timeout):
            deliver_webhook(document)

    def test_skips_delivery_if_no_webhook_url(self, db):
        document = CompletedDocumentFactory(webhook_url="")
        result = deliver_webhook(document)
        assert result is False