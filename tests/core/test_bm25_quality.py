"""Quality and consistency validation suite for BM25 keyword retrieval.

Validates retrieval behavior across diverse query scenarios using synthetic
in-memory ProjectRecord fixtures (no external datasets, embeddings, or network).
"""

from __future__ import annotations

import sys
import pytest

from src.core.bm25_retriever import BM25Retriever
from src.core.contracts import ProjectRecord, RetrievalHit


@pytest.fixture(autouse=True, scope="module")
def _cleanup_retriever_from_sys_modules() -> None:
    """Clean up sys.modules so sibling database tests verifying lazy import isolation pass."""
    yield
    sys.modules.pop("src.core.bm25_retriever", None)


def make_record(
    project_id: str,
    title: str,
    abstract: str,
    tech_stack: str | None = None,
    domain: str | None = None,
    source_type: str = "rvce",
    source_url: str | None = None,
    year: int | None = 2024,
) -> ProjectRecord:
    """Helper to construct a canonical in-memory synthetic ProjectRecord."""
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


@pytest.fixture
def tech_corpus() -> list[ProjectRecord]:
    """A realistic technical project corpus covering AI, Systems, Web, and Security."""
    return [
        make_record(
            project_id="PROJ-IOT-01",
            title="Smart Crop Irrigation System",
            abstract="Automated water management using IoT sensor telemetry and microcontroller valves.",
            tech_stack="ESP32, Arduino, C++",
            domain="Agriculture / IoT",
        ),
        make_record(
            project_id="PROJ-CNN-02",
            title="Leaf Rust Diagnostic Tool",
            abstract="Deep learning vision pipeline leveraging CNN convolutional neural networks to detect plant pathology.",
            tech_stack="PyTorch, CNN, Python",
            domain="Computer Vision",
        ),
        make_record(
            project_id="PROJ-SEC-03",
            title="Enterprise Threat Monitoring Platform",
            abstract="Real-time network security analyzer alerting on anomalous traffic and port intrusion.",
            tech_stack="Python, Zeek, Snort",
            domain="Cybersecurity",
        ),
        make_record(
            project_id="PROJ-BM25-04",
            title="Hybrid Information Retrieval Engine",
            abstract="Core search engine combining BM25 keyword matching with dense vector embeddings.",
            tech_stack="Python, BM25, ChromaDB",
            domain="Information Retrieval",
        ),
        make_record(
            project_id="PROJ-API-05",
            title="Campus Event Gateway",
            abstract="Microservice providing a high-throughput REST API for student club registration and ticketing.",
            tech_stack="FastAPI, PostgreSQL, Redis",
            domain="Web / Cloud",
        ),
    ]


# 1. Exact technical-term matching
def test_exact_technical_term_matching(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)

    # BM25 technical term
    hits_bm25 = retriever.search("BM25", top_k=5)
    assert len(hits_bm25) == 1
    assert hits_bm25[0].project_id == "PROJ-BM25-04"
    assert hits_bm25[0].rank == 1

    # API technical term
    hits_api = retriever.search("API", top_k=5)
    assert len(hits_api) == 1
    assert hits_api[0].project_id == "PROJ-API-05"
    assert hits_api[0].rank == 1


# 2. Technical terms appearing in the abstract rather than title
def test_technical_terms_in_abstract(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)

    # 'telemetry' appears only in PROJ-IOT-01 abstract, not in the title
    hits_telemetry = retriever.search("sensor telemetry", top_k=5)
    assert len(hits_telemetry) >= 1
    assert hits_telemetry[0].project_id == "PROJ-IOT-01"
    assert hits_telemetry[0].rank == 1

    # 'convolutional' appears only in PROJ-CNN-02 abstract
    hits_conv = retriever.search("convolutional pathology", top_k=5)
    assert len(hits_conv) >= 1
    assert hits_conv[0].project_id == "PROJ-CNN-02"
    assert hits_conv[0].rank == 1


# 3. Queries containing multiple distinctive terms
def test_multiple_distinctive_terms(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)

    # Query matching multiple terms from PROJ-SEC-03 ("network", "security", "threat")
    hits = retriever.search("enterprise network security threat", top_k=3)
    assert len(hits) >= 1
    assert hits[0].project_id == "PROJ-SEC-03"
    assert hits[0].rank == 1


# 4. Queries with common terms that appear in many records (IDF weighting)
def test_common_vs_distinctive_terms_ranking() -> None:
    # 'system' and 'platform' appear across all records; 'cybersecurity' is distinctive
    records = [
        make_record("P-COMMON-1", "Database System Platform", "Storage management platform and system utilities"),
        make_record("P-COMMON-2", "Monitoring System Platform", "General telemetry platform and metrics system"),
        make_record("P-DISTINCT", "Cybersecurity Audit Platform", "System performing cybersecurity threat vulnerability audits"),
    ]
    retriever = BM25Retriever(records)

    hits = retriever.search("cybersecurity system platform", top_k=3)
    assert len(hits) == 3
    # P-DISTINCT must rank #1 due to high IDF of the distinctive term 'cybersecurity'
    assert hits[0].project_id == "P-DISTINCT"
    assert hits[0].rank == 1


# 5. Unrelated queries with no searchable overlap
def test_unrelated_queries_return_empty(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)
    unrelated_queries = [
        "quantum teleportation thermodynamics",
        "astrophysics supernova spectrometry",
        "metallurgy alloy tempering",
    ]
    for query in unrelated_queries:
        assert retriever.search(query, top_k=5) == []


