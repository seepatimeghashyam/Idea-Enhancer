"""Bounded HTTP helpers shared by the live discovery providers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ProviderFailure(Exception):
    state: str
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch JSON with at most one retry and no credential/body logging."""
    for attempt in range(2):
        try:
            response = await client.get(url, params=params, headers=headers)
        except httpx.TimeoutException as error:
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            raise ProviderFailure("timeout", "timeout", "The provider request timed out.") from error
        except httpx.RequestError as error:
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            raise ProviderFailure("network_error", "network_error", "The provider could not be reached.") from error

        if response.status_code == 429:
            if attempt == 0:
                try:
                    delay = min(max(float(response.headers.get("Retry-After", "0.25")), 0.0), 1.0)
                except ValueError:
                    delay = 0.25
                await asyncio.sleep(delay)
                continue
            raise ProviderFailure("rate_limited", "rate_limited", "The provider rate limit was reached.")
        if response.status_code in {401, 403}:
            if response.headers.get("X-RateLimit-Remaining") == "0":
                raise ProviderFailure("rate_limited", "rate_limited", "The provider rate limit was reached.")
            raise ProviderFailure("authentication_error", "authentication", "The provider rejected its credentials or request.")
        if response.status_code >= 500:
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            raise ProviderFailure("upstream_error", "upstream_error", "The provider service is temporarily unavailable.")
        if response.status_code >= 400:
            raise ProviderFailure("upstream_error", "upstream_error", "The provider rejected the search request.")
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderFailure("invalid_response", "invalid_json", "The provider returned an unreadable response.") from error
        if not isinstance(payload, dict):
            raise ProviderFailure("invalid_response", "invalid_shape", "The provider response had an unexpected shape.")
        return payload
    raise ProviderFailure("upstream_error", "upstream_error", "The provider request could not be completed.")
