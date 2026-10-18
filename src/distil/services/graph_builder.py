"""Graph building: extract mentions from materials, merge into a grounded concept graph.

Steps: extract per material → drop ungrounded mentions (provenance gate) → merge concepts by label
across materials (recurrence = distinct materials) → resolve relationships between surviving
concepts → compute centrality signals. Returns concepts (with signals) + relationships to persist.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference
from distil.ports.graph import GraphAnalyzer
from distil.ports.llm import (
    ConceptExtractor,
    ConceptMention,
    ExtractionResult,
    RelationshipMention,
)
from distil.services.provenance import is_faithful


def _key(label: str) -> str:
    """Normalized grouping key so the same idea phrased differently merges into one concept."""
    return label.strip().casefold()


def _stable_id(prefix: str, *parts: str) -> str:
    """A deterministic id from identity-defining parts (a concept's label, or an edge's endpoints).

    Derived, not random, so the same concept/edge keeps the same id across rebuilds and across
    separate runs on identical input. That makes ids stable for clients holding them (US2/US3 graph
    and edge lookups) and lets the eval harness record/replay the explainer, whose prompt embeds the
    concept id, deterministically. The parts are null-separated so distinct inputs cannot collide.
    """
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"


class GraphBuilder:
    def __init__(self, extractor: ConceptExtractor, analyzer: GraphAnalyzer) -> None:
        self._extractor = extractor
        self._analyzer = analyzer
        # Extraction is memoized per material: a material's content is immutable (content_hash
        # dedup), so re-extracting it on every workspace rebuild would be wasted LLM calls (and
        # free-tier quota), and — with a non-deterministic model — would make rebuilds
        # non-idempotent: adding material N would silently re-roll the extraction of materials
        # 1..N-1 and reshape the existing graph. Caching makes each material extracted exactly once
        # per process. (A server-restart cold cache re-extracts once; the durable fix is to persist
        # per-material mentions — future work, alongside US3 delete/rebuild.)
        self._extractions: dict[str, ExtractionResult] = {}

    def build(
        self, workspace_id: str, materials: Sequence[Material]
    ) -> tuple[list[Concept], list[Relationship]]:
        materials_by_id = {m.id: m for m in materials}

        concept_mentions: list[ConceptMention] = []
        relationship_mentions: list[RelationshipMention] = []
        for material in materials:
            result = self._extract(material)
            concept_mentions.extend(result.concepts)
            relationship_mentions.extend(result.relationships)

        concepts, key_to_id = self._merge_concepts(workspace_id, concept_mentions, materials_by_id)
        relationships = self._build_relationships(
            workspace_id, relationship_mentions, key_to_id, materials_by_id
        )

        signals = self._analyzer.compute_signals(concepts, relationships)
        concepts = [replace(c, centrality=signals.get(c.id)) for c in concepts]
        return concepts, relationships

    def _extract(self, material: Material) -> ExtractionResult:
        """Extract a material's mentions, reusing the cached result if it was extracted before."""
        cached = self._extractions.get(material.id)
        if cached is None:
            cached = self._extractor.extract(material)
            self._extractions[material.id] = cached
        return cached

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
                id=_stable_id("c", workspace_id, key),
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
                id=_stable_id("e", workspace_id, src_id, tgt_id, kind or ""),
                workspace_id=workspace_id,
                source_concept_id=src_id,
                target_concept_id=tgt_id,
                sources=tuple(sources),
                kind=kind,
            )
            for (src_id, tgt_id, kind), sources in merged.items()
        ]
