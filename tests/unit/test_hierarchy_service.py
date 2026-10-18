"""Unit tests for HierarchyService (T005, T013): root selection, BFS parenting, tie-breaking,
grounded placement, coverage/unplaced, and determinism — all offline and deterministic.

Scores are controlled via distinct PageRank (the dominant weight) with equal degree/recurrence, so
the composite order is c1 > c2 > ... > c8. With 8 concepts the vital-few target (5) makes c1..c5 the
pillar roots; c6/c7 form a two-level branch; c8 is edge-less and therefore unplaced.
"""

from __future__ import annotations

from distil.domain.concept import Concept
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference
from distil.services.hierarchy import HierarchyService

_WS = "w"


def _concept(cid: str, pagerank: float) -> Concept:
    ref = SourceReference(material_id="m1", start_offset=0, end_offset=3, quote="abc")
    return Concept(
        id=cid,
        workspace_id=_WS,
        label=cid.upper(),
        sources=(ref,),
        recurrence_count=1,
        centrality={"pagerank": pagerank, "degree": 1.0},
    )


def _rel(
    rid: str, a: str, b: str, quote: str = "a links b", kind: str | None = None
) -> Relationship:
    ref = SourceReference(material_id="m1", start_offset=0, end_offset=len(quote), quote=quote)
    return Relationship(
        id=rid,
        workspace_id=_WS,
        source_concept_id=a,
        target_concept_id=b,
        sources=(ref,),
        kind=kind,
    )


def _graph() -> tuple[list[Concept], list[Relationship]]:
    concepts = [_concept(f"c{i}", pagerank=1.0 - i * 0.1) for i in range(1, 9)]  # c1..c8
    relationships = [
        _rel("e_16", "c1", "c6"),  # c6 adjacent to two pillars (c1, c2) → picks c1 (higher score)
        _rel("e_26", "c2", "c6"),
        _rel("e_67", "c6", "c7", quote="six to seven", kind="leads to"),  # c7 only via c6 → depth 2
    ]  # c3, c4, c5 isolated pillars; c8 isolated non-pillar → unplaced
    return concepts, relationships


def test_roots_are_the_vital_few_pillars_in_score_order() -> None:
    concepts, relationships = _graph()
    h = HierarchyService().build(_WS, concepts, relationships)
    assert h.roots == ("c1", "c2", "c3", "c4", "c5")  # top 5 by score
    assert all(h.nodes[r].is_pillar for r in h.roots)
    assert all(h.nodes[r].parent_concept_id is None for r in h.roots)


def test_bfs_assigns_single_nearest_parent_with_tie_break() -> None:
    concepts, relationships = _graph()
    h = HierarchyService().build(_WS, concepts, relationships)
    # c6 is adjacent to pillars c1 and c2 at the same distance → the higher-scoring c1 wins.
    assert h.nodes["c6"].parent_concept_id == "c1"
    assert h.nodes["c6"].depth == 1
    assert "c6" in h.nodes["c1"].children
    # c7 is reachable only through c6 → depth 2 under c6.
    assert h.nodes["c7"].parent_concept_id == "c6"
    assert h.nodes["c7"].depth == 2


def test_non_root_placement_is_grounded_in_a_real_edge() -> None:
    concepts, relationships = _graph()
    h = HierarchyService().build(_WS, concepts, relationships)
    c6 = h.nodes["c6"]
    assert c6.grounding, "non-root must carry the connecting edge's sources (faithfulness)"
    assert c6.grounding_edge_id == "e_16"  # smallest-id edge connecting c1 and c6
    assert c6.grounding[0].quote == "a links b"
    # c7's reason cites its parent and the edge quote (US2, deterministic — no LLM).
    assert "C6" in h.nodes["c7"].placement_reason
    assert "six to seven" in h.nodes["c7"].placement_reason
    # A root's reason cites its importance, not a parent.
    assert "core idea" in h.nodes["c1"].placement_reason


def test_edge_less_concept_is_unplaced_not_linked() -> None:
    concepts, relationships = _graph()
    h = HierarchyService().build(_WS, concepts, relationships)
    assert "c8" in h.unplaced
    assert "c8" not in h.nodes  # never given a parent (Principle I)


def test_coverage_every_concept_exactly_once() -> None:
    concepts, relationships = _graph()
    h = HierarchyService().build(_WS, concepts, relationships)
    assert set(h.nodes) | set(h.unplaced) == {c.id for c in concepts}
    assert set(h.nodes).isdisjoint(h.unplaced)
    assert h.total_concepts == len(concepts)


def test_build_is_deterministic() -> None:
    concepts, relationships = _graph()
    a = HierarchyService().build(_WS, concepts, relationships)
    b = HierarchyService().build(_WS, concepts, relationships)
    assert a.roots == b.roots
    assert a.unplaced == b.unplaced
    assert {k: v.parent_concept_id for k, v in a.nodes.items()} == {
        k: v.parent_concept_id for k, v in b.nodes.items()
    }


def test_too_small_corpus_has_no_roots_all_unplaced() -> None:
    concepts = [_concept(f"c{i}", pagerank=0.5) for i in range(1, 4)]  # 3 < minimum
    h = HierarchyService().build(_WS, concepts, [])
    assert h.roots == ()
    assert set(h.unplaced) == {c.id for c in concepts}
