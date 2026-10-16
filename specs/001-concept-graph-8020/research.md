# Phase 0 Research — Concept Graph & Explainable 80/20

Decisions resolving the plan's open choices. Each: **Decision**, **Rationale**, **Alternatives
considered**. These are planning-phase decisions recorded here (per project convention, `decisions.md`
is reserved for later decision *shifts*). Several restate choices already reasoned through with the
author; captured here so the plan is self-contained.

---

## 1. Backend language & runtime — Python 3.12

- **Decision**: Python 3.12.
- **Rationale**: Distil is AI-native; the extraction, graph-signal, ranking, and eval work all sit in
  Python's strongest ecosystem. 3.12 is stable and widely supported.
- **Alternatives**: TypeScript/Node (weaker AI/eval/parsing tooling); Python 3.11 (fine, but 3.12
  gains with no downside here).

## 2. Packaging & environment — uv

- **Decision**: **uv** for virtualenv, dependency resolution, and lockfile (`uv.lock`), via
  `pyproject.toml`.
- **Rationale**: One fast tool covering env + deps + lock; reproducible installs; increasingly the
  standard and worth learning. `pyproject.toml` keeps config declarative.
- **Alternatives**: Poetry (mature but slower); pip + venv + requirements (most manual, weaker
  locking). uv subsumes both with less ceremony.

## 3. LLM provider & model — Google Gemini free tier (behind a provider port)

- **Decision**: For the MVP, use **Google Gemini's free tier** via the official **google-genai** SDK,
  accessed only through the `ConceptExtractor` and `Ranker` **ports**. Chosen model: **Gemini 3
  Flash** (`GEMINI_MODEL=gemini-3-flash`, env config). Confirm the exact API model string and live
  rate limits in the author's AI Studio console; the design is model-agnostic behind the port.
- **Rationale**: Zero cost to prove the pipeline end-to-end; the author explicitly accepts lower
  quality for MVP and plans to swap to a more capable model later. The port makes that swap a
  contained adapter change (and a clean `decisions.md` decision-shift when it happens). Keeping the
  model as config avoids hard-coding a fast-moving value.
- **Constraints captured**:
  - **Rate limits** (free tier ≈ 10 RPM / ~250k TPM — confirm live): extraction is chunked,
    throttled, and retried with exponential backoff; this bounds throughput (see plan SC-005 note).
  - **Data use (Principle V)**: free-tier content may be used by Google to improve products → MVP use
    restricted to the author's own non-sensitive test notes; recorded as a time-boxed exception.
- **Alternatives**: Claude (Opus/Sonnet/Haiku 5.x) — higher quality and a cleaner faithfulness story,
  but paid; deferred to the post-MVP swap. A local open model — avoids data-use concerns but adds
  setup/quality burden not worth it for MVP.

## 4. Concept & relationship extraction approach — structured output with provenance spans

- **Decision**: Extract concepts and relationships via the LLM using **structured output** (a JSON
  schema the SDK validates), where **every concept and relationship must include the source span**
  (material id + character offsets / passage) it was drawn from. Long materials are **chunked** with
  overlap before extraction; concepts are then **merged/deduplicated** across chunks and materials.
- **Rationale**: Structured output keeps parsing deterministic and testable. Requiring a span per item
  operationalises Source-Faithfulness (Principle I) — an item with no locatable span is dropped or
  flagged, never asserted. Chunking respects context/token limits and the free-tier TPM cap.
- **Alternatives**: Free-text LLM output parsed heuristically (brittle, ungrounded); classical NLP
  keyword/entity extraction (no relationship semantics, misses the point of an LLM-built concept
  graph); embeddings-only clustering (no explainable edges). A hybrid can come later if evals show a
  need (would be a decision-shift).

## 5. Graph storage & computation — SQLite (source of truth) + NetworkX (compute)

- **Decision**: Persist materials, concepts, relationships, and rankings in a local **SQLite** DB
  behind a repository **port**; build an in-memory **NetworkX** graph from it to compute centrality
  and recurrence signals.
- **Rationale**: Zero servers, fast to build and test; NetworkX gives readable, explainable centrality
  algorithms (degree, betweenness, PageRank/eigenvector) for the 80/20 evidence (Principle II/IV).
  **Accepted trade-off**: NetworkX's in-memory model does not mirror Neo4j's Cypher semantics, so a
  few graph *queries* (not the centrality concepts) get rethought at the future migration.
