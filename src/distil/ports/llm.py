"""Ports: the LLM provider surface — concept/relationship extraction and ranking.

Behind these ports sits the Gemini adapter for the MVP; swapping to a more capable model later is a
contained change. The DTOs here are the *raw* LLM output (mentions, ranked concepts): they carry
provenance but not yet domain ids/recurrence — the services assign those during merge and build.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class ConceptMention:
    """A single occurrence of a concept found in one material, with its supporting span."""

    label: str
    source: SourceReference


@dataclass(frozen=True, slots=True)
class RelationshipMention:
    """A relationship between two concept labels as stated in one passage."""

    source_label: str
    target_label: str
    source: SourceReference
    kind: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Everything one extraction pass found in a material (pre-merge)."""

    concepts: tuple[ConceptMention, ...]
    relationships: tuple[RelationshipMention, ...]


class ConceptExtractor(Protocol):
    """Extracts grounded concept and relationship mentions from a material's text."""

    def extract(self, material: Material) -> ExtractionResult:
        """Return the concepts/relationships found in ``material``, each with a source span."""
        ...


@dataclass(frozen=True, slots=True)
class RankedConcept:
    """One concept's placement in the 80/20 ranking, pre-persistence (no id/run yet)."""

    concept_id: str
    rank: int
    signals: dict[str, float]
    rationale: str
    evidence: tuple[SourceReference, ...]


class Ranker(Protocol):
    """Ranks concepts into the explainable vital-few, using the graph signals as evidence."""

    def rank(
        self,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
    ) -> list[RankedConcept]:
        """Return concepts ordered most-vital-first, each with a rationale and source evidence."""
        ...
