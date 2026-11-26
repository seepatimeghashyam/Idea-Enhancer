"""Grounding and citation validator for enhancement outputs.

RULE: Every suggestion and claim must cite the ID of a retrieved match.
Strict Grounding:
1. Keeps ONLY cited project IDs that are in the retrieved matches.
2. If a suggestion has zero valid citations after filtering, it is DROPPED.
3. If overlap in a facet is claimed without valid IDs, it is downgraded to "none".
4. Zero invented/hardcoded fallback content. Malformed or ungrounded outputs
   raise LLMBadResponseError.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from src.enhance.contracts import MatchInput
from src.enhance.llm_client import LLMBadResponseError


def extract_retrieved_ids(matches: Sequence[MatchInput]) -> Set[str]:
    """Get the set of legitimate project IDs retrieved in this search (max 5)."""
    # Use max 5 matches to match prompt and scoring
    bounded = matches[:5]
    return {m.project_id.strip() for m in bounded if m.project_id and m.project_id.strip()}


def get_rank_sorted_matches(matches: Sequence[MatchInput]) -> List[MatchInput]:
    """Sort matches prioritizing lowest rank integer (rank 1 first)."""
    return sorted(matches[:5], key=lambda m: (m.rank if m.rank is not None else 9999))


def sanitize_grounded_response(
    raw_payload: Dict[str, Any],
    matches: Sequence[MatchInput],
    computed_novelty_score: Optional[float],
    computed_novelty_level: str,
    computed_novelty_reason: str,
) -> Tuple[Dict[str, Any], List[str]]:
    """Sanitize, ground, and validate LLM-generated enhancement payload.

    Raises:
        LLMBadResponseError: If payload is missing required fields, malformed,
            or contains zero grounded suggestions.
    """
    if not isinstance(raw_payload, dict):
        raise LLMBadResponseError("LLM response payload must be a JSON object.")

    valid_ids = extract_retrieved_ids(matches)
    warnings: List[str] = []

    # 1. Enforce deterministic novelty
    raw_novelty = raw_payload.get("novelty")
    if not isinstance(raw_novelty, dict):
        raise LLMBadResponseError("Missing or invalid 'novelty' object in LLM response.")

    if computed_novelty_level == "unknown":
        novelty_reason = computed_novelty_reason
    else:
        novelty_reason = str(raw_novelty.get("reason", "")).strip() or computed_novelty_reason
    raw_payload["novelty"] = {
        "level": computed_novelty_level,
        "score": computed_novelty_score,
        "reason": novelty_reason,
    }

    # 2. Overlap summary validation
    overlap_summary = raw_payload.get("overlap_summary")
    if not isinstance(overlap_summary, str) or not overlap_summary.strip():
        raise LLMBadResponseError("Missing or empty 'overlap_summary' in LLM response.")
    raw_payload["overlap_summary"] = overlap_summary.strip()

    # 3. Facet map validation
    facet_map = raw_payload.get("facet_map")
    if not isinstance(facet_map, dict):
        raise LLMBadResponseError("Missing or invalid 'facet_map' in LLM response.")

    required_facets = ["problem", "domain", "method", "tech_stack", "data"]
    sanitized_facet_map: Dict[str, Any] = {}

    for facet_name in required_facets:
        facet_data = facet_map.get(facet_name)
        if not isinstance(facet_data, dict):
            raise LLMBadResponseError(f"Missing or invalid facet '{facet_name}' in facet_map.")

        overlap = facet_data.get("overlap")
        if overlap not in ("none", "partial", "strong"):
            raise LLMBadResponseError(
                f"Invalid overlap value '{overlap}' in facet '{facet_name}'. Must be none, partial, or strong."
            )

        details = facet_data.get("details")
        if not isinstance(details, str) or not details.strip():
            raise LLMBadResponseError(f"Missing or empty details in facet '{facet_name}'.")

        raw_ids = facet_data.get("matched_project_ids", [])
        if not isinstance(raw_ids, list):
            raw_ids = []

        # Filter strictly to valid retrieved IDs
        clean_ids = [str(pid).strip() for pid in raw_ids if str(pid).strip() in valid_ids]

        # Rule: If overlap is strong/partial but there are no valid matched_project_ids,
        # downgrade to 'none' with [] (do not forge citations).
        if overlap in ("strong", "partial") and not clean_ids:
            overlap = "none"

        sanitized_facet_map[facet_name] = {
            "overlap": overlap,
            "details": details.strip(),
            "matched_project_ids": clean_ids,
        }

    raw_payload["facet_map"] = sanitized_facet_map

    # 4. Suggestions validation & strict citation filtering
    raw_suggestions = raw_payload.get("suggestions")
    if not isinstance(raw_suggestions, list):
        raise LLMBadResponseError("Missing or invalid 'suggestions' list in LLM response.")

    clean_suggestions: List[Dict[str, Any]] = []
    for item in raw_suggestions:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title", "")).strip()
        description = str(item.get("description", "")).strip()
        if not title or not description:
            continue

        # Cites filtering
        cites_raw = item.get("cites", [])
        if not isinstance(cites_raw, list):
            cites_raw = [cites_raw] if cites_raw else []

        valid_cites = [str(c).strip() for c in cites_raw if str(c).strip() in valid_ids]

        # Accept an ID mentioned literally in description/title if in valid_ids
        for pid in valid_ids:
            if pid not in valid_cites and (pid in description or pid in title):
                valid_cites.append(pid)

        # Rule: If matches were retrieved, suggestion MUST have at least 1 valid citation.
        # If zero valid cites remain after filtering, DROP the suggestion!
        if valid_ids and not valid_cites:
            continue

        # If zero matches exist, citations are empty
        if not valid_ids:
            valid_cites = []

        clean_suggestions.append({
            "title": title,
            "description": description,
            "cites": sorted(list(set(valid_cites))),
        })

    # If zero valid suggestions remain, raise 502
    if not clean_suggestions:
        raise LLMBadResponseError("No grounded suggestions could be extracted from AI response.")

    # If fewer than 3 valid suggestions remain, return valid ones and add warning
    if len(clean_suggestions) < 3:
        warnings.append("Fewer than 3 grounded suggestions were produced.")

    # Limit to top 5 suggestions
    raw_payload["suggestions"] = clean_suggestions[:5]

    # 5. Tech stack validation
    raw_stack = raw_payload.get("suggested_tech_stack")
    if not isinstance(raw_stack, list) or not raw_stack:
        raise LLMBadResponseError("Missing or empty 'suggested_tech_stack' in LLM response.")

    clean_stack: List[Dict[str, str]] = []
    for item in raw_stack:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            role = str(item.get("role", "")).strip()
            if name and role:
                clean_stack.append({"name": name, "role": role})

    if not clean_stack:
        raise LLMBadResponseError("No valid tech stack items in LLM response.")
    raw_payload["suggested_tech_stack"] = clean_stack[:6]

    # 6. Feasibility validation
    feasibility = raw_payload.get("feasibility")
    if not isinstance(feasibility, dict):
        raise LLMBadResponseError("Missing or invalid 'feasibility' object in LLM response.")

    try:
        rating = int(feasibility.get("rating"))
        if not (1 <= rating <= 5):
            raise ValueError()
    except (TypeError, ValueError):
        raise LLMBadResponseError("Feasibility rating must be an integer between 1 and 5.")

    reasons = feasibility.get("reasons")
    if not isinstance(reasons, list) or not reasons:
        raise LLMBadResponseError("Feasibility reasons must be a non-empty list of strings.")

    clean_reasons = [str(r).strip() for r in reasons if str(r).strip()]
    if not clean_reasons:
        raise LLMBadResponseError("Feasibility reasons cannot be empty strings.")

    raw_payload["feasibility"] = {
        "rating": rating,
        "reasons": clean_reasons[:4],
    }

    return raw_payload, warnings
