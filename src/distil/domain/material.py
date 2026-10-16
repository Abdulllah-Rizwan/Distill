"""Material — a single uploaded note/document and its extracted text."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from distil.domain.errors import DomainError


class MaterialFormat(StrEnum):
    """Accepted input formats for v1 (text, Markdown, text-based PDF)."""

    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"


class MaterialStatus(StrEnum):
    """Ingestion outcome for a material."""

    ACCEPTED = "accepted"  # participates in the graph
    REJECTED = "rejected"  # unsupported/ungroundable — produces no concepts
    EMPTY = "empty"  # no extractable content — contributes nothing


@dataclass(frozen=True, slots=True)
class PageSpan:
    """Maps a half-open char range of ``content_text`` to a 1-indexed page (PDF provenance)."""

    start_offset: int
    end_offset: int
    page: int


@dataclass(frozen=True, slots=True)
class ParsedContent:
    """The result of parsing a raw upload: extracted text plus optional page provenance.

    Produced by a :class:`~distil.ports.parsing.FileParser`, consumed by ingestion to build a
    :class:`Material`. ``is_empty`` lets ingestion mark contentless uploads as ``EMPTY``.
    """

    content_text: str
    page_map: tuple[PageSpan, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.content_text.strip()


@dataclass(frozen=True, slots=True)
class Material:
    """An uploaded note. ``content_text`` is the basis for every provenance span."""

    id: str
    workspace_id: str
    filename: str
    format: MaterialFormat
    content_text: str
    content_hash: str
    status: MaterialStatus
    created_at: datetime
    page_map: tuple[PageSpan, ...] = ()
    rejected_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.filename.strip():
            raise DomainError("Material.filename must be non-empty")
        if self.status is MaterialStatus.REJECTED and not (self.rejected_reason or "").strip():
            raise DomainError("A rejected Material must carry a rejected_reason")
        if self.status is MaterialStatus.ACCEPTED and not self.content_text:
            raise DomainError("An accepted Material must have non-empty content_text")
        if not self.content_hash:
            raise DomainError("Material.content_hash must be set (used for duplicate detection)")

    def page_for_offset(self, offset: int) -> int | None:
        """Return the page containing ``offset``, or None if unknown (non-PDF or no map)."""
        for span in self.page_map:
            if span.start_offset <= offset < span.end_offset:
                return span.page
        return None
