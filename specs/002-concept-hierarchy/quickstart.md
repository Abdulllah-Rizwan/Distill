# Quickstart — Concept Hierarchy (validation guide)

How to prove the hierarchy feature works end-to-end once implemented. Runnable scenarios only;
implementation lives in `tasks.md` and the code. Builds on feature 001's quickstart (ingestion +
graph must already work).

## Prerequisites

- Feature 001 working (ingest → graph → vital-few), green test suite.
- `uv sync` done; an LLM provider configured in `.env` (`LLM_PROVIDER=gemini` or `deepseek`) only for
  the live ingest step — the hierarchy build itself makes **no** LLM call.

## Scenario 1 — Offline, deterministic (no LLM, no network): the fast gate

Runs the whole chain on the fake LLM + real SQLite, so it is free and deterministic.

```bash
uv run pytest tests/unit/test_hierarchy_service.py tests/integration/test_hierarchy.py \
              tests/contract/test_hierarchy_api.py -q
```

**Expected**: all pass — asserting that

- roots are the vital-few pillars; every non-root link is a real relationship edge with provenance;
- every concept appears exactly once (placed or `unplaced`);
- building twice yields identical structure (determinism);
- a too-small corpus returns empty roots + a note.

## Scenario 2 — Eval harness: faithfulness + coverage + relevance (replay = zero quota)

```bash
uv run python -m evals.harness --dataset energy-cycle     # replay recorded fixtures (0 quota)
```

**Expected**: the hierarchy scorer reports

- **structural faithfulness = 100%** (every parent→child link is a real edge) — a hard gate;
- **coverage = 100%** (all concepts placed or unplaced, once each);
- **relevance** — roots match the dataset's curated main-theme concepts and children are related to
  their parent, at or above the dataset threshold.

Re-record with `--live` only after a change to the hierarchy logic or prompts (budget the LLM quota).

## Scenario 3 — Live end-to-end via the API (the real thing)

```bash
# 1. start the app (feature 001)
uv run uvicorn distil.api.main:app --reload

# 2. ingest a few notes (feature 001 endpoint)
curl -F workspace_id=w_demo -F file=@notes/01.md  http://localhost:8000/api/v1/materials
curl -F workspace_id=w_demo -F file=@notes/02.md  http://localhost:8000/api/v1/materials

# 3. fetch the hierarchy
curl "http://localhost:8000/api/v1/hierarchy?workspace_id=w_demo"

# 4. drill into one branch
curl "http://localhost:8000/api/v1/hierarchy/concepts/<root-concept-id>?workspace_id=w_demo"
```

**Expected**:

- `GET /hierarchy` returns a **small set of root pillars** (not the whole corpus), each with nested
  `children`; every non-root node carries a non-empty `placement.grounding` (a source quote from your
  notes); `unplaced` lists any edge-less concepts.
- Eyeball check: the roots are the genuine big ideas of the notes, and each child reads as genuinely
  "under" its parent per the cited passage.
- `GET /hierarchy/concepts/{id}` returns just that concept's subtree.

## What "done" looks like

- Scenario 1 green; Scenario 2 shows faithfulness 100% + coverage 100% + relevance ≥ threshold on the
  recorded baseline; Scenario 3 produces a sensible, source-linked tree on real notes.
- No faithfulness regression on feature 001's evals (shared gate).
