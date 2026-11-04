"""Offline, deterministic tests for live research integrations (all records are test-only)."""

from __future__ import annotations

import asyncio
from typing import Sequence

import httpx
import pytest
from fastapi.testclient import TestClient

from src.live_search.contracts import CandidateRecord, ProviderResult
from src.live_search.providers import GitHubProvider, OpenAlexProvider, reconstruct_abstract
from src.live_search.retrieval import DenseUnavailable, rank_candidates
from src.live_search.service import LiveSearchService, LiveSearchUnavailable
from src.main import create_app


def candidate(candidate_id: str, title: str, description: str, *, kind: str = "paper", topics: tuple[str, ...] = ()) -> CandidateRecord:
    """Create clearly synthetic records for tests; never used in production search."""
    return CandidateRecord(
        candidate_id=candidate_id,
        source_provider="openalex" if kind == "paper" else "github",
        provider_id=f"test-only:{candidate_id}",
        candidate_type=kind,  # type: ignore[arg-type]
        title=title, description=description,
        source_url=f"https://example.invalid/test-only/{candidate_id}",
        topics=topics,
    )


class FakeEncoder:
    """Deterministic synthetic embedder; no model or network access."""

    def encode(self, texts: Sequence[str], *, query: bool = False) -> Sequence[Sequence[float]]:
        return [[1.0, 0.0] if "vibration" in text.casefold() or query else [0.0, 1.0] for text in texts]


class FixedProvider:
    def __init__(self, name: str, result: ProviderResult | None = None, error: Exception | None = None) -> None:
        self.name = name
        self.result = result or ProviderResult(name, "empty")
        self.error = error

    async def search(self, _idea: str, _client: httpx.AsyncClient, _limit: int) -> ProviderResult:
        if self.error:
            raise self.error
        return self.result


def test_reconstruct_abstract_orders_tokens_by_position_and_ignores_invalid_values() -> None:
    assert reconstruct_abstract({"system": [2], "A": [0], "works": [1], "ignored": [-1, "x"]}) == "A works system"
    assert reconstruct_abstract(None) is None


