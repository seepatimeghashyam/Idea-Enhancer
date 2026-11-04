"""Offline evaluation-workflow tests; all records and relevance grades are test-only."""

from __future__ import annotations

import asyncio
import csv
from io import StringIO
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from scripts.evaluation_workflow import (
    ANNOTATION_COLUMNS,
    build_reviewed_snapshot,
    capture_catalogue,
    complete_capture,
    load_query_catalogue,
    write_annotations,
)
from scripts.evaluate_live_search import evaluate_snapshot
from src.live_search.providers import GitHubProvider, OpenAlexProvider
from src.live_search.service import LiveSearchService


def _catalogue() -> dict[str, Any]:
    return load_query_catalogue({
        "version": 1,
        "queries": [{
            "query_id": "test-only-query",
            "query": "A test-only project for monitoring vibration in small motors",
            "slice": "industrial_automation",
            "tags": ["test-only"],
        }],
    })


def _openalex_records(count: int) -> list[dict[str, Any]]:
    return [{
        "id": f"https://openalex.org/WTEST{i}",
        "display_name": f"Test-only vibration monitoring paper {i}",
        "publication_year": 2023,
        "publication_date": "2023-01-01",
        "authorships": [],
        "primary_location": {"landing_page_url": f"https://papers.example/test-{i}", "source": {"display_name": "Test-only Journal"}},
        "open_access": {"is_oa": True},
        "cited_by_count": 0,
        "type": "article",
        "abstract_inverted_index": {"test-only": [0], "motor": [1], "vibration": [2]},
    } for i in range(count)]


def _github_records(count: int) -> list[dict[str, Any]]:
    return [{
        "id": 1000 + i,
        "full_name": f"test-only/motor-monitor-{i}",
        "description": "Test-only vibration monitor for motors",
        "html_url": f"https://github.com/test-only/motor-monitor-{i}",
        "owner": {"login": "test-only"},
        "topics": ["test-only", "monitoring"],
        "language": "Python",
        "stargazers_count": 0,
        "forks_count": 0,
        "archived": False,
        "license": {"spdx_id": "MIT"},
        "default_branch": "main",
    } for i in range(count)]


def _one_candidate_capture() -> dict[str, Any]:
    return {
        "format": "idea-enhancer-live-capture",
        "version": 1,
        "captured_at": "2026-11-04T00:00:00+00:00",
        "provenance": {"query_catalogue_sha256": "test-only-hash", "ranking_performed": False},
        "queries": [{
            "query_id": "test-only-query",
            "query": "A test-only project for monitoring vibration in small motors",
            "normalized_query": "A test-only project for monitoring vibration in small motors",
            "slice": "industrial_automation",
            "tags": ["test-only"],
            "captured_at": "2026-11-04T00:00:00+00:00",
            "providers": {
                "github": {"state": "success", "count": 1, "error_code": None, "message": None},
                "openalex": {"state": "empty", "count": 0, "error_code": None, "message": None},
            },
            "candidate_count": 1,
            "candidates": [{
                "candidate_id": "test-only-github-candidate",
                "provider_id": "repo-test-only-1",
                "source_provider": "github",
                "candidate_type": "repository",
                "title": "Test-only motor vibration monitor",
                "description": "A test-only description for motor vibration monitoring.",
                "source_url": "https://github.com/test-only/repo",
                "provider_discovery_rank": 1,
                "programming_language": "Python",
                "topics": ["test-only", "monitoring"],
                "provider_metadata": {"default_branch": "main"},
            }],
            "warnings": [],
        }],
    }


def test_capture_uses_real_adapters_and_keeps_the_full_pre_fusion_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        requests: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.host == "api.openalex.org":
                return httpx.Response(200, json={"results": _openalex_records(30)})
            assert request.url.host == "api.github.com"
            return httpx.Response(200, json={"items": _github_records(30), "total_count": 30})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = LiveSearchService(
                providers=(OpenAlexProvider(), GitHubProvider(token="test-only-never-a-real-secret")),
                client=client,
            )
            monkeypatch.setattr("src.live_search.service.rank_candidates", lambda *_a, **_kw: pytest.fail("capture must not rank"))
            capture = await capture_catalogue(_catalogue(), service)

        assert len(requests) == 2
        assert {request.url.host for request in requests} == {"api.openalex.org", "api.github.com"}
        query = capture["queries"][0]
        assert query["providers"]["openalex"]["state"] == "success"
        assert query["providers"]["github"]["state"] == "success"
        assert query["providers"]["openalex"]["count"] == 25
        assert query["providers"]["github"]["count"] == 25
        assert query["candidate_count"] == 50
        for provider in ("openalex", "github"):
            ranks = [item["provider_discovery_rank"] for item in query["candidates"] if item["source_provider"] == provider]
            assert ranks == list(range(1, 26))
        github_item = next(item for item in query["candidates"] if item["source_provider"] == "github")
        assert github_item["provider_metadata"] == {"default_branch": "main"}
        assert "test-only-never-a-real-secret" not in json.dumps(capture)
        assert capture["queries"][0]["normalized_query"] == _catalogue()["queries"][0]["query"]

    asyncio.run(scenario())


