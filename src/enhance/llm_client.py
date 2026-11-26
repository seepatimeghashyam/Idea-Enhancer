"""LLM Client interface, Gemini implementation, and test fakes."""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_ENDPOINT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"


class LLMError(RuntimeError):
    """Base exception for LLM operations."""


class LLMTimeoutError(LLMError):
    """The LLM request timed out."""


class LLMUnavailableError(LLMError):
    """The LLM provider is unconfigured, rate-limited, or unavailable."""


class LLMClientProtocol(Protocol):
    """Protocol for LLM interactions."""

    def generate_enhancement(self, prompt: str, timeout_seconds: float = 12.0) -> str:
        """Submit prompt and return raw string text response."""
        ...


class GeminiLLMClient:
    """Production client calling Google Gemini REST API using standard libraries."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_GEMINI_MODEL):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("LLM_MODEL", model).strip() or model

    def generate_enhancement(self, prompt: str, timeout_seconds: float = 12.0) -> str:
        if not self.api_key:
            raise LLMUnavailableError("GEMINI_API_KEY is not configured in environment or .env.")

        url = GEMINI_ENDPOINT_URL.format(model=self.model, api_key=self.api_key)
        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        json_data = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                resp_text = response.read().decode("utf-8")
                payload = json.loads(resp_text)
                candidates = payload.get("candidates", [])
                if not candidates:
                    raise LLMUnavailableError("Gemini returned no candidates.")
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise LLMUnavailableError("Gemini candidate has no text content.")
                return str(parts[0]["text"])

        except urllib.error.HTTPError as err:
            if err.code in (408, 504):
                raise LLMTimeoutError(f"Gemini gateway timed out with HTTP {err.code}.") from err
            if err.code == 429:
                raise LLMUnavailableError("Gemini rate limit exceeded. Please retry later.") from err
            if err.code == 403:
                raise LLMUnavailableError("Gemini API key is invalid or unauthorized.") from err
            raise LLMUnavailableError(f"Gemini API returned HTTP {err.code}: {err.reason}") from err

        except (socket.timeout, urllib.error.URLError) as err:
            if isinstance(err.reason, socket.timeout) or "timed out" in str(err).lower():
                raise LLMTimeoutError(f"Gemini request timed out after {timeout_seconds}s.") from err
            raise LLMUnavailableError(f"Could not connect to Gemini service: {err.reason}") from err

        except Exception as err:
            raise LLMUnavailableError(f"Unexpected error communicating with Gemini: {err}") from err


class FakeLLMClient:
    """Configurable fake LLM client for fast, deterministic unit testing."""

    def __init__(
        self,
        canned_response: Optional[str] = None,
        raise_timeout: bool = False,
        raise_unavailable: bool = False,
        error_message: str = "Simulated error",
    ):
        self.canned_response = canned_response
        self.raise_timeout = raise_timeout
        self.raise_unavailable = raise_unavailable
        self.error_message = error_message
        self.calls: list[str] = []

    def generate_enhancement(self, prompt: str, timeout_seconds: float = 12.0) -> str:
        self.calls.append(prompt)
        if self.raise_timeout:
            raise LLMTimeoutError("FakeLLM simulated timeout.")
        if self.raise_unavailable:
            raise LLMUnavailableError(self.error_message)

        if self.canned_response is not None:
            return self.canned_response

        # Default realistic synthetic JSON response
        sample_output = {
            "overlap_summary": "Moderate overlap found in the agricultural IoT sensing space.",
            "facet_map": {
                "problem": {
                    "overlap": "strong",
                    "details": "Both address foliar disease detection.",
                    "matched_project_ids": ["mock_001"],
                },
                "domain": {
                    "overlap": "strong",
                    "details": "Smart agriculture and crop monitoring.",
                    "matched_project_ids": ["mock_001"],
                },
                "method": {
                    "overlap": "partial",
                    "details": "Computer vision on embedded hardware.",
                    "matched_project_ids": ["mock_001"],
                },
                "tech_stack": {
                    "overlap": "strong",
                    "details": "Shared usage of Raspberry Pi and CNNs.",
                    "matched_project_ids": ["mock_001"],
                },
                "data": {
                    "overlap": "partial",
                    "details": "Standard image dataset collection.",
                    "matched_project_ids": ["mock_001"],
                },
            },
            "novelty": {
                "level": "medium",
                "score": 0.50,
                "reason": "The baseline is well represented, but edge optimization provides a clear novel path.",
            },
            "suggestions": [
                {
                    "title": "Quantized INT8 MobileNet Backbone",
                    "description": "Quantize models to INT8 to increase inference throughput beyond mock_001.",
                    "cites": ["mock_001"],
                },
                {
                    "title": "LoRaWAN Offline Mesh Alerting",
                    "description": "Implement battery-powered long range telemetry where internet is unavailable, extending mock_001.",
                    "cites": ["mock_001"],
                },
                {
                    "title": "Soil Moisture Microclimate Cross-Correlation",
                    "description": "Correlate leaf camera images with moisture sensors to detect root distress, improving on mock_001.",
                    "cites": ["mock_001"],
                },
            ],
            "suggested_tech_stack": [
                {"name": "TensorFlow Lite", "role": "INT8 quantized inference on edge hardware"},
                {"name": "LoRa SX1276", "role": "Low-power long-distance radio communication"},
                {"name": "FastAPI", "role": "Centralized telemetry ingestion API"},
            ],
            "feasibility": {
                "rating": 4,
                "reasons": [
                    "Open-source models and affordable hardware modules are readily available.",
                    "Well-suited for student capstone execution within a semester.",
                ],
            },
        }
        return json.dumps(sample_output)
