"""Unit tests for the ranking service: the vital-few cap and faithful-evidence fallback (T028)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from distil.domain.concept import Concept
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.source_reference import SourceReference
from distil.ports.llm import RankedConcept
from distil.services.ranking import (
    VITAL_FEW_MAX_FRACTION,
    RankingService,
    vital_few_size,
)

_CONTENT = "alpha beta gamma delta epsilon zeta eta theta"


def _material() -> Material:
    return Material(
        id="m1",
        workspace_id="w1",
        filename="n.txt",
        format=MaterialFormat.TEXT,
        content_text=_CONTENT,
        content_hash="h",
        status=MaterialStatus.ACCEPTED,
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
    )


def _concept(cid: str, label: str, start: int, end: int) -> Concept:
    ref = SourceReference(
        material_id="m1", start_offset=start, end_offset=end, quote=_CONTENT[start:end]
    )
    return Concept(id=cid, workspace_id="w1", label=label, sources=(ref,), recurrence_count=1)


@pytest.mark.parametrize(
    ("total", "expected"),
    [
        (0, 0),
        (4, 0),  # below the minimum → no vital few
        (5, 1),  # ceil(1.0)=1, cap floor(1.25)=1
        (6, 1),  # ceil(1.2)=2 but capped at floor(1.5)=1  (never exceeds 25%)
        (10, 2),  # 20%
        (20, 4),  # 20%, under the 25% cap of 5
        (100, 20),
    ],
)
def test_vital_few_size_targets_20pct_never_above_25pct(total: int, expected: int) -> None:
    size = vital_few_size(total)
    assert size == expected
    # SC-004 hard cap: the vital few never exceeds 25% of the corpus.
    assert size <= total * VITAL_FEW_MAX_FRACTION


def test_too_small_corpus_yields_empty_run() -> None:
    concepts = [_concept("c1", "alpha", 0, 5), _concept("c2", "beta", 6, 10)]

    class _AllRanker:
        def rank(self, concepts, relationships):  # type: ignore[no-untyped-def]
            return [
                RankedConcept(c.id, i + 1, {"pagerank": 0.1}, "because", c.sources)
                for i, c in enumerate(concepts)
            ]

    run, entries = RankingService(_AllRanker()).rank("w1", concepts, [], [_material()])
    assert entries == []
    assert run.vital_few_size == 0


def test_unfaithful_evidence_falls_back_to_concept_sources() -> None:
    # 5 concepts so a vital few forms; the ranker cites a bogus span for the top concept.
    concepts = [
        _concept("c1", "alpha", 0, 5),
        _concept("c2", "beta", 6, 10),
        _concept("c3", "gamma", 11, 16),
        _concept("c4", "delta", 17, 22),
        _concept("c5", "epsilon", 23, 30),
    ]
    bogus = SourceReference(material_id="m1", start_offset=0, end_offset=5, quote="WRONG")

    class _LyingRanker:
        def rank(self, concepts, relationships):  # type: ignore[no-untyped-def]
            return [RankedConcept("c1", 1, {"pagerank": 0.9}, "top", (bogus,))]

    run, entries = RankingService(_LyingRanker()).rank("w1", concepts, [], [_material()])
    assert run.vital_few_size == 1
    entry = entries[0]
    # The bogus citation was dropped; the concept's own grounded source stands in.
    assert len(entry.evidence) == 1
    assert entry.evidence[0].quote == "alpha"
    assert entry.evidence[0].is_faithful_to(_CONTENT)
