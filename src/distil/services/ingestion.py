"""Ingestion: turn a raw upload into a stored :class:`Material`.

Selects a parser by file extension, extracts text, classifies the outcome (accepted / empty /
unsupported), and persists — deduplicating by content hash so a repeat upload never creates a
second material (FR-014). Rebuilding the graph after a new accepted material is the pipeline's
job, not this service's.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from distil.domain.errors import UnsupportedContentError
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.ports.parsing import FileParser
from distil.ports.repositories import MaterialRepository

_FORMAT_BY_EXTENSION: dict[str, MaterialFormat] = {
    ".txt": MaterialFormat.TEXT,
    ".text": MaterialFormat.TEXT,
    ".md": MaterialFormat.MARKDOWN,
    ".markdown": MaterialFormat.MARKDOWN,
    ".pdf": MaterialFormat.PDF,
}


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Outcome of an ingest call; ``duplicate`` means an identical material already existed."""

    material: Material
    duplicate: bool


def detect_format(filename: str) -> MaterialFormat | None:
    """Return the supported format for a filename, or None if unsupported."""
    return _FORMAT_BY_EXTENSION.get(Path(filename).suffix.lower())


class IngestionService:
    def __init__(self, repo: MaterialRepository, parsers: Sequence[FileParser]) -> None:
        self._repo = repo
        self._parsers = tuple(parsers)

    def ingest(self, workspace_id: str, filename: str, data: bytes) -> IngestResult:
        """Parse and store one upload.

        Raises :class:`UnsupportedContentError` for unsupported formats or unreadable content
        (the API maps this to 415); never fabricates content it could not read.
        """
        fmt = detect_format(filename)
        if fmt is None:
            raise UnsupportedContentError(
                "Only text, Markdown, and text-based PDF are supported in v1."
            )
        parser = self._select_parser(filename)
        parsed = parser.parse(data)  # may raise UnsupportedContentError (e.g. image-only PDF)

        content = parsed.content_text
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        existing = self._repo.find_by_hash(workspace_id, content_hash)
        if existing is not None:
            return IngestResult(material=existing, duplicate=True)

        status = MaterialStatus.EMPTY if parsed.is_empty else MaterialStatus.ACCEPTED
        material = Material(
            id=f"m_{uuid4().hex}",
            workspace_id=workspace_id,
            filename=filename,
            format=fmt,
            content_text=content,
            content_hash=content_hash,
            status=status,
            created_at=datetime.now(UTC),
            page_map=parsed.page_map,
        )
        self._repo.add(material)
        return IngestResult(material=material, duplicate=False)

    def _select_parser(self, filename: str) -> FileParser:
        for parser in self._parsers:
            if parser.supports(filename):
                return parser
        # detect_format already passed, so a parser should exist; guard defensively.
        raise UnsupportedContentError(f"No parser available for {filename!r}.")
