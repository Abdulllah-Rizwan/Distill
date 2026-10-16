---
description: "Task list for Concept Graph & Explainable 80/20 (feature 001)"
---

# Tasks: Concept Graph & Explainable 80/20

**Input**: Design documents from `specs/001-concept-graph-8020/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-api.md

**Tests**: INCLUDED — not optional here. Constitution **Principle VII** mandates deterministic tests
for ingestion/parsing, graph construction, API contracts, and workspace isolation, and an **eval
suite** for every AI capability (faithfulness + relevance). Test/eval tasks below are required.

**Organization**: Grouped by user story (US1 = P1 MVP, US2 = P2, US3 = P3) so each is independently
implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task).
- **[Story]**: US1 / US2 / US3. Setup, Foundational, and Polish tasks carry no story label.
- Paths follow the hexagonal layout in `plan.md` (`src/distil/...`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and structure.

- [x] T001 Create the hexagonal project structure per plan.md: `src/distil/{domain,ports,services,adapters/{persistence/sqlite,graph/networkx,llm/gemini,parsing},api}`, `tests/{unit,integration,contract,_fakes}`, `evals/{datasets,harness}` (with `__init__.py` where needed)
- [x] T002 Initialize uv project in `pyproject.toml` (Python 3.12): runtime deps `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `networkx`, `pymupdf`, `google-genai`; dev deps `pytest`, `ruff`, `mypy`; then `uv sync`
- [x] T003 [P] Configure `ruff` (lint + format) and `mypy` (strict-ish) in `pyproject.toml`
- [x] T004 [P] Implement `src/distil/config.py` loading settings from env/`.env` (`GEMINI_API_KEY`, `GEMINI_MODEL` default `gemini-3-flash`, `DISTIL_DB_PATH` default `./data/distil.db`); add `.env.example` (placeholders only, no secret)

**Checkpoint**: Project installs and lints; config loads from env.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain model, ports, persistence, and app skeleton that ALL stories depend on.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [x] T005 [P] Define `SourceReference` value object in `src/distil/domain/source_reference.py` with fields `material_id, start_offset, end_offset, quote, page?`; enforce "`0 ≤ start_offset < end_offset ≤ len(content_text)`" and "`quote` MUST equal `content_text[start_offset:end_offset]`" via a `validate(content_text)` method (the core faithfulness check)
- [x] T006 [P] Define `Workspace` (`src/distil/domain/workspace.py`) and `Material` (`src/distil/domain/material.py`): `Material.format` enum = `text|markdown|pdf`, `status` enum = `accepted|rejected|empty`, `content_hash`; rules — a `pdf` with no extractable text → `status=rejected` with `rejected_reason`; blank content → `status=empty`; `content_hash` unique per workspace
- [x] T007 [P] Define `Concept` (`src/distil/domain/concept.py`) and `Relationship` (`src/distil/domain/relationship.py`): Concept requires `len(sources) ≥ 1` and `recurrence_count ≥ 1`; Relationship requires `source_concept_id != target_concept_id`, `len(sources) ≥ 1`, and no duplicate `(pair, kind)` (merge sources instead)
- [x] T008 [P] Define `VitalFewEntry` and `RankingRun` in `src/distil/domain/ranking.py`: VitalFewEntry requires `rank ≥ 1` unique within a run, non-empty `rationale`, `len(evidence) ≥ 1`; RankingRun requires `vital_few_size ≤ cap` (target ≤ 25% of total concepts, per SC-004)
- [x] T009 Define port interfaces (Protocols/ABCs) in `src/distil/ports/`: `MaterialRepository`, `GraphRepository`, `FileParser`, `ConceptExtractor`, `Ranker`, `GraphAnalyzer` (depends on T005–T008)
- [x] T010 Create SQLite schema + connection/init in `src/distil/adapters/persistence/sqlite/schema.py` (tables for workspace, material, concept + concept_source, relationship + relationship_source, ranking_run, vital_few_entry + vital_few_evidence; every row carries `workspace_id`; `content_hash` unique per `(workspace_id)`)
- [x] T011 Implement SQLite `MaterialRepository` + `GraphRepository` in `src/distil/adapters/persistence/sqlite/repositories.py`; **every query scoped by `workspace_id`** (depends on T009, T010)
- [x] T012 [P] Implement `FakeExtractor` + `FakeRanker` test doubles in `tests/_fakes/llm.py` (deterministic, implement the LLM ports) so integration tests run with no network and no cost
- [x] T013 FastAPI app skeleton in `src/distil/api/main.py`: base path `/api/v1`, consistent error envelope `{"error":{"code","message"}}`, dependency wiring that injects adapters via ports (depends on T009)
- [x] T014 [P] Logging + error-handling infrastructure (structured logs, never logging secrets or full user content)
- [x] T015 [P] Unit test `SourceReference` provenance validation (offset bounds + `quote == slice`) in `tests/unit/test_source_reference.py`
- [x] T016 Integration test workspace isolation (repositories never return cross-workspace rows) in `tests/integration/test_workspace_isolation.py` (depends on T011)

