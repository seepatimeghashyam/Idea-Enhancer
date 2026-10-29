"""Small shared types used by the Core Search retrievers and orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


VerificationStatus = Literal["checked", "unchecked", "insufficient"]


@dataclass(frozen=True, slots=True)
class ProjectRecord:
    """One canonical project row. Optional source metadata stays unknown as None."""

    project_id: str
    title: str
    abstract: str
    tech_stack: str | None
    domain: str | None
    source_type: str
    source_url: str | None
    year: int | None


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    """A project identifier and its 1-based position in one retriever's ranking."""

    project_id: str
    rank: int


class Retriever(Protocol):
    """Shared method each independent retrieval module must implement."""

    def search(self, query: str, top_k: int) -> list[RetrievalHit]:
        """Return at most ``top_k`` hits, ordered by rank (1-based)."""


@dataclass(frozen=True, slots=True)
class SearchMatch:
    """Canonical project plus fused ranking and conservative evidence fields."""

    project: ProjectRecord
    rank: int
    bm25_rank: int | None
    vector_rank: int | None
    rrf_score: float
    shared_elements: list[str]
    verification_status: VerificationStatus


def build_search_text(record: ProjectRecord) -> str:
    """Build identical retrieval content from title, abstract, stack, and domain."""

    fields = (record.title, record.abstract, record.tech_stack, record.domain)
    return " ".join(value.strip() for value in fields if value and value.strip())
