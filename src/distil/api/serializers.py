"""Serialize domain objects into the JSON shapes defined in ``contracts/http-api.md``.

Kept in one place so the contract-level faithfulness guarantee — every returned concept, edge, and
vital-few entry carries a non-empty ``sources``/``evidence`` array — is visible and testable.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from distil.domain.concept import Concept
from distil.domain.hierarchy import ConceptHierarchy, HierarchyNode
from distil.domain.material import Material
from distil.domain.ranking import RankingRun, VitalFewEntry
from distil.domain.relationship import Relationship
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


def graph_node(concept: Concept) -> dict[str, Any]:
    """GET /graph node: label + the graph signals used for ranking (no sources here; the concept
    detail endpoint carries provenance)."""
    return {
        "id": concept.id,
        "label": concept.label,
        "centrality": concept.centrality,
        "recurrence_count": concept.recurrence_count,
    }


def graph_edge(relationship: Relationship) -> dict[str, Any]:
    """GET /graph edge: the relationship with its grounding passage(s) — always non-empty
    (the Relationship invariant guarantees >= 1 source, the faithfulness guarantee)."""
    return {
        "id": relationship.id,
        "source": relationship.source_concept_id,
        "target": relationship.target_concept_id,
        "kind": relationship.kind,
        "sources": [source_ref(s) for s in relationship.sources],
    }


def graph_view(
    concepts: Sequence[Concept], relationships: Sequence[Relationship]
) -> dict[str, Any]:
    """GET /graph: nodes (with centrality/recurrence) + edges (with source provenance)."""
    return {
        "nodes": [graph_node(c) for c in concepts],
        "edges": [graph_edge(r) for r in relationships],
    }


def _node_signals(concept: Concept | None) -> dict[str, Any]:
    """The graph signals shown on a hierarchy node (empty-safe if the concept is missing)."""
    centrality = (concept.centrality or {}) if concept is not None else {}
    return {
        "pagerank": centrality.get("pagerank"),
        "degree": centrality.get("degree"),
        "recurrence": concept.recurrence_count if concept is not None else None,
    }


def hierarchy_node_view(
    node: HierarchyNode,
    hierarchy: ConceptHierarchy,
    concepts_by_id: dict[str, Concept],
) -> dict[str, Any]:
    """One hierarchy node with its signals, grounded placement, and nested children (recursive).

    Every non-root node carries a non-empty ``placement.grounding`` — the faithfulness guarantee.
    """
    concept = concepts_by_id.get(node.concept_id)
    return {
        "concept": {
            "id": node.concept_id,
            "label": concept.label if concept is not None else node.concept_id,
        },
        "is_pillar": node.is_pillar,
        "depth": node.depth,
        "signals": _node_signals(concept),
        "placement": {
            "reason": node.placement_reason,
            "grounding_edge_id": node.grounding_edge_id,
            "grounding": [source_ref(s) for s in node.grounding],
        },
        "children": [
            hierarchy_node_view(hierarchy.nodes[child_id], hierarchy, concepts_by_id)
            for child_id in node.children
            if child_id in hierarchy.nodes
        ],
    }


def hierarchy_view(
    hierarchy: ConceptHierarchy, concepts_by_id: dict[str, Concept]
) -> dict[str, Any]:
    """GET /hierarchy: the forest (roots → children) plus any edge-less ``unplaced`` concepts.

    When ``roots`` is empty (corpus too small to form a hierarchy) an explanatory ``note`` is added.
    """
    body: dict[str, Any] = {
        "workspace_id": hierarchy.workspace_id,
        "total_concepts": hierarchy.total_concepts,
        "roots": [
            hierarchy_node_view(hierarchy.nodes[root_id], hierarchy, concepts_by_id)
            for root_id in hierarchy.roots
        ],
        "unplaced": [
            {
                "id": cid,
                "label": concepts_by_id[cid].label if cid in concepts_by_id else cid,
            }
            for cid in hierarchy.unplaced
        ],
    }
    if not hierarchy.roots:
        body["note"] = (
            "Not enough material yet to form a concept hierarchy. Add more notes and the tree will "
            "appear once there are enough connected concepts to organise."
        )
    return body


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
