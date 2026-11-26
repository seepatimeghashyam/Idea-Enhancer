"""Tests for LLM clients."""

import os
import pytest
from src.enhance.llm_client import (
    FakeLLMClient,
    GeminiLLMClient,
    LLMBadResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)


def test_fake_llm_client_success() -> None:
    client = FakeLLMClient(canned_response='{"status": "ok"}')
    result = client.generate_enhancement("test prompt")
    assert result == '{"status": "ok"}'
    assert len(client.calls) == 1
    assert client.calls[0] == "test prompt"


def test_fake_llm_client_timeout() -> None:
    client = FakeLLMClient(raise_timeout=True)
    with pytest.raises(LLMTimeoutError):
        client.generate_enhancement("prompt")


def test_fake_llm_client_unavailable() -> None:
    client = FakeLLMClient(raise_unavailable=True, error_message="Rate limit")
    with pytest.raises(LLMUnavailableError) as exc_info:
        client.generate_enhancement("prompt")
    assert "Rate limit" in str(exc_info.value)


def test_fake_llm_client_bad_response() -> None:
    client = FakeLLMClient(raise_bad_response=True, error_message="Abnormal finish")
    with pytest.raises(LLMBadResponseError) as exc_info:
        client.generate_enhancement("prompt")
    assert "Abnormal finish" in str(exc_info.value)


def test_gemini_client_missing_api_key() -> None:
    old_key = os.environ.pop("GEMINI_API_KEY", None)
    try:
        client = GeminiLLMClient(api_key=None)
        with pytest.raises(LLMUnavailableError) as exc_info:
            client.generate_enhancement("prompt")
        assert "GEMINI_API_KEY is not configured" in str(exc_info.value)
    finally:
        if old_key is not None:
            os.environ["GEMINI_API_KEY"] = old_key


def test_gemini_endpoint_url_no_query_key() -> None:
    client = GeminiLLMClient(api_key="test_key", model="gemini-2.5-flash")
    from src.enhance.llm_client import GEMINI_ENDPOINT_URL
    formatted = GEMINI_ENDPOINT_URL.format(model=client.model)
    assert "?key=" not in formatted
    assert formatted.endswith("/gemini-2.5-flash:generateContent")
