"""Unit tests for the ranking service (T028 service seam).

Covers the vital-few sizing (a small bounded set, SC-004), the deterministic composite ordering with
degree folded in, the LLM-rationale-with-fallback behaviour, and that evidence is always the
concept's own grounded sources (the explainer never supplies evidence or ordering).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from distil.domain.concept import Concept
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.source_reference import SourceReference
from distil.ports.llm import ExplanationRequest
from distil.services.ranking import (
    VITAL_FEW_TARGET_SIZE,
    RankingService,
    composite_scores,
    vital_few_size,
)
from tests._fakes.llm import FakeExplainer

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


def _concept(
    cid: str, label: str, start: int, end: int, *, pagerank: float, degree: float, recurrence: int
) -> Concept:
    ref = SourceReference(
        material_id="m1", start_offset=start, end_offset=end, quote=_CONTENT[start:end]
    )
    return Concept(
        id=cid,
        workspace_id="w1",
        label=label,
        sources=(ref,),
        recurrence_count=recurrence,
        centrality={"pagerank": pagerank, "degree": degree},
    )


@pytest.mark.parametrize(
    ("total", "expected"),
    [(0, 0), (4, 0), (5, 5), (6, 5), (10, 5), (20, 5), (100, 5), (211, 5)],
)
def test_vital_few_size_is_bounded_small_set(total: int, expected: int) -> None:
    size = vital_few_size(total)
    assert size == expected
    # A fixed small target, clamped to the corpus — never grows with corpus size (SC-004).
    assert size <= VITAL_FEW_TARGET_SIZE
    assert size <= total


def test_composite_score_folds_in_degree() -> None:
    # Two concepts tied on PageRank and recurrence; only degree differs → the higher degree wins.
    low = _concept("c_low", "low", 0, 5, pagerank=0.1, degree=1.0, recurrence=1)
    high = _concept("c_high", "high", 6, 10, pagerank=0.1, degree=9.0, recurrence=1)
    scores = composite_scores([low, high])
    assert scores["c_high"] > scores["c_low"]


def _five_concepts() -> list[Concept]:
    # Distinct PageRank values so the order is unambiguous.
    data = [
        ("c1", "alpha", 0, 5, 0.30, 4.0, 2),
        ("c2", "beta", 6, 10, 0.25, 3.0, 1),
        ("c3", "gamma", 11, 16, 0.20, 2.0, 1),
        ("c4", "delta", 17, 22, 0.15, 1.0, 1),
        ("c5", "epsilon", 23, 30, 0.10, 1.0, 1),
    ]
    return [
        _concept(cid, label, s, e, pagerank=pr, degree=deg, recurrence=rec)
        for cid, label, s, e, pr, deg, rec in data
    ]


def test_rank_is_deterministic_and_independent_of_explainer_order() -> None:
    concepts = _five_concepts()

    class _ReversingExplainer:
        """Returns rationales keyed by id; the service must ignore any order it implies."""

        def explain(self, requests: Sequence[ExplanationRequest]) -> dict[str, str]:
            return {r.concept_id: f"because {r.label}" for r in reversed(list(requests))}

    run, entries = RankingService(_ReversingExplainer()).rank("w1", concepts, [], [_material()])
    # 5 concepts → all 5 are the vital few (target is 5), ordered by composite score regardless of
    # the order the explainer returned rationales in.
    assert run.vital_few_size == 5
    assert [e.concept_id for e in entries] == ["c1", "c2", "c3", "c4", "c5"]
    assert [e.rank for e in entries] == [1, 2, 3, 4, 5]
    assert entries[0].signals["degree"] == 4.0  # the full breakdown is stored


def test_missing_rationale_falls_back_to_deterministic_sentence() -> None:
    concepts = _five_concepts()

    class _SilentExplainer:
        def explain(self, requests: Sequence[ExplanationRequest]) -> dict[str, str]:
            return {}  # the model returned nothing usable

    _, entries = RankingService(_SilentExplainer()).rank("w1", concepts, [], [_material()])
    assert entries[0].rationale.strip()  # never empty (VitalFewEntry invariant + graceful degrade)
    assert "Ranked #1" in entries[0].rationale


def test_evidence_is_the_concepts_grounded_sources() -> None:
    concepts = _five_concepts()
    _, entries = RankingService(FakeExplainer()).rank("w1", concepts, [], [_material()])
    entry = entries[0]
    assert len(entry.evidence) == 1
    assert entry.evidence[0].is_faithful_to(_CONTENT)


def test_too_small_corpus_yields_empty_run() -> None:
    concepts = _five_concepts()[:2]  # below the minimum
    run, entries = RankingService(FakeExplainer()).rank("w1", concepts, [], [_material()])
    assert entries == []
    assert run.vital_few_size == 0
