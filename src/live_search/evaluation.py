"""Small deterministic information-retrieval metrics for labelled snapshots."""

from __future__ import annotations

import math
from collections.abc import Sequence


def precision_at_k(ranking: Sequence[str], relevance: dict[str, int], k: int = 5) -> float:
    if k < 1:
        raise ValueError("k must be positive")
    return sum(relevance.get(item, 0) > 0 for item in ranking[:k]) / k


def recall_at_k(ranking: Sequence[str], relevance: dict[str, int], k: int = 10) -> float:
    relevant_total = sum(value > 0 for value in relevance.values())
    if relevant_total == 0:
        return 0.0
    return sum(relevance.get(item, 0) > 0 for item in ranking[:k]) / relevant_total


def ndcg_at_k(ranking: Sequence[str], relevance: dict[str, int], k: int = 10) -> float:
    if k < 1:
        raise ValueError("k must be positive")

    def dcg(grades: Sequence[int]) -> float:
        return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades[:k]))

    actual = dcg([relevance.get(item, 0) for item in ranking])
    ideal = dcg(sorted(relevance.values(), reverse=True))
    return actual / ideal if ideal else 0.0


def mrr_at_k(ranking: Sequence[str], relevance: dict[str, int], k: int = 10) -> float:
    for index, item in enumerate(ranking[:k], start=1):
        if relevance.get(item, 0) > 0:
            return 1.0 / index
    return 0.0


def ranking_metrics(ranking: Sequence[str], relevance: dict[str, int]) -> dict[str, float]:
    return {
        "precision_at_5": precision_at_k(ranking, relevance, 5),
        "recall_at_10": recall_at_k(ranking, relevance, 10),
        "ndcg_at_10": ndcg_at_k(ranking, relevance, 10),
        "mrr_at_10": mrr_at_k(ranking, relevance, 10),
    }
