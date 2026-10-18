"""US1 (feature 002) read endpoints: the concept hierarchy and a single concept's subtree.

The forest is computed on read from the current concept graph (no new storage). Every non-root node
returned carries a non-empty, source-linked ``placement.grounding`` — the faithfulness guarantee —
because the builder only ever attaches a concept to a parent it shares a real relationship edge.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from distil.api.dependencies import Services, get_services
from distil.api.errors import error_response
from distil.api.serializers import hierarchy_node_view, hierarchy_view

router = APIRouter(prefix="/api/v1", tags=["hierarchy"])


@router.get("/hierarchy")
def get_hierarchy(
    workspace_id: str,
    services: Services = Depends(get_services),
) -> JSONResponse:
    """Return the workspace's concept hierarchy (roots → children) plus any unplaced concepts."""
    concepts = services.graph.list_concepts(workspace_id)
    if not concepts:
        return error_response(
            404, "no_graph", "No concept graph for this workspace yet. Upload material first."
        )
    relationships = services.graph.list_relationships(workspace_id)
    hierarchy = services.hierarchy.build(workspace_id, concepts, relationships)
    concepts_by_id = {c.id: c for c in concepts}
    return JSONResponse(content=hierarchy_view(hierarchy, concepts_by_id))


@router.get("/hierarchy/concepts/{concept_id}")
def get_hierarchy_subtree(
    concept_id: str,
    workspace_id: str,
    services: Services = Depends(get_services),
) -> JSONResponse:
    """Return the subtree rooted at ``concept_id`` (the concept plus its descendants)."""
    concepts = services.graph.list_concepts(workspace_id)
    if not concepts:
        return error_response(
            404, "no_graph", "No concept graph for this workspace yet. Upload material first."
        )
    relationships = services.graph.list_relationships(workspace_id)
    hierarchy = services.hierarchy.build(workspace_id, concepts, relationships)
    node = services.hierarchy.subtree(hierarchy, concept_id)
    if node is not None:
        concepts_by_id = {c.id: c for c in concepts}
        return JSONResponse(content=hierarchy_node_view(node, hierarchy, concepts_by_id))
    if concept_id in hierarchy.unplaced:
        return error_response(
            404, "unplaced", f"Concept {concept_id!r} has no relationships, so it has no subtree."
        )
    return error_response(404, "not_found", f"Concept {concept_id!r} not found.")
