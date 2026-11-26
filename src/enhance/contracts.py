"""Data contracts and schemas for POST /enhance."""

from __future__ import annotations

from typing import Any, List, Literal, Optional
try:
    from pydantic import BaseModel, Field, field_validator
except ImportError:
    # Fallback shim if pydantic is not installed yet
    class BaseModel:  # type: ignore[no-redef]
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self) -> dict[str, Any]:
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

        def model_dump(self) -> dict[str, Any]:
            return self.dict()

    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return kwargs.get("default", kwargs.get("default_factory", lambda: None)()) if "default" in kwargs or "default_factory" in kwargs else None

    def field_validator(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        def decorator(fn: Any) -> Any:
            return fn
        return decorator


class MatchInput(BaseModel):
    """A single project match retrieved from search."""

    project_id: str
    title: str
    description_excerpt: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    year: Optional[int] = None
    domain: Optional[str] = None
    technologies: Optional[List[str]] = None
    rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    rrf_score: Optional[float] = None
    shared_elements: Optional[List[str]] = None
    verification_status: Optional[str] = None


class EnhanceRequest(BaseModel):
    """Public payload for POST /enhance."""

    idea: str = Field(..., description="Student project proposal text (10-2000 chars)")
    matches: List[MatchInput] = Field(default_factory=list, description="Top retrieved matches")

    @field_validator("idea")
    @classmethod
    def validate_idea_length(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 10:
            raise ValueError("The 'idea' field must contain at least 10 characters.")
        if len(trimmed) > 2000:
            raise ValueError("The 'idea' field must contain at most 2000 characters.")
        return trimmed


class FacetDetail(BaseModel):
    """Overlap assessment for a single conceptual facet."""

    overlap: Literal["none", "partial", "strong"] = "none"
    details: str
    matched_project_ids: List[str] = Field(default_factory=list)


class FacetMap(BaseModel):
    """Multi-dimensional overlap map."""

    problem: FacetDetail
    domain: FacetDetail
    method: FacetDetail
    tech_stack: FacetDetail
    data: FacetDetail


class NoveltyAssessment(BaseModel):
    """Evidence-grounded novelty evaluation."""

    level: Literal["low", "medium", "high"]
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str


class SuggestionItem(BaseModel):
    """Actionable improvement suggestion with traceable citations."""

    title: str
    description: str
    cites: List[str] = Field(default_factory=list, description="List of cited match project IDs")


class TechStackItem(BaseModel):
    """Recommended architectural technology with role."""

    name: str
    role: str


class FeasibilityRating(BaseModel):
    """Student feasibility estimation."""

    rating: int = Field(..., ge=1, le=5)
    reasons: List[str] = Field(default_factory=list)


class EnhanceResponse(BaseModel):
    """Public response envelope for POST /enhance."""

    status: str = "success"
    idea: str
    overlap_summary: str
    facet_map: FacetMap
    novelty: NoveltyAssessment
    suggestions: List[SuggestionItem]
    suggested_tech_stack: List[TechStackItem]
    feasibility: FeasibilityRating
    cached: bool = False
