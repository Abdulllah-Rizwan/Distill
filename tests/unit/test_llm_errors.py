"""LLM failure handling (T048): provider errors become a clean LlmUnavailableError → 503.

Covers the message mapping (Gemini), retry-exhaustion wrapping (DeepSeek, offline via a mock
transport), and the end-to-end contract that an LLM failure during ingest surfaces as 503
`llm_unavailable` rather than an opaque 500.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import errors
from pydantic import BaseModel

from distil.adapters.llm.base import LlmUnavailableError
from distil.adapters.llm.deepseek._client import DeepSeekClient
from distil.adapters.llm.gemini._client import _unavailable_message
from distil.adapters.persistence.sqlite.schema import connect, initialize
from distil.api.dependencies import build_services, get_services
from distil.api.main import create_app
from distil.domain.material import Material
from distil.ports.llm import ExtractionResult
from tests._fakes.llm import FakeExplainer


class _Schema(BaseModel):
    answer: str


def test_gemini_message_mapping_is_user_facing() -> None:
    assert "rate limit" in _unavailable_message(errors.ClientError(429, {"error": {"code": 429}}))
    assert "credentials" in _unavailable_message(errors.ClientError(403, {"error": {"code": 403}}))
    assert "unavailable" in _unavailable_message(errors.ServerError(500, {"error": {"code": 500}}))


def test_deepseek_wraps_exhausted_retries_as_llm_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "overloaded"}})

    client = DeepSeekClient(
        api_key="k",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
        max_retries=2,
        base_delay=0.0,
        sleep=lambda _s: None,
    )
    with pytest.raises(LlmUnavailableError, match="unavailable"):
        client.generate_json(system_instruction="s", user_content="u", response_schema=_Schema)


class _RaisingExtractor:
    """A ConceptExtractor that fails as if the LLM provider were unreachable."""

    def extract(self, material: Material) -> ExtractionResult:
        raise LlmUnavailableError("The language model is over its rate limit right now. Try again.")


def test_llm_failure_during_ingest_returns_503() -> None:
    conn = connect(":memory:")
    initialize(conn)
    services = build_services(conn, _RaisingExtractor(), FakeExplainer())
    app = create_app()
    app.dependency_overrides[get_services] = lambda: services
    client = TestClient(app)

    resp = client.post(
        "/api/v1/materials",
        data={"workspace_id": "w"},
        files={"file": ("m.md", b"Alpha Beta", "application/octet-stream")},
    )
    assert resp.status_code == 503
    body = resp.json()
    assert body["error"]["code"] == "llm_unavailable"
    assert body["error"]["message"].strip()
