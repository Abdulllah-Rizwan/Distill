"""Serialize domain objects into the JSON shapes defined in ``contracts/http-api.md``.

Kept in one place so the contract-level faithfulness guarantee — every returned concept, edge, and
vital-few entry carries a non-empty ``sources``/``evidence`` array — is visible and testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.ranking import RankingRun, VitalFewEntry
from distil.domain.source_reference import SourceReference


def source_ref(ref: SourceReference) -> dict[str, Any]:
    """A SourceReference; ``page`` is included only when known (PDF-sourced material)."""
    body: dict[str, Any] = {
        "material_id": ref.material_id,
        "start_offset": ref.start_offset,
        "end_offset": ref.end_offset,
        "quote": ref.quote,
    }
    if ref.page is not None:
        body["page"] = ref.page
    return body


def material_summary(material: Material) -> dict[str, Any]:
    """The POST/GET /materials item shape."""
    return {
        "id": material.id,
        "filename": material.filename,
        "format": material.format.value,
        "status": material.status.value,
        "created_at": material.created_at.isoformat(),
    }


def concept_detail(concept: Concept) -> dict[str, Any]:
    """GET /concepts/{id}: the concept with its centrality, recurrence, and grounded sources."""
    return {
        "id": concept.id,
        "label": concept.label,
        "aliases": list(concept.aliases),
        "recurrence_count": concept.recurrence_count,
        "centrality": concept.centrality,
        "sources": [source_ref(s) for s in concept.sources],
    }


def vital_few_view(
    run: RankingRun,
    entries: Sequence[VitalFewEntry],
    concepts_by_id: dict[str, Concept],
    total_concepts: int,
) -> dict[str, Any]:
    """GET /vital-few: the latest ranking, each entry explained and source-linked.

    When ``entries`` is empty (corpus too small to form a vital few) an explanatory ``note`` is
    added rather than returning an arbitrary shortlist.
    """
    body: dict[str, Any] = {
        "ranking_run_id": run.id,
        "generated_at": run.created_at.isoformat(),
        "total_concepts": total_concepts,
        "vital_few_size": run.vital_few_size,
        "entries": [_vital_few_entry(e, concepts_by_id) for e in entries],
    }
    if not entries:
        body["note"] = (
            "Not enough material yet to surface a vital few. Add more notes and the 80/20 view "
            "will appear once there are enough distinct concepts to rank."
        )
    return body


def _vital_few_entry(entry: VitalFewEntry, concepts_by_id: dict[str, Concept]) -> dict[str, Any]:
    concept = concepts_by_id.get(entry.concept_id)
    return {
        "rank": entry.rank,
        "concept": {
            "id": entry.concept_id,
            "label": concept.label if concept is not None else entry.concept_id,
        },
        "signals": entry.signals,
        "rationale": entry.rationale,
        "evidence": [source_ref(s) for s in entry.evidence],
    }
