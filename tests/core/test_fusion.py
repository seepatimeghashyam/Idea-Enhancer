from __future__ import annotations

import pytest

from src.core.contracts import ProjectRecord, RetrievalHit
from src.core.fusion import FusionError, fuse_rankings


def record(project_id: str) -> ProjectRecord:
    return ProjectRecord(project_id, f"MOCK ONLY {project_id}", "MOCK ONLY abstract", None, None, "MOCK ONLY", None, None)


def mapping(*ids: str) -> dict[str, ProjectRecord]:
    return {project_id: record(project_id) for project_id in ids}


def test_fuses_both_retrievers_and_preserves_missing_rank_as_none() -> None:
    matches = fuse_rankings(
        [RetrievalHit("both", 1), RetrievalHit("keyword-only", 2)],
        [RetrievalHit("vector-only", 1), RetrievalHit("both", 3)],
        mapping("both", "keyword-only", "vector-only"),
        top_k=5,
    )
    by_id = {match.project.project_id: match for match in matches}

    assert matches[0].project.project_id == "both"
    assert by_id["both"].rrf_score == pytest.approx(1 / 61 + 1 / 63)
    assert by_id["keyword-only"].bm25_rank == 2
    assert by_id["keyword-only"].vector_rank is None
    assert by_id["vector-only"].bm25_rank is None
    assert by_id["vector-only"].vector_rank == 1
    assert [match.rank for match in matches] == [1, 2, 3]


def test_empty_lists_return_no_matches() -> None:
    assert fuse_rankings([], [], {}, top_k=5) == []


def test_ties_are_deterministic_and_top_k_is_applied() -> None:
    bm25 = [RetrievalHit("a", 1), RetrievalHit("b", 2)]
    vector = [RetrievalHit("b", 1), RetrievalHit("a", 2)]
    records = mapping("a", "b")

    first = fuse_rankings(bm25, vector, records, top_k=1)
    second = fuse_rankings(bm25, vector, records, top_k=1)

    assert first == second
    assert len(first) == 1
    assert first[0].project.project_id == "a"


@pytest.mark.parametrize(
    ("bm25", "vector", "message"),
    [
        ([RetrievalHit("a", 1), RetrievalHit("a", 2)], [], "duplicate project_id"),
        ([RetrievalHit("a", 1)], [RetrievalHit("a", 1), RetrievalHit("a", 2)], "duplicate project_id"),
        ([RetrievalHit("a", 0)], [], "positive 1-based integer"),
        ([RetrievalHit("a", 1), RetrievalHit("b", 1)], [], "duplicate rank"),
        ([RetrievalHit("unknown", 1)], [], "absent from the canonical dataset"),
    ],
)
def test_rejects_malformed_retriever_output(bm25, vector, message: str) -> None:
    with pytest.raises(FusionError, match=message):
        fuse_rankings(bm25, vector, mapping("a", "b"), top_k=5)


@pytest.mark.parametrize("top_k", [0, -1, True])
def test_requires_positive_integer_top_k(top_k) -> None:
    with pytest.raises(ValueError, match="top_k"):
        fuse_rankings([], [], {}, top_k=top_k)
