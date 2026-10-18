"""Contract test: DELETE /api/v1/materials/{id} (T039, US3).

204 on success; 404 when the material is not in the given workspace; delete is workspace-scoped.
"""

from __future__ import annotations

from tests._fakes.wiring import make_client

_KEYWORDS = ["Alpha", "Beta"]
_WS = "wd"
_TEXT = "Alpha and Beta appear here."


def _upload(client, workspace_id: str = _WS) -> str:  # type: ignore[no-untyped-def]
    resp = client.post(
        "/api/v1/materials",
        data={"workspace_id": workspace_id},
        files={"file": ("m.md", _TEXT.encode("utf-8"), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_delete_removes_material_then_404_on_repeat() -> None:
    client = make_client(_KEYWORDS)
    material_id = _upload(client)

    resp = client.delete(f"/api/v1/materials/{material_id}", params={"workspace_id": _WS})
    assert resp.status_code == 204

    listing = client.get("/api/v1/materials", params={"workspace_id": _WS}).json()
    assert all(m["id"] != material_id for m in listing["materials"])

    again = client.delete(f"/api/v1/materials/{material_id}", params={"workspace_id": _WS})
    assert again.status_code == 404
    assert again.json()["error"]["code"] == "not_found"


def test_delete_unknown_material_returns_404() -> None:
    client = make_client(_KEYWORDS)
    resp = client.delete("/api/v1/materials/m_missing", params={"workspace_id": _WS})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_delete_is_workspace_scoped() -> None:
    client = make_client(_KEYWORDS)
    material_id = _upload(client, _WS)

    # Deleting from a different workspace must not touch this one.
    resp = client.delete(f"/api/v1/materials/{material_id}", params={"workspace_id": "other"})
    assert resp.status_code == 404

    listing = client.get("/api/v1/materials", params={"workspace_id": _WS}).json()
    assert any(m["id"] == material_id for m in listing["materials"])
