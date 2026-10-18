# Implementation Plan: Concept Hierarchy (Tree View)

**Branch**: `002-concept-hierarchy` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-concept-hierarchy/spec.md`

## Summary

Organize the workspace's source-grounded concept graph (feature 001) into a navigable **forest**: a
few **pillar roots** — the vital-few concepts from the existing ranking — with the remaining concepts
hanging beneath them along **real relationship edges**. Each non-root concept gets exactly one parent;
every parent→child link is an actual edge from the graph (never invented), so the tree is faithful by
construction. The hierarchy is a **pure, deterministic function of the already-persisted graph**,
computed on read and exposed through the HTTP API — no new storage, no new dependency, and no extra
LLM calls.

Technical approach: a new framework-agnostic **`HierarchyService`** reuses the deterministic composite
scores from the ranking service to pick roots, then builds a **breadth-first forest** over the
undirected relationship graph (shortest hops from the nearest pillar, deterministic tie-breaking). A
thin FastAPI router exposes `GET /hierarchy` (and a subtree endpoint). Placement rationales are
generated deterministically from the grounding edge (relationship kind + source quote), so the view
is fully explainable without a model call. The eval harness is extended with a structural-faithfulness
check (every link is a real edge) and coverage/relevance checks against a curated hierarchy.

## Technical Context

**Language/Version**: Python 3.12, managed with **uv** (unchanged from feature 001).

**Primary Dependencies**: **No new dependencies.** Reuses FastAPI + Pydantic v2 (delivery/DTOs),
the existing SQLite persistence (concepts + relationships are already stored), and the existing
domain/ports/services. The forest build is plain-Python breadth-first traversal over an adjacency map
derived from the stored relationships — NetworkX is *not* required for it (see research.md).

**Storage**: **None added.** The hierarchy is a pure function of the persisted concept graph
(concepts with their signals + relationships), computed on read. No new tables, no rebuild wiring.

**Testing**: pytest — deterministic unit tests for the hierarchy builder (root selection, parent
assignment, tie-breaking, coverage, orphan handling, reproducibility), a contract test for the
endpoints, and an integration test through the fake-LLM pipeline. Eval harness extended with a
hierarchy scorer (structural faithfulness = every link is a real edge; coverage; relevance).

**Target Platform**: Local developer machine, single-user, single workspace (unchanged).

**Project Type**: Backend HTTP web service over a framework-agnostic core (unchanged from 001).

**Performance Goals**: The build is an O(V+E) graph traversal over an in-memory adjacency map —
negligible next to ingestion/LLM steps. No new performance concern; the hierarchy endpoint returns in
well under the SC-005 budget inherited from 001.

**Constraints**:
- **Source-faithfulness (Principle I):** a parent→child link MUST correspond to a real relationship
  edge in the graph; the builder MUST NOT attach a concept to a parent it has no edge to. Concepts
  with no path to a pillar are surfaced honestly (own-component root, or an explicit `unplaced` set),
  never linked by invention.
- **Determinism (DS-0003 consistency):** stable concept ids + fully-ordered traversal (by composite
  score, then label) → identical tree for identical input, verifiable by building twice.
- **No extra LLM spend:** placement and its rationale are deterministic; no model call is added (the
  free-tier/credit budget is untouched). An LLM phrasing of rationales is explicitly deferred.

**Scale/Scope**: Same as 001 — one user, tens of materials, low-hundreds of concepts (the 5-lecture
local run produced 211 concepts / 89 edges, which this feature turns into a browsable forest).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | How this plan satisfies it | Gate |
|---|-----------|----------------------------|------|
| I | Source-Faithfulness | Every parent→child link is an existing relationship edge (grounded, with the same `SourceReference`s); the builder never fabricates a link. Unreachable concepts are surfaced, not invented into the tree. A deterministic eval asserts 0 ungrounded links. | ✅ |
| II | Explainable Intelligence | Roots are the vital-few pillars (importance signals shown); each child carries a visible reason = the grounding edge (relationship kind + source quote). Placement is deterministic code, not a black box; no reordering by a model. | ✅ |
| III | Documented Decisions | This plan + [research.md](./research.md) record every decision (roots = vital few, BFS-forest parenting, compute-on-read, pure service vs NetworkX, deterministic rationale) with rationale and alternatives. | ✅ |
| IV | Understand Before Adopt | No new dependency to adopt; the one algorithm (BFS forest) is simple, explainable plain Python the author can reason about fully. | ✅ |
| V | Privacy & Data Stewardship | Computed from already-stored, workspace-scoped data; the endpoint is workspace-scoped like all others. No new data leaves the machine; no new secrets. | ✅ |
| VI | Simplicity that Ships | Reuses the graph, the scores, and the architecture; adds one pure service + one router. Compute-on-read means **no new table and no rebuild wiring**. No new dependency, no new LLM call. | ✅ |
| VII | Verified Reliability | Deterministic unit tests (build correctness, coverage, determinism, orphans) + contract test + eval scorer (structural faithfulness 100%, coverage, relevance) gating changes. | ✅ |
| VIII | Senior-Grade Code Quality | A cohesive `HierarchyService` behind the existing ports/adapters layering; DTOs at the boundary; consistent with the ranking service's shape; ruff + mypy clean. | ✅ |

**Result: PASS.** The two load-bearing guarantees — Source-Faithfulness (I) and Verified Reliability
(VII) — are structural: links can only be real edges, and a deterministic eval enforces it. No new
complexity beyond one pure service and a router, so Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-concept-hierarchy/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions, rationale, alternatives
├── data-model.md        # Phase 1 — hierarchy entities (computed), fields, rules
├── quickstart.md        # Phase 1 — runnable end-to-end validation guide
├── contracts/
│   └── hierarchy-api.md # Phase 1 — HTTP API contract for the hierarchy endpoints
└── checklists/
    └── requirements.md  # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root) — additions to the existing layout

```text
src/distil/
├── domain/
│   └── hierarchy.py         # NEW: HierarchyNode + ConceptHierarchy value objects (computed,
│                            #      immutable); pure, no I/O.
├── services/
│   └── hierarchy.py         # NEW: HierarchyService — roots = vital-few pillars (reuses
│                            #      ranking.composite_scores + vital_few_size); BFS forest over the
│                            #      relationship adjacency; deterministic placement + rationale.
├── api/
│   ├── routers/
│   │   └── hierarchy.py     # NEW: GET /hierarchy, GET /hierarchy/concepts/{id}
│   ├── serializers.py       # EXTEND: serialize ConceptHierarchy → DTO (nested nodes)
│   └── dependencies.py      # EXTEND: expose the hierarchy read path on Services
└── (no new adapter — reads existing GraphRepository via the composition root)