def test_capture_retains_empty_and_failed_provider_states() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.openalex.org":
                return httpx.Response(200, json={"results": []})
            return httpx.Response(503, json={"message": "test-only upstream"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = LiveSearchService(providers=(OpenAlexProvider(), GitHubProvider()), client=client)
            capture = await capture_catalogue(_catalogue(), service)
        query = capture["queries"][0]
        assert query["candidate_count"] == 0
        assert query["providers"]["openalex"]["state"] == "empty"
        assert query["providers"]["github"]["state"] == "upstream_error"
        assert query["warnings"]

    asyncio.run(scenario())


def test_annotation_export_hides_ranks_and_initializes_all_review_fields_blank() -> None:
    stream = StringIO(newline="")
    rows_written = write_annotations(_one_candidate_capture(), stream)
    stream.seek(0)
    reader = csv.DictReader(stream)
    rows = list(reader)
    assert rows_written == 1
    assert set(reader.fieldnames or []) == set(ANNOTATION_COLUMNS)
    assert rows[0]["query_id"] == "test-only-query"
    assert rows[0]["candidate_id"] == "test-only-github-candidate"
    assert rows[0]["relevance_grade"] == ""
    assert rows[0]["reviewer_rationale"] == ""
    assert rows[0]["reviewer_confidence"] == ""
    assert "rank" not in " ".join(reader.fieldnames or []).casefold()


def test_reviewed_builder_matches_ids_not_row_order_and_remains_evaluator_compatible(tmp_path: Path) -> None:
    capture = _one_candidate_capture()
    annotation_file = tmp_path / "test-only-annotations.csv"
    with annotation_file.open("w", encoding="utf-8", newline="") as stream:
        rows_written = write_annotations(capture, stream)
    assert rows_written == 1
    with annotation_file.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["relevance_grade"] = "3"
    rows[0]["reviewer_rationale"] = "Test-only rationale: clear problem and approach overlap."
    rows[0]["reviewer_confidence"] = "high"
    with annotation_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    reviewed = build_reviewed_snapshot(capture, annotation_file)
    case = reviewed["cases"][0]
    assert case["relevance_grades"] == {"test-only-github-candidate": 3}
    assert case["review_annotations"]["test-only-github-candidate"]["confidence"] == "high"
    assert case["providers"] == capture["queries"][0]["providers"]
    assert case["candidates"][0]["provider_discovery_rank"] == 1
    assert reviewed["capture_provenance"] == capture["provenance"]
    report = evaluate_snapshot(reviewed, use_dense=False)
    assert report["reviewed_candidate_count"] == 1
    assert report["label_distribution"] == {"0": 0, "1": 0, "2": 0, "3": 1}
    assert report["provider_summary"]["github"]["state_counts"]["success"] == 1
    assert "github" in report["cases"][0]["provider_native_metrics"]


@pytest.mark.parametrize(
    "grade, message",
    [("", "needs an integer grade"), ("4", "needs an integer grade"), ("1.0", "needs an integer grade")],
)
def test_reviewed_builder_rejects_missing_or_invalid_grades(tmp_path: Path, grade: str, message: str) -> None:
    capture = _one_candidate_capture()
    path = tmp_path / "test-only-annotations.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        write_annotations(capture, stream)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["relevance_grade"] = grade
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match=message):
        build_reviewed_snapshot(capture, path)


def test_reviewed_builder_rejects_incomplete_duplicate_and_unknown_annotations(tmp_path: Path) -> None:
    capture = _one_candidate_capture()
    path = tmp_path / "test-only-annotations.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
    with pytest.raises(ValueError, match="Incomplete annotations.*test-only-github-candidate"):
        build_reviewed_snapshot(capture, path)

    def write_rows(rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=ANNOTATION_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    with path.open("w", encoding="utf-8", newline="") as stream:
        write_annotations(capture, stream)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    row["relevance_grade"] = "2"
    write_rows([row, row.copy()])
    with pytest.raises(ValueError, match="Duplicate annotation"):
        build_reviewed_snapshot(capture, path)
    unknown = row.copy()
    unknown["candidate_id"] = "test-only-unknown"
    write_rows([unknown])
    with pytest.raises(ValueError, match="unknown candidate"):
        build_reviewed_snapshot(capture, path)


def test_reviewed_builder_rejects_edited_annotation_context(tmp_path: Path) -> None:
    capture = _one_candidate_capture()
    path = tmp_path / "test-only-edited-context.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerow({
            "query_id": "test-only-query", "query": capture["queries"][0]["query"],
            "slice": "industrial_automation", "candidate_id": "test-only-github-candidate",
            "candidate_type": "repository", "title": "Edited title", "description": "A test-only description for motor vibration monitoring.",
            "source_url": "https://github.com/test-only/repo", "source_provider": "github",
            "relevance_grade": "2", "reviewer_rationale": "Test-only", "reviewer_confidence": "medium",
        })
    with pytest.raises(ValueError, match="display fields do not match"):
        build_reviewed_snapshot(capture, path)


