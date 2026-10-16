"""Graph building: extract mentions from materials, merge into a grounded concept graph.

Steps: extract per material → drop ungrounded mentions (provenance gate) → merge concepts by label
across materials (recurrence = distinct materials) → resolve relationships between surviving
concepts → compute centrality signals. Returns concepts (with signals) + relationships to persist.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from uuid import uuid4

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference
from distil.ports.graph import GraphAnalyzer
from distil.ports.llm import ConceptExtractor, ConceptMention, RelationshipMention
from distil.services.provenance import is_faithful


def _key(label: str) -> str:
    """Normalized grouping key so the same idea phrased differently merges into one concept."""
    return label.strip().casefold()


class GraphBuilder:
    def __init__(self, extractor: ConceptExtractor, analyzer: GraphAnalyzer) -> None:
        self._extractor = extractor
        self._analyzer = analyzer

    def build(
        self, workspace_id: str, materials: Sequence[Material]
    ) -> tuple[list[Concept], list[Relationship]]:
        materials_by_id = {m.id: m for m in materials}

        concept_mentions: list[ConceptMention] = []
        relationship_mentions: list[RelationshipMention] = []
        for material in materials:
            result = self._extractor.extract(material)
            concept_mentions.extend(result.concepts)
            relationship_mentions.extend(result.relationships)

        concepts, key_to_id = self._merge_concepts(workspace_id, concept_mentions, materials_by_id)
        relationships = self._build_relationships(
            workspace_id, relationship_mentions, key_to_id, materials_by_id
        )

        signals = self._analyzer.compute_signals(concepts, relationships)
        concepts = [replace(c, centrality=signals.get(c.id)) for c in concepts]
        return concepts, relationships

    def _merge_concepts(
        self,
        workspace_id: str,
        mentions: Sequence[ConceptMention],
        materials_by_id: dict[str, Material],
    ) -> tuple[list[Concept], dict[str, str]]:
        groups: dict[str, list[ConceptMention]] = defaultdict(list)
        for mention in mentions:
            if is_faithful(mention.source, materials_by_id):  # provenance gate
                groups[_key(mention.label)].append(mention)

        concepts: list[Concept] = []
        key_to_id: dict[str, str] = {}
        for key, group in groups.items():
            sources = tuple(m.source for m in group)
            canonical = group[0].label.strip()
            aliases = tuple(sorted({m.label.strip() for m in group} - {canonical}))
            recurrence = len({s.material_id for s in sources})
            concept = Concept(
                id=f"c_{uuid4().hex}",
                workspace_id=workspace_id,
                label=canonical,
                sources=sources,
                recurrence_count=recurrence,
                aliases=aliases,
            )
            concepts.append(concept)
            key_to_id[key] = concept.id
        return concepts, key_to_id

    def _build_relationships(
        self,
        workspace_id: str,
        mentions: Sequence[RelationshipMention],
        key_to_id: dict[str, str],
        materials_by_id: dict[str, Material],
    ) -> list[Relationship]:
        merged: dict[tuple[str, str, str | None], list[SourceReference]] = defaultdict(list)
        for mention in mentions:
            if not is_faithful(mention.source, materials_by_id):  # provenance gate
                continue
            src_id = key_to_id.get(_key(mention.source_label))
            tgt_id = key_to_id.get(_key(mention.target_label))
            if src_id is None or tgt_id is None or src_id == tgt_id:
                continue
            merged[(src_id, tgt_id, mention.kind)].append(mention.source)

        return [
            Relationship(
                id=f"e_{uuid4().hex}",
                workspace_id=workspace_id,
                source_concept_id=src_id,
                target_concept_id=tgt_id,
                sources=tuple(sources),
                kind=kind,
            )
            for (src_id, tgt_id, kind), sources in merged.items()
        ]
