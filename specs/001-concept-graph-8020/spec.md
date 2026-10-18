# Feature Specification: Concept Graph & Explainable 80/20

**Feature Branch**: `001-concept-graph-8020`

**Created**: 2026-10-16

**Status**: Draft

**Input**: User description: "v1 slice: ingest a student's notes (plain text, Markdown, and text-based PDFs), extract concepts and build a concept knowledge graph from them, and present an explainable 80/20 (Pareto) view that surfaces the vital-few concepts — each ranking carrying a visible, source-linked 'why' grounded in graph-derived signals (concept centrality, recurrence across materials). Single-user, local. Every concept, edge, and ranking must trace back to the user's uploaded material (source-faithfulness). Out of scope for v1: flashcard/slide generation, multi-user collaboration, OCR/scanned images, DOCX/PPTX."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Surface the vital few, explained (Priority: P1)

A student has a pile of course notes and little time. They add their notes to Distil and ask,
"what are the most important ideas here?" Distil returns a short, ranked set of "vital few"
concepts — a small, fixed-size shortlist of the ideas that carry most of the weight — and, next to each one, a plain
rationale for *why* it ranked where it did, with links to the exact passages in their own notes that
support it. The student can trust the list because every claim points back to their material.

**Why this priority**: This is Distil's core differentiator and the whole reason the feature exists.
On its own it delivers the central promise — turning a mass of notes into a trustworthy, explained
study priority list. It is the minimum viable product.

**Independent Test**: Add a representative set of notes, request the vital-few view, and confirm the
result is a ranked, explained shortlist in which every concept and every rationale links to a real
passage in the uploaded notes.

**Acceptance Scenarios**:

1. **Given** a set of accepted notes containing recurring, interconnected ideas, **When** the student
   requests the vital-few view, **Then** Distil presents a ranked shortlist of concepts, each with a
   visible plain-language rationale and at least one openable link to a supporting source passage.
2. **Given** the vital-few view is displayed, **When** the student opens a concept's rationale,
   **Then** the rationale refers only to evidence drawn from the uploaded notes (e.g., how often the
   concept recurs and how connected it is) and never to outside knowledge.
3. **Given** a concept that cannot be confidently grounded in the notes, **When** the ranking is
   produced, **Then** Distil surfaces the uncertainty (or omits the concept) rather than presenting
   an ungrounded claim as fact.
4. **Given** the student clicks any ranked concept, **When** they ask "where does this come from?",
   **Then** Distil shows the specific source material and passage(s) the concept was extracted from.

---

### User Story 2 - Explore the concept graph behind the ranking (Priority: P2)

Having seen the vital-few shortlist, the student wants to understand how the ideas fit together: what
connects to what, which concepts are hubs, and how a given concept relates to its neighbours. They
browse the concept graph built from their notes, with every concept and every connection traceable
to the source that asserted it.

**Why this priority**: The graph is the evidence base that makes the 80/20 ranking explainable and
correctable. Exposing it deepens trust and understanding, but the ranking (US1) already delivers
standalone value, so this comes second.

**Independent Test**: With a graph already built from notes, browse concepts and their connections
and confirm each concept and each connection can be traced to the source passage that supports it.

**Acceptance Scenarios**:

1. **Given** a graph built from the student's notes, **When** the student views it, **Then** they see
   concepts and the relationships between them as expressed in their materials.
2. **Given** the student selects a relationship between two concepts, **When** they inspect it,
   **Then** Distil shows the source passage(s) in which that relationship is expressed.
3. **Given** a concept appears in the graph, **When** the student inspects it, **Then** they can see
   which materials it was drawn from and how central/recurrent it is relative to other concepts.

---

### User Story 3 - Keep the knowledge base current (Priority: P3)

As the course progresses the student adds more notes (and occasionally removes material that is no
longer relevant). After each change, the concept graph and the vital-few ranking reflect the current
set of materials, so the study priorities stay accurate.

**Why this priority**: Real study is iterative, but a student can get value from a single batch of
notes first; incremental updating is an enhancement over the core loop.

**Independent Test**: Start from an existing graph and ranking, add a new note that introduces and
reinforces a concept, and confirm the graph and the vital-few view update to reflect it; then remove
a material and confirm its ungrounded concepts no longer appear.

**Acceptance Scenarios**:

1. **Given** an existing graph and ranking, **When** the student adds a new accepted note, **Then**
   the graph and vital-few view update to incorporate concepts and connections from the new material.
2. **Given** a concept that was supported only by one material, **When** that material is removed,
   **Then** the concept (and connections that depended on it) no longer appear, preserving
   faithfulness to the current materials.
3. **Given** the same material is added twice, **When** the graph is rebuilt, **Then** the duplicate
   does not inflate a concept's apparent importance.

---

### Edge Cases

- **Unsupported format**: A student uploads a DOCX, PPTX, image, or scanned/image-only PDF (no
  selectable text). Distil declines it with a clear message naming the supported formats, and does
  not fabricate concepts from content it could not read.
- **Empty or contentless material**: A blank file, or one with no extractable ideas, is handled
  gracefully — it contributes nothing to the graph rather than producing noise or errors.
- **Single material**: With only one note, recurrence-across-materials evidence is weak; the ranking
  still works from within-material signals and the rationale honestly reflects the thinner evidence.
- **Very small corpus**: Too few concepts to form a meaningful "vital few" — Distil communicates this
  rather than presenting an arbitrary shortlist.
- **Conflicting statements across notes**: Two materials assert different things about the same
  concept; Distil represents what the sources say and does not silently pick a "winner" as fact.
- **Large upload**: A large set of notes is ingested without the student having to tag or
  pre-process anything.
- **Ambiguous/duplicate concepts**: The same idea phrased differently across notes is recognized as
  one concept where the materials support it, rather than fragmenting importance.