def test_openalex_provider_maps_paper_fields_and_preserves_unknowns() -> None:
    payload = {
        "results": [{
            "id": "https://openalex.org/W123", "doi": "https://doi.org/10.1234/test",
            "display_name": "Test-only vibration monitoring paper", "publication_year": 2022,
            "publication_date": "2022-05-01", "authorships": [{"author": {"display_name": "Test Author"}}],
            "primary_location": {"landing_page_url": "https://publisher.example/paper", "source": {"display_name": "Test Journal"}},
            "open_access": {"is_oa": True}, "cited_by_count": 4, "type": "article",
            "abstract_inverted_index": {"Monitoring": [0], "vibration": [1], "systems": [2]},
        }]}

    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["per-page"] == "5"
            return httpx.Response(200, json=payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await OpenAlexProvider().search("vibration monitoring", client, 5)
        assert result.state == "success"
        paper = result.candidates[0]
        assert paper.description == "Monitoring vibration systems"
        assert paper.authors == ("Test Author",)
        assert paper.publication_year == 2022
        assert paper.work_type == "article"
        assert paper.venue == "Test Journal"
        assert paper.open_access is True
        assert paper.citation_count == 4
        assert paper.source_url == "https://publisher.example/paper"
        assert paper.repository_created_at is None
        assert paper.owner is None

    asyncio.run(scenario())


def test_github_provider_maps_repository_metadata_without_conflating_dates() -> None:
    payload = {"items": [{
        "id": 987, "full_name": "test-only/monitoring", "description": "Synthetic vibration monitor",
        "html_url": "https://github.com/test-only/monitoring", "owner": {"login": "test-only"},
        "language": "Python", "topics": ["iot", "maintenance"], "created_at": "2020-01-02T00:00:00Z",
        "pushed_at": "2024-02-03T00:00:00Z", "stargazers_count": 10, "forks_count": 2,
        "archived": False, "license": {"spdx_id": "MIT"},
    }]}

    async def scenario() -> None:
        seen_headers: list[str | None] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.append(request.headers.get("authorization"))
            return httpx.Response(200, json=payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await GitHubProvider(token="test-token-never-a-real-secret").search("vibration monitor", client, 4)
        repo = result.candidates[0]
        assert seen_headers == ["Bearer test-token-never-a-real-secret"]
        assert repo.source_url == "https://github.com/test-only/monitoring"
        assert repo.owner == "test-only"
        assert repo.programming_language == "Python"
        assert repo.topics == ("iot", "maintenance")
        assert repo.repository_created_at.startswith("2020")
        assert repo.repository_pushed_at.startswith("2024")
        assert repo.publication_date is None
        assert repo.stars == 10 and repo.forks == 2 and repo.archived is False
        assert repo.license_name == "MIT"

    asyncio.run(scenario())


@pytest.mark.parametrize("status, expected", [(429, "rate_limited"), (401, "authentication_error"), (503, "upstream_error")])
def test_provider_failures_are_classified_without_becoming_empty_successes(status: int, expected: str) -> None:
    async def scenario() -> None:
        async def handler(_request: httpx.Request) -> httpx.Response:
            headers = {"X-RateLimit-Remaining": "0"} if status == 429 else {}
            return httpx.Response(status, headers=headers, json={"message": "test-only provider response"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await OpenAlexProvider().search("test-only query", client, 3)
        assert result.state == expected
        assert result.candidates == ()
        assert result.error_code is not None

    asyncio.run(scenario())


def test_provider_rejects_malformed_payload_and_unsafe_http_links() -> None:
    payload = {"results": [{"id": "https://openalex.org/W1", "display_name": "test only", "best_oa_location": {"landing_page_url": "http://unsafe.example"}}]}

    async def scenario() -> None:
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await OpenAlexProvider().search("test only", client, 1)
        assert result.candidates[0].source_url is None

    asyncio.run(scenario())


def test_provider_timeout_retries_once_and_malformed_json_is_not_empty_success() -> None:
    async def timeout_scenario() -> None:
        attempts = 0

        async def timeout_handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise httpx.ReadTimeout("test-only timeout")

        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler)) as client:
            result = await OpenAlexProvider().search("test-only timeout query", client, 2)
        assert attempts == 2
        assert result.state == "timeout"
        assert result.error_code == "timeout"
        assert not result.candidates

    async def malformed_scenario() -> None:
        async def malformed_handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not-json")

        async with httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler)) as client:
            result = await OpenAlexProvider().search("test-only malformed query", client, 2)
        assert result.state == "invalid_response"
        assert result.error_code == "invalid_json"
        assert not result.candidates

    asyncio.run(timeout_scenario())
    asyncio.run(malformed_scenario())


def test_real_bm25_dense_and_rrf_rank_test_only_candidates_deterministically() -> None:
    both = candidate("test-only-both", "Vibration motor maintenance", "IoT sensors detect vibration faults")
    lexical_only = candidate("test-only-lexical", "Vibration sensor monitor", "Predictive fault alerts", kind="repository")
    semantic_only = candidate("test-only-semantic", "Crop disease imaging", "Plant leaf classification")
    ranked, dense_available, warning = rank_candidates(
        "IoT vibration sensors for predictive maintenance of motor faults",
        [both, lexical_only, semantic_only], encoder=FakeEncoder(), top_k=3,
    )
    assert dense_available is True and warning is None
    assert len({match.candidate.candidate_id for match in ranked}) == 3
    assert [match.rank for match in ranked] == [1, 2, 3]
    assert ranked[0].candidate.candidate_id == both.candidate_id
    assert ranked[0].bm25_rank is not None and ranked[0].dense_rank is not None
    assert ranked[0].rrf_score == pytest.approx(1 / (60 + ranked[0].bm25_rank) + 1 / (60 + ranked[0].dense_rank))
    assert ranked[0].shared_concepts
    assert "keyword rank" in ranked[0].explanation and "semantic rank" in ranked[0].explanation


def test_dense_failure_returns_explicit_bm25_only_results() -> None:
    class FailingEncoder:
        def encode(self, _texts: Sequence[str], *, query: bool = False) -> Sequence[Sequence[float]]:
            raise DenseUnavailable("test-only injected encoder failure")

    record = candidate("test-only-bm25", "Vibration sensor", "Motor fault monitoring")
    ranked, dense_available, warning = rank_candidates("vibration sensor motor", [record], encoder=FailingEncoder(), top_k=3)
    assert not dense_available
    assert warning and "keyword ranking only" in warning
    assert len(ranked) == 1
    assert ranked[0].bm25_rank == 1
    assert ranked[0].dense_rank is None
    assert ranked[0].semantic_similarity is None


