"""Deterministic Reciprocal Rank Fusion over rank-only retriever output."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from src.core.contracts import ProjectRecord, RetrievalHit, SearchMatch


class FusionError(ValueError):
    """A retriever returned invalid or unresolvable ranking output."""


def _validated_ranks(hits: Sequence[RetrievalHit], label: str) -> dict[str, int]:
    ranks: dict[str, int] = {}
    used_ranks: set[int] = set()
    previous_rank = 0
    for hit in hits:
        if not isinstance(hit, RetrievalHit):
            raise FusionError(f"{label} retriever output must contain RetrievalHit values.")
        if not isinstance(hit.project_id, str) or not hit.project_id:
            raise FusionError(f"{label} retriever returned an empty or invalid project_id.")
        if isinstance(hit.rank, bool) or not isinstance(hit.rank, int) or hit.rank < 1:
            raise FusionError(f"{label} rank for {hit.project_id!r} must be a positive 1-based integer.")
        if hit.project_id in ranks:
            raise FusionError(f"{label} retriever returned duplicate project_id {hit.project_id!r}.")
        if hit.rank in used_ranks:
            raise FusionError(f"{label} retriever returned duplicate rank {hit.rank}.")
        if hit.rank <= previous_rank:
            raise FusionError(f"{label} retriever output must be ordered by increasing rank.")
        ranks[hit.project_id] = hit.rank
        used_ranks.add(hit.rank)
        previous_rank = hit.rank
    return ranks


def fuse_rankings(
    bm25_hits: Sequence[RetrievalHit],
    vector_hits: Sequence[RetrievalHit],
    records_by_id: Mapping[str, ProjectRecord],
    top_k: int,
    rrf_constant: int = 60,
) -> list[SearchMatch]:
    """Fuse ranked lists using ``sum(1 / (rrf_constant + rank))``.

    Ties are resolved by earliest rank from either retriever, then BM25 rank,
    vector rank, and finally the stable project ID. Duplicate hit IDs are invalid
    and rejected so they can never be counted twice.
    """

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer.")
    if isinstance(rrf_constant, bool) or not isinstance(rrf_constant, int) or rrf_constant < 1:
        raise ValueError("rrf_constant must be a positive integer.")

    bm25_ranks = _validated_ranks(bm25_hits, "BM25")
    vector_ranks = _validated_ranks(vector_hits, "Vector")
    project_ids = set(bm25_ranks) | set(vector_ranks)

    unknown_ids = sorted(project_ids - records_by_id.keys())
    if unknown_ids:
        raise FusionError(f"Retriever returned project_id(s) absent from the canonical dataset: {', '.join(unknown_ids)}.")

    fused: list[SearchMatch] = []
    for project_id in project_ids:
        bm25_rank = bm25_ranks.get(project_id)
        vector_rank = vector_ranks.get(project_id)
        score = 0.0
        if bm25_rank is not None:
            score += 1.0 / (rrf_constant + bm25_rank)
        if vector_rank is not None:
            score += 1.0 / (rrf_constant + vector_rank)
        fused.append(
            SearchMatch(
                project=records_by_id[project_id],
                rank=0,
                bm25_rank=bm25_rank,
                vector_rank=vector_rank,
                rrf_score=score,
                shared_elements=[],
                verification_status="unchecked",
            )
        )

    fused.sort(
        key=lambda match: (
            -match.rrf_score,
            min(rank for rank in (match.bm25_rank, match.vector_rank) if rank is not None),
            match.bm25_rank if match.bm25_rank is not None else math.inf,
            match.vector_rank if match.vector_rank is not None else math.inf,
            match.project.project_id,
        )
    )
    return [
        SearchMatch(
            project=match.project,
            rank=index,
            bm25_rank=match.bm25_rank,
            vector_rank=match.vector_rank,
            rrf_score=match.rrf_score,
            shared_elements=match.shared_elements,
            verification_status=match.verification_status,
        )
        for index, match in enumerate(fused[:top_k], start=1)
    ]
