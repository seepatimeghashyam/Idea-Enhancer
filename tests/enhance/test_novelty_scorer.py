"""Tests for deterministic evidence-based novelty scoring."""

from src.enhance.contracts import MatchInput
from src.enhance.novelty_scorer import compute_evidence_novelty


def test_novelty_score_empty_matches() -> None:
    score, level, reason = compute_evidence_novelty("A novel underwater wireless charging device", [])
    assert score == 0.95
    assert level == "high"
    assert "No prior-art matches" in reason


def test_novelty_score_heavy_overlap() -> None:
    matches = [
        MatchInput(
            project_id=f"proj_{i}",
            title=f"Smart Agriculture Monitoring {i}",
            rrf_score=0.032,
            shared_elements=["agriculture", "monitoring", "iot", "sensor", "crops", "raspberry pi"],
        )
        for i in range(5)
    ]
    score, level, reason = compute_evidence_novelty("Smart Agriculture Monitoring IoT System", matches)
    assert score < 0.40
    assert level == "low"
    assert "High direct overlap" in reason


def test_novelty_score_moderate_overlap() -> None:
    matches = [
        MatchInput(
            project_id="proj_01",
            title="General Plant Disease Image Dataset",
            rrf_score=0.015,
            shared_elements=["plant"],
        )
    ]
    score, level, reason = compute_evidence_novelty("Drone-based spectral plant disease diagnosis", matches)
    assert 0.40 <= score <= 0.85
    assert level in ("medium", "high")


def test_novelty_score_bounds() -> None:
    # Extreme hypothetical match
    matches = [
        MatchInput(
            project_id="proj_ext",
            title="Exact Idea Match",
            rrf_score=0.05,
            shared_elements=[f"term_{i}" for i in range(20)],
        )
        for _ in range(10)
    ]
    score, _, _ = compute_evidence_novelty("Exact idea", matches)
    assert 0.05 <= score <= 0.95
