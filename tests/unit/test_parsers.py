"""Unit tests for the file parsers (T020)."""

from __future__ import annotations

import pymupdf
import pytest

from distil.adapters.parsing.pdf import PdfParser
from distil.adapters.parsing.text import TextParser
from distil.domain.errors import UnsupportedContentError


def test_text_parser_supports_text_and_markdown() -> None:
    parser = TextParser()
    assert parser.supports("notes.md")
    assert parser.supports("notes.txt")
    assert parser.supports("NOTES.MARKDOWN")
    assert not parser.supports("scan.pdf")


def test_text_parser_keeps_content_verbatim() -> None:
    raw = "# Heading\n\nAlpha relates to **Beta**.\n"
    parsed = TextParser().parse(raw.encode("utf-8"))
    assert parsed.content_text == raw  # offsets will map exactly onto this
    assert not parsed.is_empty


def _pdf_with_text(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data: bytes = doc.tobytes()
    doc.close()
    return data


def test_pdf_parser_extracts_text_and_page_map() -> None:
    data = _pdf_with_text("Backpropagation uses the chain rule")
    parsed = PdfParser().parse(data)
    assert "Backpropagation" in parsed.content_text
    assert len(parsed.page_map) == 1
    assert parsed.page_map[0].page == 1
    # The page span covers the extracted text.
    span = parsed.page_map[0]
    assert span.start_offset == 0
    assert span.end_offset == len(parsed.content_text)


def test_pdf_parser_rejects_image_only_pdf() -> None:
    doc = pymupdf.open()
    doc.new_page()  # a blank page: no extractable text
    data: bytes = doc.tobytes()
    doc.close()
    with pytest.raises(UnsupportedContentError):
        PdfParser().parse(data)
