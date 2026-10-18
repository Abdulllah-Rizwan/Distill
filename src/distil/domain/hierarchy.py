"""Concept hierarchy value objects — a computed forest over the concept graph (feature 002).

Immutable and built on read (not persisted, research.md D5). A :class:`HierarchyNode` places one
concept under a single parent via a **real relationship edge** (its ``grounding``), so the tree is
faithful by construction (Principle I): a node with a parent always carries that edge's source
passages. A :class:`ConceptHierarchy` holds the roots, every placed node, and any edge-less concepts
surfaced as ``unplaced`` — every concept appears exactly once (coverage, SC-002).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from distil.domain.errors import DomainError
from distil.domain.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    """One concept's place in the forest.

    A root has ``parent_concept_id is None``, ``depth == 0`` and empty ``grounding`` (its own
    grounding is the concept's sources). A non-root carries the relationship that links it to its
    parent: ``grounding`` is that edge's source passage(s) and MUST be non-empty.
    """

    concept_id: str
    parent_concept_id: str | None
    depth: int
    is_pillar: bool
    children: tuple[str, ...]
    placement_reason: str
    grounding: tuple[SourceReference, ...]
    grounding_edge_id: str | None = None

    def __post_init__(self) -> None:
        if self.concept_id == self.parent_concept_id:
            raise DomainError("HierarchyNode cannot be its own parent")
        if not self.placement_reason.strip():
            raise DomainError("HierarchyNode.placement_reason must be non-empty")
        if self.parent_concept_id is None:
            if self.depth != 0:
                raise DomainError("A root HierarchyNode must have depth 0")
            if self.grounding:
                raise DomainError("A root HierarchyNode must have empty grounding")
            if self.grounding_edge_id is not None:
                raise DomainError("A root HierarchyNode must have no grounding edge")
        else:
            if self.depth < 1:
                raise DomainError("A non-root HierarchyNode must have depth >= 1")
            if not self.grounding:
                raise DomainError(
                    "A non-root HierarchyNode must have >= 1 grounding source (faithfulness)"
                )
            if self.grounding_edge_id is None:
                raise DomainError("A non-root HierarchyNode must name its grounding edge")

    @property
    def is_root(self) -> bool:
        return self.parent_concept_id is None


@dataclass(frozen=True, slots=True)
class ConceptHierarchy:
    """The whole forest for one build of a workspace's concept graph."""

    workspace_id: str
    roots: tuple[str, ...]
    nodes: Mapping[str, HierarchyNode]
    unplaced: tuple[str, ...]
    total_concepts: int

    def __post_init__(self) -> None:
        placed = set(self.nodes)
        unplaced = set(self.unplaced)
        if len(unplaced) != len(self.unplaced):
            raise DomainError("ConceptHierarchy.unplaced contains duplicates")
        overlap = placed & unplaced
        if overlap:
            raise DomainError(f"Concepts both placed and unplaced: {sorted(overlap)}")
        if len(placed) + len(unplaced) != self.total_concepts:
            raise DomainError(
                "Coverage invariant violated: placed + unplaced must equal total_concepts "
                f"({len(placed)} + {len(unplaced)} != {self.total_concepts})"
            )
        for root_id in self.roots:
            node = self.nodes.get(root_id)
            if node is None:
                raise DomainError(f"Root {root_id!r} is missing from nodes")
            if not node.is_root:
                raise DomainError(f"Root {root_id!r} has a parent")
