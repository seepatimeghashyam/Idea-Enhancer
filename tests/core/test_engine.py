from __future__ import annotations

from pathlib import Path

import pytest

from src.core.contracts import RetrievalHit
from src.core.dataset_loader import load_project_records
from src.core.engine import CoreSearchEngine


FIXTURE = Path(__file__).parents[1] / "fixtures" / "synthetic_core_projects.csv"


class FakeRetriever:
    def __init__(self, hits: list[RetrievalHit], error: Exception | None = None) -> None:
        self.hits = hits
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        self.calls.append((query, top_k))
        if self.error:
            raise self.error
        return self.hits[:top_k]


def make_engine(bm25: FakeRetriever, vector: FakeRetriever) -> CoreSearchEngine:
    return CoreSearchEngine(load_project_records(FIXTURE), bm25, vector)


def test_orchestrates_same_query_and_top_k_then_enriches_with_evidence() -> None:
    bm25 = FakeRetriever([RetrievalHit("SYNTHETIC-001", 1)])
    vector = FakeRetriever([RetrievalHit("SYNTHETIC-002", 1), RetrievalHit("SYNTHETIC-001", 2)])
    engine = make_engine(bm25, vector)

    matches = engine.search("  crop disease monitoring system  ", 2)

    assert bm25.calls == [("crop disease monitoring system", 2)]
    assert vector.calls == [("crop disease monitoring system", 2)]
    assert matches[0].project.project_id == "SYNTHETIC-001"
    assert matches[0].bm25_rank == 1
    assert matches[0].vector_rank == 2
    assert matches[0].shared_elements == ["crop", "disease"]
    assert matches[0].verification_status == "checked"
    assert matches[1].verification_status == "insufficient"


@pytest.mark.parametrize("which", ["bm25", "vector"])
def test_retriever_errors_propagate_from_engine(which: str) -> None:
    failure = RuntimeError(f"MOCK ONLY: {which} retriever failed")
    bm25 = FakeRetriever([], failure if which == "bm25" else None)
    vector = FakeRetriever([], failure if which == "vector" else None)

    with pytest.raises(RuntimeError, match="MOCK ONLY"):
        make_engine(bm25, vector).search("a sufficiently detailed idea")


@pytest.mark.parametrize(
    ("idea", "top_k"),
    [("short", 5), ("a" * 2001, 5), ("a sufficiently detailed idea", 0), ("a sufficiently detailed idea", 21), ("a sufficiently detailed idea", True)],
)
def test_engine_validates_direct_search_arguments(idea: str, top_k: int) -> None:
    engine = make_engine(FakeRetriever([]), FakeRetriever([]))

    with pytest.raises(ValueError):
        engine.search(idea, top_k)
