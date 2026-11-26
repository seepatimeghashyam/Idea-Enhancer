"""Deterministic, evidence-based novelty scoring module.

Novelty is NOT determined arbitrarily by an LLM prompt. Instead, a reproducible
overlap intensity is computed directly from retrieval evidence (RRF score,
shared keywords, and match volume). The LLM is then instructed to explain
and contextualize this specific calculated score.
"""

from __future__ import annotations

from typing import List, Literal, Sequence, Tuple
from src.enhance.contracts import MatchInput


def compute_evidence_novelty(
    idea: str, matches: Sequence[MatchInput]
) -> Tuple[float, Literal["low", "medium", "high"], str]:
    """Calculate an evidence-based novelty score and category.

    Returns:
        (score, level, baseline_reason)
        score: float between 0.05 and 0.95
        level: 'low' | 'medium' | 'high'
        baseline_reason: concise factual summary of the evidence
    """
    if not matches:
        return (
            0.95,
            "high",
            "No prior-art matches were found in the indexed corpus. While this indicates high novelty relative to the dataset, it is not proof of universal originality.",
        )

    # 1. Top RRF score contribution (up to 40% of overlap intensity)
    # Typical top-1 hybrid rank has RRF ~ 0.0328 (1/(60+1) + 1/(60+1))
    top_rrf = 0.0
    for match in matches:
        if match.rrf_score is not None and match.rrf_score > top_rrf:
            top_rrf = float(match.rrf_score)
    rrf_overlap = min(top_rrf / 0.033, 1.0) * 0.40

    # 2. Distinct shared lexical elements (up to 35% of overlap intensity)
    shared_tokens = set()
    for match in matches:
        if match.shared_elements:
            for token in match.shared_elements:
                shared_tokens.add(token.strip().lower())
    shared_overlap = min(len(shared_tokens) / 6.0, 1.0) * 0.35

    # 3. Match density / count (up to 25% of overlap intensity)
    density_overlap = min(len(matches) / 5.0, 1.0) * 0.25

    # Total overlap intensity between 0.0 (no overlap) and 1.0 (identical/heavy overlap)
    total_overlap = rrf_overlap + shared_overlap + density_overlap

    # Invert overlap to get novelty
    raw_score = 1.0 - total_overlap
    score = round(max(0.05, min(0.95, raw_score)), 2)

    if score >= 0.65:
        level: Literal["low", "medium", "high"] = "high"
        reason = (
            f"Moderate to low overlap with {len(matches)} retrieved project(s). "
            f"The concept introduces unique application angles or methodologies beyond existing corpus records."
        )
    elif score >= 0.40:
        level = "medium"
        reason = (
            f"Significant overlap detected with {len(matches)} retrieved project(s) "
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
