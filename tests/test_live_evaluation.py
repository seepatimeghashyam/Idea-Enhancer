"""Metric and snapshot tests use invented, explicitly test-only relevance labels."""

from __future__ import annotations

import pytest

from scripts.evaluate_live_search import evaluate_snapshot
from src.live_search.evaluation import ndcg_at_k, precision_at_k, recall_at_k, mrr_at_k


def test_retrieval_metrics_respect_relevance_grades_and_cutoffs() -> None:
    grades = {"test-only-a": 3, "test-only-b": 1, "test-only-c": 0}
    ranking = ["test-only-c", "test-only-a", "test-only-b"]
    assert precision_at_k(ranking, grades, 2) == 0.5
    assert recall_at_k(ranking, grades, 2) == 0.5
    assert mrr_at_k(ranking, grades, 10) == 0.5
    assert 0 < ndcg_at_k(ranking, grades, 10) < 1


def test_snapshot_evaluator_reports_methods_slices_and_discovery_recall_without_network() -> None:
    snapshot = {
        "version": 1,
        "cases": [{
            "id": "test-only-case", "slice": "repository",
            "query": "IoT vibration sensor fault monitoring",
            "candidates": [
                {"candidate_id": "test-only-relevant", "candidate_type": "repository", "source_provider": "github", "provider_id": "test-only-1", "title": "Vibration monitoring", "description": "IoT sensor fault" , "provider_discovery_rank": 1},
                {"candidate_id": "test-only-other", "candidate_type": "repository", "source_provider": "github", "provider_id": "test-only-2", "title": "Music archive", "description": "Audio playlists", "provider_discovery_rank": 2},
            ],
            "relevance_grades": {"test-only-relevant": 3, "test-only-other": 0},
            "known_relevant_ids": ["test-only-relevant"],
        }],
    }
    report = evaluate_snapshot(snapshot, use_dense=False)
    assert report["case_count"] == 1
    assert report["mean_discovery_recall"] == 1.0
    assert set(report["cases"][0]["metrics"]) == {"bm25"}
    assert report["cases"][0]["provider_native_rankings"] == {
        "github": ["test-only-relevant", "test-only-other"]
    }
    assert "github" in report["cases"][0]["provider_native_metrics"]
    assert report["cases"][0]["rankings"]["dense"] is None
    assert report["cases"][0]["rankings"]["hybrid_rrf"] is None
    assert report["cases"][0]["dense_state"] == "disabled"
    assert "fixed snapshot only" in report["interpretation"]


def test_snapshot_evaluator_rejects_unlabelled_or_invalid_grade_values() -> None:
    with pytest.raises(ValueError, match="relevance_grades"):
        evaluate_snapshot({"version": 1, "cases": [{"query": "test only query", "candidates": []}]}, use_dense=False)

    with pytest.raises(ValueError, match="grades 0..3"):
        evaluate_snapshot({"version": 1, "cases": [{"query": "test only query", "candidates": [], "relevance_grades": {"x": 4}}]}, use_dense=False)


def test_provider_native_recall_counts_relevant_candidates_missed_by_that_provider() -> None:
    snapshot = {
        "version": 1,
        "cases": [{
            "query": "test-only vibration monitor",
            "candidates": [
                {"candidate_id": "test-only-github-hit", "candidate_type": "repository", "source_provider": "github", "title": "Vibration monitor", "provider_discovery_rank": 1},
                {"candidate_id": "test-only-openalex-missed", "candidate_type": "paper", "source_provider": "openalex", "title": "Vibration monitoring study", "provider_discovery_rank": 1},
            ],
            "relevance_grades": {"test-only-github-hit": 3, "test-only-openalex-missed": 3},
        }],
    }
    result = evaluate_snapshot(snapshot, use_dense=False)["cases"][0]
    assert result["provider_native_metrics"]["github"]["recall_at_10"] == 0.5
    assert result["provider_native_metrics"]["openalex"]["recall_at_10"] == 0.5


def test_snapshot_evaluator_requires_complete_labels_and_unique_ids() -> None:
    candidate_record = {
        "candidate_id": "test-only-duplicate", "candidate_type": "paper",
        "source_provider": "openalex", "title": "test-only title",
    }
    with pytest.raises(ValueError, match="needs a reviewed relevance grade"):
        evaluate_snapshot({"version": 1, "cases": [{
            "query": "test-only query", "candidates": [candidate_record], "relevance_grades": {},
        }]}, use_dense=False)

    with pytest.raises(ValueError, match="Duplicate candidate_id"):
        evaluate_snapshot({"version": 1, "cases": [{
            "query": "test-only query", "candidates": [candidate_record, candidate_record],
            "relevance_grades": {"test-only-duplicate": 1},
        }]}, use_dense=False)


def test_snapshot_evaluator_rejects_malformed_known_relevant_ids() -> None:
    with pytest.raises(ValueError, match="known_relevant_ids must be an array"):
        evaluate_snapshot({"version": 1, "cases": [{
            "query": "test-only query", "candidates": [], "relevance_grades": {},
            "known_relevant_ids": "test-only-id",
        }]}, use_dense=False)
