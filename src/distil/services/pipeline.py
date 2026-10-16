"""Batch pipeline orchestration (ADR-0007): ingest a material, then rebuild the whole view.

The 80/20 is computed as a batch over the full corpus on every change, not incrementally — simpler
to reason about and keep faithful (Principle VI). ``ingest`` stores one upload and, when it adds a
new accepted material, rebuilds; ``rebuild`` runs the extract → merge → graph → rank chain and
persists the result atomically per store.
"""

from __future__ import annotations

from distil.domain.material import MaterialStatus
from distil.domain.ranking import RankingRun
from distil.ports.repositories import (
    GraphRepository,
    MaterialRepository,
    WorkspaceRepository,
)
from distil.services.graph_builder import GraphBuilder
from distil.services.ingestion import IngestionService, IngestResult
from distil.services.ranking import RankingService


class Pipeline:
    """Wires ingestion, graph building, and ranking into the on-upload batch workflow."""

    def __init__(
        self,
        workspaces: WorkspaceRepository,
        materials: MaterialRepository,
        graph: GraphRepository,
        ingestion: IngestionService,
        builder: GraphBuilder,
        ranking: RankingService,
    ) -> None:
        self._workspaces = workspaces
        self._materials = materials
        self._graph = graph
        self._ingestion = ingestion
        self._builder = builder
        self._ranking = ranking

    def ingest(self, workspace_id: str, filename: str, data: bytes) -> IngestResult:
        """Store one upload; rebuild the graph + ranking if it added a new accepted material."""
        self._workspaces.ensure(workspace_id)
        result = self._ingestion.ingest(workspace_id, filename, data)
        # Duplicates change nothing; empty/rejected materials contribute no concepts. Only a fresh
        # accepted material alters the corpus and warrants recomputing the batch view.
        if not result.duplicate and result.material.status is MaterialStatus.ACCEPTED:
            self.rebuild(workspace_id)
        return result

    def rebuild(self, workspace_id: str) -> RankingRun:
        """Recompute the concept graph and the 80/20 ranking for the whole workspace."""
        self._workspaces.ensure(workspace_id)
        materials = self._materials.list_accepted(workspace_id)
        concepts, relationships = self._builder.build(workspace_id, materials)
        self._graph.replace_graph(workspace_id, concepts, relationships)
        run, entries = self._ranking.rank(workspace_id, concepts, relationships, materials)
        self._graph.save_ranking(run, entries)
        return run
