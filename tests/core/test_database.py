from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.core.contracts import RetrievalHit
from src.core.dataset_loader import load_project_records
from src.core.engine import CoreSearchEngine
from src.database import CoreSearchUnavailable, configure_search_engine, search_projects
from tests.core.test_engine import FakeRetriever


FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic_core_projects.csv"


def test_public_facade_returns_canonical_api_formatter_fields_without_fabricated_metadata() -> None:
    engine = CoreSearchEngine(
        load_project_records(FIXTURE),
        FakeRetriever([RetrievalHit("SYNTHETIC-001", 1)]),
        FakeRetriever([RetrievalHit("SYNTHETIC-001", 1)]),
    )
    configure_search_engine(engine)
    try:
        matches = search_projects("crop disease monitoring system", top_k=5)
    finally:
        configure_search_engine(None)

    assert set(matches[0]) == {
        "project_id", "title", "abstract", "tech_stack", "source_type", "source_url", "year", "domain",
        "rank", "bm25_rank", "vector_rank", "rrf_score", "shared_elements", "verification_status",
    }
    assert matches[0]["abstract"].startswith("MOCK ONLY:")
    assert matches[0]["source_url"] is None
    assert matches[0]["tech_stack"] == "Raspberry Pi"
    assert matches[0]["verification_status"] == "checked"


def test_missing_default_dataset_is_unavailable_and_does_not_import_retrievers(monkeypatch) -> None:
    from src import database

    configure_search_engine(None)
    monkeypatch.setattr(database, "CANONICAL_DATASET_PATH", Path("missing-synthetic-dataset.csv"))

    with pytest.raises(CoreSearchUnavailable, match="Canonical dataset not found"):
        search_projects("a sufficiently detailed idea")

    assert "src.core.vector_retriever" not in sys.modules
    assert "src.core.bm25_retriever" not in sys.modules


def test_unexpected_retriever_errors_remain_internal_errors() -> None:
    engine = CoreSearchEngine(
        load_project_records(FIXTURE),
        FakeRetriever([], RuntimeError("synthetic engine defect")),
        FakeRetriever([]),
    )
    configure_search_engine(engine)
    try:
        with pytest.raises(RuntimeError, match="synthetic engine defect") as exc_info:
            search_projects("a sufficiently detailed idea")
        assert not isinstance(exc_info.value, CoreSearchUnavailable)
    finally:
        configure_search_engine(None)


def test_vector_index_unavailability_maps_to_core_search_unavailable() -> None:
    module_name = "src.core.vector_retriever"
    previous_module = sys.modules.get(module_name)
    try:
        from src.core.vector_retriever import VectorIndexUnavailableError

        engine = CoreSearchEngine(
            load_project_records(FIXTURE),
            FakeRetriever([]),
            FakeRetriever([], VectorIndexUnavailableError("synthetic vector outage")),
        )
        configure_search_engine(engine)
        with pytest.raises(CoreSearchUnavailable, match="synthetic vector outage"):
            search_projects("a sufficiently detailed idea")
    finally:
        configure_search_engine(None)
        if previous_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous_module


@pytest.mark.parametrize("top_k", [0, 21, True])
def test_public_facade_rejects_invalid_top_k_before_initialization(top_k) -> None:
    with pytest.raises(ValueError, match="top_k"):
        search_projects("a sufficiently detailed idea", top_k)
