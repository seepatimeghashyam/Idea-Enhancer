"""FastAPI router integration tests for POST /enhance."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.enhance.cache import EnhanceCache
from src.enhance.llm_client import FakeLLMClient
from src.enhance.service import EnhanceService
from src.enhance_router import enhance_router, set_enhance_service


def create_test_app(service: EnhanceService) -> TestClient:
    app = FastAPI()
    app.include_router(enhance_router)
    set_enhance_service(service)
    return TestClient(app)


def test_enhance_endpoint_success() -> None:
    service = EnhanceService(
        llm_client=FakeLLMClient(),
        cache=EnhanceCache(),
    )
    client = create_test_app(service)

    payload = {
        "idea": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
        "matches": [
            {
                "project_id": "rvce_042",
                "title": "Smart Crop Monitoring System",
                "description_excerpt": "Crop disease monitoring via CNN",
                "technologies": ["Raspberry Pi", "CNN"],
                "rrf_score": 0.032,
                "shared_elements": ["Raspberry Pi", "CNN"],
            }
        ],
    }

    response = client.post("/enhance", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["idea"] == payload["idea"]
    assert "facet_map" in data
    assert "problem" in data["facet_map"]
    assert "novelty" in data
    assert 0.0 <= data["novelty"]["score"] <= 1.0
    assert data["novelty"]["level"] in ("low", "medium", "high")
    assert 3 <= len(data["suggestions"]) <= 5
    assert data["cached"] is False

    # Second call with identical payload must be served from cache
    cached_resp = client.post("/enhance", json=payload)
    assert cached_resp.status_code == 200
    cached_data = cached_resp.json()
    assert cached_data["cached"] is True


def test_enhance_validation_error_too_short() -> None:
    service = EnhanceService(llm_client=FakeLLMClient())
    client = create_test_app(service)

    response = client.post("/enhance", json={"idea": "Short", "matches": []})
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "VALIDATION_ERROR"


def test_enhance_llm_timeout_handling() -> None:
    service = EnhanceService(
        llm_client=FakeLLMClient(raise_timeout=True),
        cache=EnhanceCache(),
    )
    client = create_test_app(service)

    payload = {
        "idea": "Autonomous drone navigation for disaster relief in collapsed structures",
        "matches": [],
    }
    response = client.post("/enhance", json=payload)
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "LLM_TIMEOUT"


def test_enhance_llm_unavailable_handling() -> None:
    service = EnhanceService(
        llm_client=FakeLLMClient(raise_unavailable=True, error_message="Gemini quota exhausted"),
        cache=EnhanceCache(),
    )
    client = create_test_app(service)

    payload = {
        "idea": "Autonomous drone navigation for disaster relief in collapsed structures",
        "matches": [],
    }
    response = client.post("/enhance", json=payload)
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "error"
    assert data["error_code"] == "LLM_UNAVAILABLE"


def test_enhance_with_zero_matches() -> None:
    service = EnhanceService(
        llm_client=FakeLLMClient(),
        cache=EnhanceCache(),
    )
    client = create_test_app(service)

    payload = {
        "idea": "Sub-surface quantum gravimeter for planetary geological surveys",
        "matches": [],
    }
    response = client.post("/enhance", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["novelty"]["level"] == "high"
    assert data["novelty"]["score"] >= 0.90
