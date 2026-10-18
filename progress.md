# Distil — Progress Log

Rolling log of what was done each day and what to pick up next. Decisions and their rationale live
in `decisions.md`; this file tracks *activity and todos* only.

---

## 2026-10-18

### Context — eval baseline blocked by Gemini quota, pivoted to a DeepSeek provider
- **Tried to record the eval baseline first thing** (`evals.harness --live --dataset energy-cycle`).
  Replay seam verified (fails cleanly on missing fixtures). **Still 429 `RESOURCE_EXHAUSTED`** — the
  free-tier daily window does **not** reset at local midnight; the 429 returns `retryDelay ~20h`.
  Nothing recorded, working tree untouched. Also learned: the 429 labels the bucket `gemini-3-flash`
  even though we call `gemini-3-flash-preview` — **both share one 20/day quota bucket** (config is
  correct; DS-0001 confirmed in effect). Updated the quota memory with the reset-timing correction.

### Done today — DeepSeek LLM provider added (decision-shift DS-0002, milestone #2 = first DeepSeek call)
- **Author added a DeepSeek API key** and asked to develop against it until its credit runs out
  (Gemini quota being the blocker). Implemented a pluggable provider behind the existing `JsonLLM`
  port — logged as **DS-0002** (decisions.md).
- **Refactor (promote the already-neutral core):** the extractor, explainer, and prompts only ever
  depended on the narrow `JsonLLM` port, so they moved out of `adapters/llm/gemini/` up to
  `adapters/llm/` (`extractor.py`, `explainer.py`, `prompts.py`, new `base.py` = `JsonLLM` protocol +
  a now provider-agnostic `with_retries`). Classes renamed `GeminiConceptExtractor`/`GeminiExplainer`
  → `JsonConceptExtractor`/`JsonExplainer`. `gemini/` keeps only `GeminiClient`.
- **New `adapters/llm/deepseek/`:** `DeepSeekClient` — a thin `httpx` POST to the OpenAI-compatible
  `/chat/completions` (no new dependency; `httpx` already transitive). JSON **mode** + schema injected
  into the prompt (DeepSeek has no server-side schema); response re-validated against the Pydantic
  model as before. Retries reuse the shared policy (429/5xx + transport errors; **402 out-of-credit
  propagates immediately**, no retry loop).
- **Config/wiring:** new `LLM_PROVIDER` setting (default `gemini`) + `DEEPSEEK_API_KEY/MODEL/BASE_URL`
  fields; `build_llm_provider` and the eval harness `--live` client both dispatch on it. `.env.example`
  updated.
- **First live DeepSeek call (synthetic non-sensitive snippet, Principle V):** 3 concepts + 2
  relationships, **all spans faithful** (`quote == source slice`). Integration validated.
- **Everything green:** ruff + format + mypy (configured `uv run mypy`, 51 files) clean; **79 tests**
  (was 71; +7 DeepSeek client tests via `httpx.MockTransport`, + a generalized-retry test; the old
  `test_gemini_adapter.py` became the neutral `test_llm_adapters.py`).

### Done today (cont.) — first eval baseline recorded + two pipeline defects the baseline exposed
- Set `LLM_PROVIDER=deepseek` (user, in `.env`) and ran `evals.harness --live --dataset energy-cycle`.
  Recording worked but **replay `LookupError`'d on the explainer** — tracing (per-call key hit/miss)
  found **two real defects**, now fixed and logged as **DS-0003**:
  1. **Non-deterministic ids** — concept/edge ids were `uuid4`, and the explainer prompt embeds the
     concept id, so recorded fixtures couldn't be matched/replayed. Fix: ids derived from identity
     (`c_<sha256(workspace|label)>`, `e_<sha256(workspace|src|tgt|kind)>`). Bonus: ids are now stable
     across rebuilds (US2/US3 lookups).
  2. **Re-extraction on every rebuild** — `GraphBuilder.build` re-ran the LLM on *all* materials each
     rebuild (3× the quota here) and, being non-deterministic, made rebuilds non-idempotent and the
     intermediate graph states unrecordable. Fix: **memoize extraction per material** (process-level;
     the Pipeline/GraphBuilder is a singleton). Durable fix (persist per-material mentions) deferred —
     see DS-0003; dovetails with US3.
- **Baseline recorded + reproducible:** replay now reproduces the live run **exactly and stably across
  repeated replays**, at zero quota. First real numbers (energy-cycle, DeepSeek):
  **faithfulness 100% (30/30 spans grounded), relevance 0.60** (judge 0.60; precision 1.00, recall
  0.40). `fixtures.json` written (6 entries).
