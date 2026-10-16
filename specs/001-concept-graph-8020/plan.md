# Implementation Plan: Concept Graph & Explainable 80/20

**Branch**: `001-concept-graph-8020` | **Date**: 2026-10-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-concept-graph-8020/spec.md`

## Summary

Build the v1 backend that ingests a student's notes (plain text, Markdown, text-based PDF),
extracts concepts and the relationships between them into a source-grounded knowledge graph, and
produces an explainable 80/20 ranking of the "vital few" concepts — each with a visible, source-
linked rationale derived from graph signals (centrality, recurrence).

Technical approach: a **framework-agnostic core domain** (entities + use-case services) that depends
only on **ports** (interfaces), with swappable **adapters** behind them — SQLite for persistence,
NetworkX for graph computation, an LLM provider for extraction/ranking, and file parsers per format.
A thin **FastAPI** layer exposes the capability over HTTP for the (deferred) frontend and for tests.
For the MVP the LLM adapter targets **Google Gemini's free tier**; the port makes a later swap to a
more capable model a contained change. The whole pipeline runs **locally, single-user**.

## Technical Context

**Language/Version**: Python 3.12, managed with **uv** (virtualenv + resolution + lockfile).

**Primary Dependencies**:
- **FastAPI** + **Uvicorn** — HTTP API (thin delivery layer).
- **Pydantic v2** — request/response DTOs and validation at the boundary.
- **NetworkX** — in-memory graph + centrality/recurrence algorithms (graph-signal computation).
- **PyMuPDF** — text extraction from text-based PDFs.
- **google-genai** (official Google Gen AI SDK) — Gemini adapter for concept extraction + ranking.
- **pytest** — deterministic tests; plus a small in-repo eval harness for AI capabilities.
- Tooling: **ruff** (lint + format), **mypy** (types).

**Storage**: Local **SQLite** file as the source of truth (materials, concepts, relationships,
rankings, all scoped by workspace), accessed only through a repository **port**. **NetworkX** holds
the in-memory graph built from SQLite for signal computation. Documented future target (not v1):
PostgreSQL (workspace/user data) + Neo4j (graph). Migration trigger: going cloud / multi-user.

**Testing**: pytest for deterministic logic (parsing, graph construction, API contracts, workspace
isolation); an eval suite (in `evals/`) scoring every AI capability for **faithfulness** (no
ungrounded output) and **relevance**, run before any prompt/model/pipeline change.

**Target Platform**: Local developer machine, cross-platform (developed on Windows 10). Single-user,
single workspace. The only network dependency is outbound LLM calls to Gemini.

**Project Type**: Backend HTTP web service over a framework-agnostic core library. Frontend deferred
(will be TypeScript, consuming this API).

**Performance Goals**: Spec **SC-005** (upload → vital-few view in under 2 minutes for ~50 pages) is
the target. **Constraint:** Gemini free-tier rate limits (order-of ~10 requests/min, ~250k tokens/min
— confirm live in AI Studio) throttle LLM-bound steps, so for larger batches SC-005 may relax on the
free tier; extraction is chunked, throttled, and retried with backoff. This is an MVP constraint, not
a property of the design.

**Constraints**:
- **Source-faithfulness (Principle I):** every concept, relationship, and ranking MUST carry a
  provenance reference (material + passage span); no outside enrichment.
- **Secrets (Principle V):** `GEMINI_API_KEY` and all config via environment / `.env` (gitignored),
  never committed.
- **Gemini free-tier data use (Principle V):** content sent to the free tier may be used by Google to
  improve their products. Acceptable for the author's **own, non-sensitive test notes during MVP
  only**; real third-party student coursework MUST NOT be processed until on a paid/no-training tier.
  Recorded as a time-boxed exception (see Constitution Check → Complexity Tracking).

**Scale/Scope**: One user, one workspace, tens of materials, ~50 pages per ingest batch for v1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | How this plan satisfies it | Gate |
|---|-----------|----------------------------|------|
| I | Source-Faithfulness | Every derived entity (Concept, Relationship, Vital-Few Entry) carries a `SourceReference` to the material + passage span; the extractor is prompted to ground every item and to emit the supporting span; ungrounded items are dropped or flagged; enforced by the faithfulness eval. | ✅ |
| II | Explainable Intelligence | Ranking = graph signals (centrality, recurrence) as evidence + LLM explainer; `VitalFewEntry` stores the signals and a plain rationale with source links. No black-box scores. | ✅ |
| III | Documented Decisions | All tech/design decisions recorded here and in [research.md](./research.md) with rationale and alternatives (the plan is the ADR home per project convention). | ✅ |
| IV | Understand Before Adopt | Each dependency is deliberately chosen and explainable (research.md gives the "why" for FastAPI, Pydantic, NetworkX, PyMuPDF, google-genai, uv, pytest). No copy-paste adoption. | ✅ |
| V | Privacy & Data Stewardship | All data scoped by `workspace_id` at storage and query layers (isolation seam ready for multi-user); secrets via env; local TLS not required. **Caveat:** Gemini free-tier data-use — handled as a time-boxed MVP exception (below). | ⚠️→✅ |
| VI | Simplicity that Ships | Single project, SQLite + NetworkX, one LLM model, one HTTP app. The only abstractions are the ports — each justified by a *concrete, already-known* future change (see Complexity Tracking), not speculation. | ✅ |
| VII | Verified Reliability | Deterministic tests (parsing, graph build, API contract, workspace isolation) + eval suite (faithfulness, relevance) gating prompt/model/pipeline changes. | ✅ |
| VIII | Senior-Grade Code Quality | Hexagonal core/ports/adapters layout, consistent patterns, DTOs at the boundary, lint+types (ruff, mypy). | ✅ |

**Result: PASS** (with the Gemini free-tier data-use item justified and time-boxed in Complexity
Tracking). The two load-bearing guarantees — Source-Faithfulness (I) and Verified Reliability (VII) —
are designed in, not bolted on.

## Project Structure

### Documentation (this feature)

```text
specs/001-concept-graph-8020/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions, rationale, alternatives
├── data-model.md        # Phase 1 — entities, fields, relationships, validation
├── quickstart.md        # Phase 1 — runnable end-to-end validation guide
├── contracts/
│   └── http-api.md      # Phase 1 — HTTP API contract (endpoints, shapes, errors)
└── checklists/
    └── requirements.md  # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root)

