"""Contract test: POST /api/v1/materials status codes and body (T017).

201 accepted / 200 duplicate / 202 empty / 415 unsupported, per contracts/http-api.md.
"""

from __future__ import annotations

from tests._fakes.wiring import make_client

_KEYWORDS = ["alpha", "beta", "gamma", "delta", "epsilon"]
_WS = "w1"


def _upload(client, filename: str, content: bytes):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/v1/materials",
        data={"workspace_id": _WS},
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_accepted_returns_201_with_material_body() -> None:
    client = make_client(_KEYWORDS)
    resp = _upload(client, "notes.md", b"alpha beta gamma delta epsilon")
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "notes.md"
    assert body["format"] == "markdown"
    assert body["status"] == "accepted"
    assert body["id"].startswith("m_")


def test_duplicate_returns_200_with_same_id() -> None:
    client = make_client(_KEYWORDS)
    first = _upload(client, "notes.md", b"alpha beta gamma")
    second = _upload(client, "notes.md", b"alpha beta gamma")  # identical bytes
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


def test_empty_file_returns_202() -> None:
    client = make_client(_KEYWORDS)
    resp = _upload(client, "blank.txt", b"   \n  ")
    assert resp.status_code == 202
    assert resp.json()["status"] == "empty"


def test_unsupported_format_returns_415_envelope() -> None:
    client = make_client(_KEYWORDS)
    resp = _upload(client, "slides.pptx", b"whatever")
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "unsupported_format"
