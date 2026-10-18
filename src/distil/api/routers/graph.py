"""US2 read endpoints: explore the concept graph and inspect a single relationship.

Every node exposes its graph signals (centrality, recurrence) and every edge exposes the source
passage(s) that assert the relationship — the contract-level faithfulness guarantee, which holds by
construction because a ``Relationship`` cannot exist without at least one source.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from distil.api.dependencies import Services, get_services
from distil.api.errors import error_response
from distil.api.serializers import graph_edge, graph_view

router = APIRouter(prefix="/api/v1", tags=["graph"])


@router.get("/graph")
def get_graph(
    workspace_id: str,
    services: Services = Depends(get_services),
) -> JSONResponse:
    """Return the workspace's concept graph: nodes (label, centrality, recurrence) + edges."""
    concepts = services.graph.list_concepts(workspace_id)
    relationships = services.graph.list_relationships(workspace_id)
    return JSONResponse(content=graph_view(concepts, relationships))


@router.get("/graph/edges/{edge_id}")
def get_edge(
    edge_id: str,
    workspace_id: str,
    services: Services = Depends(get_services),
) -> JSONResponse:
    """Return one relationship with its provenance (FR-006), or 404 if not in this workspace."""
    relationship = services.graph.get_relationship(workspace_id, edge_id)
    if relationship is None:
        return error_response(404, "not_found", f"Relationship {edge_id!r} not found.")
    return JSONResponse(content=graph_edge(relationship))
