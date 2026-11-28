"""Tests for the automatic Gemini model fallback chain (no network used)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest

from src.enhance.provider import GeminiProvider, ProviderBadOutput, ProviderUnavailable, parse_model_list

REQ = httpx.Request("POST", "https://example.invalid")
GOOD = {"overlap_summary": "ok"}


def ok(payload_text='{"overlap_summary": "ok"}', finish="STOP"):
    body = {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": payload_text}]}}]}
    return httpx.Response(200, json=body, request=REQ)


def err(status, headers=None):
    return httpx.Response(status, headers=headers or {}, json={"error": {"message": "x"}}, request=REQ)


class FakeClient:
    """Returns scripted responses per model id and records every call."""

    def __init__(self, script):
        self.script = {model: list(items) for model, items in script.items()}
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        model = url.split("/models/")[1].split(":")[0]
        self.calls.append((model, "responseSchema" in json["generationConfig"]))
        items = self.script[model]
        return items.pop(0) if len(items) > 1 else items[0]


def run(provider, client):
    with patch("httpx.AsyncClient", return_value=client):
        return asyncio.run(provider.generate("prompt"))


def make(*models):
    return GeminiProvider(api_key="k", models=list(models))


def test_falls_back_when_first_model_is_out_of_quota():
    client = FakeClient({"a": [err(429)], "b": [ok()]})
    provider = make("a", "b")
    assert run(provider, client) == GOOD
    assert [m for m, _ in client.calls] == ["a", "b"]
    assert provider.last_model_used == "b"


def test_skips_missing_model_then_bad_output_then_succeeds():
    client = FakeClient({"a": [err(404)], "b": [ok("not json at all")], "c": [ok()]})
    assert run(make("a", "b", "c"), client) == GOOD


def test_failed_model_is_skipped_during_cooldown():
    provider = make("a", "b")
    first = FakeClient({"a": [err(429)], "b": [ok()]})
    run(provider, first)
    second = FakeClient({"a": [ok()], "b": [ok()]})
    run(provider, second)
    assert [m for m, _ in second.calls] == ["b"]


def test_all_models_failing_reports_every_model():
    client = FakeClient({"a": [err(503)], "b": [err(429)]})
    with pytest.raises(ProviderUnavailable, match="All configured.*a:.*b:"):
        run(make("a", "b"), client)


def test_single_model_keeps_original_error_message():
    client = FakeClient({"a": [err(429, {"Retry-After": "30"})]})
    with pytest.raises(ProviderUnavailable, match="HTTP 429.*30"):
        run(make("a"), client)


def test_schema_rejection_is_retried_without_schema():
    client = FakeClient({"a": [err(400), ok()]})
    assert run(make("a"), client) == GOOD
    assert client.calls == [("a", True), ("a", False)]


def test_truncated_output_is_reported_and_falls_back():
    client = FakeClient({"a": [ok('{"overlap_summary": "cut', finish="MAX_TOKENS")], "b": [ok()]})
    assert run(make("a", "b"), client) == GOOD


def test_markdown_fenced_json_is_accepted():
    client = FakeClient({"a": [ok('```json\n{"overlap_summary": "ok"}\n```')]})
    assert run(make("a"), client) == GOOD


def test_model_list_parsing_and_env(monkeypatch):
    # Do not let the real .env file in the project folder change this test.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    assert parse_model_list("a, models/b ,a,bad id,../x") == ["a", "b"]
    monkeypatch.setenv("GEMINI_MODELS", "m1,m2")
    assert GeminiProvider(api_key="k").models == ("m1", "m2")
    monkeypatch.delenv("GEMINI_MODELS")
    monkeypatch.setenv("GEMINI_MODEL", "mine")
    chain = GeminiProvider(api_key="k").models
    assert chain[0] == "mine" and len(chain) > 1
