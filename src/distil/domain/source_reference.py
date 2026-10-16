"""SourceReference — the backbone of source-faithfulness.

Every derived item (concept, relationship, ranking entry) points back to the exact passage that
supports it via one or more ``SourceReference``s. The invariant that ``quote`` equals the cited
material's text at ``[start_offset:end_offset]`` is what makes a claim verifiable (Principle I).
"""

from __future__ import annotations

from dataclasses import dataclass

from distil.domain.errors import ProvenanceError


@dataclass(frozen=True, slots=True)
class SourceReference:
    """A pointer from a derived item back to a passage in a :class:`Material`.

    Offsets index into the material's extracted ``content_text``. ``quote`` is the passage itself,
    denormalised so it can be displayed and verified without re-reading the material.
    """

    material_id: str
    start_offset: int
    end_offset: int
    quote: str
    page: int | None = None  # 1-indexed page, for PDF-sourced material only

    def __post_init__(self) -> None:
        # Bounds that hold regardless of the source text.
        if self.start_offset < 0:
            raise ProvenanceError(f"start_offset must be >= 0, got {self.start_offset}")
        if self.end_offset <= self.start_offset:
            raise ProvenanceError(
                f"end_offset ({self.end_offset}) must be > start_offset ({self.start_offset})"
            )
        if self.page is not None and self.page < 1:
            raise ProvenanceError(f"page must be >= 1 when present, got {self.page}")

    def is_faithful_to(self, content_text: str) -> bool:
        """Return True iff the span lies within ``content_text`` and ``quote`` matches it."""
        if self.end_offset > len(content_text):
            return False
        return content_text[self.start_offset : self.end_offset] == self.quote

    def validate_against(self, content_text: str) -> None:
        """Raise :class:`ProvenanceError` if this reference is not faithful to ``content_text``."""
        if not self.is_faithful_to(content_text):
            raise ProvenanceError(
                f"quote does not match source {self.material_id}"
                f"[{self.start_offset}:{self.end_offset}]"
            )
