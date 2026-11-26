"""Bounded HTTP helpers shared by the live discovery providers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from typing import Any

import httpx

MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024


@dataclass
class ProviderFailure(Exception):
    state: str
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def _retry_after_seconds(value: str | None) -> float:
    """Parse delta-seconds or an HTTP date and cap the retry delay to one second."""
    if not value:
        return 0.25
    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            delay = (retry_at - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return 0.25
    return min(max(delay, 0.0), 1.0)


async def _read_bounded(response: httpx.Response) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > MAX_PROVIDER_RESPONSE_BYTES:
                raise ProviderFailure("invalid_response", "response_too_large", "The provider response exceeded the size limit.")
        except ValueError:
            # Ignore a malformed length header; the streamed byte cap still applies.
            pass

    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > MAX_PROVIDER_RESPONSE_BYTES:
            raise ProviderFailure("invalid_response", "response_too_large", "The provider response exceeded the size limit.")
        chunks.append(chunk)
    return b"".join(chunks)


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch bounded JSON with at most one retry and no credential/body logging."""
    for attempt in range(2):
        try:
            async def fetch_once() -> tuple[dict[str, Any] | None, float | None]:
                async with client.stream("GET", url, params=params, headers=headers) as response:
                    status = response.status_code
                    if status == 429:
                        if attempt == 0:
                            return None, _retry_after_seconds(response.headers.get("Retry-After"))
                        raise ProviderFailure("rate_limited", "rate_limited", "The provider rate limit was reached.")
                    if status == 401:
                        raise ProviderFailure("authentication_error", "authentication", "The provider rejected its credentials or request.")
                    if status == 403:
                        rate_limited = (
                            response.headers.get("X-RateLimit-Remaining") == "0"
                            or "Retry-After" in response.headers
                        )
                        if rate_limited:
                            if attempt == 0 and response.headers.get("Retry-After") is not None:
                                return None, _retry_after_seconds(response.headers.get("Retry-After"))
                            raise ProviderFailure("rate_limited", "rate_limited", "The provider rate limit was reached.")
                        raise ProviderFailure("authentication_error", "authentication", "The provider rejected its credentials or request.")
                    if status >= 500:
                        if attempt == 0:
                            return None, 0.2
                        raise ProviderFailure("upstream_error", "upstream_error", "The provider service is temporarily unavailable.")
                    if 300 <= status < 400:
                        raise ProviderFailure("upstream_error", "unexpected_redirect", "The provider returned an unexpected redirect.")
                    if status >= 400:
                        raise ProviderFailure("upstream_error", "upstream_error", "The provider rejected the search request.")
                    body = await _read_bounded(response)
                    try:
                        payload = json.loads(body)
                    except (ValueError, UnicodeDecodeError) as error:
                        raise ProviderFailure("invalid_response", "invalid_json", "The provider returned an unreadable response.") from error
                    if not isinstance(payload, dict):
                        raise ProviderFailure("invalid_response", "invalid_shape", "The provider response had an unexpected shape.")
                    return payload, None

            payload, retry_delay = await asyncio.wait_for(fetch_once(), timeout=12.0)
        except asyncio.TimeoutError as error:
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            raise ProviderFailure("timeout", "timeout", "The provider request timed out.") from error
        except httpx.TimeoutException as error:
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            else:
                raise ProviderFailure("timeout", "timeout", "The provider request timed out.") from error
        except httpx.RequestError as error:
            if attempt == 0:
                await asyncio.sleep(0.2)
                continue
            else:
                raise ProviderFailure("network_error", "network_error", "The provider could not be reached.") from error

        if retry_delay is not None:
            await asyncio.sleep(retry_delay)
            continue
        assert payload is not None
        return payload
    raise ProviderFailure("upstream_error", "upstream_error", "The provider request could not be completed.")