def test_capture_validator_rejects_nested_credential_metadata() -> None:
    capture = _one_candidate_capture()
    capture["queries"][0]["candidates"][0]["provider_metadata"] = {"details": {"api_key": "test-only-secret"}}
    with pytest.raises(ValueError, match="credential-like key"):
        complete_capture(capture)


def test_capture_validator_rejects_duplicate_ids_and_bad_rank() -> None:
    value = _one_candidate_capture()
    duplicate = value["queries"][0]["candidates"][0].copy()
    value["queries"][0]["candidates"].append(duplicate)
    value["queries"][0]["candidate_count"] = 2
    with pytest.raises(ValueError, match="duplicate candidate_id"):
        complete_capture(value)

    invalid_rank = _one_candidate_capture()
    invalid_rank["queries"][0]["candidates"][0]["provider_discovery_rank"] = 0
    with pytest.raises(ValueError, match="discovery rank"):
        complete_capture(invalid_rank)


def test_capture_validator_preserves_native_rank_gaps_after_identity_deduplication() -> None:
    value = _one_candidate_capture()
    value["queries"][0]["candidates"].append({
        **value["queries"][0]["candidates"][0],
        "candidate_id": "test-only-github-candidate-2",
        "provider_id": "repo-test-only-2",
        "provider_discovery_rank": 3,
    })
    value["queries"][0]["candidate_count"] = 2
    value["queries"][0]["providers"]["github"]["count"] = 2
    complete_capture(value)


def test_catalogue_rejects_invalid_slice_and_duplicate_query_ids() -> None:
    value = _catalogue()
    value["queries"].append(value["queries"][0].copy())
    with pytest.raises(ValueError, match="Duplicate query_id"):
        load_query_catalogue(value)
    invalid = _catalogue()
    invalid["queries"][0]["slice"] = "made-up"
    with pytest.raises(ValueError, match="unsupported evaluation slice"):
        load_query_catalogue(invalid)


def test_evaluator_reports_only_bm25_when_dense_is_disabled_and_excludes_no_relevant_cases() -> None:
    snapshot = {
        "version": 1,
        "cases": [
            {
                "id": "test-only-fallback", "slice": "iot_embedded", "query": "A test-only motor monitoring query",
                "candidates": [{"candidate_id": "test-only-c1", "candidate_type": "repository", "source_provider": "github", "title": "Test-only motor sensor"}],
                "relevance_grades": {"test-only-c1": 3},
            },
            {
                "id": "test-only-no-relevant", "slice": "iot_embedded", "query": "A test-only empty relevance query",
                "candidates": [{"candidate_id": "test-only-c2", "candidate_type": "paper", "source_provider": "openalex", "title": "Unrelated test-only topic"}],
                "relevance_grades": {"test-only-c2": 0},
            },
        ],
    }
    report = evaluate_snapshot(snapshot, use_dense=False)
    first, second = report["cases"]
    assert first["metrics"].keys() == {"bm25"}
    assert first["rankings"]["hybrid_rrf"] is None
    assert report["dense_evaluation"]["state_counts"]["disabled"] == 2
    assert report["slice_summary"]["iot_embedded"]["query_count"] == 2
    assert report["slice_summary"]["iot_embedded"]["aggregate_comparable_query_count"] == 1
    assert report["excluded_cases"][0]["id"] == second["id"]


