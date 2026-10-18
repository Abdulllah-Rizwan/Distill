# Distil — Decision Log

This log records decisions that fall **outside** the Spec Kit planning artifacts — chiefly
**decision shifts**: cases where implementation (or later learning) made us abandon or change
something we had planned, recorded with the rationale for the change. Keeping both the *original
plan* and the *reasoned reversal* together is deliberate — it is valuable for future work and for the
author's learning to see not just what we do, but what we tried and why we changed course.

**Planned decisions do NOT go here.** They live in their proper Spec Kit home:
- **Product scope & requirements →** `spec.md` (via `/speckit-specify`).
- **Architecture, tech-stack & design decisions →** `plan.md` (via `/speckit-plan`).

This file complements those artifacts and still serves **Principle III (Documented Decisions)** for
anything the spec/plan workflow does not naturally capture (e.g. governance changes, and the shifts
described above).

Each shift entry: **what** changed, the **original plan**, the **context / what we hit**, and the
**rationale** for moving. Newest entries at the top. Don't delete superseded history — mark the old
decision `SUPERSEDED` and add a new entry that explains the change.

---

## Founding decisions (made before the Spec Kit specify/plan workflow was engaged)

These three predate the first spec and plan; they are kept here as the project's founding record.
Going forward, decisions of this kind belong in `spec.md` / `plan.md` as noted above — this section
is not a precedent for logging future planned decisions here.

### ADR-0001 — Adopt a project constitution before writing code
- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** Distil is a solo, learning-first build. The author wants to grow into a strong
  engineer (not a "vibe coder") and to keep control of and understanding over every key decision.
