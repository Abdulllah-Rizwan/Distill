# Distil — Progress Log

Rolling log of what was done each day and what to pick up next. Decisions and their rationale live
in `decisions.md`; this file tracks *activity and todos* only.

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

### Planning direction agreed in discussion (to be formalized in `spec.md` / `plan.md`, NOT yet recorded as ADRs)
- **Backend language = Python**; frontend TS deferred until the backend is proven. → `plan.md`
- **v1 ingestion formats = text, Markdown, text-based PDF**; DOCX/PPTX/OCR deferred. → `spec.md`/`plan.md`
- **Storage = SQLite + NetworkX behind a thin persistence port for v1**, with **Postgres + Neo4j on
  cloud as the documented target** and **migration trigger = going cloud / multi-user**. Accepted the
  trade-off that NetworkX won't mirror Neo4j's Cypher semantics (some queries rethought at migration). → `plan.md`
- **80/20 ranking = batch step on ingest**, re-run when new material is added. → `plan.md`
- **Eval datasets live in `evals/` at the repo root**, versioned in-git (Principle VII). → `plan.md`

### State of the repo
- Still **not a git repository** and **no application code** yet. Constitution now at **v1.1.0**
  (8 principles). `decisions.md` holds the three founding entries (ADR-0001–0003) and no shifts yet.

### Pick up here next
1. **`git init`** — worth it now, so the constitution, decisions, specs, and code are all versioned
   from the first commit.
2. **Run `/speckit-specify`** for the v1 slice: ingest (text/md/text-PDF) → concept knowledge graph
   → explainable 80/20 view. The scope and format decisions above land here.
3. **Run `/speckit-plan`** — this is where the Python / storage / persistence-port / batch-ranking /
   evals decisions get formally recorded with their rationale.
4. Open technical questions to settle during plan: Python tooling/layout, LLM provider+model (prompt
   in source), eval tooling, PDF extraction library.

### Open questions to resolve
- Python dependency/tooling: uv vs. poetry vs. pip-tools?
- Which LLM provider + model for concept extraction and the 80/20 ranker? (needs an ADR + prompt in
  source control)
- Eval tooling: ragas vs. deepeval vs. a small custom harness?
- PDF text extraction: pymupdf vs. pdfplumber?

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
