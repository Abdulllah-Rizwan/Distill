# Phase 1 Data Model — Concept Graph & Explainable 80/20

Domain entities, their fields, relationships, and validation rules, derived from the spec. This
describes the **domain model** (the `src/distil/domain/` layer) and, where noted, how it persists in
SQLite. It is storage-shape guidance, not DDL — exact schema/migrations are an implementation task.

**Cross-cutting invariants (from the Constitution & spec):**
- **Provenance everywhere (Principle I / FR-006, FR-007):** every `Concept`, `Relationship`, and
  `VitalFewEntry` MUST reference at least one `SourceReference`. An item that cannot be grounded is
  never persisted as fact (it is dropped or flagged uncertain).
- **Workspace isolation (Principle V / FR-015):** every record carries a `workspace_id`; all reads and
  writes are scoped by it.

---

## Entity: Workspace

The container isolating one student's data. (v1 has exactly one; modelled now for the isolation seam.)

| Field | Type | Notes |
|-------|------|-------|
| `id` | id | Primary key. |
| `name` | string | Human label. |
| `created_at` | timestamp | |

- **Relationships**: owns many `Material`, `Concept`, `Relationship`, `VitalFewEntry`.
- **Validation**: `name` non-empty.

## Entity: Material

A single uploaded note/document.

| Field | Type | Notes |
|-------|------|-------|
| `id` | id | Primary key. |
| `workspace_id` | fk → Workspace | Scope. |
| `filename` | string | Original name. |
| `format` | enum | `text` \| `markdown` \| `pdf`. |
| `content_text` | text | Extracted plain text (the basis for all provenance spans). |
| `content_hash` | string | Hash of extracted text; used to detect duplicate uploads (FR-014). |
| `page_map` | json (optional) | For PDFs: char-offset → page number, to render passage locations. |
| `status` | enum | `accepted` \| `rejected` (unsupported/ungroundable) \| `empty`. |
| `rejected_reason` | string (optional) | Clear message when `rejected` (FR-002). |
| `created_at` | timestamp | |

- **Relationships**: a Material is cited by many `SourceReference`s.
- **Validation**: `format` in the supported set; a `pdf` with no extractable text → `status=rejected`;
  blank content → `status=empty` (contributes nothing); `content_hash` unique per workspace (a repeat
  upload maps to the existing Material rather than a second row).
- **State**: `accepted` materials participate in the graph; `rejected`/`empty` never produce concepts.

## Value Object: SourceReference

A pointer from a derived item back to the exact supporting passage. Embedded on concepts, relationships,
and rankings — the backbone of faithfulness.

| Field | Type | Notes |
|-------|------|-------|
| `material_id` | fk → Material | Which material. |
| `start_offset` | int | Char offset into `Material.content_text`. |
| `end_offset` | int | Exclusive end; `start < end`. |
| `quote` | text | The exact passage (denormalised for display + verification). |

- **Validation**: `0 ≤ start_offset < end_offset ≤ len(content_text)`; `quote` MUST equal
  `content_text[start_offset:end_offset]` (a deterministic faithfulness check the eval harness and
  tests assert — if it doesn't match, the derived item is not faithful).

## Entity: Concept

A distinct idea extracted from one or more materials.

| Field | Type | Notes |
|-------|------|-------|
| `id` | id | Primary key. |
| `workspace_id` | fk → Workspace | Scope. |
| `label` | string | Canonical concept name (after cross-material dedup/merge). |
| `aliases` | json (optional) | Other surface forms merged into this concept. |
| `sources` | list<SourceReference> | ≥ 1 required (invariant). Every occurrence that supports it. |
| `recurrence_count` | int | # of distinct materials the concept appears in (a ranking signal). |
| `centrality` | json (optional) | Computed signals (e.g. `degree`, `pagerank`); filled by the graph step. |

- **Relationships**: participates in many `Relationship`s; may appear in a `VitalFewEntry`.
- **Validation**: `label` non-empty; `len(sources) ≥ 1`; `recurrence_count ≥ 1`; dedup so the same
  idea phrased differently is one Concept where the materials support merging (FR; edge cases).

## Entity: Relationship

A directed or undirected connection between two concepts, as expressed in the materials.

| Field | Type | Notes |
|-------|------|-------|
| `id` | id | Primary key. |
| `workspace_id` | fk → Workspace | Scope. |
| `source_concept_id` | fk → Concept | One end. |
| `target_concept_id` | fk → Concept | Other end. |
| `kind` | string (optional) | Short relation label as stated in the material (e.g. "is a", "causes"). |
| `sources` | list<SourceReference> | ≥ 1 required (invariant) — the passage(s) asserting the relation. |

- **Validation**: both concepts exist in the same workspace; `source != target`; `len(sources) ≥ 1`;
  no duplicate (same pair + kind) — merge sources instead. Conflicting assertions across materials are
  represented as-is (both kept), never silently resolved (edge case).

## Entity: VitalFewEntry

A concept's place in the explainable 80/20 ranking, with its rationale and evidence.

| Field | Type | Notes |
|-------|------|-------|
| `id` | id | Primary key. |
| `workspace_id` | fk → Workspace | Scope. |
| `concept_id` | fk → Concept | The ranked concept. |
| `rank` | int | 1 = most vital; unique order within a ranking run. |
| `signals` | json | The evidence used: e.g. `{ "pagerank": .., "degree": .., "recurrence": .. }`. |
| `rationale` | text | Plain-language "why", referencing the signals and source (Principle II). |
| `evidence` | list<SourceReference> | Source passages justifying the placement (FR-012). |
| `ranking_run_id` | fk → RankingRun | Which batch computed it. |

- **Validation**: `rank ≥ 1` and unique within a run; `rationale` non-empty; `len(evidence) ≥ 1`; every
  `concept_id` resolves to a persisted Concept in the same workspace.

## Entity: RankingRun

One batch computation of the graph signals + 80/20 ranking (ADR-0007: batch on ingest).

| Field | Type | Notes |
|-------|------|-------|
| `id` | id | Primary key. |
| `workspace_id` | fk → Workspace | Scope. |
| `created_at` | timestamp | |
| `material_count` | int | # accepted materials included (for reproducibility/trace). |
| `vital_few_size` | int | Size of the vital-few set this run (adaptive, capped — see spec assumptions). |

- **Relationships**: has many `VitalFewEntry`. The current view = entries of the latest run.
- **Validation**: `vital_few_size ≤ cap` (target ≤ 25% of concepts, per SC-004).

---

## Lifecycle (how the entities are produced)

1. **Ingest** → create `Material` (parse to `content_text`, set `status`, dedup by `content_hash`).
2. **Extract** → LLM produces `Concept`s + `Relationship`s, each with `SourceReference`s; merge/dedup
   across chunks and materials; drop any item whose `quote` fails the offset check.
3. **Build graph** → load concepts/edges into NetworkX; compute `centrality`; set `recurrence_count`.
4. **Rank** → new `RankingRun`; LLM ranker + signals produce ordered `VitalFewEntry`s with rationale
   and evidence.
5. **Serve** → API returns the latest run's vital-few, the graph, and drill-downs to sources.

Steps 2–4 re-run (batch) whenever accepted materials change (FR-013); duplicate uploads do not inflate
importance because of `content_hash` dedup (FR-014).
