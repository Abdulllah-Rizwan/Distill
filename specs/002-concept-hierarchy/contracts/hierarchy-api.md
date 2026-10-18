# Phase 1 Contract — Hierarchy HTTP API

Extends feature 001's HTTP API ([../../001-concept-graph-8020/contracts/http-api.md](../../001-concept-graph-8020/contracts/http-api.md)).
Same conventions: base path `/api/v1`, JSON, the shared error envelope, ISO-8601 UTC timestamps,
opaque string ids, and an explicit `workspace_id` (isolation seam, Principle V).

**Faithfulness guarantee (contract-level):** every **non-root** node returned MUST include a
non-empty `placement.grounding` array of `SourceReference`s (the edge that links it to its parent),
and every node's `concept` MUST resolve to a real concept with its own sources. A contract test fails
the build if any non-root node lacks a grounded placement.

**Shared shape — HierarchyNode** (nested; `children` is recursive):
```json
{
  "concept": { "id": "c_ab12", "label": "Cellular Respiration" },
  "is_pillar": true,
  "depth": 0,
  "signals": { "pagerank": 0.23, "degree": 5, "recurrence": 2 },
  "placement": {
    "reason": "Recurs across 2 of your materials and links to 5 other concepts — a core idea.",
    "grounding_edge_id": null,
    "grounding": []
  },
  "children": [
    {
      "concept": { "id": "c_9f33", "label": "ATP" },
      "is_pillar": false,
      "depth": 1,
      "signals": { "pagerank": 0.07, "degree": 1, "recurrence": 2 },
      "placement": {
        "reason": "Sits under 'Cellular Respiration' — your notes state it 'produces ATP'.",
        "grounding_edge_id": "e_77aa",
        "grounding": [
          { "material_id": "m_2", "start_offset": 120, "end_offset": 158, "quote": "produces ATP", "page": 1 }
        ]
      },
      "children": []
    }
  ]
}
```
- Roots have `depth: 0`, `placement.grounding: []`, `grounding_edge_id: null` (a root's own grounding
  is its concept sources, reachable via `GET /concepts/{id}` from feature 001).
- Non-roots have non-empty `placement.grounding` and a `grounding_edge_id` (the relationship).

---

## GET /api/v1/hierarchy?workspace_id=... — the concept hierarchy (US1)

Builds and returns the forest for the workspace's current graph (computed on read).

**200 OK**:
```json
{
  "workspace_id": "w_1",
  "total_concepts": 211,
  "roots": [ /* HierarchyNode, pillars first then secondary roots, children nested */ ],
  "unplaced": [ { "id": "c_isol", "label": "LAMP" } ]
}
```
- `roots` is ordered pillars-first (by vital-few rank), then secondary component roots.
- `unplaced` lists concepts with no edges at all (surfaced, never linked — research.md D4). May be `[]`.
- `200` with `roots: []` and an explanatory `note` when the corpus is too small to form a hierarchy
  (FR-011), mirroring `GET /vital-few`.
- `404` with `code: "no_graph"` if the workspace has no built graph yet.

## GET /api/v1/hierarchy/concepts/{id}?workspace_id=... — a subtree (US1 drill-down)

Returns the `HierarchyNode` rooted at the given concept (that concept plus its descendants), for
drilling into one branch without the whole forest.

**200 OK**: a single `HierarchyNode` object (as above) for `{id}`, with its `children` nested.
- `404` with `code: "not_found"` if the concept is not in the workspace.
- `404` with `code: "unplaced"` if the concept exists but is in the `unplaced` set (it has no subtree).

---

## Contract test checklist (asserted in `tests/contract/test_hierarchy_api.py`)

- Every **non-root** node returned includes a non-empty `placement.grounding` array, and each
  `grounding` `SourceReference.quote` equals the referenced material's text at `[start_offset:end_offset]`
  (deterministic faithfulness check) — i.e. the parent link is a real, grounded edge.
- The top level is a small set of pillars (not the entire corpus): `len(roots)` is on the order of the
  vital-few size, independent of `total_concepts` (SC-001).
- Coverage: the set of concept ids across all nested nodes plus `unplaced` equals the workspace's full
  concept id set, each exactly once (SC-002).
- Building the hierarchy twice for the same workspace returns identical structure (reproducibility,
  SC-006).
- Too-small corpus returns `roots: []` + a `note` (never an arbitrary tree).
- Both endpoints are workspace-scoped (no cross-workspace leakage).
