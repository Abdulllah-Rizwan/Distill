"""Unit tests for the hierarchy eval scorer (T021): structural faithfulness + coverage gates.

A faithful forest scores 100% structural and full coverage; an unfaithful parent link (an edge whose
quote does not match the source text) fails the gate — the regression guard for Principle I on the
tree structure.
"""

from __future__ import annotations

from datetime import UTC, datetime

from evals.harness.hierarchy import score_hierarchy

from distil.domain.concept import Concept
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference

_WS = "w"
_CONTENT = "alpha beta gamma delta epsilon zeta"  # words at known offsets


def _material() -> Material:
    return Material(
        id="m1",
        workspace_id=_WS,
        filename="n.txt",
        format=MaterialFormat.TEXT,
        content_text=_CONTENT,
        content_hash="h",
        status=MaterialStatus.ACCEPTED,
        created_at=datetime(2026, 10, 18, tzinfo=UTC),
    )


def _ref(start: int, end: int) -> SourceReference:
    return SourceReference(
        material_id="m1", start_offset=start, end_offset=end, quote=_CONTENT[start:end]
    )


def _concept(cid: str, label: str, start: int, end: int, pagerank: float) -> Concept:
    return Concept(
        id=cid,
        workspace_id=_WS,
        label=label,
        sources=(_ref(start, end),),
        recurrence_count=1,
        centrality={"pagerank": pagerank, "degree": 1.0},
    )


def _concepts() -> list[Concept]:
    spans = [
        ("c1", "alpha", 0, 5),
        ("c2", "beta", 6, 10),
        ("c3", "gamma", 11, 16),
        ("c4", "delta", 17, 22),
        ("c5", "epsilon", 23, 30),
        ("c6", "zeta", 31, 35),
    ]
    return [
        _concept(cid, label, s, e, pagerank=0.9 - i * 0.1)
        for i, (cid, label, s, e) in enumerate(spans)
    ]


def test_faithful_forest_passes_structure_and_coverage() -> None:
    # c6 (lowest score) is the only non-root; its edge to pillar c1 is faithful.
    rel = Relationship(
        id="e_16",
        workspace_id=_WS,
        source_concept_id="c1",
        target_concept_id="c6",
        sources=(_ref(0, 10),),  # "alpha beta" — faithful
    )
    result = score_hierarchy([_material()], _concepts(), [rel], important_keys={"alpha", "beta"})

    assert result.passed
    assert result.structural_score == 1.0
    assert result.link_total == 1 and result.link_grounded == 1
    assert result.covered
    assert set(result.pillar_labels) == {"alpha", "beta", "gamma", "delta", "epsilon"}
    assert result.root_recall == 1.0  # both important concepts are pillars


def test_unfaithful_parent_link_fails_the_gate() -> None:
    rel = Relationship(
        id="e_16",
        workspace_id=_WS,
        source_concept_id="c1",
        target_concept_id="c6",
        sources=(SourceReference(material_id="m1", start_offset=0, end_offset=3, quote="zzz"),),
    )
    result = score_hierarchy([_material()], _concepts(), [rel], important_keys={"alpha"})

    assert not result.passed
    assert result.structural_score < 1.0
    assert result.link_violations
