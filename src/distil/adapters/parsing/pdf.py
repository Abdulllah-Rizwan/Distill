"""Parser for text-based PDFs (PyMuPDF).

Extracts text page by page, recording a :class:`PageSpan` per page so provenance can report the page
a passage came from. Image-only/scanned PDFs (no extractable text) are rejected — v1 has no OCR
(FR-002 / Principle I: never fabricate from unreadable content).
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

from distil.domain.errors import UnsupportedContentError
from distil.domain.material import PageSpan, ParsedContent


class PdfParser:
    """Handles ``.pdf`` files. Satisfies :class:`~distil.ports.parsing.FileParser`."""

    def supports(self, filename: str) -> bool:
        return Path(filename).suffix.lower() == ".pdf"

    def parse(self, data: bytes) -> ParsedContent:
        parts: list[str] = []
        spans: list[PageSpan] = []
        offset = 0
        doc = pymupdf.open(stream=data, filetype="pdf")
        try:
            for page_index in range(doc.page_count):
                page_text: str = doc[page_index].get_text()
                if not page_text:
                    continue
                start = offset
                parts.append(page_text)
                offset += len(page_text)
                spans.append(PageSpan(start_offset=start, end_offset=offset, page=page_index + 1))
        finally:
            doc.close()

        content = "".join(parts)
        if not content.strip():
            raise UnsupportedContentError(
                "This PDF has no extractable text (it may be scanned or image-only). "
                "OCR is not supported in v1 — only text-based PDFs."
            )
        return ParsedContent(content_text=content, page_map=tuple(spans))
