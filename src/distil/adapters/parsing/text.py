"""Parser for plain-text and Markdown uploads.

Markdown is kept raw (not stripped) so character offsets in provenance references map exactly onto
the stored ``content_text``.
"""

from __future__ import annotations

from pathlib import Path

from distil.domain.material import ParsedContent

_EXTENSIONS = {".txt", ".text", ".md", ".markdown"}


class TextParser:
    """Handles ``.txt`` and Markdown files. Satisfies :class:`~distil.ports.parsing.FileParser`."""

    def supports(self, filename: str) -> bool:
        return Path(filename).suffix.lower() in _EXTENSIONS

    def parse(self, data: bytes) -> ParsedContent:
        # Decode once to canonical text; `replace` avoids hard failures on stray bytes.
        text = data.decode("utf-8", errors="replace")
        return ParsedContent(content_text=text)
