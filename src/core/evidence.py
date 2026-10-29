"""Explainable lexical overlap inspection; it does not infer equivalence."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.core.contracts import ProjectRecord, VerificationStatus, build_search_text


_WORD = re.compile(r"[\w]+", flags=re.UNICODE)
_STOP_WORDS = frozenset(
    "a an and are as at be by for from has have in into is it of on or that the their this to was were with using system project based"
    .split()
)


@dataclass(frozen=True, slots=True)
class Evidence:
    shared_elements: list[str]
    verification_status: VerificationStatus


def _evidence_terms(text: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in _WORD.findall(text.casefold()):
        if len(raw) < 3 or raw in _STOP_WORDS or raw.isdigit() or raw in seen:
            continue
        seen.add(raw)
        result.append(raw)
    return result


def inspect_evidence(query: str, record: ProjectRecord) -> Evidence:
    """Return exact meaningful token overlap drawn only from approved content fields."""

    query_terms = _evidence_terms(query)
    record_terms = set(_evidence_terms(build_search_text(record)))
    shared = [term for term in query_terms if term in record_terms]
    return Evidence(
        shared_elements=shared,
        verification_status="checked" if shared else "insufficient",
    )
