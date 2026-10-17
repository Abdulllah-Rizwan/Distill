"""Deterministic faithfulness scoring: every emitted span must resolve to real source text.

Faithfulness (Principle I) is the non-negotiable gate. A concept, relationship, or vital-few
evidence quote whose span does not match its material's text *exactly* is an ungrounded claim and
fails the run. The Gemini adapter already drops quotes it cannot locate, so this is the regression
guard that proves the guarantee still holds — including through merge, persistence, and ranking.
"""

from __future__ import annotations

from dataclasses import dataclass

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.ranking import VitalFewEntry
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference


@dataclass(frozen=True, slots=True)
class FaithfulnessResult:
    """How many emitted source spans are grounded, and any that are not."""

    total: int
    grounded: int
    violations: tuple[str, ...]

    @property
    def score(self) -> float:
        """Fraction of spans that resolve to real text (1.0 when there is nothing to check)."""
        return 1.0 if self.total == 0 else self.grounded / self.total

    @property
    def passed(self) -> bool:
        """Faithfulness passes only at 100% — any ungrounded span fails (Principle I)."""
        return not self.violations


def _grounded(
    ref: SourceReference, materials: dict[str, Material], where: str, violations: list[str]
) -> bool:
    material = materials.get(ref.material_id)
    if material is None:
        violations.append(f"{where}: references unknown material {ref.material_id!r}")
        return False
    actual = material.content_text[ref.start_offset : ref.end_offset]
    if actual != ref.quote:
        violations.append(
            f"{where}: quote {ref.quote!r} != text[{ref.start_offset}:{ref.end_offset}] {actual!r}"
        )
        return False
    return True


def score_faithfulness(
    materials: list[Material],
    concepts: list[Concept],
    relationships: list[Relationship],
    entries: list[VitalFewEntry],
) -> FaithfulnessResult:
    """Verify every concept, relationship, and vital-few evidence span against its material text."""
    by_id = {m.id: m for m in materials}
    violations: list[str] = []
    total = 0
    grounded = 0

    def check(ref: SourceReference, where: str) -> None:
        nonlocal total, grounded
        total += 1
        if _grounded(ref, by_id, where, violations):
            grounded += 1

    for concept in concepts:
        for source in concept.sources:
            check(source, f"concept {concept.label!r}")
    for relationship in relationships:
        for source in relationship.sources:
            check(source, f"relationship {relationship.id}")
    for entry in entries:
        for source in entry.evidence:
            check(source, f"vital-few rank {entry.rank}")

    return FaithfulnessResult(total=total, grounded=grounded, violations=tuple(violations))
