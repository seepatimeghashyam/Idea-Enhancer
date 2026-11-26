"""Shared, standard-library helpers for the local human-labelled evaluation workflow."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, TextIO

from src.live_search.contracts import CandidateRecord, ProviderResult
from src.live_search.evaluation import EVALUATION_SLICES


QUERY_CATALOGUE_VERSION = 1
CAPTURE_FORMAT = "idea-enhancer-live-capture"
CAPTURE_VERSION = 1
REVIEWED_SNAPSHOT_FORMAT = "idea-enhancer-reviewed-live-snapshot"
REVIEWED_SNAPSHOT_VERSION = 1
ANNOTATION_COLUMNS = (
    "query_id", "query", "slice", "candidate_id", "candidate_type", "title",
    "description", "source_url", "source_provider", "relevance_grade",
    "reviewer_rationale", "reviewer_confidence",
)
_QUERY_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_SECRET_KEYS = {"authorization", "token", "access_token", "api_key", "secret", "password", "headers"}
_PROVIDER_STATES = {
    "success", "empty", "timeout", "rate_limited", "authentication_error",
    "configuration_error", "invalid_response", "network_error", "upstream_error",
}


def _is_secret_key(key: Any) -> bool:
    normalized = str(key).casefold().replace("-", "_")
    return any(part in normalized for part in _SECRET_KEYS)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> tuple[Any, bytes]:
    raw = path.read_bytes()
    try:
        return json.loads(raw.decode("utf-8-sig")), raw
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: expected valid UTF-8 JSON ({error}).") from error


def load_query_catalogue(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != QUERY_CATALOGUE_VERSION:
        raise ValueError("Query catalogue must be an object with version=1.")
    queries = value.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("Query catalogue must contain a non-empty queries array.")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(queries, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Query catalogue entry {index} must be an object.")
        query_id, query, slice_name = item.get("query_id"), item.get("query"), item.get("slice")
        if not isinstance(query_id, str) or not _QUERY_ID.fullmatch(query_id):
            raise ValueError(f"Query catalogue entry {index} has an invalid query_id.")
        if query_id in seen:
            raise ValueError(f"Duplicate query_id in catalogue: {query_id!r}.")
        seen.add(query_id)
        if not isinstance(query, str) or not 10 <= len(query.strip()) <= 2000:
            raise ValueError(f"Query {query_id!r} must contain 10 to 2000 characters after trimming.")
        if not isinstance(slice_name, str) or slice_name not in EVALUATION_SLICES - {"paper", "repository", "mixed", "other"}:
            raise ValueError(f"Query {query_id!r} has an unsupported evaluation slice: {slice_name!r}.")
        tags = item.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 20 or not all(
            isinstance(tag, str) and 0 < len(tag.strip()) <= 80 for tag in tags
        ):
            raise ValueError(f"Query {query_id!r} tags must be an array of at most 20 non-empty strings (80 characters maximum).")
        normalized.append({"query_id": query_id, "query": query, "slice": slice_name, "tags": tags})
    return {"version": QUERY_CATALOGUE_VERSION, "queries": normalized}


def _safe_json_value(value: Any, *, key: str = "") -> Any:
    """Preserve JSON-safe provider metadata while excluding credential-like fields."""
    if _is_secret_key(key):
        return None
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Provider metadata contains a non-finite number.")
        return value
    if isinstance(value, list | tuple):
        return [_safe_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(name): _safe_json_value(item, key=str(name))
            for name, item in value.items()
            if not _is_secret_key(name)
        }
    raise ValueError(f"Provider metadata contains a non-JSON value ({type(value).__name__}).")


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _is_secret_key(key) or _contains_secret_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret_key(item) for item in value)
    return False


def capture_candidate(candidate: CandidateRecord) -> dict[str, Any]:
    rank = candidate.provider_metadata.get("discovery_rank")
    if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
        raise ValueError(f"Candidate {candidate.candidate_id!r} is missing a valid provider discovery rank.")
    return {
        "candidate_id": candidate.candidate_id,
        "provider_id": candidate.provider_id,
        "source_provider": candidate.source_provider,
        "candidate_type": candidate.candidate_type,
        "title": candidate.title,
        "description": candidate.description,
        "source_url": candidate.source_url,
        "doi": candidate.doi,
        "authors": list(candidate.authors),
        "owner": candidate.owner,
        "publication_date": candidate.publication_date,
        "publication_year": candidate.publication_year,
        "work_type": candidate.work_type,
        "repository_created_at": candidate.repository_created_at,
        "repository_pushed_at": candidate.repository_pushed_at,
        "venue": candidate.venue,
        "programming_language": candidate.programming_language,
        "topics": list(candidate.topics),
        "stars": candidate.stars,
        "forks": candidate.forks,
        "open_access": candidate.open_access,
        "citation_count": candidate.citation_count,
        "archived": candidate.archived,
        "license_name": candidate.license_name,
        "retrieved_at": candidate.retrieved_at,
        "provider_discovery_rank": rank,
        "provider_metadata": _safe_json_value({
            key: value for key, value in candidate.provider_metadata.items() if key != "discovery_rank"
        }),
    }


def provider_capture_summary(result: ProviderResult) -> dict[str, Any]:
    return result.public_dict()


async def capture_catalogue(catalogue: dict[str, Any], service: Any) -> dict[str, Any]:
    """Collect full normalized provider pools via the production service boundary."""
    queries: list[dict[str, Any]] = []
    for query in catalogue["queries"]:
        normalized_query, provider_results = await service.discover_candidates(query["query"])
        sorted_results = sorted(provider_results, key=lambda result: result.provider)
        candidates: list[dict[str, Any]] = []
        providers: dict[str, Any] = {}
        warnings: list[str] = []
        for result in sorted_results:
            providers[result.provider] = provider_capture_summary(result)
            if result.state not in {"success", "empty"}:
                warnings.append(f"{result.provider}: {result.state} ({result.error_code or 'provider_error'}).")
            candidates.extend(capture_candidate(candidate) for candidate in result.candidates)
        queries.append({
            **query,
            "normalized_query": normalized_query,
            "captured_at": utc_now(),
            "providers": providers,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "warnings": warnings,
        })
    return {
        "format": CAPTURE_FORMAT,
        "version": CAPTURE_VERSION,
        "captured_at": utc_now(),
        "queries": queries,
    }


def complete_capture(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("format") != CAPTURE_FORMAT or value.get("version") != CAPTURE_VERSION:
        raise ValueError("Expected an Idea Enhancer live capture with format/version 1.")
    queries = value.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("Capture must contain a non-empty queries array.")
    seen_queries: set[str] = set()
    for query in queries:
        if not isinstance(query, dict):
            raise ValueError("Every captured query must be an object.")
        query_id = query.get("query_id")
        if not isinstance(query_id, str) or not _QUERY_ID.fullmatch(query_id) or query_id in seen_queries:
            raise ValueError(f"Invalid or duplicate query_id in capture: {query_id!r}.")
        seen_queries.add(query_id)
        if (
            not isinstance(query.get("query"), str) or not 10 <= len(query["query"].strip()) <= 2000
            or not isinstance(query.get("normalized_query"), str) or not query["normalized_query"].strip()
        ):
            raise ValueError(f"Capture query {query_id!r} is missing query text.")
        if not isinstance(query.get("slice"), str) or query.get("slice") not in EVALUATION_SLICES:
            raise ValueError(f"Capture query {query_id!r} has an unsupported slice.")
        candidates = query.get("candidates")
        providers = query.get("providers")
        if not isinstance(candidates, list) or len(candidates) > 50 or not isinstance(providers, dict):
            raise ValueError(f"Capture query {query_id!r} needs candidate and provider arrays/maps.")
        ids: set[str] = set()
        provider_ranks: dict[str, list[int]] = {}
        provider_counts: dict[str, int] = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError(f"Capture query {query_id!r} contains a non-object candidate.")
            cid, provider, rank = candidate.get("candidate_id"), candidate.get("source_provider"), candidate.get("provider_discovery_rank")
            if not isinstance(cid, str) or not cid or cid in ids:
                raise ValueError(f"Capture query {query_id!r} contains a missing or duplicate candidate_id: {cid!r}.")
            ids.add(cid)
            if not isinstance(provider, str) or not provider or len(provider) > 100:
                raise ValueError(f"Candidate {cid!r} is missing source_provider.")
            candidate_type = candidate.get("candidate_type")
            if not isinstance(candidate_type, str) or candidate_type not in {"paper", "repository"} or not isinstance(candidate.get("title"), str) or not candidate["title"].strip():
                raise ValueError(f"Candidate {cid!r} has invalid type or title data.")
            if len(candidate["title"]) > 2000:
                raise ValueError(f"Candidate {cid!r} title exceeds 2000 characters.")
            description = candidate.get("description")
            if description is not None and (not isinstance(description, str) or len(description) > 20000):
                raise ValueError(f"Candidate {cid!r} has an invalid or oversized description.")
            source_url = candidate.get("source_url")
            if source_url is not None:
                from src.live_search.providers import _safe_url

                if not isinstance(source_url, str) or _safe_url(source_url) != source_url:
                    raise ValueError(f"Candidate {cid!r} has an invalid or unsafe source_url.")
            metadata = candidate.get("provider_metadata", {})
            if not isinstance(metadata, dict):
                raise ValueError(f"Candidate {cid!r} provider_metadata must be an object.")
            if _contains_secret_key(metadata):
                raise ValueError(f"Candidate {cid!r} provider_metadata contains a credential-like key.")
            if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 25:
                raise ValueError(f"Candidate {cid!r} has an invalid provider discovery rank.")
            provider_ranks.setdefault(provider, []).append(rank)
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            if provider_counts[provider] > 25:
                raise ValueError(f"Capture query {query_id!r} exceeds the 25-candidate limit for {provider!r}.")
        for provider, ranks in provider_ranks.items():
            if len(ranks) != len(set(ranks)):
                raise ValueError(f"Capture query {query_id!r} has duplicate discovery ranks for {provider!r}.")
        if query.get("candidate_count") != len(candidates):
            raise ValueError(f"Capture query {query_id!r} has an inconsistent candidate_count.")
        for provider, status in providers.items():
            if not isinstance(provider, str) or not provider or len(provider) > 100:
                raise ValueError(f"Capture query {query_id!r} has an invalid provider name.")
            if not isinstance(status, dict) or not isinstance(status.get("state"), str) or status["state"] not in _PROVIDER_STATES:
                raise ValueError(f"Capture query {query_id!r} has an invalid provider state for {provider!r}.")
            count = status.get("count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"Capture query {query_id!r} has an invalid provider count for {provider!r}.")
            if count != provider_counts.get(provider, 0):
                raise ValueError(f"Capture query {query_id!r} provider count does not match candidates for {provider!r}.")
            if status["state"] == "empty" and count != 0:
                raise ValueError(f"Empty provider {provider!r} cannot have candidates.")
            if status["state"] == "success" and count == 0:
                raise ValueError(f"Successful provider {provider!r} must have candidates; use empty for zero results.")
            if status["state"] not in {"success", "empty"} and count != 0:
                raise ValueError(f"Failed provider {provider!r} cannot contribute candidates.")
        if any(provider not in providers for provider in provider_counts):
            raise ValueError(f"Capture query {query_id!r} has candidates without provider status.")
    return value


def write_json_new(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    except FileExistsError as error:
        raise ValueError(f"Refusing to overwrite existing file: {path}") from error

def write_annotations(capture: dict[str, Any], stream: TextIO) -> int:
    capture = complete_capture(capture)
    writer = csv.DictWriter(stream, fieldnames=ANNOTATION_COLUMNS, extrasaction="raise")
    writer.writeheader()
    row_count = 0
    for query in capture["queries"]:
        for candidate in query["candidates"]:
            writer.writerow({
                "query_id": query["query_id"], "query": query["query"], "slice": query["slice"],
                "candidate_id": candidate["candidate_id"], "candidate_type": candidate["candidate_type"],
                "title": candidate["title"], "description": candidate.get("description") or "",
                "source_url": candidate.get("source_url") or "", "source_provider": candidate["source_provider"],
                "relevance_grade": "", "reviewer_rationale": "", "reviewer_confidence": "",
            })
            row_count += 1
    return row_count


def build_reviewed_snapshot(capture_value: Any, annotation_path: Path) -> dict[str, Any]:
    capture = complete_capture(capture_value)
    captured_queries = {query["query_id"]: query for query in capture["queries"]}
    candidate_maps = {
        query_id: {candidate["candidate_id"]: candidate for candidate in query["candidates"]}
        for query_id, query in captured_queries.items()
    }
    required_columns = set(ANNOTATION_COLUMNS)
    grades: dict[tuple[str, str], int] = {}
    review_notes: dict[tuple[str, str], dict[str, str | None]] = {}
    try:
        with annotation_path.open("r", encoding="utf-8-sig", newline="") as stream:
            text = stream.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError(f"Cannot read annotation CSV {annotation_path}: {error}.") from error
    from io import StringIO

    reader = csv.DictReader(StringIO(text, newline=""))
    headers = reader.fieldnames
    if headers is None or len(headers) != len(set(headers)) or not required_columns.issubset(headers):
        missing = sorted(required_columns - set(headers or []))
        raise ValueError(f"Annotation CSV is missing required or unique columns: {', '.join(missing) or 'duplicate headers'}.")
    for row_number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"Annotation row {row_number} has missing or extra CSV fields.")
        query_id, candidate_id = row.get("query_id", "").strip(), row.get("candidate_id", "").strip()
        if query_id not in captured_queries:
            raise ValueError(f"Annotation row {row_number} refers to unknown query_id {query_id!r}.")
        if candidate_id not in candidate_maps[query_id]:
            raise ValueError(f"Annotation row {row_number} refers to unknown candidate {candidate_id!r} for query {query_id!r}.")
        key = (query_id, candidate_id)
        if key in grades:
            raise ValueError(f"Duplicate annotation for query {query_id!r}, candidate {candidate_id!r}.")
        if row.get("query", "") != captured_queries[query_id]["query"]:
            raise ValueError(f"Annotation row {row_number} query text does not match capture query {query_id!r}.")
        candidate = candidate_maps[query_id][candidate_id]
        expected_context = {
            "slice": captured_queries[query_id]["slice"],
            "candidate_type": candidate["candidate_type"],
            "title": candidate["title"],
            "description": candidate.get("description") or "",
            "source_url": candidate.get("source_url") or "",
            "source_provider": candidate["source_provider"],
        }
        if any(row.get(column, "") != expected for column, expected in expected_context.items()):
            raise ValueError(f"Annotation row {row_number} display fields do not match captured candidate {candidate_id!r}.")
        raw_grade = row.get("relevance_grade", "").strip()
        if raw_grade not in {"0", "1", "2", "3"}:
            raise ValueError(f"Annotation row {row_number} for {query_id}/{candidate_id} needs an integer grade 0, 1, 2, or 3.")
        rationale = row.get("reviewer_rationale", "").strip()
        if len(rationale) > 3000:
            raise ValueError(f"Annotation rationale is too long at row {row_number} (maximum 3000 characters).")
        confidence = row.get("reviewer_confidence", "").strip().lower()
        if confidence and confidence not in {"low", "medium", "high"}:
            raise ValueError(f"Annotation confidence at row {row_number} must be low, medium, high, or blank.")
        grades[key] = int(raw_grade)
        review_notes[key] = {"rationale": rationale or None, "confidence": confidence or None}

    missing: list[str] = []
    for query_id, candidates in candidate_maps.items():
        pending = [candidate_id for candidate_id in candidates if (query_id, candidate_id) not in grades]
        if pending:
            missing.append(f"{query_id}: {', '.join(pending)}")
    if missing:
        raise ValueError("Incomplete annotations; candidates still needing human review: " + "; ".join(missing))

    cases: list[dict[str, Any]] = []
    for query_id, query in captured_queries.items():
        query_grades = {cid: grades[(query_id, cid)] for cid in candidate_maps[query_id]}
        annotations = {cid: review_notes[(query_id, cid)] for cid in candidate_maps[query_id]}
        cases.append({
            "id": query_id,
            "query": query["query"],
            "slice": query["slice"],
            "tags": query.get("tags", []),
            "captured_at": query.get("captured_at"),
            "providers": query["providers"],
            "candidate_count": query["candidate_count"],
            "candidates": query["candidates"],
            "relevance_grades": query_grades,
            "review_annotations": annotations,
        })
    return {
        "format": REVIEWED_SNAPSHOT_FORMAT,
        "version": REVIEWED_SNAPSHOT_VERSION,
        "reviewed_at": utc_now(),
        "capture_provenance": capture.get("provenance", {}),
        "cases": cases,
    }


def write_csv_new(path: Path, capture: dict[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8-sig", newline="") as stream:
            return write_annotations(capture, stream)
    except FileExistsError as error:
        raise ValueError(f"Refusing to overwrite existing file: {path}") from error
