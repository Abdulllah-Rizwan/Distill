"""Unit tests for the NetworkX graph-signal analyzer (T021)."""

from __future__ import annotations

from distil.adapters.graph.networkx.analyzer import NetworkxGraphAnalyzer
from distil.domain.concept import Concept
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference

_SRC = SourceReference(material_id="m1", start_offset=0, end_offset=3, quote="abc")


def _concept(cid: str) -> Concept:
    return Concept(id=cid, workspace_id="w1", label=cid, sources=(_SRC,), recurrence_count=1)


def _edge(src: str, tgt: str) -> Relationship:
    return Relationship(
        id=f"e_{src}{tgt}",
        workspace_id="w1",
        source_concept_id=src,
        target_concept_id=tgt,
        sources=(_SRC,),
    )


def test_empty_graph_returns_no_signals() -> None:
    assert NetworkxGraphAnalyzer().compute_signals([], []) == {}


def test_star_graph_center_is_most_central() -> None:
    # center connected to three leaves
    concepts = [_concept(c) for c in ("center", "a", "b", "c")]
    edges = [_edge("center", "a"), _edge("center", "b"), _edge("center", "c")]
    signals = NetworkxGraphAnalyzer().compute_signals(concepts, edges)

    assert signals["center"]["degree"] == 3.0
    assert signals["a"]["degree"] == 1.0
    # The hub carries the highest PageRank.
    assert signals["center"]["pagerank"] > signals["a"]["pagerank"]


def test_no_edges_gives_uniform_pagerank() -> None:
    concepts = [_concept("a"), _concept("b")]
    signals = NetworkxGraphAnalyzer().compute_signals(concepts, [])
    assert signals["a"]["degree"] == 0.0
    assert signals["a"]["pagerank"] == signals["b"]["pagerank"] == 0.5
