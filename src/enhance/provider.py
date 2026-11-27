"""LLM provider boundary and Gemini implementation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol


class ProviderUnavailable(RuntimeError):
    pass


class ProviderBadOutput(RuntimeError):
    pass


class EnhancementProvider(Protocol):
    name: str
    model: str

    def generate(self, prompt: str) -> dict[str, Any]: ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        # create_app() constructs this provider before FastAPI enters lifespan,
        # where the rest of the app loads dotenv. Load it here so local .env
        # configuration is available on the first request.
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        self.api_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()
        # 2.5 Flash is no longer available to many newly created API projects.
        # Flash-Lite is the current free-tier oriented text model.
        self.model = (model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")).strip()

    def generate(self, prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderUnavailable("Gemini is not configured. Set GEMINI_API_KEY on the server.")
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.25, "responseMimeType": "application/json"}}).encode()
        request = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.loads(response.read(1_000_000))
        except urllib.error.HTTPError as error:
            if error.code == 429:
                retry_after = error.headers.get("Retry-After", "")
                suffix = f" Retry after {retry_after} seconds." if retry_after.isdigit() else ""
                raise ProviderUnavailable(f"Gemini rate limit reached (HTTP 429).{suffix}") from error
            if error.code in (408, 500, 502, 503, 504):
                raise ProviderUnavailable(f"Gemini is temporarily unavailable (HTTP {error.code}). Try again shortly.") from error
            if error.code == 400:
                raise ProviderBadOutput("Gemini rejected the request format (HTTP 400).") from error
            if error.code in (401, 403):
                raise ProviderUnavailable(f"Gemini rejected the API key or project access (HTTP {error.code}).") from error
            if error.code == 404:
                raise ProviderUnavailable(f"Gemini model '{self.model}' was not found or is not enabled for this project (HTTP 404).") from error
            raise ProviderUnavailable(f"Gemini request failed (HTTP {error.code}).") from error
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise ProviderUnavailable("Could not reach Gemini or read its response.") from error
        try:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError("Expected an object")
            return payload
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProviderBadOutput("Gemini returned an invalid structured response.") from error
