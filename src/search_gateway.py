"""API-owned boundary for the future Core Search integration.

This module deliberately contains no retrieval logic and no project records.  Once
the Core Search owner supplies their approved public interface, this gateway is the
only API-owned place that should be changed to call it.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class SearchOutcome:
    """Intermediate result returned to the API by a search gateway."""

    matches: Sequence[Mapping[str, Any]]
    warnings: Sequence[str] = field(default_factory=tuple)


class CoreSearchUnavailable(Exception):
    """The search dependency has not been connected or cannot serve requests."""


class SearchGateway(Protocol):
    """Local API boundary; not a claimed Core Search public signature."""

    def search(self, idea: str, top_k: int) -> SearchOutcome:
        """Return search records for a validated query, or raise an integration error."""


class UnavailableCoreSearchGateway:
    """Safe default until the Core Search handoff has been completed."""

    def search(self, idea: str, top_k: int) -> SearchOutcome:
        raise CoreSearchUnavailable(
            "Core Search is not connected yet. Please try again after the search index is ready."
        )
