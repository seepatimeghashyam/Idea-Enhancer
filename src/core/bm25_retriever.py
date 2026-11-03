"""BM25 keyword retrieval module for Idea Enhancer Core Search backend."""

from __future__ import annotations

import re
from collections.abc import Sequence

from rank_bm25 import BM25Okapi

from src.core.contracts import ProjectRecord, RetrievalHit, build_search_text


_TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)
_QUERY_STOP_WORDS = frozenset(
    "a an and are as at be by for from has have in into is it its of on or that the their this to was were "
    "with using use used based system project idea".split()
)


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    if not text:
        return []
    return _TOKEN_PATTERN.findall(text.lower())


class BM25Retriever:
    """Keyword retriever based on BM25Okapi over canonical project records."""

    def __init__(self, records: Sequence[ProjectRecord]) -> None:
        """Initialize the BM25 index from a sequence of canonical project records.

        Searchable text is constructed strictly using the shared `build_search_text`
        helper, which includes title, abstract, tech_stack, and domain. Provenance,
        source URLs, and project IDs are excluded from searchable text.
        """
        seen_ids: set[str] = set()
        self._records: list[ProjectRecord] = []
        tokenized_corpus: list[list[str]] = []

        for record in records:
            if not isinstance(record, ProjectRecord):
                raise ValueError("records must contain ProjectRecord instances.")
            if not isinstance(record.project_id, str) or not record.project_id.strip():
                raise ValueError("ProjectRecord must have a non-empty project_id.")
            if record.project_id in seen_ids:
                raise ValueError(f"Duplicate project_id {record.project_id!r} in supplied records.")

            seen_ids.add(record.project_id)
            self._records.append(record)
            searchable_text = build_search_text(record)
            tokenized_corpus.append(tokenize(searchable_text))

        if tokenized_corpus:
            self._bm25: BM25Okapi | None = BM25Okapi(tokenized_corpus)
            # Ensure zero/negative IDF values receive a floor to avoid division artifacts
            # on small corpora (e.g., when a term appears in exactly half of documents).
            if self._bm25.corpus_size > 0:
                eps = 0.25 * getattr(self._bm25, "average_idf", 0.0)
                if eps <= 0:
                    eps = 0.25
                for word, idf in list(self._bm25.idf.items()):
                    if idf <= 0:
                        self._bm25.idf[word] = eps
        else:
            self._bm25 = None

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        """Search the indexed records and return ordered RetrievalHit objects.

        Returns at most ``top_k`` hits, ordered by 1-based rank (best match first).
        If no query term overlaps the corpus, returns an empty list. Ties are resolved
        deterministically by stable project ID.
        """
        if not isinstance(query, str):
            raise ValueError("query must be a string.")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k must be a positive integer.")

        if self._bm25 is None or not self._records:
            return []

        query_tokens = [token for token in tokenize(query) if token not in _QUERY_STOP_WORDS]
        if not query_tokens:
            return []

        # Return no candidates when no searchable query term overlaps the corpus
        if not any(token in self._bm25.idf for token in query_tokens):
            return []

        scores = self._bm25.get_scores(query_tokens)

        candidates: list[tuple[str, float]] = []
        for record, score in zip(self._records, scores):
            if score > 0:
                candidates.append((record.project_id, float(score)))

        if not candidates:
            return []

        # Deterministic sorting: higher BM25 score first; tie-break by project_id ascending
        candidates.sort(key=lambda item: (-item[1], item[0]))

        return [
            RetrievalHit(project_id=project_id, rank=rank)
            for rank, (project_id, _) in enumerate(candidates[:top_k], start=1)
        ]