- **Honest quality signal (feeds extraction tuning):** vital-few = {Glucose, Cellular Respiration};
  the judge correctly flags that **Photosynthesis and ATP are missing** though they recur across all
  three notes (recall 0.40). Faithfulness is perfect; **recall/extraction completeness is the gap.**
- **81 tests green** (+2: extraction memoized across rebuilds; ids deterministic across builds); ruff
  + format + mypy clean. `fixtures.json` is a versioned asset (DS-0002: **provider-specific** — the
  current baseline is DeepSeek; re-record if the provider changes).

### Done today (cont.) — pushed to GitHub; diagnosed the real 80/20 blocker; fixed vital-few sizing (DS-0004)
- **GitHub:** added remote `origin` (https://github.com/Abdulllah-Rizwan/Distill.git), pushed `main`.
  Workflow going forward: **push after every feature done + tested** (saved to memory). `.env`/`Notes/`
  confirmed untracked before pushing.
- **Diagnosed the recall gap (it was NOT extraction).** Dumped the full ranking from replay: the
  top-4 by score ARE the 4 important extracted concepts (Glucose, Cellular Respiration, Photosynthesis,
  ATP) — ranking is sound. Recall was low because **the vital-few cut was 2** (20% of 9).
- **Local eyeball run on the 5 lecture PDFs** (real DeepSeek, isolated gitignored scratch DB, nothing
  committed — Principle V): 5 lectures → **211 concepts, vital-few of 43**. Confirmed the flat % cut
  breaks at both ends (2 when tiny, 43 when large). Also: extraction is verbose/noisy (proper-noun &
  slide-fragment clutter), and only 12/211 concepts recur across lectures (disjoint topics — but the
  12 that do recur are the real core: IaaS/SaaS/PaaS/cloud computing/…).
- **Fixed vital-few sizing (DS-0004):** `vital_few_size` is now a **fixed small target (5), clamped to
  the corpus**, not a percentage. Updated SC-004 + spec wording + domain docstring + tests. Re-recorded
  the energy-cycle baseline: **faithfulness 100% (35/35), relevance 1.00** (precision/recall 0.80, up
  from 0.60/0.40); replay reproduces it. 82 tests green; ruff + format + mypy clean.
- **Remaining known gap:** "energy" is never extracted as a standalone concept (expressed as "chemical
  energy"/"energy cycle") — an extraction-granularity question, parked.

### Done today (cont.) — feature 002 specced→planned→tasked, then built feature 001 US2 + US3
- **Feature 002 (Concept Hierarchy) through the full Spec Kit lifecycle** (all pushed):
  `/speckit-specify` → `specs/002-concept-hierarchy/spec.md` (3 user stories, 12 FRs, 7 SCs; checklist
  all-pass); `/speckit-plan` → plan + research + data-model + contracts/hierarchy-api + quickstart
  (Constitution Check PASS; approach = pure `HierarchyService` building a **BFS forest** over the real
  graph, roots = vital-few pillars, **compute-on-read, no new dep, no extra LLM call**, links only ever
  real edges); `/speckit-tasks` → 27 tasks. **Not yet implemented.**
- **Feature 001 US2 — graph endpoints (T034–T038): done.** `GET /api/v1/graph` (nodes with
  centrality/recurrence + edges with grounded sources) and `GET /api/v1/graph/edges/{id}` in
  `api/routers/graph.py` + serializers; wired into the app. Contract + integration tests.
- **Feature 001 US3 — keep current (T039–T043): done.** `DELETE /api/v1/materials/{id}` →
  `Pipeline.remove_material` (delete + batch rebuild). Orphan removal is **automatic**: `replace_graph`
  wipes-and-rewrites, so a rebuild from the remaining materials drops concepts/edges the deleted
  material solely supported; re-uploading an identical file dedups (no inflation). Contract +
  integration tests prove both.
- **91 tests green** (+9: graph contract/integration, delete contract, keep-current integration); ruff
  + format + mypy clean; eval replay still **faithfulness 100% / relevance 1.00** (no regression).
  All three of feature 001's user stories are now implemented.

### Done today (cont.) — feature 002 concept hierarchy implemented (US1–US3, T001–T020 + edge cases)
- **Built the concept hierarchy** per plan: `domain/hierarchy.py` (`HierarchyNode` + `ConceptHierarchy`
  value objects with faithfulness/coverage invariants), `services/hierarchy.py` (pure, deterministic
  `HierarchyService.build` — roots = vital-few pillars, layered multi-source **BFS forest** over the
  undirected relationship graph, secondary roots for pillar-less components, edge-less concepts →
  `unplaced`, deterministic placement reasons, **no LLM call**), serializers (recursive nested DTO),
  router `GET /api/v1/hierarchy` + `GET /api/v1/hierarchy/concepts/{id}`, wired via a `HierarchyService`
  on `Services`.
- **Faithful by construction:** a parent→child link is only ever a real relationship edge (its sources
  become the child's `grounding`); nothing attached without an edge.
- **27 tests added** (domain invariants, service root/BFS/tie-break/coverage/determinism, contract
  faithfulness+shape, integration link-is-real-edge/coverage/reproducible/add-delete, 3 edge cases).
  **115 tests green**; ruff + format + mypy clean; eval replay unchanged (faithfulness 100%).
- **Eyeballed on the 5 lectures** (211 concepts, read-only scratch DB): 5 pillars (SaaS, PaaS,
  Monolithic/Microservices architecture, Microservices lifecycle) + 19 secondary roots; coherent
  multi-level subtrees (e.g. PaaS → Availability → Fault tolerance). **Honest finding: 104/211 concepts
  are `unplaced` (edge-less)** — correct (no invented links), and it shows the quality ceiling is
  **relationship extraction + label merging** ("AWS" root vs "Amazon Web Services (AWS)" unplaced).

### Done today (cont.) — feature 002 COMPLETE: hierarchy eval scorer + README + release gate
- **Hierarchy eval scorer (T021/T022):** `evals/harness/hierarchy.py` scores the built tree on
  **structural faithfulness** (every parent→child link is a real relationship edge with a faithful
  grounding quote — a hard gate, Principle I), **coverage** (every concept placed-or-unplaced once),
  and **root relevance** (pillar labels vs the dataset's `important_concepts` — reused as the expected
  themes, so no new ground truth / re-record). Wired into `DatasetReport.passed` + `format_report` and
  the runner. Replay now reports `hierarchy: structure 100.0% (3/3 links on real edges), coverage ok`.
- **README (T025):** documented the full API (incl. `/hierarchy`), the `LLM_PROVIDER` switch (DS-0002),
  and the dual-provider privacy caveat. **Release gate (T027):** full pytest + evals green, ruff/mypy
  clean.
- **120 tests green** (+2 scorer tests); `mypy evals` clean. **All 27 feature-002 tasks done.**

### Done today (cont.) — feature 001 polish COMPLETE (T046–T051)
- **T048 LLM error hardening:** both providers translate an exhausted-retry / non-recoverable error
  (rate limit, out of credit, bad key, timeout, outage) into a neutral `LlmUnavailableError` with a
  plain message; the API maps it to **503 `llm_unavailable`** (new handler) instead of a raw 500.
  Contract doc updated.
- **T046 edge-case tests:** empty material (202, no ranking), too-small corpus (empty vital-few +
  note), and **conflicting cross-material statements kept** (A→B "causes" and A→B "prevents" both
  survive — conflict surfaced, not resolved; Principle I).
- **T048 error tests:** Gemini message mapping, DeepSeek retry-exhaustion wrapping (offline), and the
  end-to-end 503 contract.
- **T047/T049:** README covers setup/run + the Principle V caveat + the full API; ruff + mypy clean.
- **T050:** real-model path validated via the active provider (live DeepSeek: smoke, `--live` baseline,
  5-lecture run); Gemini id/limit confirmed in DS-0001; not re-run against Gemini (quota exhausted).
- **T051 release gate:** **126 tests green**, eval OVERALL PASS (faithfulness 100%, hierarchy structure
  100%), ruff + format + mypy clean, no unresolved constitution violations.

### State of the repo
- **Feature 001 (concept graph + 80/20): COMPLETE** — all 51 tasks done (US1–US3 + polish + gate).
- **Feature 002 (concept hierarchy): COMPLETE** (US1–US3 + evals + docs + gate).
- Everything green and pushed to GitHub `main`.

### Pick up here next time
1. **Extraction tuning — the top quality lever** (relationship recall + label merging; ~half the
   lecture concepts are edge-less). Measurable against the harness; a `decisions.md` entry on concept
   identity (exact vs normalised/fuzzy merge). Budget `--live` DeepSeek re-records.
2. Optional: recurrence-vs-degree ranking-weight tuning (eval-tunable); a thin TS frontend over the API.

### Pick up here next time
1. **Extraction tuning — the highest-leverage quality work now.** The hierarchy made it visceral:
   ~half the lecture concepts are edge-less (`unplaced`) because *relationship* extraction is sparse,
   and label merging misses variants ("AWS" vs "Amazon Web Services (AWS)"). Both are measurable
   against the harness; budget `--live` DeepSeek re-records. Decide concept identity (exact vs
   normalised/fuzzy) → a `decisions.md` entry.
2. **Feature 001 polish:** T046–T051 (edge-case tests, README Principle V caveat — partly done, adapter
   error hardening, live-model quickstart, final release gate).
3. Optional: recurrence-vs-degree reweighting of the ranking signals (eval-tunable).

---

## 2026-10-17

### Done today — first real Gemini calls (milestone #1)
- **Made the first live Gemini calls ever.** Staged smoke per yesterday's plan: a tiny synthetic
  non-sensitive snippet through the extractor first, then real lecture PDFs through the full HTTP
  stack (`POST /materials` → `GET /vital-few`) via FastAPI `TestClient` against the production
  composition root (real Gemini provider), into an **isolated scratchpad DB** (no project pollution,
  Principle V preserved for the repo).
- **Found and fixed a real bug + a dead model id — logged as `DS-0001` (decisions.md):**
  - Planned `gemini-3-flash` **does not exist** on the API (404). Corrected to `gemini-3-flash-preview`
    (confirmed against the live model list for this key).
  - `gemini-3-flash-preview` is a *thinking* model → reasoning tokens drained `max_output_tokens`,
    truncating the JSON (`MAX_TOKENS`) so **0 concepts** came back. Fix: `GeminiClient(thinking_budget=0)`
    (default). Cheaper on free-tier TPM; our tasks are mechanical and need no reasoning.
  - Files: `src/distil/config.py`, `.env.example` (model id), `src/distil/adapters/llm/gemini/_client.py`
    (thinking_budget param + rationale comment). Everything still green: ruff + format + mypy --strict
    + **64 tests**.
- **Faithfulness verified live (Principle I holds):** every returned concept/relationship span is
  verbatim (`quote == content_text[start:end]`) with page provenance; evidence arrays non-empty.
- Added `Notes/` to `.gitignore` (local course material — must never be committed, Principle V).

### Honest quality findings from the live runs (feed the eval/tuning phase)
- **Single-document ranking is degenerate:** all signals tie at `score=1.0` (recurrence is uniformly
  1.0, graph too sparse) → the "vital few" is effectively arbitrary on one doc.
- **Multi-document (3 Cloud lectures, 75pp):** the **graph/centrality half works** — ranking now
  discriminates (`IaaS` #1 at degree 6, then `web-based portal`, `PaaS`, `Security`). **But the
  recurrence half is inert:** **0 of 56 concepts** recur across materials.
  - *Correction (same-day, after inspecting the DB):* an earlier note here claimed extraction was
    "too sparse (12 concepts)". That was wrong — 12 was the *vital-few shortlist*; the corpus
    actually extracted **56 concepts**. Extraction is **verbose and noisy, not sparse.**
  - Real causes of the inert recurrence: (a) **noise** — the extractor pulls slide headers
    (`Stage 1. Design`…`Stage 8. Decommission`), proper nouns (AWS, Netflix, Uber, Spotify,
    Kubernetes), and **within-material near-duplicates that don't merge** (`virtual machine
    management` vs `Virtual Machine technique` — casefold match is too strict); (b) **premise** —
    these three lectures cover *disjoint sequential topics*, so even perfect extraction yields little
    shared vocabulary. Recurrence-as-importance assumes materials **revisit** concepts (e.g. notes +
    textbook on one topic), which a sequential course violates. Worth revisiting the recurrence
    weight / the kind of corpus the 80/20 is pitched at.
  - **Merge logic and the full-corpus rebuild were verified correct** — the issue is extraction
    quality + label normalisation, not the graph code.

### Done today (cont.) — eval harness + dataset (T044/T045, code complete)
- **Built the eval harness** in `evals/harness/` (`python -m evals.harness`), modular per Principle
  VIII: `dataset.py` (load synthetic notes + ground truth), `recording.py` (record/replay at the
  `JsonLLM` port), `pipeline_run.py` (run the real ingest→graph→rank over an in-memory DB behind any
  LLM), `faithfulness.py` (deterministic — every emitted span must equal its source text; 100% or
  fail), `relevance.py` (LLM-judge score + deterministic precision/recall vs curated
  `important_concepts`; judge prompt in source), `report.py` (gate: faithfulness==100% AND
  relevance≥`min_relevance`; drives exit code for T051), `runner.py`, `__main__.py` (`--live`,
  `--dataset`).
- **Design choice (user-approved):** both scorers now; **recorded fixtures + `--live`** — replay runs
  are deterministic, offline, and cost **zero** quota; `--live` re-records only when a prompt/model
  actually changes (Principle VII). This seam records/replays at `JsonLLM.generate_json`, so the real
  extractor/explainer/judge code runs against fixed model output.
- **Dataset `evals/datasets/energy-cycle/`:** 3 short synthetic biology notes engineered so core
  concepts (glucose, photosynthesis, cellular respiration, ATP, energy) **recur** across materials —
  giving the 80/20 a known right answer and exercising the recurrence signal the lectures couldn't.
- **7 new deterministic tests** (`tests/unit/test_evals_harness.py`) via a schema-routing fake LLM:
  prove the full chain — real pipeline + faithfulness + relevance + replay + gating — offline.
  **71 tests green**; ruff + format + mypy --strict clean across `src`, `tests`, **and `evals`**
  (added `evals` to ruff `src`).
- ⚠️ **`fixtures.json` NOT yet recorded** — see the quota finding below. The harness is complete and
  tested; a single `--live` run records the real baseline once quota resets.

### ⚠️ Free-tier quota confirmed the hard way (answers an open question)
- Hit `429 RESOURCE_EXHAUSTED`: **free tier = 20 `generate_content` requests PER DAY** per model
  (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit 20). Today's smoke + debug + the
  3-lecture run (~10 calls) exhausted it; retry window ~16h. **Lesson:** be frugal with `--live`;
  this is exactly why recorded fixtures (replay = 0 quota) is the right default. A real lecture PDF is
  ~4 calls, so ≤5 PDFs/day on free tier.

### Pick up here next time
1. **Record the eval baseline:** once quota resets, run `uv run python -m evals.harness --live
   --dataset energy-cycle` to write `fixtures.json`, then `uv run python -m evals.harness` (replay)
   and read the first real faithfulness + relevance numbers. Commit the fixtures (versioned asset).
2. **Raise extraction recall quality + fix cross-material merge** — the core 80/20 blocker, now
   measurable against the harness:
   - Tune the extraction prompt (noise: slide headers / proper nouns; near-duplicate labels).
   - Decide concept identity: exact-label vs. normalised/fuzzy merge (→ a `decisions.md` entry).
   - Re-run `--live` after any prompt change (Principle VII) — budget the 20/day.
3. Then **US2 (T034–T038)** graph endpoints and **US3 (T039–T043)**.

### Open questions
- ~~Free-tier request limits~~ → **confirmed: 20 generate_content/day/model.** Still open: TPM/RPM
  within a day, and whether to raise `DEFAULT_MAX_CHARS` to cut calls-per-PDF.
- Cross-material concept identity: exact-label match vs. normalised/fuzzy merge (decision pending —
  a `decisions.md` entry once chosen).
- Recurrence premise: is the 80/20 pitched at revisited-topic corpora vs. sequential course lectures?
  May warrant reweighting recurrence vs. centrality (eval-tunable now).

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
  multi-user path). (`build_llm_provider` previously raised `NotImplementedError` as a placeholder;
  it now delegates to `build_gemini_provider`.)

### State of the repo (end of day)
- **Git repo on `main`**, ~17 commits; latest `d18997d` (Gemini adapters). Constitution **v1.1.0**.
- Feature 001 specced + planned; **US1 MVP wired end-to-end, now with the real Gemini adapters in
  place** — but still **only exercised on the fake LLM**. No live Gemini call has been made (no key
  loaded, Principle V preserved).
- Everything green: `ruff check` + `ruff format --check` + `mypy --strict` + `pytest` (**64 passed**).
- Working tree clean; all of today's work committed.

### Pick up here tomorrow
1. **First real Gemini call (the next real milestone).** Before it:
   - Confirm in AI Studio the exact `gemini-3-flash` API model string **and** the live free-tier
     rate/token limits — the TPM limit is what sets whether `DEFAULT_MAX_CHARS=6000` / `overlap=250`
     in `extractor.py` are right.
   - Put `GEMINI_API_KEY` in a local `.env` (gitignored — never commit it).
   - Smoke-run a single upload of the **author's own non-sensitive test notes** (Principle V) through
     `POST /materials` → `GET /vital-few`, and eyeball that quotes are faithful and rationales read
     honestly. This is the first time the prompts meet a real model.
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
