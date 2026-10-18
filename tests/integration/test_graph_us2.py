"""Integration test (US2, T035): the built graph exposes signals on nodes and provenance on edges.

Runs the real pipeline on the fake LLM + in-memory SQLite, then reads GET /graph and asserts every
node carries computed centrality + recurrence and every edge carries grounded sources.
"""

from __future__ import annotations

from tests._fakes.wiring import make_client

_KEYWORDS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
_WS = "w2"
_TEXT = "Alpha relates to Beta and Gamma. Delta then Epsilon."


def test_nodes_carry_signals_and_edges_carry_sources() -> None:
    client = make_client(_KEYWORDS)
    resp = client.post(
        "/api/v1/materials",
        data={"workspace_id": _WS},
        files={"file": ("m.md", _TEXT.encode("utf-8"), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text

    body = client.get("/api/v1/graph", params={"workspace_id": _WS}).json()

    assert body["nodes"]
    for node in body["nodes"]:
        assert node["recurrence_count"] >= 1
        assert node["centrality"] is not None
        assert "pagerank" in node["centrality"] and "degree" in node["centrality"]

    assert body["edges"]
    for edge in body["edges"]:
        assert edge["sources"], "every edge is grounded in a source passage"
        assert edge["source"] != edge["target"]  # no self-loops (domain invariant)