**Checkpoint**: Domain + ports + SQLite + app skeleton ready; faithfulness check and isolation proven.

---

## Phase 3: User Story 1 — Surface the vital few, explained (Priority: P1) 🎯 MVP

**Goal**: Upload notes → source-grounded concept graph → explainable 80/20 vital-few view, every item traceable to source.

**Independent Test**: Upload a set of notes, call `GET /vital-few`, and confirm a ranked, explained shortlist where every entry has a rationale and non-empty, verifiable `evidence` (quote == source slice).

### Tests for User Story 1 (write first, ensure they FAIL)

- [x] T017 [P] [US1] Contract test `POST /api/v1/materials` (201 accepted / 200 duplicate / 202 empty / 415 unsupported) in `tests/contract/test_materials_post.py`
- [x] T018 [P] [US1] Contract test `GET /api/v1/vital-few` and `GET /api/v1/concepts/{id}` incl. the faithfulness guarantee (every entry has non-empty `evidence`; each `quote == content[start:end]`) in `tests/contract/test_vital_few.py`
- [x] T019 [P] [US1] End-to-end integration test with `FakeExtractor`/`FakeRanker`: upload markdown + text → `vital-few` returns ranked explained entries with provenance, in `tests/integration/test_pipeline_us1.py`
- [x] T020 [P] [US1] Unit tests for parsers (text, markdown, PDF incl. no-text rejection) in `tests/unit/test_parsers.py`
- [x] T021 [P] [US1] Unit test graph-signal computation (degree, PageRank, recurrence) in `tests/unit/test_graph_signals.py`

### Implementation for User Story 1

