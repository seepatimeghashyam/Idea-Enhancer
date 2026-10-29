"""Unit tests for the BM25 keyword retrieval module."""

from __future__ import annotations

import sys
import pytest

from src.core.bm25_retriever import BM25Retriever, tokenize
from src.core.contracts import ProjectRecord, RetrievalHit


@pytest.fixture(autouse=True, scope="module")
def _cleanup_retriever_from_sys_modules() -> None:
    """Clean up sys.modules so sibling database tests verifying lazy import isolation pass."""
    yield
    sys.modules.pop("src.core.bm25_retriever", None)


def make_record(
    project_id: str,
    title: str = "Test Title",
    abstract: str = "Test Abstract",
    tech_stack: str | None = "Python",
    domain: str | None = "AI",
    source_type: str = "rvce",
    source_url: str | None = None,
    year: int | None = 2024,
) -> ProjectRecord:
    """Helper to create a synthetic in-memory ProjectRecord."""
    return ProjectRecord(
        project_id=project_id,
        title=title,
        abstract=abstract,
        tech_stack=tech_stack,
        domain=domain,
        source_type=source_type,
        source_url=source_url,
        year=year,
    )


# 1. Exact title and technology matches
def test_exact_title_match() -> None:
    records = [
        make_record("P1", title="Autonomous Drone Delivery", abstract="General logistics", tech_stack="C++"),
        make_record("P2", title="Smart Farming Soil Analysis", abstract="Agricultural robotics", tech_stack="Python"),
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("Autonomous Drone", top_k=5)
    assert len(hits) == 1
    assert hits[0].project_id == "P1"
    assert hits[0].rank == 1


def test_technology_match() -> None:
    records = [
        make_record("P1", title="System A", abstract="Database system", tech_stack="PostgreSQL, Redis"),
        make_record("P2", title="System B", abstract="Web application", tech_stack="React, FastAPI"),
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("FastAPI", top_k=5)
    assert len(hits) == 1
    assert hits[0].project_id == "P2"
    assert hits[0].rank == 1


# 2. Relevant terms appearing in an abstract
def test_abstract_match() -> None:
    records = [
        make_record("P1", title="Project Alpha", abstract="Uses convolutional neural networks for leaf rust detection"),
        make_record("P2", title="Project Beta", abstract="Blockchain-based voting mechanism for student elections"),
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("leaf rust detection", top_k=5)
    assert len(hits) == 1
    assert hits[0].project_id == "P1"
    assert hits[0].rank == 1


# 3. Different ranking when query terms differ
def test_different_ranking_for_different_queries() -> None:
    records = [
        make_record("P1", title="Water Quality Monitoring", abstract="Sensor networks detecting water pollution in rivers"),
        make_record("P2", title="Air Pollution Tracker", abstract="Monitoring particulate matter and smog in urban air"),
    ]
    retriever = BM25Retriever(records)

    hits_water = retriever.search("water quality sensor", top_k=2)
    assert hits_water[0].project_id == "P1"

    hits_air = retriever.search("urban air smog", top_k=2)
    assert hits_air[0].project_id == "P2"


# 4. An unrelated query with no keyword overlap
def test_unrelated_query_returns_no_candidates() -> None:
    records = [
        make_record("P1", title="Crop Disease Detection", abstract="Computer vision models for agriculture"),
        make_record("P2", title="Campus Navigation Assistant", abstract="Indoor mapping for university buildings"),
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("quantum cryptography encryption", top_k=5)
    assert hits == []


# 5. An empty corpus and empty/tokenless query
def test_empty_corpus() -> None:
    retriever = BM25Retriever([])
    hits = retriever.search("machine learning", top_k=5)
    assert hits == []


def test_empty_and_whitespace_query() -> None:
    records = [make_record("P1", title="Machine Learning Platform")]
    retriever = BM25Retriever(records)
    assert retriever.search("", top_k=5) == []
    assert retriever.search("   ", top_k=5) == []


def test_tokenless_punctuation_query() -> None:
    records = [make_record("P1", title="Machine Learning Platform")]
    retriever = BM25Retriever(records)
    assert retriever.search("!@#$%^&*()_+", top_k=5) == []


# 6. Missing optional record metadata
def test_missing_optional_metadata() -> None:
    records = [
        make_record(
            "P1",
            title="Solar Panel Efficiency Optimizer",
            abstract="Tracking solar irradiance for power maximization",
            tech_stack=None,
            domain=None,
            source_url=None,
            year=None,
        )
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("solar irradiance", top_k=5)
    assert len(hits) == 1
    assert hits[0].project_id == "P1"


# 7. Duplicate project IDs
def test_duplicate_project_ids_raise_error() -> None:
    records = [
        make_record("P1", title="First Instance"),
        make_record("P1", title="Duplicate Instance"),
    ]
    with pytest.raises(ValueError, match="Duplicate project_id 'P1'"):
        BM25Retriever(records)


# 8. top_k limits
def test_top_k_limit_applied() -> None:
    records = [
        make_record("P1", title="Traffic AI System 1", abstract="Deep learning traffic optimization"),
        make_record("P2", title="Traffic AI System 2", abstract="Deep learning traffic signal control"),
        make_record("P3", title="Traffic AI System 3", abstract="Deep learning traffic congestion monitor"),
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("traffic deep learning", top_k=2)
    assert len(hits) == 2
    assert hits[0].rank == 1
    assert hits[1].rank == 2


# 9. Stable tie-breaking
def test_stable_tie_breaking_by_project_id() -> None:
    # Two records with identical content will produce identical BM25 scores.
    # Tie-breaking should deterministically place 'A_PROJECT' before 'Z_PROJECT'.
    records = [
        make_record("Z_PROJECT", title="Duplicate Content Model", abstract="Identical search text here"),
        make_record("A_PROJECT", title="Duplicate Content Model", abstract="Identical search text here"),
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("Duplicate Content", top_k=2)
    assert len(hits) == 2
    assert hits[0].project_id == "A_PROJECT"
    assert hits[0].rank == 1
    assert hits[1].project_id == "Z_PROJECT"
    assert hits[1].rank == 2


# 10. Ordered, contiguous 1-based ranks
def test_contiguous_1_based_ranks() -> None:
    records = [
        make_record("P1", title="Smart Healthcare EHR", abstract="Medical database application"),
        make_record("P2", title="Healthcare Diagnostics", abstract="AI diagnostics for healthcare"),
        make_record("P3", title="Hospital Bed Management", abstract="Healthcare resource scheduling"),
    ]
    retriever = BM25Retriever(records)
    hits = retriever.search("Healthcare AI diagnostics", top_k=10)
    assert len(hits) >= 2
    for expected_rank, hit in enumerate(hits, start=1):
        assert hit.rank == expected_rank
        assert isinstance(hit, RetrievalHit)


# 11. Every returned ID exists in the supplied records
def test_every_returned_id_exists_in_supplied_records() -> None:
    records = [
        make_record("RVCE_001", title="Smart Energy Grid"),
        make_record("RVCE_002", title="Water Pipeline Monitoring"),
    ]
    valid_ids = {"RVCE_001", "RVCE_002"}
    retriever = BM25Retriever(records)
    hits = retriever.search("energy pipeline", top_k=5)
    for hit in hits:
        assert hit.project_id in valid_ids


# 12. Repeated identical queries produce deterministic results
def test_deterministic_results_for_repeated_queries() -> None:
    records = [
        make_record("P1", title="Cybersecurity Intrusion Detection", abstract="Anomaly detection in network traffic"),
        make_record("P2", title="Malware Classification", abstract="Deep learning classification of malicious executables"),
        make_record("P3", title="Phishing URL Detector", abstract="Transformer models detecting phishing URLs"),
    ]
    retriever = BM25Retriever(records)
    result_first = retriever.search("network security anomaly", top_k=3)
    result_second = retriever.search("network security anomaly", top_k=3)
    assert result_first == result_second


# 13. Invalid input and error behavior
@pytest.mark.parametrize("invalid_top_k", [0, -1, -10, True, False, "5", None, 3.14])
def test_invalid_top_k_raises_value_error(invalid_top_k) -> None:
    records = [make_record("P1", title="Some Project")]
    retriever = BM25Retriever(records)
    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        retriever.search("Some Project", top_k=invalid_top_k)


@pytest.mark.parametrize("invalid_query", [None, 123, ["query"], {"text": "query"}])
def test_invalid_query_type_raises_value_error(invalid_query) -> None:
    records = [make_record("P1", title="Some Project")]
    retriever = BM25Retriever(records)
    with pytest.raises(ValueError, match="query must be a string"):
        retriever.search(invalid_query, top_k=5)


def test_invalid_record_element_raises_value_error() -> None:
    with pytest.raises(ValueError, match="ProjectRecord"):
        BM25Retriever(["not_a_record"])  # type: ignore[list-item]


def test_empty_project_id_raises_value_error() -> None:
    with pytest.raises(ValueError, match="non-empty project_id"):
        BM25Retriever([make_record("   ")])


# Additional: Verify tokenization helper function
def test_tokenizer() -> None:
    assert tokenize("Hello, World! 123") == ["hello", "world", "123"]
    assert tokenize("") == []
    assert tokenize("   ---   ") == []
