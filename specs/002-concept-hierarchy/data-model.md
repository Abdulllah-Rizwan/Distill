# Phase 1 Data Model — Concept Hierarchy

These are **computed, immutable value objects** built on read from the persisted graph (research.md
D5) — they are not stored. They reuse `Concept`, `Relationship`, and `SourceReference` from feature
001 unchanged. All structure is scoped to one workspace (the concepts/relationships it is built from
already are).

## HierarchyNode

One concept's place in the forest.

| Field | Type | Notes |
|-------|------|-------|
| `concept_id` | str | The concept this node represents (stable id, DS-0003). |
| `parent_concept_id` | str \| None | `None` for a root; otherwise the id of the single parent. |
| `depth` | int | 0 for roots, parent.depth + 1 otherwise. |
| `is_pillar` | bool | True if this root is a vital-few pillar (D1); False for a secondary (component) root. Only meaningful when `parent_concept_id is None`. |
| `children` | tuple[str, ...] | Child concept ids, ordered by composite score desc, then label (D3). |
| `placement_reason` | str | Deterministic "why" (research.md D7). For a child: the grounding relationship to its parent; for a root: its importance signals. Always non-empty. |
| `grounding` | tuple[SourceReference, ...] | For a child: the source span(s) of the edge linking it to its parent (non-empty — the faithfulness guarantee). For a root: empty (a root's own grounding is the concept's `sources`). |

**Validation rules**
- A root (`parent_concept_id is None`) has `depth == 0` and empty `grounding`.
- A non-root MUST have `grounding` non-empty — the parent link is a real edge with provenance
  (Principle I). A non-root with no grounding edge is a contradiction and MUST NOT be produced (such a
  concept belongs in `unplaced`, see below).
- `concept_id` never equals `parent_concept_id`; the parent/child relation forms no cycle (BFS
  guarantees a tree).

## ConceptHierarchy

The whole forest for one build.

| Field | Type | Notes |
|-------|------|-------|
| `workspace_id` | str | Whose graph this was built from. |
| `roots` | tuple[str, ...] | Root concept ids in display order: pillars first (by rank), then secondary roots (by score, then label). |
| `nodes` | Mapping[str, HierarchyNode] | Every placed concept by id. |
| `unplaced` | tuple[str, ...] | Concept ids with no edges at all — surfaced, not linked (research.md D4). |
| `total_concepts` | int | `len(nodes) + len(unplaced)`; equals the workspace's concept count. |

**Invariants**
- **Coverage (SC-002):** every extracted concept id appears exactly once across `nodes` (placed) and
  `unplaced` — no orphans, no duplicates.
- **Structural faithfulness (SC-003):** for every node with a parent, there exists a real
  `Relationship` between `concept_id` and `parent_concept_id`, and `grounding` holds that edge's
  sources. No parent link exists without such an edge.
- **Determinism (SC-006):** built from stable ids with fully-ordered selection/traversal (D3), so the
  same `(concepts, relationships)` input yields an identical `ConceptHierarchy`.
- **Too-small corpus:** if the concept count is below the vital-few minimum (feature 001's
  `MIN_CONCEPTS_FOR_VITAL_FEW`), `roots` is empty and the view carries an explanatory note (FR-011),
  mirroring the flat vital-few.

## Relationship to feature 001 entities

- **Concept** (reused): supplies `label`, `recurrence_count`, `centrality` (for root selection and
  signal display) and `sources` (a root's grounding). Unchanged.
- **Relationship** (reused): its `(source_concept_id, target_concept_id)` pairs form the undirected
  adjacency the forest is built over; its `sources` become a child node's `grounding`; its `kind`
  feeds the `placement_reason`. Unchanged.
- **RankingRun / VitalFewEntry** (reused, read-only): define which concepts are pillars (D1). The
  hierarchy does not modify them.
