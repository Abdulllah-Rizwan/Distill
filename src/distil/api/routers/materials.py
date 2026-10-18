"""US1 materials endpoints: upload a note and list a workspace's materials.

Thin delivery layer: it reads the request, calls the pipeline, and maps the outcome to a status
code per the contract. Domain errors (e.g. unsupported content) propagate to the registered
exception handlers, which render the error envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import JSONResponse

from distil.api.dependencies import Services, get_services
from distil.api.errors import error_response
from distil.api.serializers import material_summary
from distil.domain.material import MaterialStatus

router = APIRouter(prefix="/api/v1", tags=["materials"])


@router.post("/materials")
async def upload_material(
    workspace_id: str = Form(...),
    file: UploadFile = File(...),
    services: Services = Depends(get_services),
) -> JSONResponse:
    """Ingest one note; (re)build the graph + ranking when it adds a new accepted material.

    Status codes (contract): ``201`` accepted, ``200`` duplicate, ``202`` empty, ``415``
    unsupported.
    """
    data = await file.read()
    result = services.pipeline.ingest(workspace_id, file.filename or "", data)
    body = material_summary(result.material)

    if result.duplicate:
        status_code = 200
    elif result.material.status is MaterialStatus.EMPTY:
        status_code = 202
    else:
        status_code = 201
    return JSONResponse(status_code=status_code, content=body)


@router.get("/materials")
def list_materials(
    workspace_id: str,
    services: Services = Depends(get_services),
) -> JSONResponse:
    """List every material in the workspace (newest-last, as stored)."""
    materials = services.materials.list_all(workspace_id)
    return JSONResponse(content={"materials": [material_summary(m) for m in materials]})


@router.delete("/materials/{material_id}")
def delete_material(
    material_id: str,
    workspace_id: str,
    services: Services = Depends(get_services),
) -> Response:
    """Remove a material and rebuild the graph + ranking (US3, FR-013).

    ``204`` on success; ``404`` if the material is not in this workspace.
    """
    deleted = services.pipeline.remove_material(workspace_id, material_id)
    if not deleted:
        return error_response(404, "not_found", f"Material {material_id!r} not found.")
    return Response(status_code=204)
