"""Relationship — a connection between two concepts, as expressed in the materials."""

from __future__ import annotations

from dataclasses import dataclass

from distil.domain.errors import DomainError
from distil.domain.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class Relationship:
    """An edge between two distinct concepts, grounded in the passage(s) that assert it.

    ``kind`` is the short relation label as stated in the material (e.g. "is a", "causes"); it
    may be ``None`` when the material connects two concepts without naming the relation.
    """

    id: str
    workspace_id: str
    source_concept_id: str
    target_concept_id: str
    sources: tuple[SourceReference, ...]
    kind: str | None = None

    def __post_init__(self) -> None:
        if self.source_concept_id == self.target_concept_id:
            raise DomainError("Relationship endpoints must differ (no self-loops)")
        if len(self.sources) < 1:
            raise DomainError("Relationship must have >= 1 source (faithfulness)")
