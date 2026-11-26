"""Deterministic, evidence-based novelty scoring module.

Novelty is NOT determined arbitrarily by an LLM prompt. Instead, a reproducible
overlap intensity is computed directly from retrieval evidence (RRF score,
shared keywords, and match volume). The LLM is then instructed to explain
and contextualize this specific calculated score.
"""

from __future__ import annotations

from typing import Literal, Optional, Sequence, Tuple
from src.enhance.contracts import MatchInput

# Provisional weights for evidence-based novelty scoring (to be calibrated with benchmark)
TOP_RRF_DENOMINATOR = 0.033
RRF_WEIGHT = 0.40

SHARED_TERMS_DENOMINATOR = 6.0
SHARED_TERMS_WEIGHT = 0.35

DENSITY_DENOMINATOR = 5.0
DENSITY_WEIGHT = 0.25

HIGH_NOVELTY_THRESHOLD = 0.65
MEDIUM_NOVELTY_THRESHOLD = 0.40


def compute_evidence_novelty(
    idea: str,
    matches: Sequence[MatchInput],
    evidence_scope: Literal["local", "local+online"] = "local",
) -> Tuple[Optional[float], Literal["low", "medium", "high", "unknown"], str]:
    """Calculate an evidence-based novelty score and category.

    Returns:
        (score, level, baseline_reason)
        score: float between 0.05 and 0.95, or None when level is 'unknown'
        level: 'low' | 'medium' | 'high' | 'unknown'
        baseline_reason: concise factual summary of the evidence
    """
    if not matches:
        if evidence_scope == "local+online":
            reason = "No match found in local or online sources searched; this still does not prove originality."
        else:
            reason = "No match was found in the searched sources. This is not evidence that the idea is novel; a wider online check is required."
        return None, "unknown", reason

    # Rank-aware sorting: lowest rank integer comes first
    sorted_matches = sorted(
        matches,
        key=lambda m: (m.rank if m.rank is not None else 9999)
    )

    # 1. Top RRF score contribution
    top_rrf = 0.0
    for match in sorted_matches:
        if match.rrf_score is not None and match.rrf_score > top_rrf:
            top_rrf = float(match.rrf_score)
    rrf_overlap = min(top_rrf / TOP_RRF_DENOMINATOR, 1.0) * RRF_WEIGHT

    # 2. Distinct shared lexical elements
    shared_tokens = set()
    for match in sorted_matches:
        if match.shared_elements:
            for token in match.shared_elements:
                shared_tokens.add(token.strip().lower())
    shared_overlap = min(len(shared_tokens) / SHARED_TERMS_DENOMINATOR, 1.0) * SHARED_TERMS_WEIGHT

    # 3. Match density / count
    density_overlap = min(len(sorted_matches) / DENSITY_DENOMINATOR, 1.0) * DENSITY_WEIGHT

    # Total overlap intensity
    total_overlap = rrf_overlap + shared_overlap + density_overlap

    # Invert overlap to get novelty
    raw_score = 1.0 - total_overlap
    score = round(max(0.05, min(0.95, raw_score)), 2)

    if score >= HIGH_NOVELTY_THRESHOLD:
        level: Literal["low", "medium", "high", "unknown"] = "high"
        reason = (
            f"Moderate to low overlap with {len(sorted_matches)} retrieved project(s). "
            f"The concept introduces unique application angles or methodologies beyond existing corpus records."
        )
    elif score >= MEDIUM_NOVELTY_THRESHOLD:
        level = "medium"
        reason = (
            f"Significant overlap detected with {len(sorted_matches)} retrieved project(s) "
            f"(shared elements: {', '.join(sorted(shared_tokens)[:4]) or 'structural domain overlap'}). "
            f"The core concept is established, but novel variations in execution or architecture are viable."
        )
    else:
        level = "low"
        reason = (
            f"High direct overlap with existing records in the corpus "
            f"(notably top match with RRF score {top_rrf:.4f} and {len(shared_tokens)} shared terms). "
            f"The problem and methodology are already well-represented in existing projects."
        )

    return score, level, reason
