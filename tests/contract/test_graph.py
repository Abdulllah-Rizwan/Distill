"""Contract test: GET /api/v1/graph and /graph/edges/{id} (T034, US2).

Nodes carry label + graph signals; every edge carries non-empty, faithful source provenance
(quote == cited material text at [start:end]). A single edge is retrievable with its provenance.
"""

from __future__ import annotations

from tests._fakes.wiring import make_client

_KEYWORDS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]
_WS = "wg"
_M1 = "Alpha leads to Beta and Gamma. Delta and Epsilon follow. Zeta concludes."


def _corpus(client) -> dict[str, str]:  # type: ignore[no-untyped-def]
    resp = client.post(
        "/api/v1/materials",
        data={"workspace_id": _WS},
        files={"file": ("m1.md", _M1.encode("utf-8"), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    return {resp.json()["id"]: _M1}


def test_graph_nodes_and_edges_shapes_and_faithful() -> None:
    client = make_client(_KEYWORDS)
    contents = _corpus(client)

    resp = client.get("/api/v1/graph", params={"workspace_id": _WS})
    assert resp.status_code == 200
    body = resp.json()

    assert body["nodes"], "expected concept nodes"
    assert body["edges"], "expected relationship edges"
    assert "Alpha" in {n["label"] for n in body["nodes"]}
    for node in body["nodes"]:
        assert node["id"] and node["label"]
        assert "centrality" in node and "recurrence_count" in node
    for edge in body["edges"]:
        assert edge["id"] and edge["source"] and edge["target"]
        assert edge["sources"], "faithfulness guarantee: edge carries sources"
        for ref in edge["sources"]:
            content = contents[ref["material_id"]]
            assert content[ref["start_offset"] : ref["end_offset"]] == ref["quote"]


def test_single_edge_endpoint_returns_provenance() -> None:
    client = make_client(_KEYWORDS)
    _corpus(client)
    edges = client.get("/api/v1/graph", params={"workspace_id": _WS}).json()["edges"]
    edge_id = edges[0]["id"]

    resp = client.get(f"/api/v1/graph/edges/{edge_id}", params={"workspace_id": _WS})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == edge_id
    assert body["sources"], "faithfulness guarantee: non-empty sources"


def test_unknown_edge_returns_404() -> None:
    client = make_client(_KEYWORDS)
    _corpus(client)
    resp = client.get("/api/v1/graph/edges/e_missing", params={"workspace_id": _WS})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_graph_is_workspace_scoped() -> None:
    client = make_client(_KEYWORDS)
    _corpus(client)
    body = client.get("/api/v1/graph", params={"workspace_id": "never_used"}).json()
    assert body["nodes"] == [] and body["edges"] == []