def test_live_service_reports_complete_partial_empty_and_all_unavailable_states() -> None:
    first = candidate("test-only-paper", "Vibration monitoring", "IoT motor sensor maintenance")
    second = candidate("test-only-repo", "Vibration sensor tool", "Motor maintenance", kind="repository")

    async def scenario() -> None:
        full = LiveSearchService(
            providers=(
                FixedProvider("openalex", ProviderResult("openalex", "success", (first,))),
                FixedProvider("github", ProviderResult("github", "success", (second,))),
            ), encoder=FakeEncoder(),
        )
        complete = await full.search("IoT vibration monitoring system", 5)
        assert complete.state == "complete"
        assert complete.ranking_mode == "hybrid_rrf"
        assert complete.providers["openalex"]["count"] == 1

        partial = LiveSearchService(
            providers=(FixedProvider("openalex", ProviderResult("openalex", "success", (first,))), FixedProvider("github", error=RuntimeError("test only"))),
            encoder=FakeEncoder(),
        )
        partial_result = await partial.search("IoT vibration monitoring system", 5)
        assert partial_result.state == "partial"
        assert partial_result.providers["github"]["state"] == "upstream_error"
        assert partial_result.matches

        empty = LiveSearchService(providers=(FixedProvider("openalex"), FixedProvider("github")), encoder=FakeEncoder())
        assert (await empty.search("A test only empty search", 5)).state == "no_candidates"

        unavailable = LiveSearchService(
            providers=(FixedProvider("openalex", error=RuntimeError()), FixedProvider("github", error=RuntimeError())),
            encoder=FakeEncoder(),
        )
        with pytest.raises(LiveSearchUnavailable):
            await unavailable.search("No fallback to test records", 5)

    asyncio.run(scenario())


def test_live_api_uses_injected_test_providers_and_returns_traceable_candidate_fields() -> None:
    record = candidate("test-only-api", "Vibration motor fault research", "IoT sensors monitor vibration")
    service = LiveSearchService(
        providers=(FixedProvider("openalex", ProviderResult("openalex", "success", (record,))), FixedProvider("github")),
        encoder=FakeEncoder(),
    )
    client = TestClient(create_app(live_search_service=service))
    response = client.post("/live-search", json={"idea": "IoT vibration motor fault monitoring", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success" and data["search_state"] == "complete"
    assert data["result_count"] == 1
    item = data["matches"][0]
    assert item["candidate_id"] == "test-only-api"
    assert item["source_type"] == "research_paper"
    assert item["source_url"].startswith("https://")
    assert item["description_excerpt"] == record.description
    assert "provider_metadata" not in item


def test_live_service_reports_partial_when_one_source_fails_and_the_other_is_empty() -> None:
    service = LiveSearchService(
        providers=(FixedProvider("openalex"), FixedProvider("github", error=RuntimeError("test only"))),
        encoder=FakeEncoder(),
    )
    outcome = asyncio.run(service.search("An empty result from the working source", 5))
    assert outcome.state == "partial"
    assert not outcome.matches
    assert outcome.providers["openalex"]["state"] == "empty"
    assert outcome.providers["github"]["state"] == "upstream_error"


def test_live_api_distinguishes_validation_and_unavailable_from_empty_success() -> None:
    service = LiveSearchService(
        providers=(FixedProvider("openalex", error=RuntimeError("test only")), FixedProvider("github", error=RuntimeError("test only"))),
        encoder=FakeEncoder(),
    )
    client = TestClient(create_app(live_search_service=service))
    invalid = client.post("/live-search", json={"idea": "short"})
    assert invalid.status_code == 422
    unavailable = client.post("/live-search", json={"idea": "A valid enough test query"})
    assert unavailable.status_code == 503
    assert unavailable.json()["error_code"] == "LIVE_SEARCH_UNAVAILABLE"
    assert "test only" not in unavailable.text
