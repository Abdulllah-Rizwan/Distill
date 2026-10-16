# Distil — Progress Log

Rolling log of what was done each day and what to pick up next. Decisions and their rationale live
in `decisions.md`; this file tracks *activity and todos* only.

---

## 2026-10-16

### Done today
- Reasoned out the foundational tech-stack / ingestion direction through discussion, then **corrected
  where it gets recorded**: these are *planning-phase* decisions, so they belong in `plan.md` via
  `/speckit-plan`, not in `decisions.md`. `decisions.md` is now reserved for decision *shifts*
  (plan → implementation divergence) and governance. Rationale is retained below so `/speckit-plan`
  can capture it formally.
- **Amended the constitution → v1.1.0**, adding **Principle VIII — Senior-Grade Code Quality**.
  Recorded in the constitution's own version history (not as a decisions.md ADR).
- Reframed `decisions.md`: new purpose statement (shifts + governance only), kept the three founding
  entries (ADR-0001–0003), removed the planning entries I had wrongly logged there.
- **`git init` + two commits**: initial scaffold/constitution/logs, then the spec. Branch renamed
  `master` → `main`. Added `.gitignore` (secrets, Python, SQLite) and `.gitattributes` (LF for `.sh`).
- **Ran `/speckit-specify`** → `specs/001-concept-graph-8020/spec.md` (3 user stories, 16 FRs, 8 SCs,
  edge cases, assumptions). Quality checklist all-pass. Committed.
- **Ran `/speckit-plan`** → generated `plan.md`, `research.md`, `data-model.md`,
  `contracts/http-api.md`, `quickstart.md`. Post-design Constitution Check PASS.

### Planning decisions formalized (now in `plan.md` / `research.md`)
- **Python 3.12**, packaging via **uv**. Backend-first; TS frontend deferred.
- **Interface = FastAPI HTTP API over a framework-agnostic core** (hexagonal ports/adapters).
- **Storage = SQLite (source of truth) + NetworkX (compute) behind a persistence port**; target
  Postgres + Neo4j on cloud; migration trigger = cloud/multi-user.
- **80/20 = batch ranking on ingest** (graph signals: centrality + recurrence) + LLM explainer.
- **PDF = PyMuPDF; tests = pytest; evals = small in-repo harness** (faithfulness deterministic +
  relevance LLM-judge) in `evals/`.
- **LLM = Google Gemini 3 Flash, free tier** (`GEMINI_MODEL=gemini-3-flash`), behind an LLM provider
  port — **changed from the Claude options I had offered**; user chose free-tier to avoid cost and
  plans to swap to a more capable model later (that swap will be a `decisions.md` decision-shift).
- ⚠️ **Principle V caveat recorded**: Gemini free-tier content may be used by Google to improve
  products → MVP only with the author's own non-sensitive test notes; not for real student data until
  on a paid/no-training tier.

### Implementation progress (feature 001)
- Ran `/speckit-tasks` → 51 tasks. Building incrementally, committing each verified chunk (ruff +
  mypy + pytest green at every commit).
- **Phase 1 Setup (T001–T004): done** — uv project (Python 3.12), hexagonal layout, ruff/mypy/pytest
  config, pydantic-settings config, `.env.example`, README.
- **Phase 2 Foundational (T005–T016): done** — domain entities (frozen dataclasses) with invariants
  incl. the `SourceReference` faithfulness check; ports (Protocols); SQLite schema + repositories
  (JSON columns, workspace-scoped); FakeExtractor/FakeRanker; FastAPI skeleton + error envelope;
  logging.
- **Phase 3 US1 (MVP) — in progress:** parsers (text/md/PDF, T020/T022/T023) ✅; ingestion
  (T024) ✅; provenance gate + graph builder/merge + NetworkX signals (T021/T026/T027/T030) ✅.
  **Remaining:** ranking service + pipeline orchestration (T028/T029), API endpoints
  (T031/T032/T033), contract + E2E tests (T017/T018/T019), real Gemini extractor/ranker adapters
  (T025/T028).
- **28 tests passing.** numpy/scipy added as networkx's PageRank backend.

### State of the repo
- **Git repo on `main`**, ~13 commits. Constitution **v1.1.0**. Feature 001 specced + planned +
  ~65% of the MVP built. Everything green.

### Pick up here next
1. Ranking service + pipeline orchestration (ingest → extract → build → rank → persist).
2. API endpoints (POST/GET /materials, GET /vital-few, /concepts/{id}) + contract/E2E tests → MVP.
3. Real **Gemini 3 Flash** extractor + ranker adapters (prompts in source per Principle VII; worth a
   review). Confirm the exact API model string + live free-tier limits in AI Studio before first call.

### Open questions to resolve
- Confirm the `gemini-3-flash` API model string + live free-tier rate limits (AI Studio).
- Signal weighting for the 80/20 (degree + PageRank in; tune via evals).
- Chunk size / overlap for extraction (set from model context window + free-tier TPM).

---

## 2026-10-15

### Done today
- Explored the project: confirmed it's a fresh, empty Spec Kit scaffold (only `.claude/` and
  `.specify/`), initialized for the `claude` integration. No source code yet.
- Read and discussed the product vision (`problem.txt`) — Distil as a collaborative AI "second
  brain" for students.
- Scoped the product through discussion:
  - Confirmed **v1 = ingestion → concept graph → explainable 80/20 view** (see ADR-0002).
  - Confirmed solo, learning-first build; every key decision to be logged with rationale.
- **Drafted and ratified the project constitution** at `.specify/memory/constitution.md` (v1.0.0),
  7 principles tailored to Distil. Ratification date set to 2026-10-15; removed the scratch Sync
  Impact Report comment.
- Established decision-tracking: confirmed Spec Kit has no built-in progress/decision mechanism, so
  created `decisions.md` (ADR log, satisfies constitution Principle III) and this `progress.md`.
  Logged ADR-0001, ADR-0002, ADR-0003.

### State of the repo
- Not yet a git repository (`git init` not run). No application code. No feature specs yet.

### Pick up here tomorrow
1. **Decide ingestion & graph storage first (ADR-TBD).** In the spirit of Principle III, reason out
   — and record in `decisions.md` — how notes get in (which file formats for v1, parsing/OCR
   approach) and what the concept graph is stored in (graph DB vs. relational vs. other). This is
   the foundational choice everything else rests on.
2. **Then run `/speckit-specify`** for the v1 slice (ingest → graph → explainable 80/20) once the
   storage/ingestion direction is set.
3. **Consider `git init`** so decisions, specs, and code are version-controlled from the start.

### Open questions to resolve
- Which note formats must v1 accept (PDF, docx, slides, plain text, images needing OCR)?
- Graph storage engine — and does the 80/20 ranking run as a batch step or on demand?
- Where will AI eval datasets live in the repo structure (needed per Principle VII)?
