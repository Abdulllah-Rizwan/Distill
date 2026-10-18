"""Integration tests for the concept hierarchy (T007, T017, T018, US1/US3).

Runs the real pipeline (fake LLM + in-memory SQLite). Verifies that every parent→child link is an
actual relationship edge (faithful structure), that coverage is exact, and that the hierarchy is
reproducible and reflects materials being added/removed.
"""

from __future__ import annotations

from typing import Any

from tests._fakes.wiring import make_client

_KEYWORDS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota"]
_WS = "wi"
_M1 = (
    "Alpha relates to Beta. Beta relates to Gamma. Gamma relates to Delta. "
    "Delta relates to Epsilon. Epsilon relates to Zeta. Zeta relates to Eta. Eta relates to Theta."
)
_M2 = "Alpha relates to Iota."  # introduces Iota, connected to the existing Alpha


def _upload(client, text: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/materials",
        data={"workspace_id": _WS},
        files={"file": ("note.md", text.encode("utf-8"), "application/octet-stream")},
    )


def _walk(node: dict[str, Any], out: list[tuple[str, str | None, str | None]]) -> None:
    """Collect (concept_id, parent_id, grounding_edge_id) for every node, recursively."""
    parent = None if node["depth"] == 0 else node.get("_parent")
    out.append((node["concept"]["id"], parent, node["placement"]["grounding_edge_id"]))
    for child in node["children"]:
        child["_parent"] = node["concept"]["id"]
        _walk(child, out)


def test_every_parent_child_link_is_a_real_edge() -> None:
    client = make_client(_KEYWORDS)
    assert _upload(client, _M1).status_code == 201

    graph = client.get("/api/v1/graph", params={"workspace_id": _WS}).json()
    edges = {e["id"]: {e["source"], e["target"]} for e in graph["edges"]}

    body = client.get("/api/v1/hierarchy", params={"workspace_id": _WS}).json()
    collected: list[tuple[str, str | None, str | None]] = []
    for root in body["roots"]:
        _walk(root, collected)

    for cid, parent_id, edge_id in collected:
        if parent_id is None:
            continue  # root
        assert edge_id in edges, "non-root placement must name a real edge"
        assert edges[edge_id] == {cid, parent_id}, "edge must connect the node and its parent"


def test_coverage_matches_full_concept_set() -> None:
    client = make_client(_KEYWORDS)
    _upload(client, _M1)

    graph = client.get("/api/v1/graph", params={"workspace_id": _WS}).json()
    all_ids = {n["id"] for n in graph["nodes"]}

    body = client.get("/api/v1/hierarchy", params={"workspace_id": _WS}).json()
    placed: list[tuple[str, str | None, str | None]] = []
    for root in body["roots"]:
        _walk(root, placed)
    placed_ids = {cid for cid, _, _ in placed}
    unplaced_ids = {u["id"] for u in body["unplaced"]}

    assert placed_ids | unplaced_ids == all_ids  # every concept appears
    assert placed_ids.isdisjoint(unplaced_ids)  # exactly once


def test_reproducible_and_reflects_add_then_delete() -> None:
    client = make_client(_KEYWORDS)
    _upload(client, _M1)

    first = client.get("/api/v1/hierarchy", params={"workspace_id": _WS}).json()
    second = client.get("/api/v1/hierarchy", params={"workspace_id": _WS}).json()
    assert first == second  # deterministic: same corpus → identical tree

    assert "Iota" not in _concept_labels(client)

    r2 = _upload(client, _M2)
    assert r2.status_code == 201
    assert "Iota" in _concept_labels(client)  # added material's concept now appears

    deleted = client.delete(f"/api/v1/materials/{r2.json()['id']}", params={"workspace_id": _WS})
    assert deleted.status_code == 204
    assert "Iota" not in _concept_labels(client)  # removed with its sole source


def _concept_labels(client) -> set[str]:  # type: ignore[no-untyped-def]
    graph = client.get("/api/v1/graph", params={"workspace_id": _WS}).json()
    return {n["label"] for n in graph["nodes"]}