- **Alternatives**: Neo4j now (native graph + GDS centrality, but a server to operate — against
  Principle VI for a local v1); Postgres nodes/edges now (hand-rolled graph algorithms, more infra
  than needed). Both are the documented *target*, not the v1 choice.

## 6. Which graph signals feed the ranking

- **Decision**: Use **centrality** (how connected a concept is — degree and a global measure such as
  PageRank) and **recurrence** (how often/broadly a concept appears across materials) as the evidence.
  The LLM acts as ranker/explainer over concepts and these signals, producing the ordered vital-few
  with a plain rationale citing the signals and source.
- **Rationale**: Directly implements ADR-0003 (graph-derived signals + LLM explainer, visible why).
  These signals are intuitive to explain to a student, satisfying Explainable Intelligence.
- **Alternatives**: LLM ranks freely (black box — rejected by ADR-0003); a single hand-tuned formula
  (rigid, less explainable, misses the learning goal). Exact signal weighting is a tuning parameter
  for the eval loop.

## 7. PDF text extraction — PyMuPDF

- **Decision**: **PyMuPDF** (`fitz`) for text-based PDF extraction, with page/offset info retained for
  provenance; detect image-only/scanned PDFs (no extractable text) and reject them with a clear
  message (no OCR in v1).
- **Rationale**: Fast, accurate text + layout/coordinates (useful for passage locating), actively
  maintained. Rejecting no-text PDFs upholds "don't fabricate from unreadable content" (FR-002).
- **Alternatives**: pdfplumber (good for tables, slower, heavier); pypdf (lighter but weaker text
  fidelity/positioning). PyMuPDF best balances fidelity, speed, and provenance support.

## 8. HTTP API framework — FastAPI

- **Decision**: **FastAPI** + Uvicorn as a thin delivery layer over the core services; **Pydantic v2**
  DTOs at the boundary; the API contract lives in `contracts/http-api.md`.
- **Rationale**: The deferred frontend is TypeScript and will consume HTTP; FastAPI gives typed
  request/response models, automatic OpenAPI docs, and easy dependency injection for wiring adapters.
  The core stays framework-agnostic so the API is replaceable.
- **Alternatives**: CLI only (simplest, but defers the API the frontend needs); Flask/Django (less
  native typing / heavier). A thin CLI driver may still be added later for scripting without being the
  primary interface.

## 9. Eval tooling — small in-repo harness (faithfulness deterministic + relevance LLM-judge)

- **Decision**: A **custom, lightweight eval harness** in `evals/`, versioned with curated datasets.
  **Faithfulness** is scored **deterministically** (does every emitted concept/edge/ranking resolve to
  a real span in the cited material? any ungrounded item = fail), complemented by an **LLM-judge** for
  **relevance** (does the vital-few capture the ideas reviewers marked important?). Thresholds gate
  prompt/model/pipeline changes; a faithfulness regression blocks the change.
- **Rationale**: Distil's core faithfulness check ("every claim traces to source") is a concrete,
  deterministic property best asserted directly rather than via a generic metric — more trustworthy
  and more instructive to build (Principle IV/VII). Keeping the harness small avoids a heavy
  dependency before we know its shape.
- **Alternatives**: ragas / deepeval (ready-made faithfulness/relevance metrics, but LLM-graded and
  tuned for RAG; heavier, less transparent for our exact provenance rule). Can be adopted later for
  the relevance side if the custom judge proves insufficient (a decision-shift).

## 10. Deterministic testing — pytest

- **Decision**: **pytest** for unit (parsers, graph build, ranking math, domain rules), integration
  (full pipeline with a *fake* LLM adapter for determinism + real SQLite), and contract (API shapes).
- **Rationale**: Standard, expressive, fixtures suit injecting fakes via ports. Deterministic logic is
  tested without ever calling the live LLM (Principle VII), keeping tests fast, free, and reliable.
- **Alternatives**: unittest (more boilerplate). None compelling over pytest.

---

## Open items to confirm (not blocking the design)

- **Gemini 3 Flash chosen** — confirm the exact API model string (`gemini-3-flash`) and live
  free-tier rate limits in the author's AI Studio console; the design is model-agnostic behind the port.
- **Centrality measure & signal weighting** — start with degree + PageRank and equal-ish weighting;
  tune via the eval loop.
- **Chunk size / overlap** — set from the chosen model's context window and the free-tier TPM cap.
