"""OpenAlex and GitHub discovery clients. Neither performs work at import time."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import os
import re
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from src.live_search.contracts import CandidateRecord, ProviderResult
from src.live_search.http import ProviderFailure, get_json

logger = logging.getLogger("idea_enhancer.providers")
MAX_PROVIDER_CANDIDATES = 30
_SPACE = re.compile(r"\s+")


class DiscoveryProvider(Protocol):
    name: str

    async def search(self, idea: str, client: httpx.AsyncClient, limit: int) -> ProviderResult: ...


def _candidate_id(provider: str, provider_id: str) -> str:
    digest = hashlib.sha256(f"{provider}:{provider_id}".encode("utf-8")).hexdigest()[:24]
    return f"{provider}_{digest}"


def _clean_text(value: Any, limit: int = 12000) -> str | None:
    if not isinstance(value, str):
        return None
    text = _SPACE.sub(" ", value).strip()
    return text[:limit] or None


def _safe_url(value: Any) -> str | None:
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or "\\" in value
        or any(char.isspace() or ord(char) < 33 for char in value)
    ):
        return None
    try:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return None
        host = parsed.hostname.rstrip(".")
        port = parsed.port
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            ascii_host = host.encode("idna").decode("ascii")
            labels = ascii_host.split(".")
            if len(labels) < 2 or any(
                not label or len(label) > 63
                or not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?", label)
                for label in labels
            ):
                return None
        else:
            if not address.is_global:
                return None
        if port is not None and not 1 <= port <= 65535:
            return None
        return value
    except ValueError:
        return None


def _result(provider: str, records: list[CandidateRecord]) -> ProviderResult:
    return ProviderResult(provider, "success" if records else "empty", tuple(records))


def _failed(provider: str, error: ProviderFailure) -> ProviderResult:
    logger.warning("%s discovery failed (%s)", provider, error.code)
    return ProviderResult(provider, error.state, (), error.code, error.message)  # type: ignore[arg-type]


def reconstruct_abstract(inverted_index: Any) -> str | None:
    """Rebuild an OpenAlex abstract from token -> positions without trusting order."""
    if not isinstance(inverted_index, Mapping):
        return None
    positions: dict[int, str] = {}
    for token, indexes in inverted_index.items():
        if not isinstance(token, str) or not isinstance(indexes, list):
            continue
        for index in indexes:
            if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < 100000:
                positions.setdefault(index, token)
    return " ".join(positions[index] for index in sorted(positions)) or None


class OpenAlexProvider:
    name = "openalex"
    endpoint = "https://api.openalex.org/works"

    async def search(self, idea: str, client: httpx.AsyncClient, limit: int = 20) -> ProviderResult:
        bounded_limit = min(max(int(limit), 1), MAX_PROVIDER_CANDIDATES)
        params = {"search": _SPACE.sub(" ", idea).strip()[:512], "per-page": bounded_limit}
        select = "id,doi,display_name,publication_year,publication_date,authorships,primary_location,best_oa_location,open_access,cited_by_count,type,abstract_inverted_index"
        params["select"] = select
        try:
            payload = await get_json(client, self.endpoint, params=params, headers={"User-Agent": "IdeaEnhancer/1.0 (student research discovery)"})
        except ProviderFailure as error:
            return _failed(self.name, error)
        results = payload.get("results")
        if not isinstance(results, list):
            return ProviderResult(self.name, "invalid_response", (), "invalid_shape", "OpenAlex returned an unexpected result list.")

        candidates: list[CandidateRecord] = []
        for item in results[:bounded_limit]:
            if not isinstance(item, dict):
                continue
            provider_id = _clean_text(item.get("id"), 512)
            title = _clean_text(item.get("display_name"), 2000)
            if not provider_id or not title:
                continue
            abstract = _clean_text(reconstruct_abstract(item.get("abstract_inverted_index")))
            location = item.get("best_oa_location")
            if not isinstance(location, dict):
                location = item.get("primary_location")
            if not isinstance(location, dict):
                location = {}
            source = location.get("source") if isinstance(location, dict) else None
            source_url = _safe_url((location.get("landing_page_url") if isinstance(location, dict) else None) or item.get("doi") or provider_id)
            authorships = item.get("authorships")
            authors = tuple(
                name for auth in (authorships if isinstance(authorships, list) else [])
                if isinstance(auth, dict)
                for author in [auth.get("author")]
                if isinstance(author, dict)
                for name in [_clean_text(author.get("display_name"), 300)] if name
            )[:30]
            oa = item.get("open_access")
            candidates.append(CandidateRecord(
                candidate_id=_candidate_id(self.name, provider_id), source_provider=self.name,
                provider_id=provider_id, candidate_type="paper", title=title, description=abstract,
                source_url=source_url, doi=_clean_text(item.get("doi"), 512), authors=authors,
                publication_date=_clean_text(item.get("publication_date"), 32),
                publication_year=(
                    item["publication_year"]
                    if isinstance(item.get("publication_year"), int)
                    and not isinstance(item.get("publication_year"), bool)
                    and 1000 <= item["publication_year"] <= 9999
                    else None
                ),
                work_type=_clean_text(item.get("type"), 120),
                venue=_clean_text(source.get("display_name"), 500) if isinstance(source, dict) else None,
                open_access=oa.get("is_oa") if isinstance(oa, dict) and isinstance(oa.get("is_oa"), bool) else None,
                citation_count=(
                    item["cited_by_count"]
                    if isinstance(item.get("cited_by_count"), int)
                    and not isinstance(item.get("cited_by_count"), bool)
                    and item["cited_by_count"] >= 0
                    else None
                ),
            ))
        if results and not candidates:
            return ProviderResult(self.name, "invalid_response", (), "invalid_records", "OpenAlex results contained no usable paper records.")
        return _result(self.name, candidates)


class GitHubProvider:
    name = "github"
    endpoint = "https://api.github.com/search/repositories"

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    async def search(self, idea: str, client: httpx.AsyncClient, limit: int = 20) -> ProviderResult:
        bounded_limit = min(max(int(limit), 1), MAX_PROVIDER_CANDIDATES)
        query = f"{_SPACE.sub(' ', idea).strip()[:400]} in:name,description,readme"
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = self._token if self._token is not None else os.getenv("GITHUB_TOKEN")
        token = token.strip() if isinstance(token, str) else None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            payload = await get_json(client, self.endpoint, params={"q": query, "per_page": bounded_limit}, headers=headers)
        except ProviderFailure as error:
            return _failed(self.name, error)
        results = payload.get("items")
        if not isinstance(results, list):
            return ProviderResult(self.name, "invalid_response", (), "invalid_shape", "GitHub returned an unexpected result list.")

        candidates: list[CandidateRecord] = []
        for item in results[:bounded_limit]:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            provider_id = str(raw_id) if isinstance(raw_id, int) and not isinstance(raw_id, bool) else _clean_text(raw_id, 128)
            title = _clean_text(item.get("full_name"), 1000)
            if not provider_id or not title:
                continue
            owner = item.get("owner")
            license_data = item.get("license")
            topics = item.get("topics")
            candidates.append(CandidateRecord(
                candidate_id=_candidate_id(self.name, provider_id), source_provider=self.name,
                provider_id=provider_id, candidate_type="repository", title=title,
                description=_clean_text(item.get("description")), source_url=_safe_url(item.get("html_url")),
                owner=_clean_text(owner.get("login"), 300) if isinstance(owner, dict) else None,
                repository_created_at=_clean_text(item.get("created_at"), 32),
                repository_pushed_at=_clean_text(item.get("pushed_at"), 32),
                programming_language=_clean_text(item.get("language"), 120),
                topics=tuple(x for x in (_clean_text(t, 120) for t in topics if isinstance(t, str)) if x)[:30] if isinstance(topics, list) else (),
                stars=(
                    item["stargazers_count"]
                    if isinstance(item.get("stargazers_count"), int)
                    and not isinstance(item.get("stargazers_count"), bool)
                    and item["stargazers_count"] >= 0
                    else None
                ),
                forks=(
                    item["forks_count"]
                    if isinstance(item.get("forks_count"), int)
                    and not isinstance(item.get("forks_count"), bool)
                    and item["forks_count"] >= 0
                    else None
                ),
                archived=item.get("archived") if isinstance(item.get("archived"), bool) else None,
                license_name=_clean_text(license_data.get("spdx_id") or license_data.get("name"), 300) if isinstance(license_data, dict) else None,
                provider_metadata={"default_branch": _clean_text(item.get("default_branch"), 200)},
            ))
        if results and not candidates:
            return ProviderResult(self.name, "invalid_response", (), "invalid_records", "GitHub results contained no usable repository records.")
        return _result(self.name, candidates)
