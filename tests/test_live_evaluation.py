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
    assert set(report["cases"][0]["metrics"]) == {"bm25", "dense", "hybrid_rrf"}
    assert report["cases"][0]["provider_native_rankings"] == {
        "github": ["test-only-relevant", "test-only-other"]
    }
    assert "github" in report["cases"][0]["provider_native_metrics"]
    assert report["cases"][0]["rankings"]["dense"] == []
    assert report["cases"][0]["rankings"]["hybrid_rrf"] == report["cases"][0]["rankings"]["bm25"]
    assert "fixed snapshot only" in report["interpretation"]


def test_snapshot_evaluator_rejects_unlabelled_or_invalid_grade_values() -> None:
    with pytest.raises(ValueError, match="relevance_grades"):
        evaluate_snapshot({"version": 1, "cases": [{"query": "test only query", "candidates": []}]}, use_dense=False)

    with pytest.raises(ValueError, match="grades 0..3"):
        evaluate_snapshot({"version": 1, "cases": [{"query": "test only query", "candidates": [], "relevance_grades": {"x": 4}}]}, use_dense=False)
