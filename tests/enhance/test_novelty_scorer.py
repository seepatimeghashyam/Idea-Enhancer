"""Tests for deterministic evidence-based novelty scoring."""

from src.enhance.contracts import MatchInput
from src.enhance.novelty_scorer import compute_evidence_novelty


def test_novelty_score_empty_matches_local() -> None:
    score, level, reason = compute_evidence_novelty(
        "A novel underwater wireless charging device", [], evidence_scope="local"
    )
    assert score is None
    assert level == "unknown"
    assert "wider online check is required" in reason


def test_novelty_score_empty_matches_online() -> None:
    score, level, reason = compute_evidence_novelty(
        "A novel underwater wireless charging device", [], evidence_scope="local+online"
    )
    assert score is None
    assert level == "unknown"
    assert "still does not prove originality" in reason


def test_novelty_score_heavy_overlap() -> None:
    matches = [
        MatchInput(
            project_id=f"proj_{i}",
            title=f"Smart Agriculture Monitoring {i}",
            rank=i + 1,
            rrf_score=0.032,
            shared_elements=["agriculture", "monitoring", "iot", "sensor", "crops", "raspberry pi"],
        )
        for i in range(5)
    ]
    score, level, reason = compute_evidence_novelty("Smart Agriculture Monitoring IoT System", matches)
    assert score is not None
    assert score < 0.40
    assert level == "low"
    assert "High direct overlap" in reason


def test_novelty_score_rank_aware_ordering() -> None:
    # Lower rank integer (rank 1) should be prioritized even if placed at end of list
    m1 = MatchInput(project_id="p_low", title="Title 2", rank=5, rrf_score=0.010)
    m2 = MatchInput(project_id="p_high", title="Title 1", rank=1, rrf_score=0.033)
    score, level, _ = compute_evidence_novelty("My test idea text", [m1, m2])
    assert score is not None
    # With rank 1 having rrf 0.033, overlap is high, score should reflect high overlap
    assert score < 0.70


def test_novelty_score_bounds() -> None:
    matches = [
        MatchInput(
            project_id="proj_ext",
            title="Exact Idea Match",
            rank=1,
            rrf_score=0.05,
            shared_elements=[f"term_{i}" for i in range(15)],
        )
        for _ in range(5)
    ]
    score, _, _ = compute_evidence_novelty("Exact idea proposal", matches)
    assert score is not None
    assert 0.05 <= score <= 0.95
