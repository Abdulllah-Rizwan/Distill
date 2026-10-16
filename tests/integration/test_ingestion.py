"""Integration tests for ingestion (T024) against a real in-memory SQLite repo."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pymupdf
import pytest

from distil.adapters.parsing.pdf import PdfParser
from distil.adapters.parsing.text import TextParser
from distil.adapters.persistence.sqlite.repositories import SqliteMaterialRepository
from distil.adapters.persistence.sqlite.schema import connect, initialize
from distil.domain.errors import UnsupportedContentError
from distil.domain.material import MaterialStatus
from distil.services.ingestion import IngestionService


@pytest.fixture
def service(request: pytest.FixtureRequest) -> Iterator[IngestionService]:
    conn: sqlite3.Connection = connect(":memory:")
    initialize(conn)
    conn.execute(
        "INSERT INTO workspace (id, name, created_at) VALUES ('w1', 'w1', '2026-01-01T00:00:00')"
    )
    conn.commit()
    yield IngestionService(SqliteMaterialRepository(conn), [TextParser(), PdfParser()])
    conn.close()


def test_accepts_markdown(service: IngestionService) -> None:
    result = service.ingest("w1", "notes.md", b"# Alpha\nAlpha relates to Beta.")
    assert result.duplicate is False
    assert result.material.status is MaterialStatus.ACCEPTED
    assert "Alpha" in result.material.content_text


def test_duplicate_upload_is_deduped(service: IngestionService) -> None:
    first = service.ingest("w1", "a.md", b"same content")
    second = service.ingest("w1", "a-again.md", b"same content")
    assert second.duplicate is True
    assert second.material.id == first.material.id  # no second row, no inflated importance


def test_empty_file_marked_empty(service: IngestionService) -> None:
    result = service.ingest("w1", "blank.txt", b"   \n  ")
    assert result.material.status is MaterialStatus.EMPTY


def test_unsupported_extension_rejected(service: IngestionService) -> None:
    with pytest.raises(UnsupportedContentError):
        service.ingest("w1", "slides.pptx", b"anything")


def test_image_only_pdf_rejected(service: IngestionService) -> None:
    doc = pymupdf.open()
    doc.new_page()  # blank page, no text
    data: bytes = doc.tobytes()
    doc.close()
    with pytest.raises(UnsupportedContentError):
        service.ingest("w1", "scan.pdf", data)
