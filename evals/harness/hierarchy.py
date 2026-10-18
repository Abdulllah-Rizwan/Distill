"""Hierarchy eval scoring (feature 002): structural faithfulness, coverage, and root relevance.

Two deterministic, offline gates mirror Principle I for the tree:

* **Structural faithfulness** — every parent→child link MUST be a real relationship edge whose
  grounding spans resolve to the source text exactly. An invented or unfaithful link fails the run,
  the same way an ungrounded concept span does for the flat pipeline.
* **Coverage** — every extracted concept appears exactly once (placed in the tree or ``unplaced``).

**Root relevance** is the soft, reported signal: the pillar roots should be the concepts the dataset
curates as important (the "main themes"). Reusing ``important_concepts`` as the expected top-level
themes keeps this ground-truth free of extra authoring, consistent with the flat relevance check.
"""

from __future__ import annotations

from dataclasses import dataclass

from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.relationship import Relationship
from distil.services.hierarchy import HierarchyService


@dataclass(frozen=True, slots=True)
class HierarchyEvalResult:
    """Structural faithfulness + coverage (hard gates) and root relevance (reported)."""

    link_total: int
    link_grounded: int
    link_violations: tuple[str, ...]
    covered: bool
    coverage_detail: str
    pillar_labels: tuple[str, ...]
    root_precision: float
    root_recall: float

    @property
    def structural_score(self) -> float:
        """Fraction of parent→child links that are real, faithful edges (1.0 if none to check)."""
        return 1.0 if self.link_total == 0 else self.link_grounded / self.link_total

    @property
    def passed(self) -> bool:
        """Hard gate: every link grounded in a real edge (100%) AND full coverage (Principle I)."""
        return not self.link_violations and self.covered


def score_hierarchy(
    materials: list[Material],
    concepts: list[Concept],
    relationships: list[Relationship],
    important_keys: set[str],
) -> HierarchyEvalResult:
    """Build the hierarchy and score its structural faithfulness, coverage, and root relevance."""
    workspace_id = concepts[0].workspace_id if concepts else "eval"
    hierarchy = HierarchyService().build(workspace_id, concepts, relationships)

    by_material = {m.id: m for m in materials}
    by_concept = {c.id: c for c in concepts}
    rel_by_id = {r.id: r for r in relationships}

    violations: list[str] = []
    link_total = 0
    link_grounded = 0

    for node in hierarchy.nodes.values():
        if node.parent_concept_id is None:
            continue  # roots are grounded by their own concept sources, not a parent link
        link_total += 1
        where = f"{node.concept_id} -> {node.parent_concept_id}"
        ok = True

        edge = rel_by_id.get(node.grounding_edge_id) if node.grounding_edge_id else None
        if edge is None:
            violations.append(
                f"{where}: grounding edge {node.grounding_edge_id!r} is not a real edge"
            )
            ok = False
        elif {edge.source_concept_id, edge.target_concept_id} != {
            node.concept_id,
            node.parent_concept_id,
        }:
            violations.append(f"{where}: edge {edge.id} does not connect the node and its parent")
            ok = False

        if not node.grounding:
            violations.append(f"{where}: non-root link has no grounding (faithfulness)")
            ok = False
        for ref in node.grounding:
            material = by_material.get(ref.material_id)
            if material is None or not ref.is_faithful_to(material.content_text):
                violations.append(f"{where}: grounding quote not faithful to source")
                ok = False
                break

        if ok:
            link_grounded += 1

    placed = set(hierarchy.nodes)
    unplaced = set(hierarchy.unplaced)
    all_ids = set(by_concept)
    covered = placed.isdisjoint(unplaced) and (placed | unplaced) == all_ids
    coverage_detail = (
        "ok" if covered else f"placed {len(placed)} + unplaced {len(unplaced)} vs {len(all_ids)}"
    )

    pillars = [by_concept[r].label for r in hierarchy.roots if hierarchy.nodes[r].is_pillar]
    pillar_keys = {p.casefold() for p in pillars}
    hits = pillar_keys & important_keys
    precision = len(hits) / len(pillar_keys) if pillar_keys else 0.0
    recall = len(hits) / len(important_keys) if important_keys else 0.0

    return HierarchyEvalResult(
        link_total=link_total,
        link_grounded=link_grounded,
        link_violations=tuple(violations),
        covered=covered,
        coverage_detail=coverage_detail,
        pillar_labels=tuple(pillars),
        root_precision=precision,
        root_recall=recall,
    )