```text
src/distil/
├── domain/              # Entities & value objects: Material, Concept, Relationship,
│                        #   VitalFewEntry, SourceReference, Workspace. Pure, no I/O.
├── ports/               # Abstract interfaces (Protocols/ABCs):
│                        #   MaterialRepository, GraphRepository, ConceptExtractor,
│                        #   Ranker, GraphAnalyzer, FileParser.
├── services/            # Use-cases orchestrating ports:
│                        #   ingestion, graph_builder, ranking. No framework/SDK imports.
├── adapters/
│   ├── persistence/sqlite/   # SQLite implementations of the repository ports
│   ├── graph/networkx/       # NetworkX implementation of GraphAnalyzer
│   ├── llm/gemini/           # Gemini implementation of ConceptExtractor + Ranker
│   └── parsing/              # text, markdown, pdf (PyMuPDF) FileParsers
├── api/                 # FastAPI app: routers, Pydantic DTOs, dependency wiring
└── config.py            # Settings from env (.env): GEMINI_API_KEY, GEMINI_MODEL, DB path

tests/
├── unit/                # Pure logic: parsers, graph build, ranking math, domain rules
├── integration/         # Pipeline with fake LLM adapter (deterministic), real SQLite
└── contract/            # API request/response contract tests against http-api.md

evals/
├── datasets/            # Curated, versioned eval inputs + expected groundings
└── harness/             # Runner scoring faithfulness (deterministic provenance checks)
                         #   and relevance (LLM-judge), with thresholds that gate changes
```

**Structure Decision**: Single Python project, **hexagonal (ports & adapters)** layout. The
`domain`, `ports`, and `services` layers are framework- and vendor-agnostic; everything that touches
SQLite, NetworkX, Gemini, PDF parsing, or HTTP lives in `adapters/` or `api/`. This keeps the two
load-bearing guarantees testable (fakes injected via ports) and makes the two already-known swaps
(DB and LLM) contained. Rationale and the dependency "why" are in [research.md](./research.md).

## Complexity Tracking

> Justifications for abstraction beyond the simplest possible script (Principle VI gate).

| Complexity | Why needed (concrete) | Simpler alternative rejected because |
|------------|------------------------|--------------------------------------|
| Persistence port (repository interface) | A migration to Postgres + Neo4j is already decided for cloud/multi-user. | Direct SQLite calls everywhere would force a rewrite at migration and prevent injecting an in-memory fake for fast tests. |
| LLM provider port (ConceptExtractor / Ranker) | The user will swap the free-tier Gemini model for a more capable one once scope expands (stated plan). | Hard-coding the Gemini SDK across services would make the swap a rewrite and block deterministic tests (no fake LLM). |
| Core/adapters/API layering | A TS frontend will consume an HTTP API (near-term, stated); faithfulness + reliability need seams to inject fakes (Principle VII); craftsmanship (Principle VIII). | A single module with inline SDK/DB/HTTP calls cannot be unit-tested for faithfulness without live services and does not survive the coming frontend + DB changes. |
| Gemini free-tier data-use exception | MVP needs a zero-cost model to prove the pipeline; the author uses only their own non-sensitive test notes. | Waiting for a paid no-training tier would block all MVP progress; the risk is bounded by using only the author's own test data and is removed at the first real-data milestone. |
