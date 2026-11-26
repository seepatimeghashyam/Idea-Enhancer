"""Data contracts and schemas for POST /enhance."""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class MatchInput(BaseModel):
    """A single project match retrieved from search."""

    project_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(..., min_length=1, max_length=300)
    description_excerpt: Optional[str] = Field(default=None, max_length=2000)
    source_type: Optional[str] = Field(default=None, max_length=100)
    source_url: Optional[str] = Field(default=None, max_length=1000)
    year: Optional[int] = None
    domain: Optional[str] = Field(default=None, max_length=200)
    technologies: Optional[List[str]] = None
    rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    rrf_score: Optional[float] = None
    shared_elements: Optional[List[str]] = None
    verification_status: Optional[str] = Field(default=None, max_length=50)

    @field_validator("technologies", "shared_elements")
    @classmethod
    def validate_string_list(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        if len(v) > 20:
            raise ValueError("List must contain at most 20 items.")
        for item in v:
            if not isinstance(item, str) or len(item) > 60:
                raise ValueError("List items must be strings of at most 60 characters.")
        return v


class EnhanceRequest(BaseModel):
    """Public payload for POST /enhance."""

    idea: str = Field(..., description="Student project proposal text (10-2000 chars)")
    matches: List[MatchInput] = Field(default_factory=list, max_length=5, description="Top retrieved matches (max 5)")
    evidence_scope: Literal["local", "local+online"] = Field(default="local", description="Scope of searched corpus")

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

    level: Literal["low", "medium", "high", "unknown"]
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
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
    warnings: List[str] = Field(default_factory=list)
