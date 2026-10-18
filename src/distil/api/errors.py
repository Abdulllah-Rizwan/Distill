"""API error envelope and exception handlers.

Maps domain exceptions to the consistent HTTP error shape defined in the API contract:
``{"error": {"code": ..., "message": ...}}``.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from distil.adapters.llm.base import LlmUnavailableError
from distil.domain.errors import DomainError, UnsupportedContentError


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Build the standard error envelope response."""
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


async def _handle_unsupported(_: Request, exc: UnsupportedContentError) -> JSONResponse:
    return error_response(415, "unsupported_format", str(exc))


async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    # A domain-rule violation surfacing at the boundary is a bad request.
    return error_response(400, "domain_error", str(exc))


async def _handle_llm_unavailable(_: Request, exc: LlmUnavailableError) -> JSONResponse:
    # The LLM provider failed (rate limit, out of credit, timeout, outage): fail cleanly, not 500.
    return error_response(503, "llm_unavailable", str(exc))


def register_exception_handlers(app: FastAPI) -> None:
    """Register domain exception handlers on the app (most specific first)."""
    app.add_exception_handler(UnsupportedContentError, _handle_unsupported)  # type: ignore[arg-type]
    app.add_exception_handler(DomainError, _handle_domain_error)  # type: ignore[arg-type]
    app.add_exception_handler(LlmUnavailableError, _handle_llm_unavailable)  # type: ignore[arg-type]
