"""LLM provider boundary and Gemini implementation with automatic model fallback.

How the fallback works (plain English):
  * You give the app an ordered list of Gemini models, best first.
  * For every request the app tries the first model. If that model is out of
    quota (429), overloaded (503), too slow, does not exist (404) or returns
    broken output, the app quietly moves on to the next model in the list.
  * A model that just failed is skipped for a short "cool-down" so the next
    requests do not waste time on it again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Protocol

import httpx

logger = logging.getLogger("idea_enhancer.enhance")

# Time allowed for ONE model attempt (seconds). Thinking models can be slow.
GEMINI_REQUEST_TIMEOUT_SECONDS = 45
# Time allowed for the WHOLE chain of models together (the browser waits 180 s).
GEMINI_CHAIN_TIMEOUT_SECONDS = 140
# Room for the answer. Models that "think" spend part of this budget thinking.
GEMINI_MAX_OUTPUT_TOKENS = 8192

# Used when nothing is configured. Best model first, safest (biggest daily
# quota) last. Unknown ids are harmless: a 404 just skips to the next model.
DEFAULT_MODEL_CHAIN = ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")

# The exact JSON shape we ask Gemini to follow (enforced by Google when the
# model supports it; the service double-checks everything afterwards).
_STR = {"type": "STRING"}
_IDS = {"type": "ARRAY", "items": {"type": "STRING"}}
_FACET = {
    "type": "OBJECT",
    "properties": {
        "overlap": {"type": "STRING", "enum": ["none", "partial", "strong"]},
        "details": _STR,
        "evidence_ids": _IDS,
    },
    "required": ["overlap", "details", "evidence_ids"],
}
ENHANCE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "overlap_summary": _STR,
        "facets": {
            "type": "OBJECT",
            "properties": {name: _FACET for name in ("problem", "domain", "method", "tech_stack", "data")},
            "required": ["problem", "domain", "method", "tech_stack", "data"],
        },
        "recommendations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": _STR,
                    "description": _STR,
                    "implementation": _STR,
                    "tradeoff": _STR,
                    "evidence_ids": _IDS,
                    "basis": {"type": "STRING", "enum": ["retrieved_evidence", "general_advice"]},
                },
                "required": ["title", "description", "implementation", "tradeoff", "evidence_ids", "basis"],
            },
        },
    },
    "required": ["overlap_summary", "facets", "recommendations"],
}


class ProviderUnavailable(RuntimeError):
    pass


class ProviderBadOutput(RuntimeError):
    pass


class EnhancementProvider(Protocol):
    name: str
    model: str

    async def generate(self, prompt: str) -> dict[str, Any]: ...


class _SchemaRejected(Exception):
    """The model refused our response schema; retry once without it."""


def _fail(kind: type[Exception], message: str, cooldown: float = 0.0) -> Exception:
    error = kind(message)
    error.cooldown = cooldown  # type: ignore[attr-defined]
    return error


def parse_model_list(raw: str) -> list[str]:
    """Turn 'a, b ,models/c' into ['a', 'b', 'c'] (safe ids only, no duplicates)."""
    result: list[str] = []
    for part in (raw or "").split(","):
        name = part.strip()
        if name.startswith("models/"):
            name = name[len("models/"):]
        if name and _MODEL_ID.match(name) and name not in result:
            result.append(name)
    return result


def _loads_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    for candidate in (cleaned, cleaned[cleaned.find("{"): cleaned.rfind("}") + 1] if "{" in cleaned else ""):
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, models: list[str] | None = None):
        # create_app() constructs this provider before FastAPI enters lifespan,
        # where the rest of the app loads dotenv. Load it here so local .env
        # configuration is available on the first request.
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        self.api_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()

        if models is not None:
            chain = parse_model_list(",".join(models))
        elif model is not None:
            chain = parse_model_list(model)  # explicit single model: no automatic extras
        else:
            chain = parse_model_list(os.getenv("GEMINI_MODELS", ""))
            if not chain:
                # Old-style single GEMINI_MODEL still works and gets safe fallbacks behind it.
                chain = parse_model_list(os.getenv("GEMINI_MODEL", ""))
                chain += [m for m in DEFAULT_MODEL_CHAIN if m not in chain]
        if not chain:
            chain = list(DEFAULT_MODEL_CHAIN)
        self.models: tuple[str, ...] = tuple(chain)
        # Shown in the cache key; changes whenever the configured chain changes.
        self.model = ",".join(self.models)
        self.last_model_used: str | None = None
        self._cooldowns: dict[str, float] = {}

    # ------------------------------------------------------------------ chain
    def _attempt_order(self) -> list[str]:
        now = time.monotonic()
        ready = [m for m in self.models if self._cooldowns.get(m, 0.0) <= now]
        return ready or list(self.models)

    async def generate(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderUnavailable("Gemini is not configured. Set GEMINI_API_KEY on the server.")
        started = time.monotonic()
        failures: list[tuple[str, Exception]] = []
        timeout = httpx.Timeout(GEMINI_REQUEST_TIMEOUT_SECONDS, connect=8.0, write=15.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for model in self._attempt_order():
                remaining = GEMINI_CHAIN_TIMEOUT_SECONDS - (time.monotonic() - started)
                if failures and remaining < 5:
                    break
                budget = min(GEMINI_REQUEST_TIMEOUT_SECONDS, remaining)
                try:
                    # The deadline is total elapsed time, not just an inactivity timeout.
                    async with asyncio.timeout(budget):
                        payload = await self._attempt(client, model, prompt)
                except TimeoutError:
                    error = _fail(ProviderUnavailable, "Gemini request timed out. Please try again shortly.", 120)
                except (ProviderUnavailable, ProviderBadOutput) as caught:
                    error = caught
                else:
                    self.last_model_used = model
                    self._cooldowns.pop(model, None)
                    if failures:
                        logger.info("Enhancement answered by fallback model %s", model)
                    return payload
                failures.append((model, error))
                cooldown = float(getattr(error, "cooldown", 0.0) or 0.0)
                if cooldown > 0:
                    self._cooldowns[model] = time.monotonic() + cooldown
                logger.warning("Gemini model %s failed (%s); trying the next model if any", model, type(error).__name__)

        if len(failures) == 1:
            raise failures[0][1]
        summary = " | ".join(f"{model}: {error}" for model, error in failures)[:500]
        if all(isinstance(error, ProviderBadOutput) for _, error in failures):
            raise ProviderBadOutput(f"No Gemini model returned a usable analysis. {summary}")
        raise ProviderUnavailable(f"All configured Gemini models failed. {summary}")

    # ---------------------------------------------------------- one model call
    async def _attempt(self, client: httpx.AsyncClient, model: str, prompt: str) -> dict[str, Any]:
        endpoint = f"{_GEMINI_BASE}/{model}:generateContent"
        try:
            result = await self._post(client, endpoint, prompt, use_schema=True)
        except _SchemaRejected:
            result = await self._post(client, endpoint, prompt, use_schema=False)
        return self._parse(result)

    async def _post(self, client: httpx.AsyncClient, endpoint: str, prompt: str, *, use_schema: bool) -> dict[str, Any]:
        config: dict[str, Any] = {
            "temperature": 0.25,
            "maxOutputTokens": GEMINI_MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
        }
        if use_schema:
            config["responseSchema"] = ENHANCE_RESPONSE_SCHEMA
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config}
        try:
            response = await client.post(endpoint, json=body, headers={"x-goog-api-key": self.api_key})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == 429:
                retry_after = error.response.headers.get("Retry-After", "")
                suffix = f" Retry after {retry_after} seconds." if retry_after.isdigit() else ""
                cooldown = min(float(retry_after), 3600.0) if retry_after.isdigit() else 60.0
                raise _fail(ProviderUnavailable, f"Gemini rate limit reached (HTTP {status}).{suffix}", cooldown) from error
            if status in (408, 500, 502, 503, 504):
                raise _fail(ProviderUnavailable, f"Gemini is temporarily unavailable (HTTP {status}). Try again shortly.", 30) from error
            if status == 400:
                if use_schema:
                    raise _SchemaRejected() from error
                if self._mentions_api_key(error.response):
                    raise _fail(ProviderUnavailable, "Gemini rejected the API key (HTTP 400). Check GEMINI_API_KEY.", 300) from error
                raise _fail(ProviderBadOutput, "Gemini rejected the request format (HTTP 400).", 300) from error
            if status in (401, 403):
                raise _fail(ProviderUnavailable, f"Gemini rejected the API key or project access (HTTP {status}).", 300) from error
            if status == 404:
                raise _fail(ProviderUnavailable, "Gemini model was not found or is not enabled for this project (HTTP 404).", 3600) from error
            raise _fail(ProviderUnavailable, f"Gemini request failed (HTTP {status}).", 60) from error
        except (httpx.TimeoutException, TimeoutError) as error:
            raise _fail(ProviderUnavailable, "Gemini request timed out. Please try again shortly.", 120) from error
        except httpx.HTTPError as error:
            raise _fail(ProviderUnavailable, "Could not reach Gemini or read its response.", 30) from error
        except json.JSONDecodeError as error:
            raise _fail(ProviderBadOutput, "Gemini returned an invalid response document.", 30) from error

    @staticmethod
    def _mentions_api_key(response: httpx.Response) -> bool:
        try:
            return "api key" in str(response.json()).lower()
        except Exception:
            return False

    @staticmethod
    def _parse(result: Any) -> dict[str, Any]:
        try:
            candidate = result["candidates"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise _fail(ProviderBadOutput, "Gemini returned no answer for this request.", 30) from error
        finish = candidate.get("finishReason") if isinstance(candidate, dict) else None
        parts = ((candidate.get("content") or {}).get("parts") or []) if isinstance(candidate, dict) else []
        text_parts = [
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought", False)
        ]
        payload = _loads_json_object("\n".join(text_parts)) if text_parts else None
        if payload is None:
            if finish == "MAX_TOKENS":
                raise _fail(ProviderBadOutput, "Gemini ran out of output space before finishing its answer.", 30)
            raise _fail(ProviderBadOutput, "Gemini returned an invalid structured response.", 30)
        return payload
