import pytest
import json
from unittest.mock import MagicMock, patch
from apps.documents.ai import (
    summarize_document,
    extract_entities,
    answer_question,
    _safe_parse_json,
)


class TestSafeParseJson:
    """Unit tests — no DB needed."""

    def test_parses_clean_json(self):
        raw = '{"people": ["Alice"], "organizations": [], "dates": [], "locations": [], "key_topics": []}'
        result = _safe_parse_json(raw)
        assert result["people"] == ["Alice"]

    def test_strips_markdown_fences(self):
        raw = '```json\n{"people": ["Bob"], "organizations": [], "dates": [], "locations": [], "key_topics": []}\n```'
        result = _safe_parse_json(raw)
        assert result["people"] == ["Bob"]

    def test_adds_missing_keys(self):
        raw = '{"people": ["Carol"]}'
        result = _safe_parse_json(raw)
        # All expected keys should be present
        assert "organizations" in result
        assert "dates" in result
        assert "locations" in result
        assert "key_topics" in result

    def test_handles_invalid_json(self):
        result = _safe_parse_json("this is not json at all")
        assert result.get("parse_error") is True
        assert result["people"] == []

    def test_handles_empty_string(self):
        result = _safe_parse_json("")
        assert result.get("parse_error") is True


class TestSummarizeDocument:

    def test_returns_placeholder_for_empty_text(self):
        result = summarize_document("")
        assert "No text content" in result

    def test_calls_groq_with_correct_model(self, mocker):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="• Summary point"))],
            usage=MagicMock(total_tokens=100),
        )
        mocker.patch("apps.documents.ai.get_groq_client", return_value=mock_client)

        result = summarize_document("Some document text here.")

        assert result == "• Summary point"
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3

    def test_raises_on_rate_limit(self, mocker):
        from groq import RateLimitError
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RateLimitError(
            message="rate limit", response=MagicMock(), body={}
        )
        mocker.patch("apps.documents.ai.get_groq_client", return_value=mock_client)

        with pytest.raises(RateLimitError):
            summarize_document("Some text")


class TestAnswerQuestion:

    def test_returns_placeholder_for_empty_text(self):
        result = answer_question("", "What is this about?")
        assert "no extractable text" in result

    def test_returns_placeholder_for_empty_question(self):
        result = answer_question("Some document text.", "")
        assert "provide a question" in result

    def test_anti_hallucination_prompt_included(self, mocker):
        """Verify the system prompt explicitly instructs against hallucination."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test answer"))],
            usage=MagicMock(total_tokens=50),
        )
        mocker.patch("apps.documents.ai.get_groq_client", return_value=mock_client)

        answer_question("Document text.", "What is this about?")

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        system_prompt = call_kwargs["messages"][0]["content"]
        assert "ONLY" in system_prompt
        assert "Never guess" in system_prompt