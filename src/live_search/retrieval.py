"""Candidate-pool BM25, dense ranking, RRF fusion, and evidence explanation."""

from __future__ import annotations

import logging
import math
import re
import threading
from collections.abc import Sequence
from typing import Protocol

from rank_bm25 import BM25Okapi

from src.live_search.contracts import CandidateRecord, RankedCandidate

logger = logging.getLogger("idea_enhancer.live_retrieval")
_WORD = re.compile(r"[\w]+", flags=re.UNICODE)
_STOP = frozenset("a an and are as at be by for from has have in into is it its of on or that the their this to was were with using use used based system project idea build create develop design".split())
RRF_CONSTANT = 60
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class DenseEncoder(Protocol):
    def encode(self, texts: Sequence[str], *, query: bool = False) -> Sequence[Sequence[float]]: ...


class DenseUnavailable(RuntimeError):
    """The configured semantic model could not produce usable embeddings."""


class SentenceTransformerEncoder:
    """Lazy CPU-first singleton encoder; model loading never happens on import."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def encode(self, texts: Sequence[str], *, query: bool = False) -> Sequence[Sequence[float]]:
        with self._lock:
            if self._model is None:
                try:
                    from src.embeddings import get_sentence_transformer

                    self._model = get_sentence_transformer(self.model_name, "cpu")
                except Exception as error:
                    raise DenseUnavailable(f"The semantic model could not be initialized ({type(error).__name__}).") from error
            prepared = [QUERY_INSTRUCTION + text if query else text for text in texts]
            try:
                vectors = self._model.encode(
                    prepared, normalize_embeddings=True, show_progress_bar=False,
                    batch_size=16, convert_to_numpy=True,
                )
                return vectors.tolist() if hasattr(vectors, "tolist") else vectors
            except Exception as error:
                raise DenseUnavailable(f"The semantic model could not encode this search ({type(error).__name__}).") from error


def _tokens(text: str) -> list[str]:
    return [token for token in _WORD.findall(text.casefold()) if len(token) > 1 and token not in _STOP and not token.isdigit()]


def _cosine_for_normalized(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise DenseUnavailable("Embedding dimensions were missing or inconsistent.")
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        raise DenseUnavailable("The embedding model returned a zero-length vector.")
    score = sum((float(a) / left_norm) * (float(b) / right_norm) for a, b in zip(left, right))
    if not math.isfinite(score):
        raise DenseUnavailable("Embedding values were not finite numbers.")
    return max(-1.0, min(1.0, score))


def rank_candidates(
    idea: str,
    candidates: Sequence[CandidateRecord],
    *,
    encoder: DenseEncoder | None,
    top_k: int,
) -> tuple[list[RankedCandidate], bool, str | None]:
    """Return hybrid rankings; if dense fails, explicitly return BM25-only mode."""
    unique = {candidate.candidate_id: candidate for candidate in candidates}
    corpus = list(unique.values())
    if not corpus:
        return [], True, None

    query_tokens = _tokens(idea)
    bm25_ranks: dict[str, int] = {}
    if query_tokens:
        index = BM25Okapi([_tokens(candidate.searchable_text) for candidate in corpus])
        if index.corpus_size:
            floor = 0.25 * getattr(index, "average_idf", 0.0)
            floor = floor if floor > 0 else 0.25
            for token, idf in list(index.idf.items()):
                if idf <= 0:
                    index.idf[token] = floor
            scores = index.get_scores(query_tokens)
            ordered = sorted(
                ((candidate, float(score)) for candidate, score in zip(corpus, scores) if score > 0),
                key=lambda item: (-item[1], item[0].candidate_id),
            )
            bm25_ranks = {candidate.candidate_id: rank for rank, (candidate, _) in enumerate(ordered, 1)}

    dense_ranks: dict[str, int] = {}
    cosine_scores: dict[str, float] = {}
    dense_available = encoder is not None
    dense_error = None
    if encoder is not None:
        try:
            corpus_vectors = encoder.encode([candidate.searchable_text for candidate in corpus])
            query_vectors = encoder.encode([idea], query=True)
            if len(corpus_vectors) != len(corpus) or len(query_vectors) != 1:
                raise DenseUnavailable("The embedding model returned an unexpected number of vectors.")
            query_vector = query_vectors[0]
            computed_similarities: dict[str, float] = {}
            for candidate, vector in zip(corpus, corpus_vectors):
                computed_similarities[candidate.candidate_id] = _cosine_for_normalized(query_vector, vector)
        except Exception as error:
            dense_available = False
            dense_error = "Semantic ranking is unavailable; results use keyword ranking only."
            logger.warning("Dense candidate ranking unavailable (%s)", type(error).__name__)
        else:
            cosine_scores = computed_similarities
            ordered_dense = sorted(corpus, key=lambda c: (-cosine_scores[c.candidate_id], c.candidate_id))
            dense_ranks = {candidate.candidate_id: rank for rank, candidate in enumerate(ordered_dense, 1)}

    ranked_ids = set(bm25_ranks) | set(dense_ranks)
    candidate_by_id = unique
    fused_scores: dict[str, float] = {}
    for candidate_id in ranked_ids:
        fused_scores[candidate_id] = sum(
            1.0 / (RRF_CONSTANT + ranks[candidate_id])
            for ranks in (bm25_ranks, dense_ranks) if candidate_id in ranks
        )
    ordered_ids = sorted(
        ranked_ids,
        key=lambda candidate_id: (
            -fused_scores[candidate_id],
            min(rank for rank in (bm25_ranks.get(candidate_id), dense_ranks.get(candidate_id)) if rank is not None),
            bm25_ranks.get(candidate_id, math.inf),
            dense_ranks.get(candidate_id, math.inf),
            candidate_id,
        ),
    )[:top_k]

    idea_set = set(query_tokens)
    result: list[RankedCandidate] = []
    for rank, candidate_id in enumerate(ordered_ids, 1):
        candidate = candidate_by_id[candidate_id]
        candidate_tokens = _tokens(candidate.searchable_text)
        shared = tuple(dict.fromkeys(token for token in candidate_tokens if token in idea_set))[:12]
        distinctive = tuple(dict.fromkeys(token for token in candidate_tokens if token not in idea_set))[:8]
        signals = []
        if candidate_id in bm25_ranks:
            signals.append(f"keyword rank {bm25_ranks[candidate_id]}")
        if candidate_id in dense_ranks:
            signals.append(f"semantic rank {dense_ranks[candidate_id]}")
        why = " and ".join(signals) if signals else "retrieval signal"
        explanation = f"Retrieved from {candidate.source_provider} by {why}."
        if shared:
            explanation += " Shared terms: " + ", ".join(shared) + "."
        if candidate.provider_metadata.get("discovery_rank") is not None:
            explanation += f" Provider discovery position: {candidate.provider_metadata['discovery_rank']}."
        result.append(RankedCandidate(
            candidate=candidate, rank=rank, bm25_rank=bm25_ranks.get(candidate_id),
            dense_rank=dense_ranks.get(candidate_id), rrf_score=fused_scores[candidate_id],
            semantic_similarity=cosine_scores.get(candidate_id), shared_concepts=shared,
            distinctive_terms=distinctive, explanation=explanation,
        ))
    return result, dense_available, dense_error
