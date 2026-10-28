"""Tests for the committed POST /search API contract."""

from fastapi.testclient import TestClient

from src.main import NO_MATCH_MESSAGE, create_app
from src.search_gateway import SearchOutcome
from tests.mock_core_search import MOCK_MATCH, MockCoreSearchGateway, unavailable_core


def test_search_returns_contract_response_and_calls_core_with_normalized_input() -> None:
    calls: list[tuple[str, int]] = []
    client = TestClient(create_app(MockCoreSearchGateway(calls=calls)))

    response = client.post("/search", json={"idea": "  Crop disease monitoring system  ", "top_k": 5})

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "query": "Crop disease monitoring system",
        "result_count": 1,
        "matches": [
            {
                "project_id": "mock_001",
                "title": "MOCK: Crop Monitoring Concept",
                "description_excerpt": MOCK_MATCH["abstract"],
                "source_type": "mock_fixture",
                "source_url": None,
                "year": None,
                "domain": "IoT",
                "technologies": ["Raspberry Pi", "Python"],
                "rank": 1,
                "bm25_rank": 1,
                "vector_rank": 2,
                "rrf_score": 0.0323,
                "shared_elements": ["Raspberry Pi"],
                "verification_status": "checked",
            }
        ],
        "message": None,
        "warnings": [],
    }
    assert "abstract" not in response.json()["matches"][0]
    assert "tech_stack" not in response.json()["matches"][0]
    assert calls == [("Crop disease monitoring system", 5)]


def test_search_rejects_too_short_ideas_using_error_envelope() -> None:
    client = TestClient(create_app(MockCoreSearchGateway()))

    response = client.post("/search", json={"idea": " short "})

    assert response.status_code == 422
    assert response.json() == {
        "status": "error",
        "error_code": "VALIDATION_ERROR",
        "message": "The 'idea' field must contain at least 10 characters.",
        "details": {"field": "idea", "constraint": "min_length", "min_length": 10, "actual_length": 5},
    }


def test_search_returns_no_match_message_for_empty_core_results() -> None:
    gateway = MockCoreSearchGateway(outcome=SearchOutcome(matches=()))
    client = TestClient(create_app(gateway))

    response = client.post("/search", json={"idea": "A novel robotics project"})

    assert response.status_code == 200
    assert response.json()["matches"] == []
    assert response.json()["result_count"] == 0
    assert response.json()["message"] == NO_MATCH_MESSAGE


def test_search_clamps_top_k_and_reports_a_warning() -> None:
    calls: list[tuple[str, int]] = []
    client = TestClient(create_app(MockCoreSearchGateway(calls=calls)))

    response = client.post("/search", json={"idea": "A novel robotics project", "top_k": 99})

    assert response.status_code == 200
    assert response.json()["warnings"] == ["top_k was clamped to 20."]
    assert calls == [("A novel robotics project", 20)]


def test_search_returns_service_error_when_core_is_unavailable() -> None:
    client = TestClient(create_app(unavailable_core()))

    response = client.post("/search", json={"idea": "A novel robotics project"})

    assert response.status_code == 503
    assert response.json()["error_code"] == "SEARCH_UNAVAILABLE"
    assert response.json()["details"] is None


def test_search_returns_safe_error_when_core_fails_unexpectedly() -> None:
    client = TestClient(create_app(MockCoreSearchGateway(error=RuntimeError("MOCK: unexpected failure"))))

    response = client.post("/search", json={"idea": "A novel robotics project"})

    assert response.status_code == 500
    assert response.json() == {
        "status": "error",
        "error_code": "SEARCH_FAILED",
        "message": "An internal error occurred while processing the search. Please try again.",
        "details": None,
    }


def test_search_allows_the_local_frontend_to_make_a_cors_preflight_request() -> None:
    client = TestClient(create_app(MockCoreSearchGateway()))

    response = client.options(
        "/search",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"
    assert "POST" in response.headers["access-control-allow-methods"]
