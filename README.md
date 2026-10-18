# Distil

AI-powered "second brain" for students: ingest notes, map the concepts into a knowledge graph, and
surface the **vital few (80/20)** ideas with an explainable, source-linked ranking.

This is the v1 backend (single-user, local). See the governing documents:

- **Constitution**: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- **Feature 001 — concept graph & 80/20**: [`specs/001-concept-graph-8020/`](specs/001-concept-graph-8020/)
- **Feature 002 — concept hierarchy (tree)**: [`specs/002-concept-hierarchy/`](specs/002-concept-hierarchy/)
- **Decision log (shifts & governance)**: [`decisions.md`](decisions.md)
- **Progress log**: [`progress.md`](progress.md)

## Quickstart

Full setup and end-to-end validation: [`specs/001-concept-graph-8020/quickstart.md`](specs/001-concept-graph-8020/quickstart.md).

```bash
uv sync                  # install into a local venv
cp .env.example .env     # then set LLM_PROVIDER + the matching API key (see below)
uv run pytest            # deterministic tests (unit + integration + contract)
uv run python -m evals.harness --dataset energy-cycle   # AI evals (replay, zero quota)
```

The LLM backend is selectable via `LLM_PROVIDER` (default `gemini`; set `deepseek` to use DeepSeek —
decision-shift DS-0002). Provide the matching key (`GEMINI_API_KEY` or `DEEPSEEK_API_KEY`) in `.env`.
Both sit behind one `JsonLLM` port, so the rest of the system is unchanged.

> **Privacy note (Constitution Principle V):** the MVP uses an LLM **free/credit tier** (Gemini or
> DeepSeek), where content you send may be used by the provider to improve their products. Use only
> your **own, non-sensitive test notes** until the project is on a paid/no-training tier.

## API (base path `/api/v1`)

- `POST /materials`, `GET /materials`, `DELETE /materials/{id}` — ingest / list / remove notes.
- `GET /vital-few` — the explainable 80/20 shortlist, each entry ranked, explained, and source-linked.
- `GET /concepts/{id}` — one concept with its provenance.
- `GET /graph`, `GET /graph/edges/{id}` — the concept graph (nodes + grounded edges).
- `GET /hierarchy`, `GET /hierarchy/concepts/{id}` — the concept **hierarchy**: a few pillar roots with
  concepts branching beneath along real relationship edges (feature 002). Every parent→child link is
  grounded in a source passage; edge-less concepts are surfaced as `unplaced`, never linked by guess.

## Stack

Python 3.12 · uv · FastAPI · Pydantic · NetworkX · PyMuPDF · Gemini **or** DeepSeek (behind one
`JsonLLM` provider port) · SQLite (behind a persistence port). Architecture is hexagonal (ports &
adapters) — see [`specs/001-concept-graph-8020/plan.md`](specs/001-concept-graph-8020/plan.md).
