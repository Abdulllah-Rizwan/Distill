"""Unit tests for the hierarchy value objects (T004): grounding rules + coverage invariant."""

from __future__ import annotations

import pytest

from distil.domain.errors import DomainError
from distil.domain.hierarchy import ConceptHierarchy, HierarchyNode
from distil.domain.source_reference import SourceReference

_REF = SourceReference(material_id="m1", start_offset=0, end_offset=4, quote="word")


def _root(cid: str = "r", children: tuple[str, ...] = ()) -> HierarchyNode:
    return HierarchyNode(cid, None, 0, True, children, "a core idea", ())


def _child(cid: str = "c", parent: str = "r") -> HierarchyNode:
    return HierarchyNode(cid, parent, 1, False, (), "linked", (_REF,), grounding_edge_id="e1")


def test_valid_root_and_child_construct() -> None:
    _root()
    _child()


def test_node_cannot_be_its_own_parent() -> None:
    with pytest.raises(DomainError):
        HierarchyNode("x", "x", 1, False, (), "r", (_REF,), grounding_edge_id="e")


def test_root_must_have_empty_grounding_and_no_edge() -> None:
    with pytest.raises(DomainError):
        HierarchyNode("r", None, 0, True, (), "r", (_REF,))
    with pytest.raises(DomainError):
        HierarchyNode("r", None, 0, True, (), "r", (), grounding_edge_id="e1")


def test_non_root_requires_grounding_and_edge_and_depth() -> None:
    with pytest.raises(DomainError):  # empty grounding
        HierarchyNode("c", "r", 1, False, (), "r", (), grounding_edge_id="e1")
    with pytest.raises(DomainError):  # missing edge id
        HierarchyNode("c", "r", 1, False, (), "r", (_REF,), grounding_edge_id=None)
    with pytest.raises(DomainError):  # depth < 1
        HierarchyNode("c", "r", 0, False, (), "r", (_REF,), grounding_edge_id="e1")


def test_empty_placement_reason_rejected() -> None:
    with pytest.raises(DomainError):
        HierarchyNode("r", None, 0, True, (), "   ", ())


def test_coverage_invariant_holds_for_valid_forest() -> None:
    hierarchy = ConceptHierarchy(
        "w", ("r",), {"r": _root("r", ("c",)), "c": _child("c", "r")}, (), 2
    )
    assert hierarchy.total_concepts == 2


def test_coverage_violation_when_counts_mismatch() -> None:
    with pytest.raises(DomainError):
        ConceptHierarchy("w", ("r",), {"r": _root("r")}, (), 5)  # 1 placed + 0 unplaced != 5


def test_placed_and_unplaced_must_be_disjoint() -> None:
    with pytest.raises(DomainError):
        ConceptHierarchy("w", ("r",), {"r": _root("r")}, ("r",), 1)  # 'r' in both


def test_root_must_exist_in_nodes() -> None:
    with pytest.raises(DomainError):
        ConceptHierarchy("w", ("missing",), {}, (), 0)
