"""Public request and response contracts for evidence grounded enhancement."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EnhanceRequest(BaseModel):
    idea: str = Field(min_length=10, max_length=2000)
    scope: Literal["local", "online"] = "local"
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("idea")
    @classmethod
    def trim_idea(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 10:
            raise ValueError("The idea must contain at least 10 characters.")
        return value


class Facet(BaseModel):
    overlap: Literal["none", "partial", "strong"]
    details: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)


class Recommendation(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    implementation: str = Field(min_length=1, max_length=500)
    tradeoff: str = Field(min_length=1, max_length=300)
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)
    basis: Literal["retrieved_evidence", "general_advice"]


class EnhanceResponse(BaseModel):
    status: Literal["success", "partial"]
    idea: str
    scope: Literal["local", "online"]
    coverage: str
    overlap_summary: str
    facets: dict[str, Facet]
    recommendations: list[Recommendation]
    evidence: list[dict]
    warnings: list[str] = Field(default_factory=list)
