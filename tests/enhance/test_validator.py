"""Tests for grounding validator and citation enforcement."""

import pytest
from src.enhance.contracts import MatchInput
from src.enhance.llm_client import LLMBadResponseError
from src.enhance.validator import sanitize_grounded_response


def test_validator_drops_invented_ids_without_substitution() -> None:
    matches = [
        MatchInput(project_id="real_01", title="Real Project 1", rank=1),
        MatchInput(project_id="real_02", title="Real Project 2", rank=2),
    ]

    raw_payload = {
        "overlap_summary": "Overlap summary text.",
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
                # Cites ONLY hallucinated project -> must be DROPPED!
                "cites": ["imaginary_project_xyz"],
            },
            {
                "title": "Sensor Calibration",
                "description": "Improve accuracy using real_02 sensors.",
                # No cites array, but real_02 is in description -> legitimate cite
                "cites": [],
            },
        ],
        "facet_map": {
            "problem": {
                "overlap": "strong",
                "details": "Details here.",
                "matched_project_ids": ["real_01", "fake_hallucinated_99"],
            },
            "domain": {
                "overlap": "partial",
                "details": "Details here.",
                # Claimed partial, but ONLY fake ID -> must downgrade to none with []
                "matched_project_ids": ["fake_only_id"],
            },
            "method": {"overlap": "none", "details": "None", "matched_project_ids": []},
            "tech_stack": {"overlap": "none", "details": "None", "matched_project_ids": []},
            "data": {"overlap": "none", "details": "None", "matched_project_ids": []},
        },
        "novelty": {"reason": "Reason from model"},
        "suggested_tech_stack": [{"name": "TFLite", "role": "Inference"}],
        "feasibility": {"rating": 4, "reasons": ["Student budget friendly"]},
    }

    sanitized, warnings = sanitize_grounded_response(
        raw_payload=raw_payload,
        matches=matches,
        computed_novelty_score=0.55,
        computed_novelty_level="medium",
        computed_novelty_reason="Reason test",
    )

    # 1. Suggestion with mixed cites should retain ONLY real_01
    assert sanitized["suggestions"][0]["cites"] == ["real_01"]

    # 2. Suggestion with only imaginary_project_xyz must be DROPPED entirely!
    # Suggestion 3 citing real_02 via text becomes the 2nd suggestion
    assert len(sanitized["suggestions"]) == 2
    assert sanitized["suggestions"][1]["cites"] == ["real_02"]

    # Since only 2 valid suggestions remain, warning must be emitted
    assert "Fewer than 3 grounded suggestions were produced." in warnings

    # 3. Facet problem strips fake ID
    assert sanitized["facet_map"]["problem"]["matched_project_ids"] == ["real_01"]
    assert sanitized["facet_map"]["problem"]["overlap"] == "strong"

    # 4. Facet domain with no valid ID must be downgraded to 'none' and []
    assert sanitized["facet_map"]["domain"]["overlap"] == "none"
    assert sanitized["facet_map"]["domain"]["matched_project_ids"] == []


def test_validator_raises_when_zero_valid_suggestions_remain() -> None:
    matches = [MatchInput(project_id="real_01", title="Real Project 1")]
    raw_payload = {
        "overlap_summary": "Overlap summary text.",
        "suggestions": [
            # Cites only non-existent ID
            {"title": "Invented", "description": "Desc", "cites": ["FAKE_ID"]}
        ],
        "facet_map": {
            "problem": {"overlap": "none", "details": "d", "matched_project_ids": []},
            "domain": {"overlap": "none", "details": "d", "matched_project_ids": []},
            "method": {"overlap": "none", "details": "d", "matched_project_ids": []},
            "tech_stack": {"overlap": "none", "details": "d", "matched_project_ids": []},
            "data": {"overlap": "none", "details": "d", "matched_project_ids": []},
        },
        "novelty": {"reason": "Reason"},
        "suggested_tech_stack": [{"name": "T", "role": "R"}],
        "feasibility": {"rating": 4, "reasons": ["R"]},
    }

    with pytest.raises(LLMBadResponseError) as exc_info:
        sanitize_grounded_response(
            raw_payload=raw_payload,
            matches=matches,
            computed_novelty_score=0.5,
            computed_novelty_level="medium",
            computed_novelty_reason="Reason",
        )
    assert "No grounded suggestions" in str(exc_info.value)


def test_validator_raises_on_missing_required_keys() -> None:
    matches = [MatchInput(project_id="real_01", title="Real Project 1")]

    # Missing overlap_summary
    with pytest.raises(LLMBadResponseError):
        sanitize_grounded_response(
            raw_payload={"suggestions": []},
            matches=matches,
            computed_novelty_score=0.5,
            computed_novelty_level="medium",
            computed_novelty_reason="Reason",
        )

    # Missing one of the 5 facets
    payload_missing_facet = {
        "overlap_summary": "Summary",
        "facet_map": {
            "problem": {"overlap": "none", "details": "d", "matched_project_ids": []},
            # missing domain, method, tech_stack, data
        },
        "novelty": {"reason": "R"},
        "suggestions": [{"title": "T", "description": "D", "cites": ["real_01"]}],
        "suggested_tech_stack": [{"name": "T", "role": "R"}],
        "feasibility": {"rating": 4, "reasons": ["R"]},
    }
    with pytest.raises(LLMBadResponseError):
        sanitize_grounded_response(
            raw_payload=payload_missing_facet,
            matches=matches,
            computed_novelty_score=0.5,
            computed_novelty_level="medium",
            computed_novelty_reason="Reason",
        )
