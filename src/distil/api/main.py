"""FastAPI application entry point.

Thin delivery layer over the core services. User-story routers are included as they are built; the
core stays framework-agnostic behind the ports.
"""

from __future__ import annotations

from fastapi import FastAPI

from distil.api.errors import register_exception_handlers
from distil.logging_setup import configure_logging


def create_app() -> FastAPI:
    """Application factory: build and configure the FastAPI app."""
    configure_logging()
    app = FastAPI(
        title="Distil API",
        version="0.1.0",
        summary="Ingest notes, build a concept graph, surface the explainable 80/20.",
    )
    register_exception_handlers(app)

    @app.get("/api/v1/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # US1/US2/US3 routers are wired here as they are implemented.
    return app


app = create_app()