## Requirements *(mandatory)*

### Functional Requirements

**Ingestion**

- **FR-001**: System MUST accept student-provided materials in plain text, Markdown, and text-based
  (selectable-text) PDF formats.
- **FR-002**: System MUST decline unsupported inputs (DOCX, PPTX, images, and scanned/image-only PDFs
  with no extractable text) with a clear message, and MUST NOT derive any concept from content it
  could not read.
- **FR-003**: System MUST extract the textual content of accepted materials faithfully, preserving
  enough locating information to point back to the passage a concept or relationship came from.

**Concept graph (grounded in source)**

- **FR-004**: System MUST identify the distinct concepts present in the uploaded materials.
- **FR-005**: System MUST identify relationships between concepts as those relationships are expressed
  in the materials.
- **FR-006**: Every concept and every relationship MUST be traceable to the specific material and
  passage(s) that support it, openable by the student.
- **FR-007**: System MUST NOT introduce concepts or relationships that are not grounded in the
  uploaded materials; it MUST NOT enrich the graph with outside knowledge.
- **FR-008**: Where a concept or relationship cannot be confidently grounded, the system MUST surface
  the uncertainty rather than assert it as fact.

**Explainable 80/20 ranking**

- **FR-009**: System MUST produce a ranked "vital few" set of concepts — a small, fixed-size
  shortlist of the ideas that carry most of the importance across the materials (sizing per SC-004).
- **FR-010**: The ranking MUST be grounded in evidence derived from the graph — specifically how
  central a concept is (how connected it is to others) and how it recurs across the materials.
- **FR-011**: Each ranked concept MUST display a visible, plain-language rationale ("why") that refers
  to that evidence and to the supporting source, with no black-box scores presented without a reason.
- **FR-012**: The student MUST be able to reach the supporting source passage(s) for any ranked
  concept in a single action.

**Keeping current**

- **FR-013**: When the student adds or removes materials, the concept graph and the vital-few ranking
  MUST update to reflect the current set of materials.
- **FR-014**: Adding the same material more than once MUST NOT inflate a concept's apparent
  importance.

**Stewardship**

- **FR-015**: The student's materials and all data derived from them (concepts, relationships,
  rankings) MUST remain isolated within the student's own workspace.
- **FR-016**: Uploaded materials MUST be used only to build and explain the student's own graph and
  ranking, and for no other purpose.

### Key Entities *(include if feature involves data)*

- **Material**: A single uploaded note/document. Attributes: original format, extracted text content,
  and the locating information needed to cite passages. Belongs to one workspace.
- **Concept**: A distinct idea extracted from one or more materials. Linked to the source
  occurrence(s) that support it. Carries graph-derived attributes (e.g., connectedness, recurrence).
- **Relationship**: A connection between two concepts, as expressed in the materials. Linked to the
  source passage(s) that assert it.
- **Vital-Few Entry**: A concept's place in the 80/20 ranking, together with its plain-language
  rationale and the source evidence that justifies the placement.
- **Workspace**: The container that isolates one student's materials and all derived data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting from a set of notes, a student reaches the explained vital-few view in a single
  session without any manual tagging, labelling, or configuration of concepts.
- **SC-002**: 100% of concepts, relationships, and ranking rationales presented to the student include
  at least one openable reference to a passage in their own materials. *(Faithfulness — non-negotiable.)*
- **SC-003**: 0 concepts or relationships that are not grounded in the uploaded materials appear in
  the graph or ranking, measured against a curated evaluation dataset.
- **SC-004**: The vital-few set is a small, fixed-size shortlist of the top concepts (target ~5,
  clamped to the corpus — NOT a percentage of it), so it stays a usable "few" whether the corpus
  yields 9 concepts or 900. In evaluation against a curated dataset it ranks the concepts domain
  reviewers mark "most important" ahead of the peripheral ones; comprehensive drill-down beyond the
  few is served by the concept hierarchy (a separate feature). *(Supersedes the original ≤25% Pareto
  cut, which collapsed to 2 on a tiny corpus and ballooned to 43 on five lectures — see decisions.md
  DS-0004.)*
- **SC-005**: For a typical upload (target: up to ~50 pages across materials), the student gets from
  upload to the vital-few view in under 2 minutes.
- **SC-006**: Given an unsupported or ungroundable input, the system informs the student and produces
  zero fabricated concepts.
- **SC-007**: For any ranked concept, the student can reach a supporting source passage in a single
  action.
- **SC-008**: After reading only a concept's displayed rationale, a new student can restate in their
  own words why that concept was marked "vital" (qualitative check with representative users).

## Assumptions

- **Single-user, local use for v1.** One student, one workspace, on their own machine; multi-user
  collaboration and cloud/shared access are out of scope (deferred per prior scope decisions).
- **Supported formats are text, Markdown, and text-based PDF only.** OCR of scanned/image content and
  DOCX/PPTX parsing are out of scope for v1.
- **Workspace-wide ranking.** The vital-few view is computed across the student's whole set of
  materials (not per individual file), because "recurrence across materials" is part of the evidence.
- **Bounded vital-few size.** "80/20" is treated as a guiding spirit, not arithmetic: the shortlist is
  a small, fixed-size set of the top concepts (SC-004), clamped to the corpus — not a percentage of
  it — so it stays a usable "few" at any scale. Depth beyond the few is the concept hierarchy's job.
- **Input is provided as one or more uploaded files.** No integration with external note apps or
  cloud drives in v1.
- **The quantitative targets in SC-004 and SC-005 are initial goals to validate and tune via the
  evaluation suite**, not contractual guarantees; faithfulness (SC-002, SC-003) is the fixed bar.
- **Generation features (flashcards, slides) are out of scope** for this feature.
