"""Tests for GraphBuilder: merge across materials, relationships, and the provenance gate (T026)."""

from __future__ import annotations

from datetime import UTC, datetime

from distil.adapters.graph.networkx.analyzer import NetworkxGraphAnalyzer
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.source_reference import SourceReference
from distil.ports.llm import ConceptMention, ExtractionResult
from distil.services.graph_builder import GraphBuilder
from tests._fakes.llm import FakeExtractor


def _material(mid: str, content: str) -> Material:
    return Material(
        id=mid,
        workspace_id="w1",
        filename=f"{mid}.md",
        format=MaterialFormat.MARKDOWN,
        content_text=content,
        content_hash=mid,
        status=MaterialStatus.ACCEPTED,
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
    )


def test_merges_same_concept_across_materials() -> None:
    m1 = _material("m1", "Alpha leads to Beta")
    m2 = _material("m2", "Beta and Alpha again")
    builder = GraphBuilder(FakeExtractor(["Alpha", "Beta"]), NetworkxGraphAnalyzer())

    concepts, relationships = builder.build("w1", [m1, m2])

    by_label = {c.label: c for c in concepts}
    assert set(by_label) == {"Alpha", "Beta"}
    # Alpha appears in both materials → recurrence 2.
    assert by_label["Alpha"].recurrence_count == 2
    # Centrality was attached and there is a relationship between the two.
    assert by_label["Alpha"].centrality is not None
    assert len(relationships) >= 1


def test_provenance_gate_drops_ungrounded_mentions() -> None:
    """An extractor that cites a span not in the text yields no concepts."""

    class LyingExtractor:
        def extract(self, material: Material) -> ExtractionResult:
            bad = SourceReference(
                material_id=material.id, start_offset=0, end_offset=10, quote="NOT IN TEXT"
            )
            return ExtractionResult(
                concepts=(ConceptMention(label="Ghost", source=bad),),
                relationships=(),
            )

    builder = GraphBuilder(LyingExtractor(), NetworkxGraphAnalyzer())
    concepts, relationships = builder.build("w1", [_material("m1", "real content here")])

    assert concepts == []  # ungrounded concept was dropped (Principle I)
    assert relationships == []