def test_evaluator_rejects_duplicate_case_ids_invalid_slices_and_bad_provider_ranks() -> None:
    case = {
        "id": "test-only-case", "query": "A test-only query for evaluation",
        "candidates": [{"candidate_id": "test-only-c1", "candidate_type": "paper", "source_provider": "openalex", "title": "Test-only paper", "provider_discovery_rank": 0}],
        "relevance_grades": {"test-only-c1": 1},
    }
    with pytest.raises(ValueError, match="provider_discovery_rank"):
        evaluate_snapshot({"version": 1, "cases": [case]}, use_dense=False)
    case["candidates"][0]["provider_discovery_rank"] = 1
    with pytest.raises(ValueError, match="unsupported evaluation slice"):
        evaluate_snapshot({"version": 1, "cases": [{**case, "slice": "not-a-slice"}]}, use_dense=False)
    with pytest.raises(ValueError, match="Duplicate case id"):
        evaluate_snapshot({"version": 1, "cases": [case, case.copy()]}, use_dense=False)


def test_provider_native_order_uses_discovery_rank_not_capture_file_order() -> None:
    snapshot = {
        "version": 1,
        "cases": [{
            "id": "test-only-ranks", "slice": "repository", "query": "A test-only query for rank ordering",
            "candidates": [
                {"candidate_id": "test-only-late", "candidate_type": "repository", "source_provider": "github", "title": "Late candidate", "provider_discovery_rank": 2},
                {"candidate_id": "test-only-early", "candidate_type": "repository", "source_provider": "github", "title": "Early candidate", "provider_discovery_rank": 1},
            ],
            "relevance_grades": {"test-only-late": 0, "test-only-early": 3},
        }],
    }
    result = evaluate_snapshot(snapshot, use_dense=False)["cases"][0]
    assert result["provider_native_rankings"]["github"] == ["test-only-early", "test-only-late"]


def test_provider_native_missing_ranks_and_failed_providers_are_explicitly_excluded() -> None:
    snapshot = {
        "version": 1,
        "cases": [{
            "id": "test-only-provider-status", "query": "A test-only query for providers",
            "providers": {
                "github": {"state": "success", "count": 1},
                "openalex": {"state": "upstream_error", "count": 0},
            },
            "candidates": [{"candidate_id": "test-only-c1", "candidate_type": "repository", "source_provider": "github", "title": "Test-only candidate"}],
            "relevance_grades": {"test-only-c1": 1},
        }],
    }
    case = evaluate_snapshot(snapshot, use_dense=False)["cases"][0]
    assert case["provider_native_metrics"] == {}
    assert {item["method"] for item in case["excluded_methods"]} == {
        "provider_native:github", "provider_native:openalex",
    }
    assert case["limitations"] == ["openalex: upstream_error"]


def test_evaluator_reports_dense_and_hybrid_only_when_dense_really_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    class TestOnlyEncoder:
        def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
            if query:
                return [[1.0, 0.0] for _ in texts]
            return [[1.0, 0.0] if "semantic-first" in text else [0.0, 1.0] for text in texts]

    monkeypatch.setattr("scripts.evaluate_live_search.SentenceTransformerEncoder", TestOnlyEncoder)
    snapshot = {
        "version": 1,
        "cases": [{
            "id": "test-only-dense", "query": "vibration sensor motor monitoring",
            "candidates": [
                {"candidate_id": "test-only-semantic", "candidate_type": "repository", "source_provider": "github", "title": "semantic-first project"},
                {"candidate_id": "test-only-keyword", "candidate_type": "repository", "source_provider": "github", "title": "vibration sensor motor monitoring"},
            ],
            "relevance_grades": {"test-only-semantic": 3, "test-only-keyword": 0},
        }],
    }
    result = evaluate_snapshot(snapshot)["cases"][0]
    assert result["dense_available"] is True
    assert set(result["metrics"]) == {"bm25", "dense", "hybrid_rrf"}
    assert result["rankings"]["dense"][0] == "test-only-semantic"


def test_evaluator_omits_dense_and_hybrid_metrics_when_dense_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class TestOnlyFailingEncoder:
        def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
            raise RuntimeError("test-only unavailable model")

    monkeypatch.setattr("scripts.evaluate_live_search.SentenceTransformerEncoder", TestOnlyFailingEncoder)
    snapshot = {
        "version": 1,
        "cases": [{
            "id": "test-only-dense-failure", "query": "test-only vibration sensor query",
            "candidates": [{"candidate_id": "test-only-c1", "candidate_type": "paper", "source_provider": "openalex", "title": "vibration sensor study"}],
            "relevance_grades": {"test-only-c1": 2},
        }],
    }
    report = evaluate_snapshot(snapshot)
    case = report["cases"][0]
    assert case["dense_state"] == "fallback_bm25"
    assert set(case["metrics"]) == {"bm25"}
    assert case["rankings"]["dense"] is None
    assert case["rankings"]["hybrid_rrf"] is None
