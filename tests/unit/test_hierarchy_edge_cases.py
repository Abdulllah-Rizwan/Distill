"""Edge-case tests for HierarchyService (T023): disconnected graphs, flat stars, and tiny corpora.

The hierarchy must degrade gracefully — never fabricating depth or links — and always keep full
coverage (every concept placed or unplaced, exactly once).
"""

from __future__ import annotations

from distil.domain.concept import Concept
from distil.domain.relationship import Relationship
from distil.services.hierarchy import HierarchyService

_WS = "w"


def _concept(cid: str, pagerank: float, degree: float = 0.0) -> Concept:
    from distil.domain.source_reference import SourceReference

    ref = SourceReference(material_id="m1", start_offset=0, end_offset=3, quote="abc")
    return Concept(
        id=cid,
        workspace_id=_WS,
        label=cid.upper(),
        sources=(ref,),
        recurrence_count=1,
        centrality={"pagerank": pagerank, "degree": degree},
    )


def _rel(rid: str, a: str, b: str) -> Relationship:
    from distil.domain.source_reference import SourceReference

    ref = SourceReference(material_id="m1", start_offset=0, end_offset=5, quote="links")
    return Relationship(
        id=rid, workspace_id=_WS, source_concept_id=a, target_concept_id=b, sources=(ref,)
    )


def test_fully_disconnected_graph_roots_pillars_rest_unplaced() -> None:
    # 7 concepts, no relationships: top 5 become isolated pillar roots, the other 2 are unplaced.
    concepts = [_concept(f"c{i}", pagerank=1.0 - i * 0.1) for i in range(1, 8)]
    h = HierarchyService().build(_WS, concepts, [])

    assert len(h.roots) == 5
    for root in h.roots:
        node = h.nodes[root]
        assert node.is_pillar and node.children == ()  # isolated pillar, no fabricated children
    assert len(h.unplaced) == 2
    assert set(h.nodes) | set(h.unplaced) == {c.id for c in concepts}  # coverage


def test_flat_star_graph_stays_shallow() -> None:
    # A hub connected to many leaves: broad and shallow, never an invented deep chain.
    hub = _concept("hub", pagerank=0.9, degree=7.0)
    leaves = [_concept(f"l{i}", pagerank=0.2, degree=1.0) for i in range(1, 8)]
    rels = [_rel(f"e{i}", "hub", f"l{i}") for i in range(1, 8)]
    h = HierarchyService().build(_WS, [hub, *leaves], rels)

    assert "hub" in h.roots  # the hub is a pillar root
    assert max(node.depth for node in h.nodes.values()) <= 2  # shallow: no fabricated depth
    assert set(h.nodes) | set(h.unplaced) == {"hub"} | {leaf.id for leaf in leaves}


def test_single_concept_corpus_is_all_unplaced() -> None:
    h = HierarchyService().build(_WS, [_concept("only", pagerank=0.5)], [])
    assert h.roots == ()
    assert h.unplaced == ("only",)
    assert h.total_concepts == 1
