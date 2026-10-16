# Distil

AI-powered "second brain" for students: ingest notes, map the concepts into a knowledge graph, and
surface the **vital few (80/20)** ideas with an explainable, source-linked ranking.

This is the v1 backend (single-user, local). See the governing documents:

- **Constitution**: [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- **Feature spec / plan / tasks**: [`specs/001-concept-graph-8020/`](specs/001-concept-graph-8020/)
- **Decision log (shifts & governance)**: [`decisions.md`](decisions.md)
- **Progress log**: [`progress.md`](progress.md)

## Quickstart

Full setup and end-to-end validation: [`specs/001-concept-graph-8020/quickstart.md`](specs/001-concept-graph-8020/quickstart.md).

```bash
uv sync                 # install into a local venv
cp .env.example .env     # then add your GEMINI_API_KEY
uv run pytest            # deterministic tests (unit + integration + contract)
```

> **Privacy note (Constitution Principle V):** the MVP uses the Google Gemini **free tier**, where
> content you send may be used by Google to improve their products. Use only your **own,
> non-sensitive test notes** until the project is on a paid/no-training tier.

## Stack

Python 3.12 · uv · FastAPI · Pydantic · NetworkX · PyMuPDF · Google Gemini (behind a provider port) ·
SQLite (behind a persistence port). Architecture is hexagonal (ports & adapters) — see
[`specs/001-concept-graph-8020/plan.md`](specs/001-concept-graph-8020/plan.md).
