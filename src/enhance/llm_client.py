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
GEMINI_ENDPOINT_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "overlap_summary": {"type": "STRING"},
        "facet_map": {
            "type": "OBJECT",
            "properties": {
                "problem": {
                    "type": "OBJECT",
                    "properties": {
                        "overlap": {"type": "STRING", "enum": ["none", "partial", "strong"]},
                        "details": {"type": "STRING"},
                        "matched_project_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["overlap", "details", "matched_project_ids"],
                },
                "domain": {
                    "type": "OBJECT",
                    "properties": {
                        "overlap": {"type": "STRING", "enum": ["none", "partial", "strong"]},
                        "details": {"type": "STRING"},
                        "matched_project_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["overlap", "details", "matched_project_ids"],
                },
                "method": {
                    "type": "OBJECT",
                    "properties": {
                        "overlap": {"type": "STRING", "enum": ["none", "partial", "strong"]},
                        "details": {"type": "STRING"},
                        "matched_project_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["overlap", "details", "matched_project_ids"],
                },
                "tech_stack": {
                    "type": "OBJECT",
                    "properties": {
                        "overlap": {"type": "STRING", "enum": ["none", "partial", "strong"]},
                        "details": {"type": "STRING"},
                        "matched_project_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["overlap", "details", "matched_project_ids"],
                },
                "data": {
                    "type": "OBJECT",
                    "properties": {
                        "overlap": {"type": "STRING", "enum": ["none", "partial", "strong"]},
                        "details": {"type": "STRING"},
                        "matched_project_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                    },
                    "required": ["overlap", "details", "matched_project_ids"],
                },
            },
            "required": ["problem", "domain", "method", "tech_stack", "data"],
        },
        "novelty": {
            "type": "OBJECT",
            "properties": {
                "reason": {"type": "STRING"},
            },
            "required": ["reason"],
        },
        "suggestions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "cites": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["title", "description", "cites"],
            },
        },
        "suggested_tech_stack": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "role": {"type": "STRING"},
                },
                "required": ["name", "role"],
            },
        },
        "feasibility": {
            "type": "OBJECT",
            "properties": {
                "rating": {"type": "INTEGER"},
                "reasons": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["rating", "reasons"],
        },
    },
    "required": [
        "overlap_summary",
        "facet_map",
        "novelty",
        "suggestions",
        "suggested_tech_stack",
        "feasibility",
    ],
}


class LLMError(RuntimeError):
    """Base exception for LLM operations."""


class LLMTimeoutError(LLMError):
    """The LLM request timed out."""


class LLMUnavailableError(LLMError):
    """The LLM provider is unconfigured, rate-limited, or unavailable."""


class LLMBadResponseError(LLMError):
    """The LLM returned an unusable, malformed, or ungrounded response."""


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

        url = GEMINI_ENDPOINT_URL.format(model=self.model)
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
                "responseSchema": RESPONSE_SCHEMA,
            },
        }

        json_data = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                resp_text = response.read().decode("utf-8")
                payload = json.loads(resp_text)
                candidates = payload.get("candidates", [])
                if not candidates:
                    raise LLMBadResponseError("Gemini returned no candidates.")

                candidate = candidates[0]
                finish_reason = candidate.get("finishReason")
                if finish_reason and finish_reason != "STOP":
                    raise LLMBadResponseError(
                        f"Gemini response finished with abnormal reason: {finish_reason}"
                    )

                parts = candidate.get("content", {}).get("parts", [])
                if not parts or "text" not in parts[0]:
                    raise LLMBadResponseError("Gemini candidate has no text content.")
                return str(parts[0]["text"])

        except urllib.error.HTTPError as err:
            error_body = ""
            try:
                error_body = err.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if err.code in (408, 504):
                raise LLMTimeoutError(f"Gemini gateway timed out with HTTP {err.code}.") from err
            if err.code == 429:
                raise LLMUnavailableError("Gemini rate limit exceeded. Please retry later.") from err
            if err.code == 403:
                raise LLMUnavailableError("Gemini API key is invalid or unauthorized.") from err
            if err.code == 400:
                if "API key" in error_body or "API_KEY_INVALID" in error_body:
                    raise LLMUnavailableError("Gemini API key is invalid. Check GEMINI_API_KEY.") from err
                raise LLMBadResponseError(f"Gemini bad request (HTTP 400): {error_body}") from err

            raise LLMUnavailableError(f"Gemini API returned HTTP {err.code}: {err.reason}") from err

        except (socket.timeout, urllib.error.URLError) as err:
            if isinstance(err, socket.timeout) or isinstance(getattr(err, "reason", None), socket.timeout) or "timed out" in str(err).lower():
                raise LLMTimeoutError(f"Gemini request timed out after {timeout_seconds}s.") from err
            raise LLMUnavailableError(f"Could not connect to Gemini service: {getattr(err, 'reason', err)}") from err

        except LLMError:
            raise
        except Exception as err:
            raise LLMUnavailableError(f"Unexpected error communicating with Gemini: {err}") from err


class FakeLLMClient:
    """Configurable fake LLM client for fast, deterministic unit testing."""

    def __init__(
        self,
        canned_response: Optional[str] = None,
        raise_timeout: bool = False,
        raise_unavailable: bool = False,
        raise_bad_response: bool = False,
        error_message: str = "Simulated error",
    ):
        self.canned_response = canned_response
        self.raise_timeout = raise_timeout
        self.raise_unavailable = raise_unavailable
        self.raise_bad_response = raise_bad_response
        self.error_message = error_message
        self.calls: list[str] = []

    def generate_enhancement(self, prompt: str, timeout_seconds: float = 12.0) -> str:
        self.calls.append(prompt)
        if self.raise_timeout:
            raise LLMTimeoutError("FakeLLM simulated timeout.")
        if self.raise_unavailable:
            raise LLMUnavailableError(self.error_message)
        if self.raise_bad_response:
            raise LLMBadResponseError(self.error_message)

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
