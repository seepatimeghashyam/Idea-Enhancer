"""API-owned boundary for the Core Search integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence


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


class CoreSearchGateway:
    """Concrete API gateway adapter calling the Core Search public facade."""

    def __init__(self, search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None) -> None:
        self._search_fn = search_fn

    def _get_search_fn(self) -> Callable[[str, int], list[dict[str, Any]]]:
        if self._search_fn is not None:
            return self._search_fn
        try:
            from src.database import search_projects

            return search_projects
        except (ImportError, ModuleNotFoundError) as error:
            raise CoreSearchUnavailable(
                "Core Search module is not installed or available."
            ) from error
        except Exception as error:
            raise CoreSearchUnavailable(
                f"Core Search module could not be loaded: {error}"
            ) from error

    def search(self, idea: str, top_k: int) -> SearchOutcome:
        """Call the facade, wrap returned records in SearchOutcome, and translate errors."""
        search_fn = self._get_search_fn()

        try:
            from src.database import CoreSearchUnavailable as DatabaseCoreSearchUnavailable
        except Exception:
            DatabaseCoreSearchUnavailable = None

        try:
            results = search_fn(idea, top_k)
        except Exception as error:
            if DatabaseCoreSearchUnavailable is not None and isinstance(error, DatabaseCoreSearchUnavailable):
                raise CoreSearchUnavailable(str(error)) from error
            if isinstance(error, CoreSearchUnavailable):
                raise
            raise

        if not isinstance(results, Sequence):
            results = list(results)

        return SearchOutcome(matches=results, warnings=())


class UnavailableCoreSearchGateway:
    """Fallback gateway explicitly raising CoreSearchUnavailable."""

    def search(self, idea: str, top_k: int) -> SearchOutcome:
        raise CoreSearchUnavailable(
            "Core Search is not connected yet. Please try again after the search index is ready."
        )
