"""US1 read endpoints: the explainable 80/20 view and concept drill-down.

Both guarantee the contract-level faithfulness property — every entry and concept returned carries
a non-empty, verifiable ``evidence``/``sources`` array — because they serialize domain objects that
cannot be constructed without one.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from distil.api.dependencies import Services, get_services
from distil.api.errors import error_response
from distil.api.serializers import concept_detail, vital_few_view

router = APIRouter(prefix="/api/v1", tags=["vital-few"])


@router.get("/vital-few")
def get_vital_few(
    workspace_id: str,
    services: Services = Depends(get_services),
) -> JSONResponse:
    """Return the latest ranking run's vital-few list, each entry explained and source-linked."""
    result = services.graph.latest_ranking(workspace_id)
    if result is None:
        return error_response(
            404,
            "no_ranking",
            "No ranking has been computed for this workspace yet. Upload material first.",
        )
    run, entries = result
    concepts = services.graph.list_concepts(workspace_id)
    concepts_by_id = {c.id: c for c in concepts}
    body = vital_few_view(run, entries, concepts_by_id, total_concepts=len(concepts))
    return JSONResponse(content=body)


@router.get("/concepts/{concept_id}")
def get_concept(
    concept_id: str,
    workspace_id: str,
    services: Services = Depends(get_services),
) -> JSONResponse:
    """Return one concept with its provenance (FR-012), or 404 if not in this workspace."""
    concept = services.graph.get_concept(workspace_id, concept_id)
    if concept is None:
        return error_response(404, "not_found", f"Concept {concept_id!r} not found.")
    return JSONResponse(content=concept_detail(concept))
