# Phase 1 Contract — HTTP API

The contract the FastAPI delivery layer exposes and the (deferred) TypeScript frontend will consume.
It is the **boundary contract**, not implementation: shapes, status codes, and faithfulness
guarantees that contract tests (`tests/contract/`) assert. v1 is single-user/local, so there is no
auth; a `workspace_id` is carried explicitly to keep the isolation seam real (Principle V).

**Conventions**
- Base path `/api/v1`. JSON request/response. Errors use a consistent envelope.
- **Faithfulness guarantee (contract-level):** every `concept`, `relationship`, and `vital_few`
  object returned MUST include a non-empty `sources`/`evidence` array of source references. A
  contract test fails the build if any derived object lacks one.
- Timestamps ISO-8601 UTC. IDs are opaque strings.

**Error envelope** (all 4xx/5xx):
```json
{ "error": { "code": "unsupported_format", "message": "Human-readable reason." } }
```
When the LLM provider fails (rate limit, out of credit, timeout, or outage) and retries cannot
recover, write endpoints return **`503`** with `code: "llm_unavailable"` and a plain message, rather
than a raw provider exception as a 500 (T048).

**Shared shape — SourceReference**:
```json
{ "material_id": "m_123", "start_offset": 40, "end_offset": 78, "quote": "exact passage text", "page": 2 }
```
(`page` present only for PDF-sourced materials.)

---

## POST /api/v1/materials — upload a material

Ingests one note. Triggers (re)build of graph + ranking in the background (batch, ADR-0007).

**Request**: `multipart/form-data` with `workspace_id` (string) and `file` (the upload).

**Responses**
- `201 Created` — accepted:
  ```json
  { "id": "m_123", "filename": "lecture1.pdf", "format": "pdf", "status": "accepted" }
  ```
- `200 OK` — duplicate of existing material (dedup by content hash, FR-014): same body, existing `id`.
- `202 Accepted` — empty/contentless file: `{ "id": "m_124", "status": "empty" }`.
- `415 Unsupported Media Type` — DOCX/PPTX/image/scanned-PDF (FR-002):
  ```json
  { "error": { "code": "unsupported_format",
      "message": "Only text, Markdown, and text-based PDF are supported in v1. This PDF has no extractable text." } }
  ```
- `400 Bad Request` — missing `workspace_id`/`file`.

## GET /api/v1/materials?workspace_id=... — list materials

**200 OK**:
```json
{ "materials": [ { "id": "m_123", "filename": "lecture1.pdf", "format": "pdf", "status": "accepted", "created_at": "..." } ] }
```

## DELETE /api/v1/materials/{id}?workspace_id=... — remove a material

Removes the material; triggers rebuild so concepts/edges it solely supported disappear (FR-013).
- `204 No Content` on success; `404` if not found in that workspace.

---

## GET /api/v1/vital-few?workspace_id=... — the explainable 80/20 view (primary, US1)

Returns the latest ranking run's vital-few list, each entry explained and source-linked.

**200 OK**:
```json
{
  "ranking_run_id": "r_9",
  "generated_at": "2026-10-16T12:00:00Z",
  "total_concepts": 120,
  "vital_few_size": 22,
  "entries": [
    {
      "rank": 1,
      "concept": { "id": "c_1", "label": "Backpropagation" },
      "signals": { "pagerank": 0.08, "degree": 14, "recurrence": 5 },
      "rationale": "Ranked highest: it connects to 14 other concepts and recurs across 5 of your notes; it is the hub linking gradient descent, loss, and the chain rule.",
      "evidence": [ { "material_id": "m_123", "start_offset": 40, "end_offset": 78, "quote": "...", "page": 2 } ]
    }
  ]
}
```
- `200` with `entries: []` and an explanatory `note` when the corpus is too small to form a vital few
  (edge case) — never an arbitrary shortlist.
- `404` if the workspace has no completed ranking run yet (e.g. ingestion still processing).

## GET /api/v1/concepts/{id}?workspace_id=... — concept detail + provenance (US1 drill-down, FR-012)

**200 OK**:
```json
{
  "id": "c_1", "label": "Backpropagation", "aliases": ["backprop"],
  "recurrence_count": 5,
  "centrality": { "pagerank": 0.08, "degree": 14 },
  "sources": [ { "material_id": "m_123", "start_offset": 40, "end_offset": 78, "quote": "...", "page": 2 } ]
}
```
- `404` if not found in the workspace.

---

## GET /api/v1/graph?workspace_id=... — the concept graph (US2)

Returns nodes and edges for exploration; every node and edge carries its sources.

**200 OK**:
```json
{
  "nodes": [ { "id": "c_1", "label": "Backpropagation", "centrality": { "pagerank": 0.08, "degree": 14 }, "recurrence_count": 5 } ],
  "edges": [ { "id": "e_1", "source": "c_1", "target": "c_2", "kind": "uses",
               "sources": [ { "material_id": "m_123", "start_offset": 10, "end_offset": 60, "quote": "..." } ] } ]
}
```

## GET /api/v1/graph/edges/{id}?workspace_id=... — relationship provenance (US2, FR-006)

**200 OK**: a single edge object (as above) including the source passage(s) asserting the relation.
- `404` if not found in the workspace.

---

## Contract test checklist (asserted in `tests/contract/`)

- Every `concept`/node, `edge`, and `vital_few` entry returned includes a non-empty
  `sources`/`evidence` array (faithfulness guarantee).
- Each returned `SourceReference.quote` equals the referenced material's text at
  `[start_offset:end_offset]` (deterministic faithfulness check).
- Unsupported uploads return `415` with `code: "unsupported_format"` and derive no concepts.
- Deleting a material removes concepts/edges it solely supported from subsequent responses.
- All list/detail endpoints are scoped by `workspace_id` (no cross-workspace leakage).
