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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.live_search.contracts import CandidateRecord
from src.live_search.evaluation import EVALUATION_SLICES, ranking_metrics
from src.live_search.retrieval import SentenceTransformerEncoder, rank_candidates


def evaluate_snapshot(snapshot: dict[str, Any], *, use_dense: bool = True) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be a JSON object.")
    cases = snapshot.get("cases")
    if snapshot.get("version") != 1 or not isinstance(cases, list) or not cases:
        raise ValueError("Snapshot must have version=1 and a cases array.")
    encoder = SentenceTransformerEncoder() if use_dense else None
    case_outputs = []
    slice_totals: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    slice_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    discovery_values: list[float] = []
    seen_case_ids: set[str] = set()
    label_distribution = {str(grade): 0 for grade in range(4)}
    provider_summary: dict[str, dict[str, Any]] = {}
    excluded_cases: list[dict[str, str]] = []
    dense_counts = {"completed": 0, "fallback_bm25": 0, "disabled": 0, "not_applicable_empty_pool": 0}
    reviewed_candidate_count = 0

    for case_number, case in enumerate(cases, 1):
        if not isinstance(case, dict) or not isinstance(case.get("candidates"), list):
            raise ValueError("Each case must contain a candidates array.")
        query = case.get("query")
        if not isinstance(query, str) or not 10 <= len(query.strip()) <= 2000:
            raise ValueError("Each case query must contain 10 to 2000 characters after trimming.")
        if len(case["candidates"]) > 50:
            raise ValueError("Each fixed candidate snapshot is limited to 50 records.")
        case_id = case.get("id", f"case-{case_number}")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("Each case id must be a non-empty string.")
        if case_id in seen_case_ids:
            raise ValueError(f"Duplicate case id in snapshot: {case_id!r}.")
        seen_case_ids.add(case_id)
        category = case.get("slice", "mixed")
        if not isinstance(category, str) or category not in EVALUATION_SLICES:
            raise ValueError(f"Case {case_id!r} has an unsupported evaluation slice: {category!r}.")
        candidate_records: list[CandidateRecord] = []
        provider_order: dict[str, list[tuple[int, str]]] = defaultdict(list)
        provider_ids: dict[str, list[str]] = defaultdict(list)
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
            provider_ids[provider].append(cid)
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
            provider_rank = item.get("provider_discovery_rank")
            if provider_rank is not None and (
                isinstance(provider_rank, bool) or not isinstance(provider_rank, int) or not 1 <= provider_rank <= 25
            ):
                raise ValueError(f"Candidate {cid!r} has an invalid provider_discovery_rank.")
            if provider_rank is not None:
                provider_order[provider].append((provider_rank, cid))
            for optional_text in ("programming_language", "venue"):
                if item.get(optional_text) is not None and not isinstance(item[optional_text], str):
                    raise ValueError(f"Candidate {cid!r} field {optional_text} must be a string or null.")
            candidate_records.append(CandidateRecord(
                candidate_id=cid, source_provider=provider,
                provider_id=item.get("provider_id") if isinstance(item.get("provider_id"), str) and item.get("provider_id") else cid,
                candidate_type=candidate_type,
                title=title, description=text,
                source_url=item.get("source_url") if isinstance(item.get("source_url"), str) else None,
                programming_language=item.get("programming_language") if isinstance(item.get("programming_language"), str) else None,
                topics=tuple(topics),
                venue=item.get("venue") if isinstance(item.get("venue"), str) else None,
            ))

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
            raise ValueError(f"Case {case_id!r} needs a reviewed relevance grade (0..3) for: {', '.join(sorted(missing_labels))}.")
        for grade in grade_map.values():
            label_distribution[str(grade)] += 1
        for provider, ranked_ids in provider_order.items():
            ranks = [rank for rank, _ in ranked_ids]
            if len(ranks) != len(set(ranks)):
                raise ValueError(f"provider_discovery_rank values must be unique within {provider!r}.")

        statuses = case.get("providers", {})
        if not isinstance(statuses, dict):
            raise ValueError(f"Case {case_id!r} providers must be an object when present.")
        provider_candidate_counts = {name: len(ids) for name, ids in provider_ids.items()}
        if any(count > 25 for count in provider_candidate_counts.values()):
            raise ValueError(f"Case {case_id!r} exceeds the 25-candidate limit for a provider.")
        for provider in set(statuses) | set(provider_ids):
            if not isinstance(provider, str) or not provider:
                raise ValueError(f"Case {case_id!r} has an invalid provider name.")
            status = statuses.get(provider)
            if status is not None:
                valid_states = {"success", "empty", "timeout", "rate_limited", "authentication_error", "configuration_error", "invalid_response", "network_error", "upstream_error"}
                if not isinstance(status, dict) or not isinstance(status.get("state"), str) or status["state"] not in valid_states:
                    raise ValueError(f"Case {case_id!r} has an invalid provider state for {provider!r}.")
                count = status.get("count")
                if isinstance(count, bool) or not isinstance(count, int) or count != provider_candidate_counts.get(provider, 0):
                    raise ValueError(f"Case {case_id!r} provider count does not match candidates for {provider!r}.")
                if status["state"] == "empty" and count != 0:
                    raise ValueError(f"Empty provider {provider!r} cannot have candidates.")
                if status["state"] == "success" and count == 0:
                    raise ValueError(f"Successful provider {provider!r} must have candidates; use empty for zero results.")
                if status["state"] not in {"success", "empty"} and count != 0:
                    raise ValueError(f"Failed provider {provider!r} cannot contribute candidate records.")
            provider_summary.setdefault(provider, {
                "state_counts": {"success": 0, "empty": 0, "failure": 0, "unrecorded": 0},
                "candidate_count": 0,
                "candidate_count_by_query": {},
            })
            summary = provider_summary[provider]
            state = status.get("state") if isinstance(status, dict) else None
            state_bucket = state if state in {"success", "empty"} else "failure" if state else "unrecorded"
            summary["state_counts"][state_bucket] += 1
            count = provider_candidate_counts.get(provider, 0)
            summary["candidate_count"] += count
            summary["candidate_count_by_query"][case_id] = count

        bm25, _, _ = rank_candidates(query, candidate_records, encoder=None, top_k=max(len(candidate_records), 1))
        dense_results: list[Any] = []
        dense_available = False
        if not use_dense:
            dense_warning = "Dense and hybrid evaluation were explicitly disabled; only BM25 was evaluated."
            dense_counts["disabled"] += 1
        elif not candidate_records:
            dense_warning = "Dense evaluation was not applicable because the captured candidate pool is empty."
            dense_counts["not_applicable_empty_pool"] += 1
        else:
            dense_results, dense_available, dense_warning = rank_candidates(
                query, candidate_records, encoder=encoder, top_k=len(candidate_records)
            )
            dense_counts["completed" if dense_available else "fallback_bm25"] += 1
        rankings = {
            "bm25": [item.candidate.candidate_id for item in bm25],
            "dense": [item.candidate.candidate_id for item in sorted(dense_results, key=lambda match: match.dense_rank or 10**9)] if dense_available else None,
            "hybrid_rrf": [item.candidate.candidate_id for item in dense_results] if dense_available else None,
        }
        actual_rankings = {method: ranking for method, ranking in rankings.items() if ranking is not None}
        metrics_by_method = {method: ranking_metrics(ranking, grade_map) for method, ranking in actual_rankings.items()}
        provider_native: dict[str, list[str]] = {}
        provider_native_metrics: dict[str, dict[str, float]] = {}
        excluded_methods: list[dict[str, str]] = []
        for provider in sorted(set(statuses) | set(provider_ids)):
            status = statuses.get(provider, {})
            state = status.get("state") if isinstance(status, dict) else None
            if state is not None and state not in {"success", "empty"}:
                excluded_methods.append({"method": f"provider_native:{provider}", "reason": f"Provider state was {state}; a failure is not an empty ranking."})
                continue
            if state == "empty":
                ranking: list[str] = []
            else:
                ids = provider_ids.get(provider, [])
                ranked_ids = provider_order.get(provider, [])
                if ids and not ranked_ids:
                    excluded_methods.append({"method": f"provider_native:{provider}", "reason": "No provider discovery ranks were supplied."})
                    continue
                if len(ranked_ids) != len(ids):
                    excluded_methods.append({"method": f"provider_native:{provider}", "reason": "Discovery ranks were missing for some candidates."})
                    continue
                ranking = [cid for _, cid in sorted(ranked_ids)]
            provider_native[provider] = ranking
            # Score every provider against the same reviewed candidate universe.
            # Relevant candidates absent from this source remain misses in recall.
            provider_native_metrics[provider] = ranking_metrics(ranking, grade_map)
        positive_relevance_count = sum(value > 0 for value in grade_map.values())
        comparable_for_aggregate = positive_relevance_count > 0
        if comparable_for_aggregate:
            for method, metrics in metrics_by_method.items():
                for metric, value in metrics.items():
                    slice_totals[category][method][metric] += value
                slice_counts[category][method] += 1
            for provider, metrics in provider_native_metrics.items():
                method = f"provider_native:{provider}"
                for metric, value in metrics.items():
                    slice_totals[category][method][metric] += value
                slice_counts[category][method] += 1
        else:
            reason = "No candidate has relevance above grade 0; query metrics are excluded from aggregate means."
            if not candidate_records:
                reason = "No candidates were captured; empty rankings are excluded from aggregate means."
            excluded_cases.append({"id": case_id, "slice": category, "reason": reason})

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
        provider_failure_notes = [
            f"{name}: {status.get('state')}"
            for name, status in statuses.items()
            if isinstance(status, dict) and status.get("state") not in {"success", "empty"}
        ]
        reviewed_candidate_count += len(candidate_records)
        case_outputs.append({
            "id": case_id, "slice": category,
            "query": query,
            "candidate_count": len(candidate_records),
            "label_distribution": {str(grade): sum(value == grade for value in grade_map.values()) for grade in range(4)},
            "provider_states": statuses,
            "rankings": rankings, "provider_native_rankings": provider_native,
            "metrics": metrics_by_method, "provider_native_metrics": provider_native_metrics,
            "discovery_recall": discovery_recall,
            "dense_state": (
                "disabled" if not use_dense else
                "not_applicable_empty_pool" if not candidate_records else
                "completed" if dense_available else "fallback_bm25"
            ),
            "dense_available": dense_available, "warning": dense_warning,
            "excluded_methods": excluded_methods,
            "aggregate_comparable": comparable_for_aggregate,
            "limitations": provider_failure_notes,
        })

    slices = {}
    for category, methods in slice_totals.items():
        slices[category] = {
            method: {metric: total / slice_counts[category][method] for metric, total in metrics.items()}
            for method, metrics in methods.items()
        }
    return {
        "format": snapshot.get("format", "version-1"),
        "snapshot_version": 1,
        "case_count": len(case_outputs),
        "reviewed_query_count": len(case_outputs),
        "reviewed_candidate_count": reviewed_candidate_count,
        "label_distribution": label_distribution,
        "provider_summary": provider_summary,
        "dense_evaluation": {
            "requested": use_dense,
            "state_counts": dense_counts,
            "completed_for_all_nonempty_cases": dense_counts["fallback_bm25"] == 0 and dense_counts["disabled"] == 0,
        },
        "slices": slices,
        "slice_summary": {
            category: {
                "query_count": sum(case["slice"] == category for case in case_outputs),
                "candidate_count": sum(case["candidate_count"] for case in case_outputs if case["slice"] == category),
                "aggregate_comparable_query_count": sum(case["slice"] == category and case["aggregate_comparable"] for case in case_outputs),
            }
            for category in sorted({case["slice"] for case in case_outputs})
        },
        "excluded_cases": excluded_cases,
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
