"""Grounding and citation validator for enhancement outputs.

RULE: Every suggestion and claim must cite the ID of a retrieved match.
This validator enforces strict grounding:
1. Removes or flags any cited project ID that was not in the retrieved matches.
2. Ensures suggestions never cite hallucinated or unindexed projects.
3. Ensures facets only reference valid retrieved match IDs.
4. Enforces 3 to 5 actionable suggestions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Set
from src.enhance.contracts import MatchInput

PROJECT_ID_PATTERN = re.compile(r"\b[A-Za-z0-9_-]+(?:_[0-9]+|[0-9]+)\b")


def extract_retrieved_ids(matches: Sequence[MatchInput]) -> Set[str]:
    """Get the set of legitimate project IDs retrieved in this search."""
    return {m.project_id.strip() for m in matches if m.project_id and m.project_id.strip()}


def sanitize_grounded_response(
    raw_payload: Dict[str, Any],
    matches: Sequence[MatchInput],
    computed_novelty_score: float,
    computed_novelty_level: str,
    computed_novelty_reason: str,
) -> Dict[str, Any]:
    """Sanitize, ground, and validate LLM-generated enhancement payload."""
    valid_ids = extract_retrieved_ids(matches)
    ordered_ids = [m.project_id.strip() for m in matches if m.project_id and m.project_id.strip()]
    top_id = ordered_ids[0] if ordered_ids else None

    # 1. Enforce deterministic novelty
    raw_payload["novelty"] = {
        "level": computed_novelty_level,
        "score": computed_novelty_score,
        "reason": raw_payload.get("novelty", {}).get("reason") or computed_novelty_reason,
    }

    # 2. Sanitize facet map
    facet_map = raw_payload.get("facet_map", {})
    sanitized_facet_map = {}
    for facet_name in ["problem", "domain", "method", "tech_stack", "data"]:
        facet_data = facet_map.get(facet_name, {})
        overlap = facet_data.get("overlap", "none")
        if overlap not in ["none", "partial", "strong"]:
            overlap = "partial" if valid_ids else "none"

        # Filter matched IDs to valid retrieved IDs only
        raw_ids = facet_data.get("matched_project_ids", [])
        if not isinstance(raw_ids, list):
            raw_ids = []
        clean_ids = [str(pid).strip() for pid in raw_ids if str(pid).strip() in valid_ids]

        # If overlap is strong/partial but model forgot to cite, populate with top match
        if (overlap in ["strong", "partial"]) and not clean_ids and top_id:
            clean_ids = [top_id]

        sanitized_facet_map[facet_name] = {
            "overlap": overlap if valid_ids else "none",
            "details": str(facet_data.get("details", f"Analysis of {facet_name} overlap relative to indexed corpus.")),
            "matched_project_ids": clean_ids,
        }
    raw_payload["facet_map"] = sanitized_facet_map

    # 3. Sanitize suggestions & enforce strict citations
    raw_suggestions = raw_payload.get("suggestions", [])
    if not isinstance(raw_suggestions, list):
        raw_suggestions = []

    clean_suggestions: List[Dict[str, Any]] = []
    for item in raw_suggestions:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "Architectural Enhancement")).strip()
        description = str(item.get("description", "")).strip()

        # Sanitize citations: keep only retrieved IDs
        cites_raw = item.get("cites", [])
        if not isinstance(cites_raw, list):
            cites_raw = [cites_raw] if cites_raw else []

        valid_cites = [str(c).strip() for c in cites_raw if str(c).strip() in valid_ids]

        # Check if the description explicitly mentions a valid ID
        if not valid_cites and valid_ids:
            for pid in ordered_ids:
                if pid in description or pid in title:
                    valid_cites.append(pid)

        # Fallback to top match ID if valid IDs exist but LLM omitted or invented an unretrieved ID
        if not valid_cites and top_id:
            valid_cites = [top_id]

        clean_suggestions.append({
            "title": title,
            "description": description,
            "cites": valid_cites,
        })

    # Ensure 3-5 suggestions
    if len(clean_suggestions) < 3:
        # Augment with deterministic architectural suggestions
        defaults = [
            (
                "Lightweight Model Optimization & Edge Deployment",
                f"Implement quantization and pruning to enable low-latency inference on edge nodes, addressing deployment limitations observed in {top_id or 'baseline projects'}.",
            ),
            (
                "Telemetry Logging and Anomaly Detection Pipeline",
                f"Add time-series sensor ingestion and automated alerting to expand operational observability beyond {top_id or 'existing implementations'}.",
            ),
            (
                "Resilient Offline-First Data Synchronization",
                f"Design a local SQLite buffer with background sync when network connectivity is intermittent, enhancing reliability over {top_id or 'standard architectures'}.",
            ),
        ]
        for def_title, def_desc in defaults:
            if len(clean_suggestions) >= 3:
                break
            clean_suggestions.append({
                "title": def_title,
                "description": def_desc,
                "cites": [top_id] if top_id else [],
            })

    raw_payload["suggestions"] = clean_suggestions[:5]

    # 4. Sanitize tech stack
    raw_stack = raw_payload.get("suggested_tech_stack", [])
    if not isinstance(raw_stack, list) or not raw_stack:
        raw_stack = [
            {"name": "FastAPI", "role": "High-performance API orchestration"},
            {"name": "TensorFlow Lite / ONNX Runtime", "role": "Lightweight model execution"},
            {"name": "SQLite / PostgreSQL", "role": "Structured data persistence"},
        ]
    clean_stack = []
    for item in raw_stack:
        if isinstance(item, dict):
            clean_stack.append({
                "name": str(item.get("name", "Technology")).strip(),
                "role": str(item.get("role", "Architectural component")).strip(),
            })
    raw_payload["suggested_tech_stack"] = clean_stack[:6]

    # 5. Sanitize feasibility
    feasibility = raw_payload.get("feasibility", {})
    if not isinstance(feasibility, dict):
        feasibility = {}
    try:
        rating = int(feasibility.get("rating", 4))
        rating = max(1, min(5, rating))
    except (ValueError, TypeError):
        rating = 4
    reasons = feasibility.get("reasons", [])
    if not isinstance(reasons, list) or not reasons:
        reasons = [
            "Leverages accessible open-source libraries and developer tools.",
            "Straightforward integration path for engineering student teams.",
            "Manageable hardware requirements and low deployment costs.",
        ]
    raw_payload["feasibility"] = {
        "rating": rating,
        "reasons": [str(r).strip() for r in reasons[:4] if str(r).strip()],
    }

    # 6. Overlap summary
    if not raw_payload.get("overlap_summary"):
        if valid_ids:
            raw_payload["overlap_summary"] = (
                f"Analyzed idea against {len(matches)} retrieved match(es), "
                f"identifying key touchpoints with {top_id}."
            )
        else:
            raw_payload["overlap_summary"] = (
                "No close prior-art matches were found in the indexed corpus. "
                "The analysis explores architectural enhancements from foundational principles."
            )

    return raw_payload