- [x] T022 [P] [US1] Implement text + Markdown `FileParser` in `src/distil/adapters/parsing/text.py` (preserve char offsets for provenance)
- [x] T023 [P] [US1] Implement PDF `FileParser` (PyMuPDF) in `src/distil/adapters/parsing/pdf.py`: extract text + `page_map`; detect and reject image-only/no-text PDFs (→ `rejected`)
- [x] T024 [US1] Implement ingestion service in `src/distil/services/ingestion.py`: parse → `Material`, set `status`, dedup by `content_hash` (FR-014) (depends on T022, T023, T011)
- [x] T025 [US1] Implement Gemini `ConceptExtractor` in `src/distil/adapters/llm/gemini/extractor.py`: structured output requiring a provenance span per concept/relationship; chunk long text with overlap; throttle + exponential backoff for free-tier rate limits; drop any item whose `quote` ≠ source slice (depends on T009) — **done: model returns verbatim quotes only, adapter computes offsets via `find` + builds faithful `SourceReference`; retry/backoff in `_client.py`; prompts + response schemas in `prompts.py`**
- [x] T026 [US1] Implement concept/relationship merge + dedup across chunks and materials in `src/distil/services/graph_builder.py` (depends on T025)
- [x] T027 [US1] Implement NetworkX `GraphAnalyzer` in `src/distil/adapters/graph/networkx/analyzer.py`: build graph, compute degree + PageRank centrality, set `recurrence_count` (depends on T009)
- [x] T028 [US1] Implement Gemini `Explainer` in `src/distil/adapters/llm/gemini/explainer.py`: write one plain `rationale` sentence per already-ranked concept in a single batched call; cannot touch rank/signals/evidence (depends on T009) — **done: ranking _service_ (cap + `RankingRun`/`VitalFewEntry` + evidence provenance gate + deterministic composite ordering) lives in `src/distil/services/ranking.py`; the `Ranker` port was split into the prose-only `Explainer` port so the model cannot reorder (Principle II). Missing/blank rationales fall back to a deterministic sentence**
- [x] T029 [US1] Implement batch pipeline orchestration (ingest → extract → merge → build graph → rank) triggered on upload, in `src/distil/services/pipeline.py` (depends on T024–T028)
- [x] T030 [US1] Implement a provenance validator applied before persisting ANY concept/edge/entry (`quote == content[start:end]`, else drop/flag) in `src/distil/services/provenance.py` — enforces Source-Faithfulness (depends on T005)
- [x] T031 [US1] Implement `POST /api/v1/materials` + `GET /api/v1/materials` in `src/distil/api/routers/materials.py` (depends on T024, T029)
- [x] T032 [US1] Implement `GET /api/v1/vital-few` + `GET /api/v1/concepts/{id}` in `src/distil/api/routers/vital_few.py`: guarantee non-empty `sources`/`evidence`; return empty list + explanatory `note` for too-small corpus (depends on T029)
- [x] T033 [US1] Wire US1 routers into the app and make T017–T019 pass (depends on T031, T032)

**Checkpoint**: MVP — a student can upload notes and get the explained, source-linked vital-few view.

---

## Phase 4: User Story 2 — Explore the concept graph (Priority: P2)

**Goal**: Browse the concept graph; every node and edge traceable to source.

**Independent Test**: With a built graph, call `GET /graph`; confirm nodes/edges render and each edge exposes the source passage asserting the relationship.

### Tests for User Story 2 (write first, ensure they FAIL)

- [ ] T034 [P] [US2] Contract test `GET /api/v1/graph` and `GET /api/v1/graph/edges/{id}` in `tests/contract/test_graph.py`
- [ ] T035 [P] [US2] Integration test: nodes carry centrality/recurrence and edges carry `sources` in `tests/integration/test_graph_us2.py`

### Implementation for User Story 2

- [ ] T036 [US2] Implement `GET /api/v1/graph` in `src/distil/api/routers/graph.py`: nodes (label, centrality, recurrence) + edges (kind, sources) (depends on T027, T011)
- [ ] T037 [US2] Implement `GET /api/v1/graph/edges/{id}` returning a single edge with relationship provenance (depends on T036)
- [ ] T038 [US2] Wire US2 routers and make T034–T035 pass

**Checkpoint**: Graph exploration works independently on top of the US1 graph.

---

## Phase 5: User Story 3 — Keep the knowledge base current (Priority: P3)

**Goal**: Adding/removing materials updates the graph and ranking; duplicates don't inflate importance.

**Independent Test**: Delete a material and confirm concepts it *solely* supported disappear; re-upload the same file and confirm it dedups (no inflated importance).

### Tests for User Story 3 (write first, ensure they FAIL)

- [ ] T039 [P] [US3] Contract test `DELETE /api/v1/materials/{id}` in `tests/contract/test_materials_delete.py`
- [ ] T040 [P] [US3] Integration test: delete → solely-supported concepts/edges removed; re-upload dedups (no inflation) in `tests/integration/test_keep_current_us3.py`

### Implementation for User Story 3

