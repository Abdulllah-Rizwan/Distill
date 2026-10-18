"""Contract test: GET /api/v1/hierarchy and /hierarchy/concepts/{id} (T006, T014, T015, US1/US2).

The top level is a small set of pillars (not the whole corpus); every non-root node carries a
non-empty, faithful placement.grounding (quote == cited material text); roots carry none. Too-small
corpora return empty roots + a note; an unbuilt workspace returns 404 no_graph.
"""

from __future__ import annotations

from typing import Any

from tests._fakes.wiring import make_client

_KEYWORDS = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"]
_WS = "wh"
_TEXT = (
    "Alpha relates to Beta. Beta relates to Gamma. Gamma relates to Delta. "
    "Delta relates to Epsilon. Epsilon relates to Zeta. Zeta relates to Eta. Eta relates to Theta."
)


def _corpus(client, workspace_id: str = _WS) -> str:  # type: ignore[no-untyped-def]
    resp = client.post(
        "/api/v1/materials",
        data={"workspace_id": workspace_id},
        files={"file": ("m.md", _TEXT.encode("utf-8"), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    return _TEXT


def _walk(node: dict[str, Any], content: str, is_root: bool, seen: set[str]) -> None:
    seen.add(node["concept"]["id"])
    placement = node["placement"]
    assert placement["reason"].strip()
    if is_root:
        assert placement["grounding"] == []
        assert placement["grounding_edge_id"] is None
    else:
        assert placement["grounding"], "faithfulness guarantee: non-root carries grounding"
        assert placement["grounding_edge_id"]
        for ref in placement["grounding"]:
            assert content[ref["start_offset"] : ref["end_offset"]] == ref["quote"]
    for child in node["children"]:
        _walk(child, content, False, seen)


def test_hierarchy_small_top_level_and_faithful_placements() -> None:
    client = make_client(_KEYWORDS)
    content = _corpus(client)

    resp = client.get("/api/v1/hierarchy", params={"workspace_id": _WS})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_concepts"] == len(_KEYWORDS)
    assert body["roots"], "expected pillar roots"
    assert len(body["roots"]) <= 5  # vital-few-sized top level, far below total (SC-001)

    seen: set[str] = set()
    for root in body["roots"]:
        assert root["is_pillar"] is True
        _walk(root, content, True, seen)
    assert len(seen) + len(body["unplaced"]) == body["total_concepts"]  # coverage


def test_subtree_endpoint_returns_that_node() -> None:
    client = make_client(_KEYWORDS)
    _corpus(client)
    root_id = client.get("/api/v1/hierarchy", params={"workspace_id": _WS}).json()["roots"][0][
        "concept"
    ]["id"]

    resp = client.get(f"/api/v1/hierarchy/concepts/{root_id}", params={"workspace_id": _WS})
    assert resp.status_code == 200
    assert resp.json()["concept"]["id"] == root_id


def test_subtree_unknown_concept_returns_404() -> None:
    client = make_client(_KEYWORDS)
    _corpus(client)
    resp = client.get("/api/v1/hierarchy/concepts/c_missing", params={"workspace_id": _WS})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_hierarchy_404_when_no_graph_yet() -> None:
    client = make_client(_KEYWORDS)
    resp = client.get("/api/v1/hierarchy", params={"workspace_id": "never_used"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_graph"


def test_too_small_corpus_returns_empty_roots_with_note() -> None:
    client = make_client(["Alpha", "Beta", "Gamma"])  # 3 concepts < minimum
    client.post(
        "/api/v1/materials",
        data={"workspace_id": "small"},
        files={"file": ("m.md", b"Alpha Beta Gamma", "application/octet-stream")},
    )
    body = client.get("/api/v1/hierarchy", params={"workspace_id": "small"}).json()
    assert body["roots"] == []
    assert "note" in body
