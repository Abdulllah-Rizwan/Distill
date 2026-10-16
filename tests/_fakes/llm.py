"""Deterministic fakes for the LLM ports, so pipeline/integration tests run offline and free.

``FakeExtractor`` grounds every mention in a real span of the material (it locates each configured
keyword in the text), guaranteeing the fakes never produce an unfaithful reference.
``FakeExplainer`` returns a templated rationale per requested concept — it never ranks (ordering is
the service's job).
"""

from __future__ import annotations

from collections.abc import Sequence

from distil.domain.material import Material
from distil.domain.source_reference import SourceReference
from distil.ports.llm import (
    ConceptMention,
    ExplanationRequest,
    ExtractionResult,
    RelationshipMention,
)


class FakeExtractor:
    """Finds each configured keyword in the material and emits a grounded mention per occurrence.

    Relationships link consecutive distinct keywords (by appearance order), giving tests a connected
    graph. Satisfies :class:`~distil.ports.llm.ConceptExtractor`.
    """

    def __init__(self, keywords: Sequence[str]) -> None:
        self._keywords = tuple(keywords)

    def extract(self, material: Material) -> ExtractionResult:
        text = material.content_text
        mentions: list[ConceptMention] = []
        for kw in self._keywords:
            start = text.find(kw)
            if start < 0:
                continue
            ref = SourceReference(
                material_id=material.id,
                start_offset=start,
                end_offset=start + len(kw),
                quote=kw,
            )
            mentions.append(ConceptMention(label=kw, source=ref))

        relationships = tuple(
            RelationshipMention(
                source_label=mentions[i].label,
                target_label=mentions[i + 1].label,
                source=mentions[i].source,
                kind="relates-to",
            )
            for i in range(len(mentions) - 1)
            if mentions[i].label != mentions[i + 1].label
        )
        return ExtractionResult(concepts=tuple(mentions), relationships=relationships)


class FakeExplainer:
    """Returns a deterministic, signal-referencing rationale per request (no ranking).

    Satisfies :class:`~distil.ports.llm.Explainer`.
    """

    def explain(self, requests: Sequence[ExplanationRequest]) -> dict[str, str]:
        rationales: dict[str, str] = {}
        for req in requests:
            links = ", ".join(req.neighbor_labels) if req.neighbor_labels else "no other concept"
            rationales[req.concept_id] = (
                f"{req.label!r} ranks #{req.rank}: it recurs across "
                f"{int(req.signals.get('recurrence', 0))} material(s) and links to {links}."
            )
        return rationales
