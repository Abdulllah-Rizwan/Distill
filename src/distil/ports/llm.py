"""Ports: the LLM provider surface — concept/relationship extraction and rationale writing.

Behind these ports sits the Gemini adapter for the MVP; swapping to a more capable model later is a
contained change. Two deliberately narrow jobs:

* :class:`ConceptExtractor` turns a material's text into grounded mentions (each with a provenance
  span the services verify before trusting it).
* :class:`Explainer` writes the plain-language "why" for concepts the ranking service has *already*
  selected and ordered. It never decides rank or signals — those are deterministic code — so the
  model cannot silently reorder the vital-few (Principle II: explainable, not black-box).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from distil.domain.material import Material
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
class ExplanationRequest:
    """One already-ranked concept the explainer should write a rationale for.

    The service fills this in; the explainer may *use* these facts but may not change them. It
    carries the computed ``rank`` and ``signals``, the labels of directly connected concepts, and
    verbatim source quotes the rationale is allowed to reference — nothing it could use to invent a
    different ordering.
    """

    concept_id: str
    label: str
    rank: int
    signals: dict[str, float]
    neighbor_labels: tuple[str, ...]
    evidence_quotes: tuple[str, ...]


class Explainer(Protocol):
    """Writes the human-readable rationale for each ranked concept — prose only, no ranking."""

    def explain(self, requests: Sequence[ExplanationRequest]) -> dict[str, str]:
        """Return ``concept_id -> one rationale sentence``, produced in a single batched call.

        A concept omitted from the returned mapping gets a deterministic fallback rationale from the
        service, so the vital-few view is always fully explained even if the model drops one.
        """
        ...
