"""Smoke tests for the FastAPI skeleton (T013) and the LLM fakes (T012)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from distil.api.main import create_app
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.ports.llm import ConceptExtractor, Explainer
from tests._fakes.llm import FakeExplainer, FakeExtractor


def test_health_endpoint_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_fakes_satisfy_ports_structurally() -> None:
    # Structural typing: the fakes are usable wherever the ports are expected.
    extractor: ConceptExtractor = FakeExtractor(["Alpha", "Beta"])
    explainer: Explainer = FakeExplainer()
    assert extractor is not None and explainer is not None


def test_fake_extractor_grounds_every_mention() -> None:
    content = "Alpha leads to Beta and Beta needs Alpha."
    material = Material(
        id="m1",
        workspace_id="w1",
        filename="n.md",
        format=MaterialFormat.MARKDOWN,
        content_text=content,
        content_hash="h",
        status=MaterialStatus.ACCEPTED,
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
    )
    result = FakeExtractor(["Alpha", "Beta"]).extract(material)

    assert {m.label for m in result.concepts} == {"Alpha", "Beta"}
    # Every mention is faithful to the source text.
    for mention in result.concepts:
        assert mention.source.is_faithful_to(content)