- **Decision:** Ratify a 7-principle constitution at `.specify/memory/constitution.md` (v1.0.0)
  before feature work begins. *(Later amended to v1.1.0 — see the constitution's own version history.)*
- **Options considered:**
  - *Generic Spec Kit defaults* (TDD, library-first, etc.) — rejected: ceremony that doesn't fit a
    solo AI product, and not grounded in what Distil actually is.
  - *No constitution, move fast* — rejected: conflicts with the learning goal; invites corner-cutting.
  - *Tailored constitution (chosen)* — principles derived from Distil's real risks and the author's goals.
- **Rationale:** For an AI study tool, the central risk is confidently-wrong output; the central
  personal goal is deliberate, documented learning. The constitution encodes both as guardrails.

### ADR-0002 — v1 scope: ingest → concept graph → explainable 80/20 (defer collaboration & generation)
- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** The product vision has three pillars — knowledge graph + 80/20, auto-generated study
  materials (flashcards/slides), and multi-user collaboration. All three at once is too much for a
  solo v1, and each adds independent complexity.
- **Decision:** v1 delivers only **ingestion → concept knowledge graph → explainable 80/20 ranking
  (graph view)**. Flashcard/slide generation and collaboration are deferred to later versions.
- **Options considered:**
  - *All three pillars in v1* — rejected: unshippable solo, dilutes the differentiator.
  - *Flashcards/slides first* — rejected: commodity feature, not the differentiator.
  - *Graph + 80/20 first (chosen)* — the actual differentiator; proves the core idea.
- **Rationale:** The knowledge graph + explainable 80/20 is what makes Distil distinct. Ingestion is
  included only because it's the unavoidable price of entry for building the graph.
- **Note:** This is scope; from here it is owned by `spec.md`.

### ADR-0003 — 80/20 ranking = graph-derived signals + LLM ranker, always with a visible rationale
- **Date:** 2026-10-15
- **Status:** Accepted
- **Context:** Open question of how the "vital few" (Pareto) concepts get chosen. One idea was to
  let an LLM rank topics directly. That risks a black box, which collides with the faithfulness and
  explainability principles.
- **Decision:** Ground the ranking in **graph-derived signals** (e.g. concept centrality, recurrence
  across materials) used as evidence; the **LLM acts as ranker/explainer** over concepts actually
  extracted from the user's material; **every ranking carries a visible, source-linked "why."**
- **Options considered:**
  - *LLM ranks freely* — rejected: black box, unverifiable, violates Principles I & II.
  - *Hand-rolled heuristic only* — rejected: rigid, and a missed learning opportunity.
  - *Graph signals + LLM judgment + visible rationale (chosen)*.
- **Rationale:** Keeps the 80/20 claim real and correctable, and satisfies Source-Faithfulness and
  Explainable Intelligence.
- **Note:** This is a design decision; from here it is owned by `plan.md`.

---

## Decision shifts

### DS-0005 — Concept identity: merge an acronym into its defining parenthetical expansion
- **Date:** 2026-10-18
- **Status:** Accepted
- **What changed:** Concept merging (`graph_builder._merge_concepts`) now treats a bare acronym and
  the expansion that defines it in parentheses as the **same concept** — e.g. `IaaS` merges into
  `Infrastructure as a Service (IaaS)` (expansion canonical, acronym an alias). Previously the merge
  key was exact casefold, so the two were separate concepts.
- **Original plan / implementation:** merge by `label.strip().casefold()` only (DS-0003 era). The
  open question "cross-material concept identity: exact vs normalised/fuzzy" was flagged in
  `progress.md` as pending a decision — this resolves the first slice of it.
- **Context / what we hit:** eyeballing the 5-lecture graph (211 concepts) with the new hierarchy and
  a read-only analysis showed: **49% of concepts are edge-less** (the big lever — relationship recall,
  separate work), **0** punctuation/casing collisions (so generic normalisation would merge nothing),
  and exactly **4 acronym/expansion pairs** — and all four are the course's *core* concepts
  (`IaaS`, `PaaS`, `SaaS`, `AWS`). Splitting them halved their recurrence/centrality and duplicated
  pillars in the hierarchy.
- **Decision:** merge acronym↔expansion, but **only when both forms were actually extracted** from the
  notes (the expansion literally defines the acronym in parentheses, so the link is grounded in the
  text, not invented — Principle I). The expansion is the canonical label; the acronym becomes an
  alias; sources combine and recurrence counts distinct materials across both forms. Deterministic,
  no LLM call, zero quota.
- **Options considered:**
  - *Exact casefold only (status quo)* — leaves core concepts split; rejected.
  - *Generic punctuation/whitespace normalisation* — the data showed 0 such collisions; wouldn't help.
  - *Fuzzy / embedding similarity merge* — powerful but non-deterministic, hard to keep faithful and
    reproducible, and over-engineered for v1 (Principle VI). Deferred; revisit only if evals demand it.
  - *Acronym↔expansion, both-present-only (chosen)* — targeted, explainable, grounded, deterministic.
- **Validation:** unit test (expansion + bare acronym across two materials → one concept, alias set,
  recurrence 2); full suite 127 green; energy-cycle eval unchanged (no acronyms there → no regression,
  faithfulness 100% / relevance 1.00). Expected lecture effect: the 4 core pairs consolidate.
- **Rationale:** consolidating acronym variants fixes duplicated pillars and restores the recurrence
  signal for the most important concepts, at zero quota and full faithfulness. **Revisit** for broader
  synonymy (non-acronym) once there is an eval metric for merge quality; **relationship recall**
  (the 49% edge-less finding) is the larger, separate extraction-prompt lever, tracked next.

### DS-0004 — Vital-few sizing: fixed small set (~5) instead of a percentage of the corpus
- **Date:** 2026-10-18
- **Status:** Accepted
- **What changed:** `vital_few_size` now returns a **fixed target (`VITAL_FEW_TARGET_SIZE = 5`),
  clamped to the corpus**, instead of ~20% of concepts capped at 25%. SC-004 and the spec's vital-few
  wording were updated to match.
- **Original plan (`spec.md` SC-004 / `plan.md`):** the vital few = a minority of concepts, target
  ≤ 25% (a Pareto/80-20 percentage).
- **Context / what we hit:** the eval baseline + a local run on 5 lecture PDFs showed the percentage
  breaks at **both** ends:
  - Tiny corpus (energy-cycle, 9 concepts): 20% → **2**. Photosynthesis and ATP were extracted and
    correctly ranked #3/#4 but fell outside a 2-item cut, so recall was 0.40 — the metric was asking
    for 5 important concepts out of a 2-slot list (impossible).
  - Larger corpus (5 lectures, 211 concepts): 20% → **43**, which is not a "vital few" anyone studies.
- **Decision:** make the vital few a small, human-sized set (~5), independent of corpus size, clamped
  to the corpus; keep the `MIN_CONCEPTS_FOR_VITAL_FEW = 5` gate (below it the view is empty + a note).
  Depth beyond the few is deferred to the **concept hierarchy** (specced next as its own feature).
- **Options considered:**
  - *Percentage with floor+ceiling* — smallest change, but still conflates "how many to show" with
    corpus size and keeps an arbitrary band.
  - *Natural-break (elbow) cut* — adaptive, but more logic and still unbounded at the top for a flat
    list; better suited to building the hierarchy than to the flat top level.
  - *Fixed small set, clamped (chosen)* — predictable, stays a real "few" at any scale, and matches
    the product intent (a few pillars up top, drill-down via the hierarchy).
- **Validation:** re-recorded the energy-cycle baseline (sizing change alters the explainer input, so
  fixtures were re-recorded per Principle VII) — **faithfulness 100% (35/35), relevance 1.00**
  (precision 0.80, recall 0.80; was 0.60/recall 0.40). Only "energy" is still missed — it is never
  extracted as a standalone concept (a later extraction-granularity question, not a sizing one).
  82 tests green.
- **Rationale:** the 80/20 is a guiding spirit, not arithmetic; a percentage of a variable corpus is
  the wrong shape for "the few ideas to study." **Revisit** `VITAL_FEW_TARGET_SIZE` once the concept
  hierarchy lands (the hierarchy, not a bigger flat list, is how broad coverage is delivered).

### DS-0003 — Deterministic concept/edge ids + memoized per-material extraction (idempotent rebuilds)
- **Date:** 2026-10-18
- **Status:** Accepted
- **What changed:** Two coupled changes to `services/graph_builder.py`, both making a workspace
  rebuild **deterministic and idempotent**:
  1. Concept and relationship ids are now **derived** from identity (`c_<sha256(workspace|label)>`,
     `e_<sha256(workspace|src|tgt|kind)>`) instead of random `uuid4`.
  2. Extraction is **memoized per material** — each material is sent to the LLM at most once per
     process, instead of re-extracting every material on every rebuild.
- **Original plan / implementation:** `uuid4()` ids minted fresh on each rebuild, and
  `GraphBuilder.build` calling `extractor.extract(material)` for *every* material on *every* rebuild
  (the batch-on-every-change pipeline, ADR-0007 / plan.md).
- **Context / what we hit (recording the first eval baseline):** `--live` recorded fixtures fine,
  but replay raised `LookupError` on the **explainer** call. Tracing showed two independent defects
  the baseline exposed:
  - *Non-deterministic ids.* The explainer's prompt embeds each concept's id, so random ids made the
    recorded fixture key (and the recorded response's id→sentence map) unreproducible on replay.
  - *Re-extraction on every rebuild.* Ingesting notes sequentially re-ran the LLM on earlier
    materials each time; with a non-deterministic model each re-extraction differed, and the fixture
    store keeps only the last extraction per passage (same input → same key → overwritten). So the
    intermediate 2-material graph the live explainer saw was built from extractions no longer in the
    fixtures — only the final full-corpus state replayed. (It was also 3× the LLM calls / quota.)
- **Decision:** Derive ids from stable identity, and memoize extraction per `material.id` in the
  builder (a process-level cache; the `Pipeline`/`GraphBuilder` is a singleton, so a running server
  is idempotent for its lifetime). A server-restart cold cache re-extracts once.
- **Options considered:**
  - *Fix only the eval harness (e.g. ingest-all-then-rebuild-once)* — rejected: hides a real
    production defect (non-idempotent rebuilds, wasted quota) behind the test.
  - *Persist per-material mentions in SQLite now* — the durable, correct end-state (survives restart,
    and is what US3 delete/rebuild wants), but a schema + repository change out of scope for
    unblocking the baseline. **Deferred as future work** (flagged in progress.md), with the in-memory
    memo as the simple shipping step (Principle VI).
  - *Deterministic ids + in-memory memo (chosen)* — minimal, understandable, fixes both the replay
    seam and the real idempotency/quota defects; ids are now stable for clients holding them (US2/US3
    graph and edge lookups), a bonus beyond the eval fix.
- **Validation:** 81 tests green (new: extraction memoized across rebuilds; ids deterministic across
  builds). Re-recorded the baseline; **replay now reproduces the live run exactly and is stable across
  repeated replays** (faithfulness 100% (30/30), relevance 0.60), at zero quota.
- **Rationale:** Rebuilds must be idempotent for the evals (Principle VII) and for a trustworthy
  product — adding a material should not silently re-roll the rest of the graph. **Revisit** when
  per-material mentions are persisted (the durable fix), which also lets ranking skip rebuild work
  for unchanged corpora.

### DS-0002 — Add a DeepSeek LLM provider alongside Gemini, selectable via `LLM_PROVIDER`
- **Date:** 2026-10-18
- **Status:** Accepted
- **What changed:** The LLM backend is now pluggable between **Gemini** and **DeepSeek** behind the
  same `JsonLLM` port, chosen by a new `LLM_PROVIDER` setting (default `gemini`). DeepSeek is used
  for active development while the Gemini free-tier daily quota is exhausted.
- **Original plan (`plan.md` / `research.md`):** A single provider — Google Gemini 3 Flash, free
  tier — behind the LLM provider port, with "swap to a more capable model later" noted as a future
  shift.
- **Context / what we hit:** The Gemini free tier is **20 `generate_content`/day/model** and the
  window does **not** reset at local midnight (the 429 returns a ~20h `retryDelay`), so a day's
  development can be blocked for most of the next day. To keep building and to record the first eval
  baseline without waiting on quota, the author added a DeepSeek API key and asked to develop against
  it until its credit runs out.
- **Decision:** Introduce a DeepSeek adapter and make the provider a config switch:
  - The extractor, explainer, and prompts were **already provider-neutral** (they depend only on the
    narrow `JsonLLM` port), so they were promoted out of `adapters/llm/gemini/` to `adapters/llm/`
    (`extractor.py`, `explainer.py`, `prompts.py`, and a new `base.py` holding the `JsonLLM` protocol
    and a now provider-agnostic `with_retries`). Classes renamed `Gemini*` → `Json*`.
  - `adapters/llm/gemini/` keeps only `GeminiClient`; new `adapters/llm/deepseek/` adds
    `DeepSeekClient` — a thin `httpx` POST to the OpenAI-compatible `/chat/completions` (no new SDK
    dependency; `httpx` is already transitive). DeepSeek supports JSON **mode** but not server-side
    JSON **schema**, so the schema is injected into the system prompt and the response is validated
    against the Pydantic model on our side (the adapters already drop malformed output — Principle I
    defence in depth, unchanged).
  - `build_llm_provider` dispatches on `settings.llm_provider`; the eval harness `--live` client does
    the same, so a baseline can be recorded against either provider.
- **Options considered:**
  - *Wait ~20h for Gemini quota* — rejected: blocks the baseline and all live iteration for most of a
    day, repeatedly.
  - *Install the `openai` SDK for DeepSeek* — rejected: an OpenAI-compatible chat call is a simple
    POST; a thin `httpx` client needs no new dependency and keeps the exact request reviewable
    (Principle IV, VI).
  - *Quick drop-in: a DeepSeek client reusing the `Gemini*`-named classes in place* — rejected: a
    "Gemini extractor" wrapping a DeepSeek client is a lasting naming lie; promoting the already-
    neutral core is the honest, cohesive structure (Principle VIII) at modest, mechanical churn.
- **Validation:** 79 deterministic tests green (ruff + format + mypy clean); first live DeepSeek call
  (one synthetic non-sensitive snippet, Principle V) returned grounded concepts/relationships with
  **100% faithful spans** (`quote == source slice`).
- **Rationale:** Preserves the plan's architecture (one LLM port, swappable adapter) and unblocks
  development and the eval baseline without burning scarce Gemini quota. Default stays `gemini` as
  the planned provider; DeepSeek is opt-in via `.env`. **Revisit** the default when choosing the
  product's long-term model, and note that evals recorded against DeepSeek are provider-specific
  fixtures (re-record if the provider changes).

### DS-0001 — Gemini model id `gemini-3-flash` → `gemini-3-flash-preview`, and disable model "thinking" for our calls
- **Date:** 2026-10-17
- **Status:** Accepted
- **What changed:** The pinned Gemini model id, plus a new client setting (`thinking_budget=0`)
  that turns off the model's internal reasoning for our structured-output calls.
- **Original plan (`plan.md` / `research.md`):** `GEMINI_MODEL=gemini-3-flash` (Gemini 3 Flash,
  free tier), behind the LLM provider port.
- **Context / what we hit (the first real Gemini call):**
  1. `gemini-3-flash` returned **HTTP 404** (`models/gemini-3-flash is not found for API version
     v1beta`). Listing the models this key can call shows **no bare `gemini-3-flash`**; the Gemini 3
     Flash model is served as **`gemini-3-flash-preview`**.
  2. After switching, the call returned **zero concepts**. `gemini-3-flash-preview` is a *thinking*
     model: with `max_output_tokens=4096` the reasoning tokens (~3,900) consumed the budget, so the
     JSON came back truncated (`finish_reason=MAX_TOKENS`) and failed schema validation — the adapter
     correctly drops an unparseable chunk, so the whole material yielded nothing. Setting
     `thinking_config.thinking_budget=0` fixed it (clean `STOP`, full valid JSON, 7/7 faithful spans
     on the synthetic probe) and is far cheaper on the free-tier tokens-per-minute budget.
- **Decision:** Pin `GEMINI_MODEL=gemini-3-flash-preview`; default `GeminiClient(thinking_budget=0)`.
  Both of our asks — copy verbatim quotes, write one grounded sentence from supplied facts — are
  mechanical and do not need model reasoning, so thinking stays off unless an eval later shows the
  explainer needs it (one knob to raise).
- **Rationale:** Preserves the plan's intent (Gemini 3 Flash) with the real API id; removes a
  silent, faithfulness-adjacent failure mode (truncation → silently dropped concepts) and conserves
  free-tier tokens. **Revisit** when a stable (non-`-preview`) Gemini 3 Flash GA id appears, or if a
  more capable model is adopted (that swap is itself a future shift).
