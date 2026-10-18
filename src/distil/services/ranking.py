"""Ranking service: turn the concept graph into the explainable 80/20 vital-few view.

Two separated responsibilities (Principle II — explainable, not black-box):

* **Ordering is deterministic code.** A composite of the graph signals — PageRank, degree, and
  recurrence, each normalised and weighted — gives every concept a score; concepts sort by that
  score, ties broken by label. Same graph in, same order out, reproducible by hand.
* **The rationale is the only LLM job.** The :class:`~distil.ports.llm.Explainer` writes one
  sentence per *already-chosen* concept and cannot touch rank or signals.

The service also owns the vital-few cut (a small, bounded set — see :func:`vital_few_size`) and
builds the persisted :class:`RankingRun` / :class:`VitalFewEntry` objects. Every entry's evidence is
the concept's own grounded sources, re-checked through the provenance gate before it is built, so an
unfaithful citation can never reach storage (Principle I).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.ranking import RankingRun, VitalFewEntry
from distil.domain.relationship import Relationship
from distil.domain.source_reference import SourceReference
from distil.ports.llm import Explainer, ExplanationRequest
from distil.services.provenance import keep_faithful

# The vital few is a small, human-sized set of top concepts, NOT a fraction of the corpus. A
# percentage breaks at both ends: on a tiny corpus (9 concepts) 20% is 2 — too few to cover the
# core ideas — while on a larger one (211 concepts from 5 lectures) 20% is 43, which is no longer a
# "few" anyone would study. A fixed target, clamped to the corpus, stays a meaningful handful at any
# scale. Depth beyond these few is served by the concept hierarchy (a separate feature); this flat
# top level is deliberately small. (Supersedes the old ~20%/25% Pareto cut — see decisions.md.)
VITAL_FEW_TARGET_SIZE = 5
# Below this many concepts a "vital few" is not meaningful (picking the top few of three ideas says
# nothing); the view comes back empty with an explanatory note instead of an arbitrary shortlist.
MIN_CONCEPTS_FOR_VITAL_FEW = 5

# Weights for the composite vital-few score. PageRank (global importance) leads; degree (local
# connectivity) and recurrence (spread across materials) each add a quarter. These sum to 1 and are
# the knob the eval harness tunes (T044/T045) — documented defaults, not magic constants.
SIGNAL_WEIGHTS: dict[str, float] = {"pagerank": 0.5, "degree": 0.25, "recurrence": 0.25}


def vital_few_size(total_concepts: int) -> int:
    """How many concepts form the vital few: a fixed small target, clamped to the corpus size.

    :data:`VITAL_FEW_TARGET_SIZE` concepts (or fewer if the corpus is smaller), independent of the
    corpus size, so the "few" stays a meaningful handful whether the notes yield 9 concepts or 900.
    Returns 0 when the corpus is too small (< :data:`MIN_CONCEPTS_FOR_VITAL_FEW`) to form one.
    """
    if total_concepts < MIN_CONCEPTS_FOR_VITAL_FEW:
        return 0
    return min(VITAL_FEW_TARGET_SIZE, total_concepts)


def _raw_signal(concept: Concept, name: str) -> float:
    """The raw value of one signal (recurrence from the concept itself, others from the graph)."""
    if name == "recurrence":
        return float(concept.recurrence_count)
    return (concept.centrality or {}).get(name, 0.0)


def composite_scores(concepts: Sequence[Concept]) -> dict[str, float]:
    """Map ``concept_id -> composite score`` in [0, 1]-ish, the deterministic ranking key.

    Each signal is normalised by its maximum across the corpus (so PageRank's tiny fractions and
    degree's whole numbers are comparable) and combined with :data:`SIGNAL_WEIGHTS`.
    """
    maxima = {
        name: max((_raw_signal(c, name) for c in concepts), default=0.0) for name in SIGNAL_WEIGHTS
    }
    scores: dict[str, float] = {}
    for concept in concepts:
        score = 0.0
        for name, weight in SIGNAL_WEIGHTS.items():
            ceiling = maxima[name]
            if ceiling > 0:
                score += weight * (_raw_signal(concept, name) / ceiling)
        scores[concept.id] = score
    return scores


class RankingService:
    """Produces a :class:`RankingRun` and its ordered, explained, source-linked entries."""

    def __init__(self, explainer: Explainer) -> None:
        self._explainer = explainer

    def rank(
        self,
        workspace_id: str,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
        materials: Sequence[Material],
    ) -> tuple[RankingRun, list[VitalFewEntry]]:
        """Deterministically rank ``concepts``, explain the vital few, return run + entries."""
        materials_by_id = {m.id: m for m in materials}
        scores = composite_scores(concepts)
        # Deterministic order: highest composite score first, ties broken alphabetically.
        ordered = sorted(concepts, key=lambda c: (-scores[c.id], c.label))
        chosen = ordered[: vital_few_size(len(concepts))]

        run_id = f"r_{uuid4().hex}"
        neighbors = _neighbor_labels(concepts, relationships)
        entries_signals = [
            (rank, concept, self._signals_for(concept, scores[concept.id]))
            for rank, concept in enumerate(chosen, start=1)
        ]

        rationales = self._rationales(entries_signals, neighbors)

        entries = [
            VitalFewEntry(
                id=f"vfe_{uuid4().hex}",
                workspace_id=workspace_id,
                ranking_run_id=run_id,
                concept_id=concept.id,
                rank=rank,
                signals=signals,
                rationale=rationales[concept.id],
                evidence=self._faithful_evidence(concept, materials_by_id),
            )
            for rank, concept, signals in entries_signals
        ]

        run = RankingRun(
            id=run_id,
            workspace_id=workspace_id,
            created_at=datetime.now(UTC),
            material_count=len(materials),
            vital_few_size=len(entries),
        )
        return run, entries

    def _rationales(
        self,
        entries_signals: Sequence[tuple[int, Concept, dict[str, float]]],
        neighbors: Mapping[str, tuple[str, ...]],
    ) -> dict[str, str]:
        """Get one rationale per chosen concept; fill any the explainer omits with a fallback."""
        if not entries_signals:
            return {}
        requests = [
            ExplanationRequest(
                concept_id=concept.id,
                label=concept.label,
                rank=rank,
                signals=signals,
                neighbor_labels=neighbors.get(concept.id, ()),
                evidence_quotes=tuple(s.quote for s in concept.sources[:3]),
            )
            for rank, concept, signals in entries_signals
        ]
        written = self._explainer.explain(requests)
        return {
            concept.id: (written.get(concept.id) or "").strip()
            or _fallback_rationale(rank, concept, signals)
            for rank, concept, signals in entries_signals
        }

    @staticmethod
    def _signals_for(concept: Concept, score: float) -> dict[str, float]:
        """The signal breakdown stored on the entry: the evidence behind its rank, all visible."""
        return {
            "pagerank": _raw_signal(concept, "pagerank"),
            "degree": _raw_signal(concept, "degree"),
            "recurrence": _raw_signal(concept, "recurrence"),
            "score": score,
        }

    @staticmethod
    def _faithful_evidence(
        concept: Concept, materials_by_id: Mapping[str, Material]
    ) -> tuple[SourceReference, ...]:
        """Re-check the concept's sources through the provenance gate before they are persisted.

        They were validated at build time; this is defence in depth (Principle I). The fallback to
        ``sources[:1]`` can only matter if a source somehow failed re-validation, and the concept
        invariant guarantees at least one source exists either way.
        """
        return keep_faithful(concept.sources, materials_by_id) or concept.sources[:1]


def _neighbor_labels(
    concepts: Sequence[Concept], relationships: Sequence[Relationship]
) -> dict[str, tuple[str, ...]]:
    """For each concept id, the sorted labels of the concepts it shares an edge with."""
    label_by_id = {c.id: c.label for c in concepts}
    adjacency: dict[str, set[str]] = {c.id: set() for c in concepts}
    for rel in relationships:
        if rel.source_concept_id in adjacency and rel.target_concept_id in label_by_id:
            adjacency[rel.source_concept_id].add(label_by_id[rel.target_concept_id])
        if rel.target_concept_id in adjacency and rel.source_concept_id in label_by_id:
            adjacency[rel.target_concept_id].add(label_by_id[rel.source_concept_id])
    return {cid: tuple(sorted(labels)) for cid, labels in adjacency.items()}


def _fallback_rationale(rank: int, concept: Concept, signals: dict[str, float]) -> str:
    """A deterministic, source-true rationale used when the explainer omits a concept."""
    return (
        f"Ranked #{rank}: {concept.label!r} recurs across "
        f"{int(signals['recurrence'])} material(s) and links to {int(signals['degree'])} other "
        f"concept(s) in your notes."
    )
