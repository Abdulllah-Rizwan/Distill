"""Deterministic fakes for the LLM ports, so pipeline/integration tests run offline and free.

``FakeExtractor`` grounds every mention in a real span of the material (it locates each configured
keyword in the text), guaranteeing the fakes never produce an unfaithful reference. ``FakeRanker``
orders concepts by their computed signals with a templated rationale.
"""

from __future__ import annotations

from collections.abc import Sequence

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference
from distil.ports.llm import (
    ConceptMention,
    ExtractionResult,
    RankedConcept,
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


class FakeRanker:
    """Ranks concepts by (pagerank, recurrence, label) with a templated rationale.

    Satisfies :class:`~distil.ports.llm.Ranker`.
    """

    def rank(
        self,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],  # noqa: ARG002 - signals already on concepts
    ) -> list[RankedConcept]:
        ordered = sorted(
            concepts,
            key=lambda c: (
                -(c.centrality or {}).get("pagerank", 0.0),
                -c.recurrence_count,
                c.label,
            ),
        )
        ranked: list[RankedConcept] = []
        for i, c in enumerate(ordered):
            signals = dict(c.centrality or {})
            signals["recurrence"] = float(c.recurrence_count)
            ranked.append(
                RankedConcept(
                    concept_id=c.id,
                    rank=i + 1,
                    signals=signals,
                    rationale=(
                        f"{c.label!r} ranks #{i + 1}: it recurs across {c.recurrence_count} "
                        f"material(s) and is connected in the concept graph."
                    ),
                    evidence=c.sources[:1],
                )
            )
        return ranked