- [ ] T041 [US3] Implement `DELETE /api/v1/materials/{id}` (workspace-scoped) + rebuild trigger in the materials router (depends on T031, T029)
- [ ] T042 [US3] Implement rebuild-on-change in the pipeline: remove orphaned concepts/edges whose supporting sources are all gone; ensure re-run is idempotent (depends on T029)
- [ ] T043 [US3] Wire US3 and make T039–T040 pass

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Evals, edge-case coverage, hardening, and the release gate.

- [ ] T044 [P] Build the eval harness in `evals/harness/` (`python -m evals.harness`): **faithfulness** scored deterministically (every emitted concept/edge/ranking resolves to a real source span — any ungrounded item fails) + **relevance** via an LLM-judge; thresholds that gate prompt/model/pipeline changes
- [ ] T045 [P] Create curated, versioned eval dataset(s) in `evals/datasets/` (sample notes + expected groundings and "most important" concept labels)
- [ ] T046 [P] Unit tests for edge cases in `tests/unit/test_edge_cases.py`: empty/single material, too-small corpus (empty vital-few + note), conflicting cross-material statements kept (not silently resolved)
- [ ] T047 [P] Write `README.md` (setup/run per `quickstart.md`); document the Principle V Gemini free-tier data-use caveat prominently
- [ ] T048 Harden Gemini adapter: rate-limit throttle/backoff and clear user-facing messages on LLM failure/timeout
- [ ] T049 [P] Make `ruff` and `mypy` clean across `src/` and `tests/`
- [ ] T050 Run `quickstart.md` end-to-end against real Gemini 3 Flash; confirm the exact model string + live free-tier limits in AI Studio
- [ ] T051 Release gate (Constitution): faithfulness eval = 100% grounded, `pytest` green, no unresolved constitution violations

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: no dependencies.
- **Foundational (P2)**: depends on Setup — **blocks all user stories**.
- **US1 (P3)**: depends on Foundational. The MVP.
- **US2 (P4)**: depends on Foundational + the graph built in US1 (T027). Endpoints are otherwise independent.
- **US3 (P5)**: depends on Foundational + US1 ingestion/pipeline (T024, T029).
- **Polish (P6)**: depends on the user stories it touches; T051 is last.

### Within each story

- Tests first (must fail), then models → services → adapters → endpoints → wire.
- Models before services; services before endpoints; provenance validation (T030) gates all persistence.

### Parallel opportunities

- Setup: T003, T004 in parallel.
- Foundational: T005–T008 (domain models) in parallel; T012, T014, T015 in parallel with each other.
- US1 tests T017–T021 in parallel; parsers T022, T023 in parallel.
- US2 tests T034–T035 in parallel; US3 tests T039–T040 in parallel.
- Polish: T044–T047, T049 largely parallel.

---

## Parallel Example: User Story 1 tests

```text
# Launch US1 test tasks together (all different files, no interdeps):
T017  Contract test POST /materials      → tests/contract/test_materials_post.py
T018  Contract test vital-few/concepts   → tests/contract/test_vital_few.py
T019  E2E integration (fake LLM)          → tests/integration/test_pipeline_us1.py
T020  Parser unit tests                   → tests/unit/test_parsers.py
T021  Graph-signal unit tests             → tests/unit/test_graph_signals.py
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational (critical) → 3. Phase 3 US1 → **STOP and validate**
   US1 independently (run T017–T021 + the quickstart US1 scenario) → demo-ready MVP.

### Incremental delivery

Setup + Foundational → US1 (MVP) → US2 → US3, each tested independently before moving on. Keep
faithfulness green at every step (it is the release gate, not a final polish item).

---

## Notes

- `[P]` = different files, no incomplete dependency.
- Integration tests use the fake LLM adapter (deterministic, free); the real Gemini adapter is
  exercised only in the quickstart/eval runs (T050) to respect free-tier limits and cost.
- Commit after each task or logical group. Keep `main` releasable (Development Workflow).
- The faithfulness provenance check (T030, T015) is the backbone of Principle I — never bypass it.
