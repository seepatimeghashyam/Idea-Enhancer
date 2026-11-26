"""FastAPI router for POST /enhance."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from src.enhance.contracts import EnhanceRequest, EnhanceResponse
from src.enhance.llm_client import LLMTimeoutError, LLMUnavailableError
from src.enhance.service import EnhanceService

logger = logging.getLogger(__name__)

enhance_router = APIRouter(tags=["Enhance"])

_service_instance: EnhanceService | None = None


def get_enhance_service() -> EnhanceService:
    """Dependency injection provider for EnhanceService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = EnhanceService()
    return _service_instance


def set_enhance_service(service: EnhanceService | None) -> None:
    """Set global or test service instance."""
    global _service_instance
    _service_instance = service


def error_response(status_code: int, error_code: str, message: str, details: Any = None) -> JSONResponse:
    """Return standard API error envelope per docs/API_CONTRACT.md."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error_code": error_code,
            "message": message,
            "details": details,
        },
    )


@enhance_router.post("/enhance", response_model=EnhanceResponse)
def enhance_idea(
    payload: EnhanceRequest,
    service: EnhanceService = Depends(get_enhance_service),
) -> Any:
    """Generate grounded architectural enhancements for a student project idea."""
    try:
        response = service.enhance(payload)
        return response
    except LLMTimeoutError as err:
        logger.warning("Enhance operation timed out: %s", err)
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "LLM_TIMEOUT",
            "The AI enhancement service timed out while generating suggestions. Please try again.",
        )
    except LLMUnavailableError as err:
        logger.warning("Enhance LLM service unavailable: %s", err)
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "LLM_UNAVAILABLE",
            f"The AI enhancement service is currently unavailable: {err}",
        )
    except ValueError as err:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            str(err),
        )
    except Exception as err:
        logger.exception("Unexpected error in /enhance: %s", err)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "ENHANCE_FAILED",
            "An internal error occurred while generating enhancements. Please try again.",
        )
