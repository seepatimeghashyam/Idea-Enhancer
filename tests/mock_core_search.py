"""MOCK ONLY: test doubles and fixtures; these are not indexed project records."""

from __future__ import annotations

from dataclasses import dataclass

from src.search_gateway import CoreSearchUnavailable, SearchOutcome


MOCK_MATCH = {
    "project_id": "mock_001",
    "title": "MOCK: Crop Monitoring Concept",
    "abstract": "MOCK ONLY: a record used to test API response formatting.",
    "tech_stack": "Raspberry Pi, Python",
    "source_type": "mock_fixture",
    "source_url": None,
    "year": None,
    "domain": "IoT",
    "rank": 1,
    "bm25_rank": 1,
    "vector_rank": 2,
    "rrf_score": 0.0323,
    "shared_elements": ["Raspberry Pi"],
    "verification_status": "checked",
}


@dataclass
class MockCoreSearchGateway:
    """MOCK ONLY: configurable stand-in for the future Core Search handoff."""

    outcome: SearchOutcome = SearchOutcome(matches=(MOCK_MATCH,))
    error: Exception | None = None
    calls: list[tuple[str, int]] | None = None

    def search(self, idea: str, top_k: int) -> SearchOutcome:
        if self.calls is not None:
            self.calls.append((idea, top_k))
        if self.error is not None:
            raise self.error
        return self.outcome


def unavailable_core() -> MockCoreSearchGateway:
    """MOCK ONLY: represent a not-ready Core Search service."""

    return MockCoreSearchGateway(error=CoreSearchUnavailable("MOCK: search index is unavailable."))
