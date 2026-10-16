"""Ranking service: turn the concept graph into the explainable 80/20 vital-few view.

Wraps a :class:`~distil.ports.llm.Ranker` (fake in tests, Gemini in production) and owns the
decisions the ranker must not: how many concepts count as the "vital few" (the Pareto cut, capped
per SC-004) and the construction of the persisted :class:`RankingRun` / :class:`VitalFewEntry`
objects. Every entry's evidence passes the provenance gate before it is built, so an unfaithful
citation from the ranker can never reach storage (Principle I).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.ranking import RankingRun, VitalFewEntry
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference
from distil.ports.llm import Ranker
from distil.services.provenance import keep_faithful

# The Pareto target — surface roughly the vital 20% of concepts — and the hard cap from SC-004
# (the vital few must never exceed 25% of the corpus).
VITAL_FEW_TARGET_FRACTION = 0.20
VITAL_FEW_MAX_FRACTION = 0.25
# Below this many concepts a "vital few" is not meaningful (an 80/20 split of three ideas says
# nothing); the view comes back empty with an explanatory note instead of an arbitrary shortlist.
MIN_CONCEPTS_FOR_VITAL_FEW = 5


def vital_few_size(total_concepts: int) -> int:
    """How many concepts form the vital few: ~20% of the corpus, never above the 25% cap (SC-004).

    Returns 0 when the corpus is too small (< :data:`MIN_CONCEPTS_FOR_VITAL_FEW`) to form one.
    """
    if total_concepts < MIN_CONCEPTS_FOR_VITAL_FEW:
        return 0
    target = math.ceil(total_concepts * VITAL_FEW_TARGET_FRACTION)
    cap = math.floor(total_concepts * VITAL_FEW_MAX_FRACTION)
    return max(1, min(target, cap))


class RankingService:
    """Produces a :class:`RankingRun` and its ordered, explained, source-linked entries."""

    def __init__(self, ranker: Ranker) -> None:
        self._ranker = ranker

    def rank(
        self,
        workspace_id: str,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
        materials: Sequence[Material],
    ) -> tuple[RankingRun, list[VitalFewEntry]]:
        """Rank ``concepts`` into the vital few; return the run and its entries (unsaved)."""
        materials_by_id = {m.id: m for m in materials}
        concepts_by_id = {c.id: c for c in concepts}
        keep = vital_few_size(len(concepts))

        run_id = f"r_{uuid4().hex}"
        entries: list[VitalFewEntry] = []
        if keep > 0:
            for ranked in self._ranker.rank(concepts, relationships)[:keep]:
                concept = concepts_by_id.get(ranked.concept_id)
                if concept is None:
                    # The ranker named a concept we don't have; skip rather than fabricate one.
                    continue
                entries.append(
                    VitalFewEntry(
                        id=f"vfe_{uuid4().hex}",
                        workspace_id=workspace_id,
                        ranking_run_id=run_id,
                        concept_id=concept.id,
                        rank=len(entries) + 1,  # re-densify so ranks stay 1..n after any skips
                        signals=dict(ranked.signals),
                        rationale=ranked.rationale,
                        evidence=self._faithful_evidence(ranked.evidence, concept, materials_by_id),
                    )
                )

        run = RankingRun(
            id=run_id,
            workspace_id=workspace_id,
            created_at=datetime.now(UTC),
            material_count=len(materials),
            vital_few_size=len(entries),
        )
        return run, entries

    @staticmethod
    def _faithful_evidence(
        evidence: Sequence[SourceReference],
        concept: Concept,
        materials_by_id: Mapping[str, Material],
    ) -> tuple[SourceReference, ...]:
        """Keep only the ranker's citations that quote their material exactly.

        If none survive the gate, fall back to the concept's own sources — already grounded and
        guaranteed non-empty — so every entry still carries verifiable evidence (Principle I).
        """
        faithful = keep_faithful(evidence, materials_by_id)
        return faithful or concept.sources[:1]
