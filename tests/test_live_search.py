"""Offline, deterministic tests for live research integrations (all records are test-only)."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys
import threading
import time
from typing import Sequence
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.live_search.contracts import CandidateRecord, ProviderResult
from src.live_search.http import MAX_PROVIDER_RESPONSE_BYTES, _retry_after_seconds
from src.live_search.providers import GitHubProvider, OpenAlexProvider, _safe_url, reconstruct_abstract
from src.live_search.retrieval import DenseUnavailable, _rrf_fuse, rank_candidates
from src.live_search.service import LiveSearchService, LiveSearchUnavailable
from src.main import create_app, configured_cors_origins


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


def test_external_url_validation_rejects_unsafe_or_malformed_hosts() -> None:
    assert _safe_url("https://publisher.example/paper") == "https://publisher.example/paper"
    for value in (
        "http://publisher.example/paper",
        "https://user:pass@publisher.example/paper",
        "https://bad host/paper",
        "https://localhost/private",
        "https://127.0.0.1/private",
        "https://publisher.example:99999/paper",
        "https://publisher.example\\@evil.example/path",
        "https://[broken/paper",
    ):
        assert _safe_url(value) is None


def test_openalex_provider_maps_paper_fields_and_preserves_unknowns() -> None:
    payload = {
        "results": [{
            "id": "https://openalex.org/W123", "doi": "https://doi.org/10.1234/test",
            "display_name": "Test-only vibration monitoring paper", "publication_year": 2022,
            "publication_date": "2022-05-01", "authorships": [{"author": {"display_name": "Test Author"}}],
            "best_oa_location": ["unexpected nested value"],
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


def test_github_forbidden_response_with_retry_after_is_classified_as_rate_limit() -> None:
    async def scenario() -> None:
        attempts = 0

        async def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(403, headers={"Retry-After": "0"}, json={"message": "test-only"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await GitHubProvider().search("test-only query", client, 2)
        assert result.state == "rate_limited"
        assert attempts == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status,headers",
    [
        (401, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"}),
        (403, {"X-RateLimit-Reset": "9999999999"}),
    ],
)
def test_github_auth_failures_are_not_misclassified_from_reset_header(status: int, headers: dict[str, str]) -> None:
    async def scenario() -> None:
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, headers=headers, json={"message": "test-only"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await GitHubProvider().search("test-only query", client, 2)
        assert result.state == "authentication_error"

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


def test_http_boundary_rejects_redirects_and_oversized_responses() -> None:
    async def scenario() -> None:
        redirect_attempts = 0

        async def redirect_handler(_request: httpx.Request) -> httpx.Response:
            nonlocal redirect_attempts
            redirect_attempts += 1
            return httpx.Response(302, headers={"Location": "http://127.0.0.1:1/private"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(redirect_handler)) as client:
            redirect = await OpenAlexProvider().search("test-only redirect query", client, 1)
        assert redirect_attempts == 1
        assert redirect.state == "upstream_error"
        assert redirect.error_code == "unexpected_redirect"

        async def large_handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"Content-Length": str(MAX_PROVIDER_RESPONSE_BYTES + 1)}, content=b"{}")

        async with httpx.AsyncClient(transport=httpx.MockTransport(large_handler)) as client:
            large = await OpenAlexProvider().search("test-only large response", client, 1)
        assert large.state == "invalid_response"
        assert large.error_code == "response_too_large"

    asyncio.run(scenario())


def test_retry_after_supports_seconds_dates_and_bounded_fallback() -> None:
    assert _retry_after_seconds("500") == 1.0
    assert _retry_after_seconds("0") == 0.0
    assert _retry_after_seconds("not a date") == 0.25
    assert 0.0 <= _retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT") <= 1.0


def test_sentence_transformer_cache_loads_once_and_serializes_shared_inference() -> None:
    from src import embeddings

    counters = {"loads": 0, "active": 0, "max_active": 0}
    counter_lock = threading.Lock()

    class FakeModel:
        def __init__(self, _name: str, device: str = "cpu") -> None:
            assert device == "cpu"
            with counter_lock:
                counters["loads"] += 1

        def encode(self, _texts: Sequence[str]) -> list[list[float]]:
            with counter_lock:
                counters["active"] += 1
                counters["max_active"] = max(counters["max_active"], counters["active"])
            time.sleep(0.01)
            with counter_lock:
                counters["active"] -= 1
            return [[1.0, 0.0]]

    fake_module = type(sys)("sentence_transformers")
    fake_module.SentenceTransformer = FakeModel
    with patch.dict(sys.modules, {"sentence_transformers": fake_module}):
        with patch.dict(embeddings._models, {}, clear=True):
            with ThreadPoolExecutor(max_workers=8) as pool:
                models = list(pool.map(lambda _: embeddings.get_sentence_transformer("test-only/concurrent", "cpu"), range(8)))
            assert len({id(model) for model in models}) == 1
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda model: model.encode(["test-only text"]), models))
            assert counters == {"loads": 1, "active": 0, "max_active": 1}


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


def test_rrf_fusion_handles_missing_ranks_with_the_standard_formula() -> None:
    ordered, scores = _rrf_fuse({"test-only-both": 1, "test-only-bm25": 2}, {"test-only-both": 2, "test-only-vector": 1}, 3)
    assert ordered == ["test-only-both", "test-only-vector", "test-only-bm25"]
    assert scores["test-only-both"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["test-only-bm25"] == pytest.approx(1 / 62)
    assert scores["test-only-vector"] == pytest.approx(1 / 61)
    assert len(_rrf_fuse({"test-only-a": 1, "test-only-b": 2}, {}, 1)[0]) == 1


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


def test_dense_failure_remains_degraded_when_bm25_has_no_match() -> None:
    class FailingEncoder:
        def encode(self, _texts: Sequence[str], *, query: bool = False) -> Sequence[Sequence[float]]:
            raise DenseUnavailable("test-only injected encoder failure")

    unrelated = candidate("test-only-unrelated", "Music playlist manager", "Organizes audio tracks")
    service = LiveSearchService(
        providers=(FixedProvider("openalex", ProviderResult("openalex", "success", (unrelated,))), FixedProvider("github")),
        encoder=FailingEncoder(),
    )
    response = asyncio.run(service.search("A detailed query about greenhouse humidity monitoring", 5))
    assert response.state == "degraded"
    assert response.ranking_mode == "bm25_only"
    assert not response.matches


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
    assert item["provider_discovery_rank"] == 1
    assert "verification_status" not in item
    assert item["shared_elements"]


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


def test_service_deduplicates_candidates_by_provider_identity_and_rejects_id_collisions() -> None:
    record = candidate("test-only-duplicate", "Vibration monitor", "IoT motor monitor")

    async def scenario() -> None:
        duplicate_service = LiveSearchService(
            providers=(FixedProvider("openalex", ProviderResult("openalex", "success", (record, record))), FixedProvider("github")),
            encoder=FakeEncoder(),
        )
        deduplicated = await duplicate_service.search("IoT motor vibration monitor", 5)
        assert deduplicated.providers["openalex"]["count"] == 1
        assert len(deduplicated.matches) == 1

        collision = CandidateRecord(
            candidate_id=record.candidate_id, source_provider="openalex", provider_id="different-provider-id",
            candidate_type="paper", title="Conflicting record", description=None, source_url=None,
        )
        collision_service = LiveSearchService(
            providers=(FixedProvider("openalex", ProviderResult("openalex", "success", (record, collision))), FixedProvider("github")),
            encoder=FakeEncoder(),
        )
        rejected = await collision_service.search("IoT motor vibration monitor", 5)
        assert rejected.state == "partial"
        assert rejected.providers["openalex"]["state"] == "upstream_error"
        assert not rejected.matches

    asyncio.run(scenario())


def test_service_bounds_concurrent_provider_searches() -> None:
    counters = {"active": 0, "peak": 0}

    class TrackingProvider:
        def __init__(self, name: str) -> None:
            self.name = name

        async def search(self, _idea: str, _client: httpx.AsyncClient, _limit: int) -> ProviderResult:
            counters["active"] += 1
            counters["peak"] = max(counters["peak"], counters["active"])
            try:
                await asyncio.sleep(0.01)
                return ProviderResult(self.name, "empty")
            finally:
                counters["active"] -= 1

    service = LiveSearchService(providers=(TrackingProvider("openalex"), TrackingProvider("github")), encoder=FakeEncoder())

    async def scenario() -> None:
        results = await asyncio.gather(*(service.search("An empty test-only candidate query", 5) for _ in range(10)))
        assert all(result.state == "no_candidates" for result in results)

    asyncio.run(scenario())
    assert counters["peak"] == 2 * 4


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


def test_cors_accepts_local_and_explicit_https_origins_but_rejects_other_sites(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://demo.example.edu")
    app = create_app(live_search_service=LiveSearchService(providers=()))
    client = TestClient(app)
    headers = {"Origin": "https://demo.example.edu", "Access-Control-Request-Method": "POST"}
    allowed = client.options("/live-search", headers=headers)
    assert allowed.headers["access-control-allow-origin"] == "https://demo.example.edu"

    denied = client.options("/live-search", headers={
        "Origin": "https://unlisted.example", "Access-Control-Request-Method": "POST",
    })
    assert "access-control-allow-origin" not in denied.headers
    assert "http://localhost:5500" in configured_cors_origins()


def test_cors_rejects_wildcards_paths_and_insecure_remote_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("*", "https://demo.example.edu/path", "http://demo.example.edu"):
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", value)
        with pytest.raises(ValueError, match="Invalid CORS origin"):
            configured_cors_origins()
