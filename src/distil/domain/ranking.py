"""Ranking entities — the explainable 80/20 output (ADR-0003, batch per ADR-0007)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from distil.domain.errors import DomainError
from distil.domain.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class RankingRun:
    """One batch computation of graph signals + the 80/20 ranking over a workspace.

    The current vital-few view is the set of :class:`VitalFewEntry` of the latest run. The
    "vital_few_size <= 25% of total concepts" cap (SC-004) is enforced by the ranking service, which
    knows the total concept count; this entity only records the resulting size.
    """

    id: str
    workspace_id: str
    created_at: datetime
    material_count: int
    vital_few_size: int

    def __post_init__(self) -> None:
        if self.material_count < 0:
            raise DomainError("RankingRun.material_count must be >= 0")
        if self.vital_few_size < 0:
            raise DomainError("RankingRun.vital_few_size must be >= 0")


@dataclass(frozen=True, slots=True)
class VitalFewEntry:
    """A concept's place in the 80/20 ranking, with its evidence and plain-language rationale.

    Carries both the graph ``signals`` used as evidence and a visible ``rationale`` plus source
    ``evidence`` — satisfying Explainable Intelligence (Principle II). No black-box scores.
    """

    id: str
    workspace_id: str
    ranking_run_id: str
    concept_id: str
    rank: int
    signals: dict[str, float]
    rationale: str
    evidence: tuple[SourceReference, ...]

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise DomainError(f"VitalFewEntry.rank must be >= 1, got {self.rank}")
        if not self.rationale.strip():
            raise DomainError("VitalFewEntry.rationale must be non-empty (Principle II)")
        if len(self.evidence) < 1:
            raise DomainError("VitalFewEntry must have >= 1 evidence source (faithfulness)")
