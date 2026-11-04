"""Evaluate live-search rankers against a reviewed, fixed candidate snapshot.

Snapshot relevance labels are human inputs. This tool never creates labels or
contacts providers. See docs/LIVE_SEARCH.md for the version-1 JSON schema.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.live_search.contracts import CandidateRecord
from src.live_search.evaluation import ranking_metrics
from src.live_search.retrieval import SentenceTransformerEncoder, rank_candidates


def evaluate_snapshot(snapshot: dict[str, Any], *, use_dense: bool = True) -> dict[str, Any]:
    cases = snapshot.get("cases")
    if snapshot.get("version") != 1 or not isinstance(cases, list) or not cases:
        raise ValueError("Snapshot must have version=1 and a cases array.")
    encoder = SentenceTransformerEncoder() if use_dense else None
    case_outputs = []
    slice_totals: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    slice_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    discovery_values: list[float] = []

    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("candidates"), list):
            raise ValueError("Each case must contain a candidates array.")
        query = case.get("query")
        if not isinstance(query, str) or not 10 <= len(query.strip()) <= 2000:
            raise ValueError("Each case query must contain 10 to 2000 characters after trimming.")
        if len(case["candidates"]) > 50:
            raise ValueError("Each fixed candidate snapshot is limited to 50 records.")
        candidate_records: list[CandidateRecord] = []
        provider_order: dict[str, list[tuple[int, str]]] = defaultdict(list)
        seen_candidate_ids: set[str] = set()
        for item in case["candidates"]:
            if not isinstance(item, dict):
                raise ValueError("Candidate entries must be objects.")
            cid = item.get("candidate_id")
            candidate_type = item.get("candidate_type")
            title = item.get("title")
            provider = item.get("source_provider")
            if not all(isinstance(value, str) and value for value in (cid, candidate_type, title, provider)):
                raise ValueError("Each candidate requires candidate_id, candidate_type, title, and source_provider.")
            if cid in seen_candidate_ids:
                raise ValueError(f"Duplicate candidate_id in snapshot: {cid!r}.")
            seen_candidate_ids.add(cid)
            if candidate_type not in {"paper", "repository"}:
                raise ValueError("candidate_type must be paper or repository.")
            if len(cid) > 512 or len(title) > 2000 or len(provider) > 100:
                raise ValueError("Candidate ID, title, or provider name exceeds its size limit.")
            text = item.get("description")
            if text is not None and (not isinstance(text, str) or len(text) > 12000):
                raise ValueError("candidate description must be a string of at most 12000 characters or null.")
            topics = item.get("topics", [])
            if not isinstance(topics, list) or len(topics) > 30 or not all(isinstance(topic, str) and len(topic) <= 120 for topic in topics):
                raise ValueError("candidate topics must be an array of at most 30 strings, each at most 120 characters.")
            candidate_records.append(CandidateRecord(
                candidate_id=cid, source_provider=provider,
                provider_id=str(item.get("provider_id") or cid), candidate_type=candidate_type,
                title=title, description=text,
                source_url=item.get("source_url") if isinstance(item.get("source_url"), str) else None,
                programming_language=item.get("programming_language") if isinstance(item.get("programming_language"), str) else None,
                topics=tuple(topics),
            ))
            provider_rank = item.get("provider_discovery_rank")
            if provider_rank is not None and (
                isinstance(provider_rank, bool) or not isinstance(provider_rank, int) or provider_rank < 1
            ):
                raise ValueError("provider_discovery_rank must be a positive integer when provided.")
            if provider_rank is not None:
                provider_order[provider].append((provider_rank, cid))

        grades = case.get("relevance_grades")
        if (
            not isinstance(grades, dict)
            or any(not isinstance(key, str) or not key for key in grades)
            or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 or v > 3 for v in grades.values())
        ):
            raise ValueError("Each case needs relevance_grades mapping candidate IDs to integer grades 0..3.")
        grade_map = grades.copy()
        if any(cid not in {record.candidate_id for record in candidate_records} for cid in grade_map):
            raise ValueError("Every relevance label must refer to a candidate in this fixed snapshot.")
        missing_labels = {record.candidate_id for record in candidate_records} - set(grade_map)
        if missing_labels:
            raise ValueError("Every candidate in a fixed snapshot needs a reviewed relevance grade (0..3).")
        for provider, ranked_ids in provider_order.items():
            ranks = [rank for rank, _ in ranked_ids]
            if len(ranks) != len(set(ranks)):
                raise ValueError(f"provider_discovery_rank values must be unique within {provider!r}.")
        case_id = str(case.get("id") or f"case-{len(case_outputs) + 1}")
        category = str(case.get("slice") or "mixed")

        bm25, _, _ = rank_candidates(query, candidate_records, encoder=None, top_k=max(len(candidate_records), 1))
        dense_results, dense_available, dense_warning = rank_candidates(
            query, candidate_records, encoder=encoder, top_k=max(len(candidate_records), 1)
        ) if use_dense else ([], False, "Dense ranking was disabled by the caller.")
        hybrid = dense_results if dense_available else bm25
        rankings = {
            "bm25": [item.candidate.candidate_id for item in bm25],
            "dense": [item.candidate.candidate_id for item in sorted(dense_results, key=lambda match: match.dense_rank or 10**9)] if dense_available else [],
            "hybrid_rrf": [item.candidate.candidate_id for item in hybrid],
        }
        metrics_by_method = {method: ranking_metrics(ranking, grade_map) for method, ranking in rankings.items()}
        provider_native = {
            provider: [cid for _, cid in sorted(ranked_ids)]
            for provider, ranked_ids in sorted(provider_order.items())
        }
        provider_native_metrics = {}
        for provider, ranking in provider_native.items():
            # Score every provider against the same reviewed candidate universe.
            # Relevant candidates absent from this source remain misses in recall.
            provider_native_metrics[provider] = ranking_metrics(ranking, grade_map)
            method = f"provider_native:{provider}"
            for metric, value in provider_native_metrics[provider].items():
                slice_totals[category][method][metric] += value
            slice_counts[category][method] += 1
        for method, metrics in metrics_by_method.items():
            for metric, value in metrics.items():
                slice_totals[category][method][metric] += value
            slice_counts[category][method] += 1

        known_relevant = case.get("known_relevant_ids")
        discovery_recall = None
        if "known_relevant_ids" in case:
            if not isinstance(known_relevant, list):
                raise ValueError("known_relevant_ids must be an array of reviewed candidate IDs.")
            if (
                not all(isinstance(cid, str) and cid for cid in known_relevant)
                or len(known_relevant) != len(set(known_relevant))
            ):
                raise ValueError("known_relevant_ids must contain unique, non-empty candidate IDs.")
            relevant_set = set(known_relevant)
            discovered = {record.candidate_id for record in candidate_records}
            discovery_recall = len(relevant_set & discovered) / len(relevant_set) if relevant_set else 0.0
            discovery_values.append(discovery_recall)
        case_outputs.append({
            "id": case_id, "slice": category,
            "rankings": rankings, "provider_native_rankings": provider_native,
            "metrics": metrics_by_method, "provider_native_metrics": provider_native_metrics,
            "discovery_recall": discovery_recall,
            "dense_available": dense_available, "warning": dense_warning,
        })

    slices = {}
    for category, methods in slice_totals.items():
        slices[category] = {
            method: {metric: total / slice_counts[category][method] for metric, total in metrics.items()}
            for method, metrics in methods.items()
        }
    return {
        "snapshot_version": 1,
        "case_count": len(case_outputs),
        "slices": slices,
        "mean_discovery_recall": sum(discovery_values) / len(discovery_values) if discovery_values else None,
        "cases": case_outputs,
        "interpretation": "Metrics describe this reviewed fixed snapshot only; they are not claims about overall web search quality.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="Human-reviewed version-1 candidate snapshot JSON")
    parser.add_argument("--bm25-only", action="store_true", help="Skip dense model loading and omit dense ranking")
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        report = evaluate_snapshot(snapshot, use_dense=not args.bm25_only)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
