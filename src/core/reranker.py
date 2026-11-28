"""Cross-encoder reranking for improved precision."""

from __future__ import annotations

import logging
import threading
from typing import Any, Protocol, Sequence

from src.core.contracts import ProjectRecord, SearchMatch

logger = logging.getLogger(__name__)

# Lazy-loaded cross-encoder model
_cross_encoder: Any = None
_cross_encoder_lock = threading.Lock()
_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker(Protocol):
    def rerank(self, query: str, matches: Sequence[SearchMatch], top_k: int) -> list[SearchMatch]: ...


def get_cross_encoder() -> Any | None:
    """Load cross-encoder model lazily. Returns None if unavailable."""
    global _cross_encoder
    if _cross_encoder is not None:
        return _cross_encoder
    with _cross_encoder_lock:
        if _cross_encoder is not None:
            return _cross_encoder
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder(_CROSS_ENCODER_MODEL, device="cpu")
            logger.info("Loaded cross-encoder model: %s", _CROSS_ENCODER_MODEL)
            return _cross_encoder
        except Exception as e:
            logger.warning("Cross-encoder unavailable: %s", e)
            return None


def rerank_with_cross_encoder(
    query: str,
    matches: Sequence[SearchMatch],
    top_k: int,
    initial_k: int = 50,
) -> list[SearchMatch]:
    """Rerank fused results using cross-encoder for higher precision."""
    if not matches:
        return []

    encoder = get_cross_encoder()
    if encoder is None:
        return list(matches[:top_k])

    # Take top initial_k for reranking to balance quality and speed
    candidates = matches[:min(initial_k, len(matches))]

    try:
        # Prepare pairs for cross-encoder: (query, document)
        pairs = [(query, match.project.abstract) for match in candidates]

        # Get relevance scores
        scores = encoder.predict(pairs, show_progress_bar=False, batch_size=16)

        # Sort by cross-encoder score
        reranked = sorted(
            zip(candidates, scores),
            key=lambda x: float(x[1]),
            reverse=True,
        )

        # Return top_k with updated rank
        result = []
        for new_rank, (match, score) in enumerate(reranked[:top_k], start=1):
            result.append(
                SearchMatch(
                    project=match.project,
                    rank=new_rank,
                    bm25_rank=match.bm25_rank,
                    vector_rank=match.vector_rank,
                    rrf_score=match.rrf_score,
                    shared_elements=match.shared_elements,
                    verification_status=match.verification_status,
                )
            )
        return result

    except Exception as e:
        logger.warning("Cross-encoder reranking failed: %s", e)
        return list(matches[:top_k])


def rerank_live_with_cross_encoder(
    query: str,
    matches: Sequence[dict[str, Any]],
    top_k: int,
    initial_k: int = 50,
) -> list[dict[str, Any]]:
    """Rerank live search results using cross-encoder."""
    if not matches:
        return []

    encoder = get_cross_encoder()
    if encoder is None:
        return list(matches[:top_k])

    candidates = matches[:min(initial_k, len(matches))]

    try:
        pairs = [(query, m.get("description", "") or m.get("title", "")) for m in candidates]
        scores = encoder.predict(pairs, show_progress_bar=False, batch_size=16)

        reranked = sorted(
            zip(candidates, scores),
            key=lambda x: float(x[1]),
            reverse=True,
        )

        result = []
        for new_rank, (match, score) in enumerate(reranked[:top_k], start=1):
            m = dict(match)
            m["rank"] = new_rank
            m["cross_encoder_score"] = float(score)
            result.append(m)
        return result

    except Exception as e:
        logger.warning("Cross-encoder reranking failed for live: %s", e)
        return list(matches[:top_k])