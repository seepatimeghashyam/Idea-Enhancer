"""Dependency-injected orchestrator for BM25, vector retrieval, and RRF."""

from __future__ import annotations

from collections.abc import Sequence

from src.core.contracts import ProjectRecord, Retriever, SearchMatch
from src.core.evidence import _evidence_terms, inspect_evidence
from src.core.fusion import fuse_rankings
from src.core.reranker import rerank_with_cross_encoder


MIN_IDEA_LENGTH = 10
MAX_IDEA_LENGTH = 2000
MIN_TOP_K = 1
MAX_TOP_K = 20


def validate_search_arguments(idea: str, top_k: int) -> tuple[str, int]:
    """Enforce the public search bounds for direct Core Search callers too."""

    if not isinstance(idea, str):
        raise ValueError("idea must be a string.")
    query = idea.strip()
    if not MIN_IDEA_LENGTH <= len(query) <= MAX_IDEA_LENGTH:
        raise ValueError(f"idea must contain {MIN_IDEA_LENGTH} to {MAX_IDEA_LENGTH} characters after trimming.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not MIN_TOP_K <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be an integer from {MIN_TOP_K} to {MAX_TOP_K}.")
    return query, top_k


class CoreSearchEngine:
    """Run both injected retrievers and enrich their RRF results with records."""

    def __init__(
        self,
        records: Sequence[ProjectRecord],
        bm25_retriever: Retriever,
        vector_retriever: Retriever,
        use_cross_encoder: bool = True,
    ) -> None:
        if not records:
            raise ValueError("Core Search requires at least one canonical project record.")
        self._records: dict[str, ProjectRecord] = {}
        for record in records:
            if record.project_id in self._records:
                raise ValueError(f"Duplicate canonical project_id {record.project_id!r}.")
            self._records[record.project_id] = record
        self._bm25 = bm25_retriever
        self._vector = vector_retriever
        self._use_cross_encoder = use_cross_encoder

    def search(self, idea: str, top_k: int = 5) -> list[SearchMatch]:
        query, limit = validate_search_arguments(idea, top_k)
        # Retrieve more candidates for cross-encoder reranking
        initial_k = max(limit * 3, 20) if self._use_cross_encoder else limit
        bm25_hits = self._bm25.search(query, initial_k)
        vector_hits = self._vector.search(query, initial_k)
        matches = fuse_rankings(bm25_hits, vector_hits, self._records, initial_k)

        query_terms = _evidence_terms(query)
        enriched: list[SearchMatch] = []
        for match in matches:
            evidence = inspect_evidence(query, match.project, query_terms=query_terms)
            enriched.append(
                SearchMatch(
                    project=match.project,
                    rank=match.rank,
                    bm25_rank=match.bm25_rank,
                    vector_rank=match.vector_rank,
                    rrf_score=match.rrf_score,
                    shared_elements=evidence.shared_elements,
                    verification_status=evidence.verification_status,
                )
            )

        # Cross-encoder reranking for better precision
        if self._use_cross_encoder and enriched:
            enriched = rerank_with_cross_encoder(query, enriched, top_k)

        return enriched
