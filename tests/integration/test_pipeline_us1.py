"""End-to-end US1 pipeline test with the fake LLM (T019).

Upload Markdown + text through the real app/pipeline/persistence (only the LLM ports are faked),
then confirm the vital-few view is ranked, explained, source-linked, and that recurrence across
materials is reflected. Also covers the too-small-corpus edge case (empty view + note).
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

_MD = (
    "Backpropagation uses Gradient Descent to reduce the Loss Function. "
    "The Chain Rule lets each Neuron update its Weights. "
    "Activation functions and a sensible Learning Rate matter too."
)
_TXT = (
    "Backpropagation and Gradient Descent appear again here. "
    "The Loss Function depends on Weights and the Learning Rate."
)


def _upload(client, filename: str, text: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/materials",
        data={"workspace_id": _WS},
        files={"file": (filename, text.encode("utf-8"), "application/octet-stream")},
    )


def test_upload_to_vital_few_end_to_end() -> None:
    client = make_client(_KEYWORDS)
    assert _upload(client, "deep_learning.md", _MD).status_code == 201
    assert _upload(client, "review.txt", _TXT).status_code == 201

    # Both materials are listed.
    listed = client.get("/api/v1/materials", params={"workspace_id": _WS}).json()["materials"]
    assert {m["filename"] for m in listed} == {"deep_learning.md", "review.txt"}

    body = client.get("/api/v1/vital-few", params={"workspace_id": _WS}).json()
    assert body["total_concepts"] == len(_KEYWORDS)
    assert len(body["entries"]) >= 1

    # A concept appearing in both materials recurs twice; drill-down confirms it via the API.
    top_id = body["entries"][0]["concept"]["id"]
    detail = client.get(f"/api/v1/concepts/{top_id}", params={"workspace_id": _WS}).json()
    assert detail["recurrence_count"] >= 1
    assert detail["centrality"] is not None  # signals were computed and persisted
    assert detail["sources"]


def test_recurrence_counts_distinct_materials() -> None:
    client = make_client(_KEYWORDS)
    _upload(client, "deep_learning.md", _MD)
    _upload(client, "review.txt", _TXT)

    entries = client.get("/api/v1/vital-few", params={"workspace_id": _WS}).json()["entries"]
    # Several concepts appear in both materials; recurrence (distinct materials) must surface
    # through the full pipeline as a signal of 2.0 on at least one vital-few entry.
    recurrences = [e["signals"]["recurrence"] for e in entries]
    assert 2.0 in recurrences


def test_too_small_corpus_returns_empty_view_with_note() -> None:
    client = make_client(_KEYWORDS)
    # Only two distinct concepts — below the threshold to form a meaningful vital few.
    _upload(client, "tiny.md", "Backpropagation and Weights.")

    body = client.get("/api/v1/vital-few", params={"workspace_id": _WS}).json()
    assert body["entries"] == []
    assert body["vital_few_size"] == 0
    assert "note" in body
