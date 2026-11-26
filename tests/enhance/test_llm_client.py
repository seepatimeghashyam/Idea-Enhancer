"""Tests for LLM clients."""

import os
try:
    import pytest
except ImportError:
    class _RaisesContext:
        def __init__(self, expected_exc):
            self.expected_exc = expected_exc
            self.value = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Expected {self.expected_exc.__name__} was not raised")
            if not issubclass(exc_type, self.expected_exc):
                return False
            self.value = exc_val
            return True

    class _MockPytest:
        @staticmethod
        def raises(expected_exc):
            return _RaisesContext(expected_exc)

    pytest = _MockPytest()  # type: ignore[assignment]
from src.enhance.llm_client import (
    FakeLLMClient,
    GeminiLLMClient,
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