tests/
├── unit/
│   └── test_hierarchy_service.py   # NEW: roots, parenting, tie-breaks, coverage, orphans, determinism
├── integration/
│   └── test_hierarchy.py           # NEW: fake-LLM pipeline → hierarchy over real SQLite
└── contract/
    └── test_hierarchy_api.py       # NEW: endpoint shapes + faithfulness guarantee (grounded links)

evals/
├── datasets/energy-cycle/          # EXTEND: add expected roots / parent-of relations (ground truth)
└── harness/
    └── hierarchy.py                # NEW: structural faithfulness (every link a real edge) + coverage
                                    #      + relevance (roots vs curated themes; child-parent relatedness)
```

**Structure Decision**: Reuse feature 001's hexagonal layout unchanged. The hierarchy is a new **pure
service** (`services/hierarchy.py`) plus a **router** — it reads the existing `GraphRepository` through
the composition root and adds no adapter and no persistence. Keeping the build as a pure service (not a
NetworkX adapter method) keeps it trivially unit-testable and makes determinism obvious; rationale and
the roots/parenting decisions are in [research.md](./research.md).

## Complexity Tracking

> No Constitution Check violations. The feature adds one pure service and one router, reuses all
> existing architecture, and introduces no new dependency, storage, or LLM call — so there is no
> complexity to justify here.
