# Quickstart — Concept Graph & Explainable 80/20 (validation guide)

How to run the v1 backend locally and prove the feature works end-to-end. This is a validation/run
guide — implementation details live in `tasks.md` (next phase) and the code. Commands are targets for
the layout in `plan.md`; exact entry points are finalized during implementation.

## Prerequisites

- **Python 3.12** and **[uv](https://docs.astral.sh/uv/)** installed.
- A **Google Gemini API key** (free tier). Confirm your available model + live rate limits in Google
  AI Studio.
- Windows, macOS, or Linux.

## Setup

1. Install dependencies into a project venv:
   ```bash
   uv sync
   ```
2. Create a local `.env` (gitignored — never commit it):
   ```ini
   GEMINI_API_KEY=your-key-here
   GEMINI_MODEL=gemini-3-flash     # Gemini 3 Flash; confirm exact API string + limits in AI Studio
   DISTIL_DB_PATH=./data/distil.db # local SQLite file (data/ is gitignored)
   ```
   > Reminder (Principle V): on the Gemini **free tier**, content you send may be used by Google to
   > improve their products. Use only your **own, non-sensitive test notes** here — not real
   > third-party student coursework — until on a paid/no-training tier.

## Run the API

```bash
uv run uvicorn distil.api.main:app --reload
```
- Open `http://127.0.0.1:8000/docs` for the live OpenAPI UI.

## End-to-end validation scenario (proves US1 — the MVP)

Using the API (via `/docs`, `curl`, or the frontend later). Endpoint shapes:
[`contracts/http-api.md`](./contracts/http-api.md).

1. **Upload a few notes** that share recurring, interconnected ideas:
   ```bash
   curl -F workspace_id=w_demo -F file=@notes/lecture1.md  http://127.0.0.1:8000/api/v1/materials
   curl -F workspace_id=w_demo -F file=@notes/lecture2.pdf http://127.0.0.1:8000/api/v1/materials
   ```
   Expect `201` with `status: "accepted"`. Ingestion triggers the batch graph + ranking build.

2. **Get the explainable vital-few view:**
   ```bash
   curl "http://127.0.0.1:8000/api/v1/vital-few?workspace_id=w_demo"
   ```
   **Expected**: a ranked `entries` list where each entry has a `rationale` and a non-empty `evidence`
   array pointing to real passages in your notes. This is the core promise.

3. **Verify faithfulness (the non-negotiable):** pick any entry, confirm each
   `evidence[].quote` is actually present in the cited material (the API also guarantees
   `quote == content_text[start:end]`). Drill into a concept:
   ```bash
   curl "http://127.0.0.1:8000/api/v1/concepts/c_1?workspace_id=w_demo"
   ```

4. **Explore the graph (US2):**
   ```bash
   curl "http://127.0.0.1:8000/api/v1/graph?workspace_id=w_demo"
   ```
   Confirm nodes/edges, and that an edge's `sources` show where the relationship was stated.

5. **Keep current (US3):** delete a material and re-fetch `vital-few`; concepts it *solely* supported
   should be gone. Re-upload the same file; it dedups (no inflated importance).

6. **Unsupported input (faithfulness guard):** upload a scanned/image-only PDF or a `.docx`:
   ```bash
   curl -F workspace_id=w_demo -F file=@notes/scanned.pdf http://127.0.0.1:8000/api/v1/materials
   ```
   **Expected**: `415` with `code: "unsupported_format"`, and no concepts derived from it.

## Run the tests (deterministic — Principle VII)

```bash
uv run pytest            # unit + integration (fake LLM) + contract tests
```
- Integration tests use a **fake LLM adapter** (no network, deterministic), so they are fast and free.

## Run the evals (AI capabilities — Principle VII)

```bash
uv run python -m evals.harness   # scores faithfulness (deterministic) + relevance (LLM-judge)
```
- **Faithfulness must be 100%** (every emitted item resolves to a real source span) or the change is
  blocked. Relevance is scored against the curated dataset in `evals/datasets/`.

## Success = all of:

- The vital-few view returns a ranked, explained shortlist for a real set of notes (SC-001).
- 100% of returned concepts/edges/rankings carry openable source references (SC-002); 0 ungrounded
  items in the eval (SC-003).
- Unsupported inputs are rejected with no fabricated concepts (SC-006).
- `pytest` and the faithfulness eval are green.
