"""Integration test (US3, T040): deleting a material prunes what it solely supported, and
re-uploading the same file dedups without inflating importance.

Runs the real pipeline (fake LLM + in-memory SQLite). M1 and M2 share Alpha/Beta; Zeta is unique to
M2; Gamma/Delta/Epsilon are unique to M1. Deleting M2 must drop Zeta and halve Alpha's recurrence;
re-uploading M1 must be a no-op duplicate.
"""

from __future__ import annotations

from tests._fakes.wiring import make_client

_KEYWORDS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]
_WS = "w3"
_M1 = "Alpha links Beta and Gamma. Delta and Epsilon appear."  # Alpha,Beta,Gamma,Delta,Epsilon
_M2 = "Alpha and Beta return. Zeta is unique here."  # Alpha,Beta,Zeta


def _upload(client, text: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/materials",
        data={"workspace_id": _WS},
        files={"file": ("note.md", text.encode("utf-8"), "application/octet-stream")},
    )


def _nodes(client) -> dict[str, dict]:  # type: ignore[no-untyped-def, type-arg]
    body = client.get("/api/v1/graph", params={"workspace_id": _WS}).json()
    return {n["label"]: n for n in body["nodes"]}


def test_delete_prunes_solely_supported_and_reupload_dedups() -> None:
    client = make_client(_KEYWORDS)
    assert _upload(client, _M1).status_code == 201
    r2 = _upload(client, _M2)
    assert r2.status_code == 201
    m2_id = r2.json()["id"]

    nodes = _nodes(client)
    assert {"Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"} <= set(nodes)
    assert nodes["Alpha"]["recurrence_count"] == 2  # in both materials

    # Delete M2 → rebuild from M1 only.
    deleted = client.delete(f"/api/v1/materials/{m2_id}", params={"workspace_id": _WS})
    assert deleted.status_code == 204

    after = _nodes(client)
    assert "Zeta" not in after  # solely supported by M2 → gone
    assert {"Alpha", "Beta", "Gamma", "Delta", "Epsilon"} <= set(after)
    assert after["Alpha"]["recurrence_count"] == 1  # now only M1 supports it

    # Re-upload M1 (identical bytes) → duplicate, no rebuild, no inflation.
    dup = _upload(client, _M1)
    assert dup.status_code == 200  # duplicate
    after_dup = _nodes(client)
    assert set(after_dup) == set(after)
    assert after_dup["Alpha"]["recurrence_count"] == 1  # unchanged (not inflated)
