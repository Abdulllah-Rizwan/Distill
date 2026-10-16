"""Port: parsing raw uploads into extracted text + provenance."""

from __future__ import annotations

from typing import Protocol

from distil.domain.material import ParsedContent


class FileParser(Protocol):
    """Parses one supported file format into :class:`ParsedContent`.

    Implementations raise :class:`~distil.domain.errors.UnsupportedContentError` when the bytes
    are a format they claim to support but cannot extract text from (e.g. an image-only PDF).
    """

    def supports(self, filename: str) -> bool:
        """Return True if this parser handles the given filename (by extension)."""
        ...

    def parse(self, data: bytes) -> ParsedContent:
        """Extract text (and page provenance, if any) from the raw bytes."""
        ...
