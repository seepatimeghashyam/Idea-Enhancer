"""Tests for enhance data contracts and Pydantic validation."""

import pytest
from pydantic import ValidationError
from src.enhance.contracts import (
    EnhanceRequest,
    EnhanceResponse,
    FacetDetail,
    FacetMap,
    FeasibilityRating,
    MatchInput,
    NoveltyAssessment,
    SuggestionItem,
    TechStackItem,
)


def test_enhance_request_valid() -> None:
    req = EnhanceRequest(
        idea="A smart autonomous greenhouse monitoring robot",
        matches=[
            MatchInput(
                project_id="proj_01",
                title="Greenhouse Robot",
                technologies=["Arduino", "ROS"],
                shared_elements=["greenhouse"],
            )
        ],
        evidence_scope="local",
    )
    assert req.idea == "A smart autonomous greenhouse monitoring robot"
    assert len(req.matches) == 1
    assert req.matches[0].project_id == "proj_01"
    assert req.evidence_scope == "local"


def test_enhance_request_rejects_too_short() -> None:
    with pytest.raises(ValidationError):
        EnhanceRequest(idea="short", matches=[])


def test_enhance_request_rejects_too_long() -> None:
    with pytest.raises(ValidationError):
        EnhanceRequest(idea="x" * 2001, matches=[])


def test_enhance_request_rejects_more_than_5_matches() -> None:
    matches = [MatchInput(project_id=f"p_{i}", title=f"Title {i}") for i in range(8)]
    with pytest.raises(ValidationError):
        EnhanceRequest(idea="A valid length proposal text for test", matches=matches)


def test_match_input_rejects_oversized_title() -> None:
    with pytest.raises(ValidationError):
        MatchInput(project_id="p1", title="x" * 301)


def test_match_input_rejects_oversized_excerpt() -> None:
    with pytest.raises(ValidationError):
        MatchInput(project_id="p1", title="Title", description_excerpt="x" * 2001)


def test_match_input_rejects_oversized_technologies() -> None:
    with pytest.raises(ValidationError):
        MatchInput(project_id="p1", title="Title", technologies=["x" * 61])

    with pytest.raises(ValidationError):
        MatchInput(project_id="p1", title="Title", technologies=[f"tech_{i}" for i in range(21)])


def test_novelty_assessment_unknown_level() -> None:
    nov = NoveltyAssessment(level="unknown", score=None, reason="No matches found in corpus.")
    assert nov.level == "unknown"
    assert nov.score is None


def test_enhance_response_structure_with_warnings() -> None:
    resp = EnhanceResponse(
        idea="A smart greenhouse monitoring robot",
        overlap_summary="Some overlap found.",
        facet_map=FacetMap(
            problem=FacetDetail(overlap="partial", details="Both monitor crops."),
            domain=FacetDetail(overlap="strong", details="AgriTech."),
            method=FacetDetail(overlap="partial", details="Autonomous navigation."),
            tech_stack=FacetDetail(overlap="none", details="Different stacks."),
            data=FacetDetail(overlap="none", details="No shared datasets."),
        ),
        novelty=NoveltyAssessment(level="medium", score=0.55, reason="Viable novel features."),
        suggestions=[SuggestionItem(title="T", description="D", cites=["p1"])],
        suggested_tech_stack=[TechStackItem(name="N", role="R")],
        feasibility=FeasibilityRating(rating=4, reasons=["Accessible hardware"]),
        warnings=["Fewer than 3 grounded suggestions were produced."],
    )
    assert resp.status == "success"
    assert resp.novelty.level == "medium"
    assert resp.cached is False
    assert len(resp.warnings) == 1