# 6. Empty or tokenless queries
def test_empty_or_tokenless_queries(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)
    assert retriever.search("", top_k=5) == []
    assert retriever.search("   ", top_k=5) == []
    assert retriever.search("\t\n", top_k=5) == []
    assert retriever.search("!@#$%^&*()-_=+", top_k=5) == []


# 7. Results limited by top_k
def test_results_strictly_limited_by_top_k() -> None:
    records = [
        make_record(f"P{i:02d}", f"Machine Learning Model {i}", f"Predictive AI neural network {i}")
        for i in range(1, 11)
    ]
    retriever = BM25Retriever(records)

    # When top_k is smaller than matching record count
    for limit in [1, 2, 5, 8]:
        hits = retriever.search("machine learning", top_k=limit)
        assert len(hits) == limit
        assert [h.rank for h in hits] == list(range(1, limit + 1))

    # When top_k is larger than total matches, return all without padding
    hits_all = retriever.search("machine learning", top_k=20)
    assert len(hits_all) == 10
    assert [h.rank for h in hits_all] == list(range(1, 11))


# 8. Deterministic tie-breaking and stable repeated results
def test_deterministic_tie_breaking_and_stability() -> None:
    # Identical content creates identical BM25 scores; tie-break must use project_id ascending
    records = [
        make_record("ZETA_PROJ", "Identical Robot System", "Hardware automated navigation"),
        make_record("ALPHA_PROJ", "Identical Robot System", "Hardware automated navigation"),
        make_record("BETA_PROJ", "Identical Robot System", "Hardware automated navigation"),
    ]
    retriever = BM25Retriever(records)

    first_run = retriever.search("robot system navigation", top_k=3)
    second_run = retriever.search("robot system navigation", top_k=3)

    # Determinism across repeated queries
    assert first_run == second_run

    # Alphabetical tie-breaking order: ALPHA_PROJ, BETA_PROJ, ZETA_PROJ
    assert [h.project_id for h in first_run] == ["ALPHA_PROJ", "BETA_PROJ", "ZETA_PROJ"]
    assert [h.rank for h in first_run] == [1, 2, 3]


# 9. Returned IDs and 1-based ranks
def test_returned_ids_and_1_based_ranks(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)
    hits = retriever.search("smart irrigation and plant pathology", top_k=5)

    assert len(hits) >= 2
    valid_corpus_ids = {r.project_id for r in tech_corpus}
    seen_ranks: set[int] = set()

    for idx, hit in enumerate(hits, start=1):
        assert isinstance(hit, RetrievalHit)
        assert hit.project_id in valid_corpus_ids
        assert hit.rank == idx  # Contiguous 1-based rank
        assert hit.rank not in seen_ranks
        seen_ranks.add(hit.rank)


# 10. Technical vocabulary: BM25, IoT, CNN, API, and network security
@pytest.mark.parametrize(
    ("query", "expected_top_id"),
    [
        ("BM25", "PROJ-BM25-04"),
        ("IoT", "PROJ-IOT-01"),
        ("CNN", "PROJ-CNN-02"),
        ("API", "PROJ-API-05"),
        ("network security", "PROJ-SEC-03"),
    ],
)
def test_technical_vocabulary_retrieval(
    tech_corpus: list[ProjectRecord], query: str, expected_top_id: str
) -> None:
    retriever = BM25Retriever(tech_corpus)
    hits = retriever.search(query, top_k=3)
    assert len(hits) >= 1
    assert hits[0].project_id == expected_top_id
    assert hits[0].rank == 1


# 11. Case-insensitivity across uppercase, lowercase, and mixed-case queries
def test_case_insensitivity_for_technical_terms(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)

    results_lower = retriever.search("iot", top_k=3)
    results_upper = retriever.search("IOT", top_k=3)
    results_mixed = retriever.search("IoT", top_k=3)

    assert results_lower == results_upper == results_mixed
    assert results_mixed[0].project_id == "PROJ-IOT-01"


# 12. Punctuation-adjacent / hyphenated technical phrase handling
def test_hyphenated_technical_phrase_retrieval(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)

    # "IoT-based" should tokenize to 'iot' and 'based', successfully matching PROJ-IOT-01
    hits_iot = retriever.search("IoT-based smart crop system", top_k=3)
    assert len(hits_iot) >= 1
    assert hits_iot[0].project_id == "PROJ-IOT-01"

    # "REST-API" should tokenize to 'rest' and 'api', matching PROJ-API-05
    hits_api = retriever.search("REST-API gateway service", top_k=3)
    assert len(hits_api) >= 1
    assert hits_api[0].project_id == "PROJ-API-05"


# 13. State immutability across alternating searches
def test_state_immutability_across_alternating_searches(tech_corpus: list[ProjectRecord]) -> None:
    retriever = BM25Retriever(tech_corpus)

    query_a = "BM25 keyword search"
    query_b = "REST API gateway"

    res_a_1 = retriever.search(query_a, top_k=2)
    res_b_1 = retriever.search(query_b, top_k=2)
    res_a_2 = retriever.search(query_a, top_k=2)
    res_b_2 = retriever.search(query_b, top_k=2)

    assert res_a_1 == res_a_2
    assert res_b_1 == res_b_2
    assert res_a_1[0].project_id == "PROJ-BM25-04"
    assert res_b_1[0].project_id == "PROJ-API-05"
