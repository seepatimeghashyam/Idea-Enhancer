"""Tests for enhance data contracts."""

try:
    import pytest
except ImportError:
    class _RaisesContext:
        def __init__(self, expected_exc):
            self.expected_exc = expected_exc
            self.value = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                raise AssertionError(f"Expected {self.expected_exc.__name__} was not raised")
            if not issubclass(exc_type, self.expected_exc):
                return False
            self.value = exc_val
            return True

    class _MockPytest:
        @staticmethod
        def raises(expected_exc):
            return _RaisesContext(expected_exc)

    pytest = _MockPytest()  # type: ignore[assignment]
from pydantic import ValidationError
from src.enhance.contracts import EnhanceRequest, MatchInput, EnhanceResponse, FacetMap, FacetDetail, NoveltyAssessment, FeasibilityRating


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
    )
    assert req.idea == "A smart autonomous greenhouse monitoring robot"
    assert len(req.matches) == 1
    assert req.matches[0].project_id == "proj_01"


def test_enhance_request_rejects_too_short() -> None:
    with pytest.raises(ValidationError):
        EnhanceRequest(idea="short", matches=[])


def test_enhance_request_rejects_too_long() -> None:
    with pytest.raises(ValidationError):
        EnhanceRequest(idea="x" * 2001, matches=[])


def test_enhance_response_structure() -> None:
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
        suggestions=[],
        suggested_tech_stack=[],
        feasibility=FeasibilityRating(rating=4, reasons=["Accessible hardware"]),
    )
    assert resp.status == "success"
    assert resp.novelty.level == "medium"
    assert resp.cached is False
