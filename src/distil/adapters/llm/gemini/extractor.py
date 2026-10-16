"""Gemini-backed concept/relationship extraction (fills :class:`ConceptExtractor`, task T025).

The model returns a verbatim quote for every concept and relationship; this adapter never trusts a
character offset from the model. For each quote it finds the span in the material's own text and
computes the offsets itself, so the resulting :class:`SourceReference` is faithful *by construction*
— and the graph builder's provenance gate re-checks it anyway (Principle I, defence in depth). A
quote the model altered or hallucinated simply will not be found, and that item is dropped: we
prefer missing a real concept over inventing an ungrounded one.

Long materials are split into overlapping character windows so a single call stays within free-tier
token limits; the window boundaries preserve absolute offsets, and the small overlap keeps a concept
that straddles a split from being lost on both sides.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from pydantic import ValidationError

from distil.adapters.llm.gemini._client import JsonLLM
from distil.adapters.llm.gemini.prompts import (
    EXTRACTION_SYSTEM_INSTRUCTION,
    ExtractionPayload,
    extraction_user_content,
)
from distil.domain.material import Material
from distil.domain.source_reference import SourceReference
from distil.ports.llm import ConceptMention, ExtractionResult, RelationshipMention

# Per-call text budget. A conservative default for the free tier; the eval/hardening pass tunes it
# once the live tokens-per-minute limit is confirmed in AI Studio. The overlap is a safety margin so
# a concept sitting on a window boundary is still seen whole in one of the two windows.
DEFAULT_MAX_CHARS = 6000
DEFAULT_OVERLAP_CHARS = 250


def iter_chunks(text: str, *, max_chars: int, overlap_chars: int) -> Iterator[tuple[int, str]]:
    """Yield ``(start_offset, chunk_text)`` windows over ``text`` that preserve absolute offsets.

    Each chunk is ``text[start:end]`` for the yielded ``start``, so a quote located at index ``i``
    within a chunk sits at ``start + i`` in the full material. Windows end on a newline or space
    boundary when possible (never mid-word, so a quote is not split needlessly) and overlap by
    ``overlap_chars`` to cover concepts that land on a boundary.
    """
    n = len(text)
    if n <= max_chars:
        yield 0, text
        return

    start = 0
    while start < n:
        end = min(start + max_chars, n)
        if end < n:  # not the final window — try to end on a clean boundary
            floor = start + overlap_chars  # don't snap back into the overlap region
            boundary = text.rfind("\n", floor, end)
            if boundary == -1:
                boundary = text.rfind(" ", floor, end)
            if boundary > start:
                end = boundary
        yield start, text[start:end]
        if end >= n:
            return
        start = max(end - overlap_chars, start + 1)


class GeminiConceptExtractor:
    """Extracts grounded mentions from a material using the Gemini model behind :class:`JsonLLM`."""

    def __init__(
        self,
        client: JsonLLM,
        *,
        max_chars: int = DEFAULT_MAX_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    ) -> None:
        self._client = client
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars

    def extract(self, material: Material) -> ExtractionResult:
        concepts: list[ConceptMention] = []
        relationships: list[RelationshipMention] = []
        seen_concepts: set[tuple[str, int, int]] = set()
        seen_relationships: set[tuple[str, str, str | None, int, int]] = set()

        for start, chunk in iter_chunks(
            material.content_text, max_chars=self._max_chars, overlap_chars=self._overlap_chars
        ):
            payload = self._extract_chunk(chunk)
            if payload is None:
                continue

            for item in payload.concepts:
                ref = self._locate(material, chunk, start, item.quote)
                label = item.label.strip()
                if ref is None or not label:
                    continue
                key = (label.casefold(), ref.start_offset, ref.end_offset)
                if key in seen_concepts:
                    continue
                seen_concepts.add(key)
                concepts.append(ConceptMention(label=label, source=ref))

            for rel in payload.relationships:
                ref = self._locate(material, chunk, start, rel.quote)
                src, tgt = rel.source_label.strip(), rel.target_label.strip()
                if ref is None or not src or not tgt:
                    continue
                rel_key = (
                    src.casefold(),
                    tgt.casefold(),
                    rel.kind,
                    ref.start_offset,
                    ref.end_offset,
                )
                if rel_key in seen_relationships:
                    continue
                seen_relationships.add(rel_key)
                relationships.append(
                    RelationshipMention(
                        source_label=src, target_label=tgt, source=ref, kind=rel.kind
                    )
                )

        return ExtractionResult(concepts=tuple(concepts), relationships=tuple(relationships))

    def _extract_chunk(self, chunk: str) -> ExtractionPayload | None:
        """Call the model for one chunk; return None if the response is unusable (skip it)."""
        raw = self._client.generate_json(
            system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
            user_content=extraction_user_content(chunk),
            response_schema=ExtractionPayload,
        )
        try:
            return ExtractionPayload.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError):
            # A malformed or empty response loses this chunk, not the whole ingest. Rare at
            # temperature 0 with an enforced schema; handled rather than trusted.
            return None

    @staticmethod
    def _locate(
        material: Material, chunk: str, chunk_start: int, quote: str
    ) -> SourceReference | None:
        """Find ``quote`` in ``chunk`` and build a faithful reference, or None if it is not present.

        The offsets are computed from the match, so ``quote == content_text[start:end]`` always
        holds. A quote the model changed will not be found and yields None (the item is dropped).
        """
        if not quote:
            return None
        local = chunk.find(quote)
        if local < 0:
            return None
        start = chunk_start + local
        end = start + len(quote)
        return SourceReference(
            material_id=material.id,
            start_offset=start,
            end_offset=end,
            quote=quote,
            page=material.page_for_offset(start),
        )
