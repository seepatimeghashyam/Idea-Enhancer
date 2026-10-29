"""Tests for the concrete CoreSearchGateway adapter."""

from __future__ import annotations

import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.main import NO_MATCH_MESSAGE, create_app
from src.search_gateway import (
    CoreSearchGateway,
    CoreSearchUnavailable,
    SearchOutcome,
)


class FakeDatabaseCoreSearchUnavailable(RuntimeError):
    """Simulates src.database.CoreSearchUnavailable without importing src.database."""


FakeDatabaseCoreSearchUnavailable.__name__ = "CoreSearchUnavailable"


SAMPLE_PROJECT: dict[str, Any] = {
    "project_id": "proj_101",
    "title": "Autonomous Drone Fleet Coordinator",
    "abstract": "A distributed system for controlling swarms of inspection drones in GPS-denied environments.",
    "tech_stack": "Python, ROS2, C++, PyTorch",
    "source_type": "open_source",
    "source_url": "https://github.com/example/drone-fleet",
    "year": 2023,
    "domain": "Robotics",
    "rank": 1,
    "bm25_rank": 2,
    "vector_rank": 1,
    "rrf_score": 0.0328,
    "shared_elements": ["ROS2", "PyTorch"],
    "verification_status": "verified",
}


def test_gateway_wraps_result_list_in_search_outcome() -> None:
    calls: list[tuple[str, int]] = []

    def fake_search(idea: str, top_k: int) -> list[dict[str, Any]]:
        calls.append((idea, top_k))
        return [SAMPLE_PROJECT]

    gateway = CoreSearchGateway(search_fn=fake_search)
    outcome = gateway.search("Autonomous drone coordination", 3)

    assert isinstance(outcome, SearchOutcome)
    assert len(outcome.matches) == 1
    assert outcome.matches[0]["project_id"] == "proj_101"
    assert outcome.warnings == ()
    assert calls == [("Autonomous drone coordination", 3)]


def test_gateway_preserves_successful_empty_results() -> None:
    def fake_search(_idea: str, _top_k: int) -> list[dict[str, Any]]:
        return []

    gateway = CoreSearchGateway(search_fn=fake_search)
    outcome = gateway.search("Nonexistent futuristic idea", 5)

    assert isinstance(outcome, SearchOutcome)
    assert list(outcome.matches) == []
    assert outcome.warnings == ()

    # Also verify through the API endpoint
    client = TestClient(create_app(gateway))
    response = client.post("/search", json={"idea": "Nonexistent futuristic idea", "top_k": 5})

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "query": "Nonexistent futuristic idea",
        "result_count": 0,
        "matches": [],
        "message": NO_MATCH_MESSAGE,
        "warnings": [],
    }


def test_gateway_translates_database_core_search_unavailable_exception() -> None:
    def unavailable_search(_idea: str, _top_k: int) -> list[dict[str, Any]]:
        raise FakeDatabaseCoreSearchUnavailable("Vector index has not been built yet.")

    gateway = CoreSearchGateway(search_fn=unavailable_search)

    with pytest.raises(CoreSearchUnavailable) as exc_info:
        gateway.search("A valid project query", 5)

    assert "Vector index has not been built yet." in str(exc_info.value)

    # Also verify API returns 503 SEARCH_UNAVAILABLE error envelope
    client = TestClient(create_app(gateway))
    response = client.post("/search", json={"idea": "A valid project query"})

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "error_code": "SEARCH_UNAVAILABLE",
        "message": "Vector index has not been built yet.",
        "details": None,
    }


def test_gateway_preserves_canonical_fields_without_fabricated_metadata() -> None:
    def fake_search(_idea: str, _top_k: int) -> list[dict[str, Any]]:
        return [dict(SAMPLE_PROJECT)]

    gateway = CoreSearchGateway(search_fn=fake_search)
    client = TestClient(create_app(gateway))

    response = client.post("/search", json={"idea": "Autonomous drone inspection swarm", "top_k": 1})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result_count"] == 1
    match = data["matches"][0]

    assert match["project_id"] == "proj_101"
    assert match["title"] == "Autonomous Drone Fleet Coordinator"
    assert match["description_excerpt"] == SAMPLE_PROJECT["abstract"]
    assert match["technologies"] == ["Python", "ROS2", "C++", "PyTorch"]
    assert match["source_type"] == "open_source"
    assert match["source_url"] == "https://github.com/example/drone-fleet"
    assert match["year"] == 2023
    assert match["domain"] == "Robotics"
    assert match["rank"] == 1
    assert match["bm25_rank"] == 2
    assert match["vector_rank"] == 1
    assert match["rrf_score"] == 0.0328
    assert match["shared_elements"] == ["ROS2", "PyTorch"]
    assert match["verification_status"] == "verified"

    # Confirm raw internal fields are not leaked directly
    assert "abstract" not in match
    assert "tech_stack" not in match


def test_gateway_lazy_import_does_not_load_facade_on_instantiation() -> None:
    # Instantiating the gateway without an injected search function must not
    # eagerly call or resolve the search_projects function.
    gateway = CoreSearchGateway()
    assert gateway._search_fn is None


def test_app_maintains_request_validation_and_error_envelopes() -> None:
    def fake_search(_idea: str, _top_k: int) -> list[dict[str, Any]]:
        return [SAMPLE_PROJECT]

    client = TestClient(create_app(CoreSearchGateway(search_fn=fake_search)))

    # Missing request body -> 422 VALIDATION_ERROR
    res_missing_body = client.post("/search")
    assert res_missing_body.status_code == 422
    assert res_missing_body.json()["error_code"] == "VALIDATION_ERROR"

    # Query too short -> 422 VALIDATION_ERROR
    res_short = client.post("/search", json={"idea": "short"})
    assert res_short.status_code == 422
    assert res_short.json()["error_code"] == "VALIDATION_ERROR"

    # Query too long -> 422 VALIDATION_ERROR
    res_long = client.post("/search", json={"idea": "A" * 2001})
    assert res_long.status_code == 422
    assert res_long.json()["error_code"] == "VALIDATION_ERROR"

    # Invalid top_k -> 422 VALIDATION_ERROR
    res_bad_top_k = client.post("/search", json={"idea": "Valid project search idea", "top_k": "five"})
    assert res_bad_top_k.status_code == 422
    assert res_bad_top_k.json()["error_code"] == "VALIDATION_ERROR"

    # Clamped top_k -> 200 with warning
    res_clamp = client.post("/search", json={"idea": "Valid project search idea", "top_k": 50})
    assert res_clamp.status_code == 200
    assert "top_k was clamped to 20." in res_clamp.json()["warnings"]
