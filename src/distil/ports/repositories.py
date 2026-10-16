"""Ports: persistence. Every method is scoped by ``workspace_id`` (Principle V isolation).

The SQLite adapter implements these for v1; the documented future target (Postgres + Neo4j) will
provide alternative implementations behind the same interfaces.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.ranking import RankingRun, VitalFewEntry
from distil.domain.relationship import Relationship


class MaterialRepository(Protocol):
    """Stores uploaded materials and their extracted text."""

    def add(self, material: Material) -> None: ...

    def get(self, workspace_id: str, material_id: str) -> Material | None: ...

    def list_all(self, workspace_id: str) -> list[Material]: ...

    def list_accepted(self, workspace_id: str) -> list[Material]:
        """Materials with status ACCEPTED — the ones that feed the graph."""
        ...

    def find_by_hash(self, workspace_id: str, content_hash: str) -> Material | None:
        """Used for duplicate detection (FR-014)."""
        ...

    def delete(self, workspace_id: str, material_id: str) -> bool:
        """Delete a material; return True if one was removed."""
        ...


class GraphRepository(Protocol):
    """Stores the derived concept graph and ranking results for a workspace."""

    def replace_graph(
        self,
        workspace_id: str,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
    ) -> None:
        """Atomically replace the workspace's concepts + relationships (batch rebuild, ADR-0007)."""
        ...

    def list_concepts(self, workspace_id: str) -> list[Concept]: ...

    def get_concept(self, workspace_id: str, concept_id: str) -> Concept | None: ...

    def list_relationships(self, workspace_id: str) -> list[Relationship]: ...

    def get_relationship(self, workspace_id: str, relationship_id: str) -> Relationship | None: ...

    def save_ranking(self, run: RankingRun, entries: Sequence[VitalFewEntry]) -> None: ...

    def latest_ranking(self, workspace_id: str) -> tuple[RankingRun, list[VitalFewEntry]] | None:
        """The most recent ranking run and its entries, or None if none computed yet."""
        ...
