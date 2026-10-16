"""Contract test: GET /api/v1/vital-few and /concepts/{id} incl. the faithfulness guarantee (T018).

Every vital-few entry and every concept returned must carry non-empty evidence/sources, and each
quote must equal the cited material's text at [start_offset:end_offset].
"""

from __future__ import annotations

from tests._fakes.wiring import make_client

_KEYWORDS = [
    "Backpropagation",
    "Gradient Descent",
    "Loss Function",
    "Chain Rule",
    "Neuron",
    "Weights",
    "Activation",
    "Learning Rate",
]
_WS = "w1"

_M1 = (
    "Backpropagation uses Gradient Descent to reduce the Loss Function. "
    "The Chain Rule lets each Neuron update its Weights. "
    "Activation functions and a sensible Learning Rate matter too."
)
_M2 = (
    "Backpropagation and Gradient Descent appear again here. "
    "The Loss Function depends on Weights and the Learning Rate."
)


def _build_corpus(client) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """Upload the two materials; return {material_id: content} for faithfulness checks."""
    contents: dict[str, str] = {}
    for filename, text in (("m1.md", _M1), ("m2.txt", _M2)):
        resp = client.post(
            "/api/v1/materials",
            data={"workspace_id": _WS},
            files={"file": (filename, text.encode("utf-8"), "application/octet-stream")},
        )
        assert resp.status_code == 201, resp.text
        contents[resp.json()["id"]] = text
    return contents


def _assert_faithful(ref: dict, contents: dict[str, str]) -> None:
    content = contents[ref["material_id"]]
    assert content[ref["start_offset"] : ref["end_offset"]] == ref["quote"]


def test_vital_few_entries_are_explained_and_source_faithful() -> None:
    client = make_client(_KEYWORDS)
    contents = _build_corpus(client)

    resp = client.get("/api/v1/vital-few", params={"workspace_id": _WS})
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_concepts"] == len(_KEYWORDS)
    assert body["vital_few_size"] == len(body["entries"]) >= 1
    ranks = [e["rank"] for e in body["entries"]]
    assert ranks == list(range(1, len(ranks) + 1))  # contiguous 1..n

    for entry in body["entries"]:
        assert entry["rationale"].strip()  # Principle II: visible "why"
        assert entry["evidence"], "faithfulness guarantee: non-empty evidence"
        for ref in entry["evidence"]:
            _assert_faithful(ref, contents)
        assert entry["concept"]["label"]


def test_concept_detail_carries_provenance() -> None:
    client = make_client(_KEYWORDS)
    contents = _build_corpus(client)

    entries = client.get("/api/v1/vital-few", params={"workspace_id": _WS}).json()["entries"]
    concept_id = entries[0]["concept"]["id"]

    resp = client.get(f"/api/v1/concepts/{concept_id}", params={"workspace_id": _WS})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == concept_id
    assert body["sources"], "faithfulness guarantee: non-empty sources"
    for ref in body["sources"]:
        _assert_faithful(ref, contents)


def test_unknown_concept_returns_404() -> None:
    client = make_client(_KEYWORDS)
    _build_corpus(client)
    resp = client.get("/api/v1/concepts/c_missing", params={"workspace_id": _WS})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_vital_few_404_when_no_ranking_yet() -> None:
    client = make_client(_KEYWORDS)
    resp = client.get("/api/v1/vital-few", params={"workspace_id": "never_used"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "no_ranking"
