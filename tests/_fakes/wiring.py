"""Build a TestClient wired to the deterministic LLM fakes and an in-memory SQLite DB.

Contract and integration tests call :func:`make_client` so they exercise the real app, routers,
pipeline, and persistence — only the LLM ports are faked (no network, no cost, Principle VII).
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi.testclient import TestClient

from distil.adapters.persistence.sqlite.schema import connect, initialize
from distil.api.dependencies import build_services, get_services
from distil.api.main import create_app
from tests._fakes.llm import FakeExplainer, FakeExtractor


def make_client(keywords: Sequence[str]) -> TestClient:
    """A TestClient whose extractor finds ``keywords`` in uploaded text; one shared in-memory DB."""
    conn = connect(":memory:")
    initialize(conn)
    services = build_services(conn, FakeExtractor(keywords), FakeExplainer())

    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    return TestClient(app)
