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

*(None yet. The first entry lands when implementation causes us to change a plan.)*
