"""Concurrent discovery orchestration and live-search response semantics."""

from __future__ import annotations

import asyncio
import logging
import os
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any

import httpx

from src.live_search.contracts import CandidateRecord, ProviderResult, SearchState
from src.live_search.providers import DiscoveryProvider, GitHubProvider, OpenAlexProvider
from src.live_search.retrieval import DenseEncoder, SentenceTransformerEncoder, rank_candidates

logger = logging.getLogger("idea_enhancer.live_search")
MAX_CANDIDATES_PER_PROVIDER = 25
MAX_CANDIDATES_TOTAL = 50
_SUCCESS_PROVIDER_STATES = {"success", "empty"}
_VALID_PROVIDER_STATES = _SUCCESS_PROVIDER_STATES | {
    "timeout", "rate_limited", "authentication_error", "configuration_error",
    "invalid_response", "network_error", "upstream_error",
}


@dataclass(frozen=True, slots=True)
class LiveSearchResponse:
    state: SearchState
    query: str
    matches: tuple[dict[str, Any], ...]
    providers: dict[str, dict[str, Any]]
    ranking_mode: str
    warnings: tuple[str, ...]
    recurring_evidence: tuple[dict[str, Any], ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "status": self.state,
            "query": self.query,
            "result_count": len(self.matches),
            "matches": list(self.matches),
            "providers": self.providers,
            "ranking_mode": self.ranking_mode,
            "warnings": list(self.warnings),
            "recurring_evidence": list(self.recurring_evidence),
        }


class LiveSearchUnavailable(RuntimeError):
    def __init__(self, providers: dict[str, dict[str, Any]]) -> None:
        super().__init__("All live discovery providers are unavailable.")
        self.providers = providers


class LiveSearchService:
    def __init__(
        self,
        providers: tuple[DiscoveryProvider, ...] | None = None,
        encoder: DenseEncoder | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.providers = providers or (OpenAlexProvider(), GitHubProvider())
        self.encoder = encoder
        self._client = client
        self._owns_client = client is None
        self._client_lock = asyncio.Lock()

    async def start(self) -> None:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    timeout = httpx.Timeout(connect=4.0, read=10.0, write=5.0, pool=3.0)
                    limits = httpx.Limits(max_connections=4, max_keepalive_connections=2)
                    self._client = httpx.AsyncClient(timeout=timeout, limits=limits, follow_redirects=True)

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _query_provider(self, provider: DiscoveryProvider, idea: str) -> ProviderResult:
        assert self._client is not None
        try:
            result = await provider.search(idea, self._client, MAX_CANDIDATES_PER_PROVIDER)
            if not isinstance(result, ProviderResult):
                raise TypeError("provider result contract mismatch")
            if result.provider != provider.name or result.state not in _VALID_PROVIDER_STATES:
                raise ValueError("provider result identity or state is invalid")
            if result.state in _SUCCESS_PROVIDER_STATES:
                if not all(isinstance(candidate, CandidateRecord) for candidate in result.candidates):
                    raise TypeError("provider candidates do not match the candidate contract")
                candidates = tuple(
                    replace(candidate, provider_metadata={**candidate.provider_metadata, "discovery_rank": index})
                    for index, candidate in enumerate(result.candidates, 1)
                )
                return ProviderResult(result.provider, result.state, candidates[:MAX_CANDIDATES_PER_PROVIDER])
            return result
        except Exception as error:
            logger.exception("Unexpected provider failure for %s (%s)", provider.name, type(error).__name__)
            return ProviderResult(provider.name, "upstream_error", (), "provider_error", "The discovery provider could not complete the request.")

    async def search(self, idea: str, top_k: int) -> LiveSearchResponse:
        if not isinstance(idea, str) or not 10 <= len(idea.strip()) <= 2000:
            raise ValueError("idea must contain 10 to 2000 characters after trimming")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
            raise ValueError("top_k must be an integer from 1 to 20")
        await self.start()
        normalized = " ".join(idea.split())[:2000]
        provider_results = await asyncio.gather(*(self._query_provider(p, normalized) for p in self.providers))
        provider_status = {result.provider: result.public_dict() for result in provider_results}
        successful = [result for result in provider_results if result.state in _SUCCESS_PROVIDER_STATES]
        if not successful:
            raise LiveSearchUnavailable(provider_status)

        candidates: dict[str, CandidateRecord] = {}
        for provider in provider_results:
            for candidate in provider.candidates:
                if len(candidates) >= MAX_CANDIDATES_TOTAL:
                    break
                candidates.setdefault(candidate.candidate_id, candidate)

        if not candidates:
            if any(result.state not in _SUCCESS_PROVIDER_STATES for result in provider_results):
                return LiveSearchResponse(
                    "partial", normalized, (), provider_status, "not_run",
                    ("Some discovery sources were unavailable; the successful source returned no candidates.",), (),
                )
            return LiveSearchResponse("no_candidates", normalized, (), provider_status, "not_run", (), ())

        encoder = self.encoder
        if encoder is None and os.getenv("LIVE_DENSE_SEARCH", "1").strip().lower() not in {"0", "false", "no", "off"}:
            model = os.getenv("LIVE_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").strip() or "BAAI/bge-small-en-v1.5"
            encoder = SentenceTransformerEncoder(model)
            self.encoder = encoder
        # Encoding is bounded to this provider-sized pool; heavy model work runs off the event loop.
        if encoder is not None:
            try:
                ranked, dense_available, dense_warning = await asyncio.to_thread(
                    rank_candidates, normalized, tuple(candidates.values()), encoder=encoder, top_k=top_k
                )
            except Exception as error:
                logger.exception("Live retrieval failed (%s)", type(error).__name__)
                raise
        else:
            ranked, dense_available, dense_warning = rank_candidates(
                normalized, tuple(candidates.values()), encoder=None, top_k=top_k
            )
            dense_warning = "Semantic ranking is disabled; results use keyword ranking only."

        provider_failed = any(result.state not in _SUCCESS_PROVIDER_STATES for result in provider_results)
        warnings: list[str] = []
        if provider_failed:
            warnings.append("Some discovery sources were unavailable; the results may be incomplete.")
        if dense_warning:
            warnings.append(dense_warning)
        if not ranked:
            warnings.append("Providers returned candidates, but no candidate matched the active ranking signals.")
        if provider_failed:
            state: SearchState = "partial"
        elif not ranked:
            state = "no_candidates"
        elif not dense_available:
            state = "degraded"
        else:
            state = "complete"
        recurring = self._recurring_evidence(ranked)
        return LiveSearchResponse(
            state, normalized, tuple(match.public_dict() for match in ranked), provider_status,
            "hybrid_rrf" if dense_available else "bm25_only", tuple(warnings), recurring,
        )

    @staticmethod
    def _recurring_evidence(ranked: list[Any]) -> tuple[dict[str, Any], ...]:
        counts: Counter[str] = Counter()
        sources: dict[str, set[str]] = {}
        for match in ranked[:10]:
            for term in set(match.shared_concepts) | set(match.candidate.topics):
                normalized = term.casefold().strip()
                if len(normalized) < 3:
                    continue
                counts[normalized] += 1
                sources.setdefault(normalized, set()).add(match.candidate.candidate_id)
        return tuple(
            {"term": term, "candidate_count": count, "candidate_ids": sorted(sources[term])}
            for term, count in counts.most_common(8) if count >= 2
        )
