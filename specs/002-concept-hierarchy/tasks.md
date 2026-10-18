---
description: "Task list for Concept Hierarchy (feature 002)"
---

# Tasks: Concept Hierarchy (Tree View)

**Input**: Design documents from `specs/002-concept-hierarchy/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/hierarchy-api.md

**Tests**: INCLUDED — required, not optional. Constitution **Principle VII** mandates deterministic
tests for API contracts and core logic, and an **eval** for every AI-facing capability. Here the
"AI capability" is the *faithfulness of the structure* (every parent→child link is a real, grounded
edge) and its relevance, scored by the eval harness.

**Organization**: Grouped by user story (US1 = P1 MVP, US2 = P2, US3 = P3) so each is independently
implementable and testable. Paths follow the hexagonal layout in `plan.md` (`src/distil/...`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task).
- **[Story]**: US1 / US2 / US3. Setup, Foundational, and Polish tasks carry no story label.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffolding. No new runtime dependency is added (plan.md): the feature reuses FastAPI,
the existing SQLite `GraphRepository`, and the ranking service.

- [x] T001 Create empty module skeletons with docstrings: `src/distil/domain/hierarchy.py`,
  `src/distil/services/hierarchy.py`, `src/distil/api/routers/hierarchy.py`; confirm `pyproject.toml`
  gains **no** new dependency (reuse-only, per plan.md).

**Checkpoint**: New modules importable; project still lints and the 001 suite still passes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The computed value objects every story returns. **No user story work begins until these
exist.**

- [x] T002 [P] Define `HierarchyNode` in `src/distil/domain/hierarchy.py` as a frozen dataclass with
  fields `concept_id: str`, `parent_concept_id: str | None`, `depth: int`, `is_pillar: bool`,
  `children: tuple[str, ...]`, `placement_reason: str`, `grounding: tuple[SourceReference, ...]`;
  enforce invariants (data-model.md): a root (`parent_concept_id is None`) MUST have `depth == 0` and
  empty `grounding`; a non-root MUST have non-empty `grounding` and `depth >= 1`; `placement_reason`
  non-empty; `concept_id != parent_concept_id`.
- [x] T003 [P] Define `ConceptHierarchy` in `src/distil/domain/hierarchy.py` as a frozen dataclass:
  `workspace_id: str`, `roots: tuple[str, ...]`, `nodes: Mapping[str, HierarchyNode]`,
  `unplaced: tuple[str, ...]`, `total_concepts: int`; enforce the coverage invariant — the ids in
  `nodes` and `unplaced` are disjoint and their union has size `total_concepts` (each concept exactly
  once, no orphans/duplicates per data-model.md).
- [x] T004 [P] Unit tests for the domain invariants in `tests/unit/test_hierarchy_domain.py`: root vs
  non-root grounding/depth rules raise on violation; self-parent rejected; coverage invariant holds
  for a valid build and is rejected when a concept is missing or duplicated.

**Checkpoint**: Value objects enforce faithfulness (non-root ⇒ grounded) and coverage at construction.

---

## Phase 3: User Story 1 — Navigate from the pillars down (Priority: P1) 🎯 MVP

**Goal**: Build the source-grounded forest — a few pillar roots with concepts branching beneath along
real edges — and expose it through the API so a student can drill from the big ideas to specifics.

**Independent Test**: Ingest notes (fake LLM), call `GET /api/v1/hierarchy`, and confirm a small set
of root pillars each with nested `children`, every non-root link corresponding to a real relationship,
and `GET /hierarchy/concepts/{id}` returning that concept's subtree.

### Tests for User Story 1 (write first, ensure they FAIL)

- [x] T005 [P] [US1] Unit tests for the builder in `tests/unit/test_hierarchy_service.py`: roots are
  the top `vital_few_size` concepts by `composite_scores` (reused from ranking); multi-source BFS gives
  every non-root exactly one parent via an existing edge; children ordered by composite score desc then
  label; `depth` = parent.depth + 1; tie-break order is parent score → parent label → parent id
  (research.md D1–D3); building twice on the same graph returns identical structure (determinism).
- [x] T006 [P] [US1] Contract test `GET /api/v1/hierarchy` in `tests/contract/test_hierarchy_api.py`:
  200 returns `roots` (nested `children`) with `len(roots)` on the order of the vital-few size and far
  below `total_concepts` (SC-001); `404 code: "no_graph"` when the workspace has no graph; too-small
  corpus returns `roots: []` + a `note`; responses are workspace-scoped (no cross-workspace leakage).
- [x] T007 [P] [US1] Integration test in `tests/integration/test_hierarchy.py` with the fake
  extractor/explainer over real SQLite: ingest a small multi-note corpus → `GET /hierarchy` yields a
  forest whose every parent→child pair is backed by a real `Relationship`.

### Implementation for User Story 1

- [x] T008 [US1] Implement `HierarchyService.build(workspace_id, concepts, relationships)` in
  `src/distil/services/hierarchy.py`: reuse `ranking.composite_scores` + `ranking.vital_few_size` to
  pick pillar roots; build an **undirected** adjacency map from relationships; run multi-source BFS
  from the roots assigning each non-root its first-reached (nearest) parent with deterministic
  tie-breaking; add a secondary root (highest-scoring concept) for any component containing no pillar;
  leave edge-less concepts for `unplaced`; order children by score then label; return a
  `ConceptHierarchy` (research.md D1–D4, D6). Depends on T002, T003.
- [x] T009 [US1] Add `HierarchyService.subtree(hierarchy, concept_id)` returning the `HierarchyNode`
  rooted at `concept_id` with its descendants (for the drill-down endpoint). Depends on T008.
- [x] T010 [US1] Extend `src/distil/api/serializers.py`: serialize `ConceptHierarchy` → `{ workspace_id,
  total_concepts, roots: [node...], unplaced: [{id,label}...] }` and a `HierarchyNode` → the nested DTO
  in `contracts/hierarchy-api.md` (concept, is_pillar, depth, signals, placement, children).
- [x] T011 [US1] Implement `GET /api/v1/hierarchy` and `GET /api/v1/hierarchy/concepts/{id}` in
  `src/distil/api/routers/hierarchy.py`: workspace-scoped; `404 no_graph` when no graph, `404 not_found`
  / `404 unplaced` for the subtree endpoint; too-small corpus → `roots: []` + `note`. Depends on
  T008, T009, T010.
- [x] T012 [US1] Wire the hierarchy read path into the composition root (`src/distil/api/dependencies.py`
  — build the hierarchy from the `GraphRepository`'s concepts/relationships on request) and register
  the router in `src/distil/api/main.py`; make T005–T007 pass. Depends on T011.

**Checkpoint**: MVP — a student can fetch a small, source-linked pillar forest and drill into a branch.

---

## Phase 4: User Story 2 — Understand why the tree is shaped this way (Priority: P2)

**Goal**: Make every placement explainable and grounded — each child shows the relationship (and
source passage) that puts it under its parent; each root shows its importance.

**Independent Test**: For any non-root node confirm a non-empty, source-linked `placement.grounding`
and a readable `placement.reason` citing that connection; for a root confirm a reason citing its
importance signals; confirm no placement exists without grounding.

### Tests for User Story 2 (write first, ensure they FAIL)

- [x] T013 [P] [US2] Unit tests (extend `tests/unit/test_hierarchy_service.py`): a child's `grounding`
  equals the connecting relationship's `sources` and its `grounding_edge_id` is that relationship's id;
  a child's `placement_reason` references the relationship (its `kind` when present, and a source
  quote); a root's `placement_reason` references its importance (recurrence + degree) and its
  `grounding` is empty (research.md D7).
- [x] T014 [P] [US2] Contract test (extend `tests/contract/test_hierarchy_api.py`): the faithfulness
  guarantee — every **non-root** node has a non-empty `placement.grounding`, and each
  `grounding[].quote` equals the referenced material's text at `[start_offset:end_offset]`; roots have
  `grounding: []` and `grounding_edge_id: null`; every node's `placement.reason` is non-empty.

### Implementation for User Story 2

- [x] T015 [US2] In `HierarchyService.build`, record for each non-root the relationship it was reached
  through and set `grounding` = that edge's `sources` and the edge id; generate a deterministic
  `placement_reason` for children (from the edge `kind` + first quote) and for roots (importance
  signals, reusing the ranking rationale style). No LLM call (research.md D7). Depends on T008.
- [x] T016 [US2] Ensure the serializer emits `placement: { reason, grounding_edge_id, grounding[] }`
  and `signals` per node, with the root vs non-root shapes from `contracts/hierarchy-api.md`. Depends
  on T010, T015.

**Checkpoint**: US1 + US2 — the tree is navigable *and* every node explains, with sources, why it sits
where it does.

---

## Phase 5: User Story 3 — A complete, current map (Priority: P3)

**Goal**: Guarantee every concept appears exactly once (placed or `unplaced`) and that the hierarchy
reflects the current corpus as materials are added/removed, reproducibly.

**Independent Test**: Compare the hierarchy to the full concept list (every concept once, no orphans);
add a material and see new concepts placed; remove a material and see solely-supported concepts gone;
rebuild the same corpus and get an identical tree.

### Tests for User Story 3 (write first, ensure they FAIL)

- [x] T017 [P] [US3] Coverage test in `tests/integration/test_hierarchy.py` (extend): the union of all
  nested node ids and `unplaced` equals the workspace's full concept-id set, each exactly once (SC-002);
  an edge-less concept appears in `unplaced` and is never given a parent (research.md D4).
- [x] T018 [P] [US3] Currentness + reproducibility test in `tests/integration/test_hierarchy.py`: after
  adding a material the hierarchy includes its new concepts; after deleting a material (feature 001
  US3 delete, if available — otherwise rebuild on the reduced set) concepts solely from it disappear;
  building the hierarchy twice yields identical structure (SC-006).

### Implementation for User Story 3

- [x] T019 [US3] Finalize coverage in `HierarchyService.build`: assert (and return) that every concept
  is either in `nodes` or `unplaced` exactly once; secondary-root each pillarless component; keep truly
  isolated concepts in `unplaced` (never linked — Principle I). Depends on T008.
- [x] T020 [US3] Confirm compute-on-read currentness: the service holds no cross-call state and reads
  the latest persisted concepts/relationships each call, so add/remove is reflected automatically; add
  an idempotency assertion (same input → identical `ConceptHierarchy`). Depends on T008, T012.

**Checkpoint**: All three stories independently functional — navigable, explained, complete, current.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Evals, edge cases, hardening, and the release gate.

- [ ] T021 [P] Build the hierarchy eval scorer in `evals/harness/hierarchy.py`: **structural
  faithfulness** (every parent→child link resolves to a real relationship edge — 100% or fail),
  **coverage** (every concept placed or unplaced, once), and **relevance** (roots vs the dataset's
  curated main-theme concepts; each child judged related to its parent); wire it into the harness
  report/gate alongside the existing faithfulness/relevance scorers.
- [ ] T022 [P] Extend `evals/datasets/energy-cycle/dataset.json` with hierarchy ground truth (expected
  root/pillar concepts and a few expected parent→child relations); re-record `fixtures.json` with
  `--live` only if needed (budget the LLM credit), then verify on replay (0 quota).
- [x] T023 [P] Edge-case unit tests in `tests/unit/test_hierarchy_edge_cases.py`: single dominant
  pillar (one root, rest beneath); fully-disconnected graph (all `unplaced`); too-small corpus (empty
  roots + note); flat/uniform graph (shallow, wide tree — no fabricated depth) per spec Edge Cases.
- [x] T024 [P] Make `ruff check`, `ruff format --check`, and `mypy` clean across `src`, `tests`, and
  `evals` for the new code.
- [ ] T025 Update docs: a README section on the hierarchy endpoints; a `decisions.md` entry only if an
  implementation decision diverged from the plan; refresh `progress.md`.
- [ ] T026 Run `quickstart.md` Scenario 1 (offline) + Scenario 2 (replay): confirm structural
  faithfulness 100%, coverage 100%, relevance ≥ the dataset threshold, and **no regression** on feature
  001's evals (shared faithfulness gate).
- [ ] T027 Release gate (Constitution): full `pytest` green, evals green (hierarchy structural
  faithfulness = 100%), ruff + mypy clean, no unresolved constitution violations; commit and push.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup — **blocks all user stories** (value objects).
- **US1 (P3)**: depends on Foundational. The MVP — builds the forest + endpoints.
- **US2 (P4)**: depends on US1 (it enriches the nodes US1 produces with grounded reasons).
- **US3 (P5)**: depends on US1 (coverage/currentness of the built forest); independent of US2.
- **Polish (P6)**: depends on the stories it touches; T027 is last.

### Within each story

- Tests first (must fail), then domain → service → serializer → endpoint → wire.
- `HierarchyService.build` (T008) is the spine; US2 and US3 extend/validate it rather than replace it.

### Parallel opportunities

- Foundational: T002, T003, T004 in parallel (same new file for T002/T003 — coordinate, or do T002
  then T003).
- US1 tests T005–T007 in parallel; US2 tests T013–T014 in parallel; US3 tests T017–T018 in parallel.
- Polish: T021–T024 largely parallel.

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1 → **STOP and validate** US1 independently
   (run T005–T007 + the quickstart live scenario) → a navigable, source-linked pillar forest.

### Incremental delivery

Setup + Foundational → US1 (MVP) → US2 (explained placements) → US3 (coverage + currentness), each
tested independently before moving on. Keep structural faithfulness (every link a real edge) green at
every step — it is the release gate, not a final polish item.

---

## Notes

- `[P]` = different files, no incomplete dependency.
- Integration/contract tests use the fake LLM adapter (deterministic, free); the hierarchy build makes
  no LLM call at all, so only the ingest step in a live run spends quota.
- The faithfulness guarantee — a parent→child link is only ever a real relationship edge — is the
  backbone of Principle I for this feature; never attach a concept to a parent it has no edge to.
- Commit after each task or logical group; push after the feature is done and tested (repo workflow).
