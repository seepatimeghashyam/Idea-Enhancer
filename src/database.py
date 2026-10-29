"""Public Core Search facade. Model and retriever imports are lazy by design."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.core.contracts import ProjectRecord
from src.core.dataset_loader import CANONICAL_DATASET_PATH, DatasetLoadError, load_project_records
from src.core.engine import CoreSearchEngine, validate_search_arguments


class CoreSearchUnavailable(RuntimeError):
    """The canonical records, vector index, or retrievers are not ready to search."""


_configured_engine: CoreSearchEngine | None = None
_cached_engine: CoreSearchEngine | None = None


def configure_search_engine(engine: CoreSearchEngine | None) -> None:
    """Explicitly configure an engine, primarily for controlled app setup/tests."""

    global _configured_engine
    _configured_engine = engine


def _make_default_engine(records: Sequence[ProjectRecord]) -> CoreSearchEngine:
    """Import contributor-owned retrievers only when a real search is requested.

    Contributor handoff contract: modules expose ``BM25Retriever(records)`` and
    ``VectorRetriever(records)``; each object implements ``search(query, top_k)``.
    The vector module is responsible for lazy model initialization and reporting
    a missing/unbuilt ChromaDB index during construction or search.
    """

    try:
        from src.core.bm25_retriever import BM25Retriever
        from src.core.vector_retriever import VectorRetriever
    except (ImportError, ModuleNotFoundError) as error:
        raise CoreSearchUnavailable(
            "Core Search retrievers are not installed yet; BM25 and vector retriever modules are required."
        ) from error

    try:
        return CoreSearchEngine(records, BM25Retriever(records), VectorRetriever(records))
    except CoreSearchUnavailable:
        raise
    except Exception as error:
        raise CoreSearchUnavailable(f"Core Search could not initialize its retrieval indexes: {error}") from error


def _get_engine() -> CoreSearchEngine:
    global _cached_engine
    if _configured_engine is not None:
        return _configured_engine
    if _cached_engine is not None:
        return _cached_engine

    try:
        records = load_project_records(CANONICAL_DATASET_PATH)
        _cached_engine = _make_default_engine(records)
    except (DatasetLoadError, CoreSearchUnavailable) as error:
        raise CoreSearchUnavailable(str(error)) from error
    return _cached_engine


def search_projects(idea: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Return canonical fields plus fusion/evidence data for the API formatter."""

    query, limit = validate_search_arguments(idea, top_k)
    try:
        matches = _get_engine().search(query, limit)
    except CoreSearchUnavailable:
        raise
    except Exception as error:
        raise CoreSearchUnavailable(f"Core Search failed while retrieving project matches: {error}") from error

    return [
        {
            "project_id": match.project.project_id,
            "title": match.project.title,
            "abstract": match.project.abstract,
            "tech_stack": match.project.tech_stack,
            "source_type": match.project.source_type,
            "source_url": match.project.source_url,
            "year": match.project.year,
            "domain": match.project.domain,
            "rank": match.rank,
            "bm25_rank": match.bm25_rank,
            "vector_rank": match.vector_rank,
            "rrf_score": match.rrf_score,
            "shared_elements": list(match.shared_elements),
            "verification_status": match.verification_status,
        }
        for match in matches
    ]
