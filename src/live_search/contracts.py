"""Provider-neutral data contracts for live research search."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


ProviderState = Literal[
    "success", "empty", "timeout", "rate_limited", "authentication_error",
    "configuration_error", "invalid_response", "network_error", "upstream_error",
]
SearchState = Literal["complete", "partial", "degraded", "no_candidates", "unavailable"]
CandidateType = Literal["paper", "repository"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class CandidateRecord:
    """Normalized paper or repository record; absent source fields remain None."""

    candidate_id: str
    source_provider: str
    provider_id: str
    candidate_type: CandidateType
    title: str
    description: str | None
    source_url: str | None
    doi: str | None = None
    authors: tuple[str, ...] = ()
    owner: str | None = None
    publication_date: str | None = None
    publication_year: int | None = None
    work_type: str | None = None
    repository_created_at: str | None = None
    repository_pushed_at: str | None = None
    venue: str | None = None
    programming_language: str | None = None
    topics: tuple[str, ...] = ()
    stars: int | None = None
    forks: int | None = None
    open_access: bool | None = None
    citation_count: int | None = None
    archived: bool | None = None
    license_name: str | None = None
    retrieved_at: str = field(default_factory=utc_now)
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def searchable_text(self) -> str:
        """Stable retrieval text; title and description receive intentional weight."""
        fields = [self.title, self.title, self.title, self.description, self.description]
        fields.extend(self.topics)
        fields.extend((self.programming_language, self.venue))
        return " ".join(value.strip() for value in fields if value and value.strip())

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if value["description"]:
            value["description"] = value["description"][:4000]
        value["authors"] = list(self.authors)
        value["topics"] = list(self.topics)
        discovery_rank = self.provider_metadata.get("discovery_rank")
        if isinstance(discovery_rank, int) and not isinstance(discovery_rank, bool) and discovery_rank > 0:
            value["provider_discovery_rank"] = discovery_rank
        value.pop("provider_metadata", None)
        return value


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider: str
    state: ProviderState
    candidates: tuple[CandidateRecord, ...] = ()
    error_code: str | None = None
    message: str | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "count": len(self.candidates),
            "error_code": self.error_code,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    candidate: CandidateRecord
    rank: int
    bm25_rank: int | None
    dense_rank: int | None
    rrf_score: float
    semantic_similarity: float | None
    shared_concepts: tuple[str, ...]
    distinctive_terms: tuple[str, ...]
    explanation: str

    def public_dict(self) -> dict[str, Any]:
        result = self.candidate.public_dict()
        result.update({
            "rank": self.rank,
            "bm25_rank": self.bm25_rank,
            "dense_rank": self.dense_rank,
            "rrf_score": self.rrf_score,
            "semantic_similarity": self.semantic_similarity,
            "shared_concepts": list(self.shared_concepts),
            "distinctive_terms": list(self.distinctive_terms),
            "explanation": self.explanation,
        })
        return result
