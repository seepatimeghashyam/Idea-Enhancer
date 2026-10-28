"""FastAPI entry point for the approved Idea Enhancer V1 search contract."""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import Body, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.search_gateway import (
    CoreSearchUnavailable,
    SearchGateway,
    SearchOutcome,
    UnavailableCoreSearchGateway,
)

MIN_IDEA_LENGTH = 10
MAX_IDEA_LENGTH = 2000
DEFAULT_TOP_K = 5
MIN_TOP_K = 1
MAX_TOP_K = 20
NO_MATCH_MESSAGE = "No close match was found in the available dataset."


class ContractValidationError(ValueError):
    """An input does not meet the approved POST /search contract."""

    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(message)
        self.details = details


def error_response(status_code: int, error_code: str, message: str, details: Any = None) -> JSONResponse:
    """Return the error envelope defined in docs/API_CONTRACT.md."""

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error_code": error_code,
            "message": message,
            "details": details,
        },
    )


def validate_search_payload(payload: Any) -> tuple[str, int, list[str]]:
    """Validate and normalize the public request without exposing framework errors."""

    if not isinstance(payload, dict):
        raise ContractValidationError(
            "The request body must be a JSON object.",
            {"field": "body", "constraint": "object"},
        )

    idea = payload.get("idea")
    if not isinstance(idea, str):
        raise ContractValidationError(
            "The 'idea' field must be a string.",
            {"field": "idea", "constraint": "string"},
        )

    query = idea.strip()
    if len(query) < MIN_IDEA_LENGTH:
        raise ContractValidationError(
            "The 'idea' field must contain at least 10 characters.",
            {
                "field": "idea",
                "constraint": "min_length",
                "min_length": MIN_IDEA_LENGTH,
                "actual_length": len(query),
            },
        )
    if len(query) > MAX_IDEA_LENGTH:
        raise ContractValidationError(
            "The 'idea' field must contain at most 2000 characters.",
            {
                "field": "idea",
                "constraint": "max_length",
                "max_length": MAX_IDEA_LENGTH,
                "actual_length": len(query),
            },
        )

    requested_top_k = payload.get("top_k", DEFAULT_TOP_K)
    if isinstance(requested_top_k, bool) or not isinstance(requested_top_k, int):
        raise ContractValidationError(
            "The 'top_k' field must be an integer.",
            {"field": "top_k", "constraint": "integer"},
        )

    top_k = min(max(requested_top_k, MIN_TOP_K), MAX_TOP_K)
    warnings = []
    if top_k != requested_top_k:
        warnings.append(f"top_k was clamped to {top_k}.")
    return query, top_k, warnings


def format_match(record: Mapping[str, Any]) -> dict[str, Any]:
    """Map a Core Search record to the committed public API fields.

    The Core Search handoff is still pending. This formatter accepts both the
    canonical data names (``abstract``, ``tech_stack``) and their public API
    equivalents so that the future adapter can be kept small.
    """

    technologies = record.get("technologies")
    if technologies is None and record.get("tech_stack"):
        technologies = [item.strip() for item in str(record["tech_stack"]).split(",") if item.strip()]

    return {
        "project_id": record.get("project_id"),
        "title": record.get("title"),
        "description_excerpt": record.get("description_excerpt", record.get("abstract", "")),
        "source_type": record.get("source_type"),
        "source_url": record.get("source_url"),
        "year": record.get("year"),
        "domain": record.get("domain"),
        "technologies": technologies,
        "rank": record.get("rank"),
        "bm25_rank": record.get("bm25_rank"),
        "vector_rank": record.get("vector_rank"),
        "rrf_score": record.get("rrf_score"),
        "shared_elements": record.get("shared_elements", []),
        "verification_status": record.get("verification_status"),
    }


def success_response(query: str, outcome: SearchOutcome, warnings: list[str]) -> dict[str, Any]:
    """Build the exact top-level success response from the approved contract."""

    matches = [format_match(record) for record in outcome.matches]
    return {
        "status": "success",
        "query": query,
        "result_count": len(matches),
        "matches": matches,
        "message": None if matches else NO_MATCH_MESSAGE,
        "warnings": [*warnings, *outcome.warnings],
    }


def create_app(search_gateway: SearchGateway | None = None) -> FastAPI:
    """Create an app with an injectable search boundary for tests and integration."""

    app = FastAPI(title="Idea Enhancer API")
    # The frontend runs on a different local port during development.
    # Allow only local browser origins to call this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(?::\d+)?$",
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    gateway = search_gateway or UnavailableCoreSearchGateway()

    @app.exception_handler(RequestValidationError)
    def handle_request_validation_error(_request: Any, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "The request body must be a valid JSON object.",
            exc.errors(),
        )

    @app.post("/search")
    def search(payload: Any = Body(None)) -> JSONResponse:
        try:
            query, top_k, warnings = validate_search_payload(payload)
        except ContractValidationError as error:
            return error_response(422, "VALIDATION_ERROR", str(error), error.details)

        try:
            outcome = gateway.search(query, top_k)
        except CoreSearchUnavailable as error:
            return error_response(503, "SEARCH_UNAVAILABLE", str(error))
        except Exception:
            return error_response(
                500,
                "SEARCH_FAILED",
                "An internal error occurred while processing the search. Please try again.",
            )

        return JSONResponse(status_code=200, content=success_response(query, outcome, warnings))

    return app


app = create_app()
