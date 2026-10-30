"""Regression tests for ignoring generic filler words in BM25 queries."""

from src.core.bm25_retriever import BM25Retriever
from src.core.contracts import ProjectRecord


def _record(pid: str, title: str, abstract: str) -> ProjectRecord:
    return ProjectRecord(pid, title, abstract, None, None, "synthetic", None, None)


def _retriever() -> BM25Retriever:
    return BM25Retriever(
        [
            _record("A", "Crop disease detection", "A system for the detection of crop disease using CNNs."),
            _record("B", "Voting platform", "A system for secure vote counting using a ledger."),
            _record("C", "Chess engine", "A program that plays chess using search."),
        ]
    )


def test_query_made_only_of_filler_words_returns_nothing() -> None:
    assert _retriever().search("the of and a for to in with using", 5) == []


def test_filler_words_do_not_pull_in_unrelated_records() -> None:
    hits = _retriever().search("a system for crop disease", 5)
    assert [hit.project_id for hit in hits] == ["A"]
