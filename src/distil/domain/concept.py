"""Concept — a distinct idea extracted from one or more materials."""

from __future__ import annotations

from dataclasses import dataclass

from distil.domain.errors import DomainError
from distil.domain.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class Concept:
    """A distinct idea, grounded in at least one source occurrence.

    ``recurrence_count`` (distinct materials the concept appears in) and ``centrality`` (computed by
    the graph step) are the evidence signals that feed the 80/20 ranking.
    """

    id: str
    workspace_id: str
    label: str
    sources: tuple[SourceReference, ...]
    recurrence_count: int
    aliases: tuple[str, ...] = ()
    centrality: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise DomainError("Concept.label must be non-empty")
        if len(self.sources) < 1:
            raise DomainError(f"Concept {self.label!r} must have >= 1 source (faithfulness)")
        if self.recurrence_count < 1:
            raise DomainError(
                f"Concept {self.label!r} recurrence_count must be >= 1, got {self.recurrence_count}"
            )
