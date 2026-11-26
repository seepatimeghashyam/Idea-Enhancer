"""Tests for grounding validator and citation enforcement."""

from src.enhance.contracts import MatchInput
from src.enhance.validator import sanitize_grounded_response


def test_validator_removes_hallucinated_citations() -> None:
    matches = [
        MatchInput(project_id="real_01", title="Real Project 1"),
        MatchInput(project_id="real_02", title="Real Project 2"),
    ]

    raw_payload = {
        "suggestions": [
            {
                "title": "Edge Inference",
                "description": "Quantize models.",
                # Cites real_01 and fake_hallucinated_99
                "cites": ["real_01", "fake_hallucinated_99"],
            },
            {
                "title": "Mesh Protocol",
                "description": "Add mesh radio.",
                # Cites only hallucinated project
                "cites": ["imaginary_project_xyz"],
            },
            {
                "title": "Sensor Calibration",
                "description": "Improve accuracy.",
                "cites": [],
            },
        ],
        "facet_map": {
            "problem": {
                "overlap": "strong",
                "matched_project_ids": ["real_01", "fake_hallucinated_99"],
            }
        },
    }

    sanitized = sanitize_grounded_response(
        raw_payload=raw_payload,
        matches=matches,
        computed_novelty_score=0.55,
        computed_novelty_level="medium",
        computed_novelty_reason="Reason test",
    )

    # First suggestion should retain only real_01
    assert sanitized["suggestions"][0]["cites"] == ["real_01"]

    # Second suggestion should have fake citation removed and fallback to top valid ID (real_01)
    assert sanitized["suggestions"][1]["cites"] == ["real_01"]

    # Facet matched_project_ids should have fake ID stripped
    assert sanitized["facet_map"]["problem"]["matched_project_ids"] == ["real_01"]

    # Novelty score should match the computed score exactly
    assert sanitized["novelty"]["score"] == 0.55
    assert sanitized["novelty"]["level"] == "medium"


def test_validator_enforces_suggestion_count() -> None:
    matches = [MatchInput(project_id="real_01", title="Real Project 1")]

    # Payload with only 1 suggestion
    raw_payload = {
        "suggestions": [
            {"title": "Only One Suggestion", "description": "Desc", "cites": ["real_01"]}
        ]
    }

    sanitized = sanitize_grounded_response(
        raw_payload=raw_payload,
        matches=matches,
        computed_novelty_score=0.70,
        computed_novelty_level="high",
        computed_novelty_reason="Reason test",
    )

    # Must be augmented to at least 3 suggestions
    assert 3 <= len(sanitized["suggestions"]) <= 5
    for s in sanitized["suggestions"]:
        assert s["cites"] == ["real_01"]


def test_validator_handles_zero_matches() -> None:
    # When zero matches exist, citations should remain empty without crashing
    sanitized = sanitize_grounded_response(
        raw_payload={"suggestions": []},
        matches=[],
        computed_novelty_score=0.95,
        computed_novelty_level="high",
        computed_novelty_reason="No matches found.",
    )
    assert len(sanitized["suggestions"]) == 3
    for s in sanitized["suggestions"]:
        assert s["cites"] == []
    for facet in sanitized["facet_map"].values():
        assert facet["matched_project_ids"] == []
