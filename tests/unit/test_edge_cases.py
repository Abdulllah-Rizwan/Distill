"""Edge-case tests (T046): empty/single material, too-small corpus, conflicting statements kept.

These pin the documented edge behaviours from spec.md: an empty upload is accepted but contributes
nothing; a corpus too small to rank returns an empty vital-few with an explanatory note (never an
arbitrary shortlist); and two materials that assert *different* relationships between the same pair
of concepts are both kept — the conflict is surfaced, not silently resolved (Principle I).
"""

from __future__ import annotations

from datetime import UTC, datetime

from distil.adapters.graph.networkx.analyzer import NetworkxGraphAnalyzer
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.source_reference import SourceReference
from distil.ports.llm import ConceptMention, ExtractionResult, RelationshipMention
from distil.services.graph_builder import GraphBuilder
from tests._fakes.wiring import make_client


def test_empty_material_accepted_as_empty_and_no_ranking() -> None:
    client = make_client(["Alpha", "Beta"])
    resp = client.post(
        "/api/v1/materials",
        data={"workspace_id": "we"},
        files={"file": ("empty.md", b"", "application/octet-stream")},
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "empty"
    # Empty material contributes no concepts, so no ranking was computed.
    assert client.get("/api/v1/vital-few", params={"workspace_id": "we"}).status_code == 404


def test_too_small_corpus_returns_empty_vital_few_with_note() -> None:
    client = make_client(["Alpha", "Beta", "Gamma"])  # only 3 concepts, below the minimum
    resp = client.post(
        "/api/v1/materials",
        data={"workspace_id": "ws"},
        files={"file": ("m.md", b"Alpha Beta Gamma", "application/octet-stream")},
    )
    assert resp.status_code == 201
    body = client.get("/api/v1/vital-few", params={"workspace_id": "ws"}).json()
    assert body["entries"] == []
    assert body["total_concepts"] == 3
    assert "note" in body  # explanatory, not an arbitrary shortlist


def _material(mid: str, content: str) -> Material:
    return Material(
        id=mid,
        workspace_id="w1",
        filename=f"{mid}.md",
        format=MaterialFormat.MARKDOWN,
        content_text=content,
        content_hash=mid,
        status=MaterialStatus.ACCEPTED,
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
    )


class _ConflictingExtractor:
    """Emits the same (A, B) concept pair in each material, with a different relationship kind."""

    def extract(self, material: Material) -> ExtractionResult:
        text = material.content_text
        a = SourceReference(material_id=material.id, start_offset=0, end_offset=1, quote=text[0:1])
        b = SourceReference(material_id=material.id, start_offset=2, end_offset=3, quote=text[2:3])
        kind = "causes" if "causes" in text else "prevents"
        return ExtractionResult(
            concepts=(ConceptMention("A", a), ConceptMention("B", b)),
            relationships=(RelationshipMention("A", "B", a, kind=kind),),
        )


def test_conflicting_cross_material_statements_are_both_kept() -> None:
    builder = GraphBuilder(_ConflictingExtractor(), NetworkxGraphAnalyzer())
    m1 = _material("m1", "A B causes")
    m2 = _material("m2", "A B prevents")

    _concepts, relationships = builder.build("w1", [m1, m2])

    # Both distinct claims survive — the conflict is surfaced, not silently merged/resolved.
    pairs = {(r.source_concept_id, r.target_concept_id, r.kind) for r in relationships}
    kinds = {r.kind for r in relationships}
    assert kinds == {"causes", "prevents"}
    assert len(pairs) == 2
