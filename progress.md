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
- **Phase 3 US1 (MVP) — functionally complete on the fake LLM:** parsers (text/md/PDF,
  T020/T022/T023) ✅; ingestion (T024) ✅; provenance gate + graph builder/merge + NetworkX signals
  (T021/T026/T027/T030) ✅; **ranking service** (Pareto cut ~20%, SC-004 hard cap ≤25%, builds
  `RankingRun`/`VitalFewEntry`, evidence provenance gate with fallback to grounded concept
  sources) ✅; **batch pipeline** (ingest → rebuild graph → rank → persist, T029) ✅; **US1 API**
  (POST/GET `/materials`, GET `/vital-few`, GET `/concepts/{id}`, T031–T033) ✅ with a composition
  root injecting adapters behind ports; **contract + E2E tests** (T017/T018/T019) ✅.
- **Ranking refactor (post-MVP):** split the old `Ranker` port into a prose-only `Explainer` port
  and moved all ordering into `services/ranking.py` — deterministic composite of normalised
  PageRank (0.5) + degree (0.25) + recurrence (0.25), ties broken by label. The LLM now only writes
  the rationale for already-chosen concepts; it **cannot** reorder (Principle II). Signal weights are
  the eval-tunable knob (T044/T045).
- **Gemini adapters landed (T025/T028):** `src/distil/adapters/llm/gemini/` — `prompts.py` (the two
  reviewed prompts + Pydantic structured-output schemas, in source per Principle VII); `_client.py`
  (`GeminiClient` over google-genai 2.31, `temperature=0`, `with_retries` exponential backoff on
  429/5xx — a pure, unit-tested policy); `extractor.py` (model returns verbatim quotes only, adapter
  locates each via `find`, computes absolute offsets across overlapping chunks, builds a faithful
  `SourceReference`, drops anything not found — malformed response skips the chunk, not the ingest);
  `explainer.py` (single batched call, blank/missing → service fallback). `build_gemini_provider`
  raises `ValueError` if `GEMINI_API_KEY` is unset; wired into `build_llm_provider`.
- **64 tests passing** (was 48; +13 offline adapter tests via a scripted fake `JsonLLM`, +others).
  Added `python-multipart` (FastAPI upload parsing). `google-genai` already a declared dep.
- Notable choices this chunk: `MIN_CONCEPTS_FOR_VITAL_FEW = 5` (below it the vital-few view returns
  empty + an explanatory note rather than an arbitrary shortlist); SQLite opened with
  `check_same_thread=False` (documented — safe for v1 single-user/local, Postgres pool is the
  multi-user path); `build_llm_provider` raises a clear `NotImplementedError` until the Gemini
  adapter lands, so the app imports and the whole MVP is testable on fakes with no network/cost.

### State of the repo
- **Git repo on `main`**, ~14 commits. Constitution **v1.1.0**. Feature 001 specced + planned;
  **US1 MVP wired end-to-end and green on the fake LLM.** Everything green (ruff + format + mypy
  strict + pytest).

### Pick up here next
1. **Before the first real Gemini call:** confirm the exact `gemini-3-flash` API model string + live
   free-tier rate/token limits in AI Studio (sets chunk size); then do a single smoke run against the
   author's own non-sensitive test notes (Principle V) to validate the prompts end-to-end. No live
   call has been made yet — everything is green on fakes only.
2. **US2 (T034–T038):** graph endpoints (concept graph view / neighborhood).
3. **US3 (T039–T043):** material delete + graph/ranking rebuild.
4. **Polish (T044–T051):** eval harness (faithfulness = 100% deterministic + relevance LLM-judge),
   datasets, edge cases, README Principle V caveat, hardening, T050 quickstart vs real Gemini, T051
   release gate. Tune signal weights + chunk size/overlap via evals.

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
