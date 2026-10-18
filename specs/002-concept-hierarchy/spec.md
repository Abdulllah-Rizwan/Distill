# Feature Specification: Concept Hierarchy (Tree View)

**Feature Branch**: `002-concept-hierarchy`

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: "Concept hierarchy (tree view) for Distil — a few root 'pillar' concepts
with supporting concepts branching beneath them, derived from the source-grounded concept graph, so
a student can navigate from the big ideas down to specifics. Extends feature 001 (concept graph +
explainable vital-few); the flat vital-few (fixed ~5 pillars, DS-0004) is the bridge: broad coverage
and depth are delivered by this hierarchy, not by a longer flat list."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Navigate from the pillars down (Priority: P1) 🎯 MVP

A student has built a concept graph from their notes and has seen the flat "vital few". Now they want
structure, not just a top list. They open the concept hierarchy and see a small number of **root
"pillar" concepts** — the big ideas of the material. Each pillar can be expanded to reveal the key
concepts that sit beneath it, and those in turn can be expanded, so the student moves from the few
big ideas down to the specifics at their own pace. Every concept they see links back to the exact
passage in their own notes.

**Why this priority**: This is the feature's core value and the reason it exists — turning a flat
list that is either too short (2 on a tiny corpus) or unusable (43 on five lectures) into a navigable
structure that scales. Without it, a large corpus has no usable "map". It is independently useful the
moment it returns a single pillar with its children.

**Independent Test**: Build a graph from a representative set of notes, request the hierarchy, and
confirm it returns a small set of root pillars, each expandable into child concepts, with every node
carrying a verifiable link to a source passage.

**Acceptance Scenarios**:

1. **Given** a built concept graph for a workspace, **When** the student requests the concept
   hierarchy, **Then** Distil returns a small set of root pillar concepts (not the whole corpus), each
   with the concepts that branch beneath it.
2. **Given** the hierarchy is displayed, **When** the student expands a pillar, **Then** they see that
   pillar's direct child concepts, and each child can itself be expanded if it has children.
3. **Given** any concept shown in the hierarchy, **When** the student opens it, **Then** they can
   reach the exact source passage(s) in their own notes that the concept is grounded in.

---

### User Story 2 - Understand why the tree is shaped this way (Priority: P2)

Having navigated the hierarchy, the student wants to trust it: why is *this* concept a top pillar, and
why does *that* concept sit underneath it rather than somewhere else? For each placement, Distil shows
a plain, source-linked reason — which connection(s) in their own notes, or which importance signal,
put the concept where it is. Nothing in the tree is an unexplained, black-box arrangement.

**Why this priority**: Explainability is a non-negotiable project principle (a tree the student cannot
question is a tree they cannot trust or correct). It builds directly on US1 but is separable: the tree
is navigable without rationales, and rationales add the trust layer.

**Independent Test**: With a hierarchy built, select any non-root concept and confirm it exposes a
human-readable reason for its placement that cites the grounding connection or signal, traceable to
source — and that no placement exists without such grounding.

**Acceptance Scenarios**:

1. **Given** a root pillar, **When** the student asks why it is a pillar, **Then** Distil explains it
   in terms of the concept's importance across their notes (how central it is, how many materials it
   recurs across).
2. **Given** a child concept, **When** the student asks why it sits under its parent, **Then** Distil
   cites the relationship/connection from their notes (or the graph proximity) that links them, with a
   path to the supporting passage.
3. **Given** the full hierarchy, **When** it is inspected, **Then** every parent→child link corresponds
   to a grounding in the source graph; there are zero invented or unexplained links.

---

### User Story 3 - A complete, current map (Priority: P3)

The student relies on the hierarchy as a map of *everything* in their notes, and expects it to stay
current. Every concept that was extracted appears somewhere in the tree (nothing silently disappears),
and when they add or remove materials, the hierarchy re-forms to reflect the new set of notes.

**Why this priority**: Coverage and freshness make the hierarchy trustworthy as a map rather than a
lossy summary, and tie it to the existing add/remove-materials flow. It is the least urgent of the
three because US1+US2 already deliver a usable, explained tree for a fixed corpus.

**Independent Test**: Confirm every extracted concept appears exactly once in the hierarchy; then add a
material and confirm new concepts are placed, and remove a material and confirm concepts it solely
supported disappear — and that rebuilding the same corpus yields the same tree.

**Acceptance Scenarios**:

1. **Given** a built hierarchy, **When** it is compared to the full concept list, **Then** every
   extracted concept appears exactly once (no orphans, no duplicates).
2. **Given** an existing hierarchy, **When** the student adds a new material, **Then** the hierarchy
   updates to incorporate that material's concepts and connections.
3. **Given** the same set of materials, **When** the hierarchy is rebuilt, **Then** it produces the
   same structure (stable, reproducible).

---

### Edge Cases

- **Corpus too small**: Too few concepts to form a meaningful hierarchy — Distil communicates this and
  does not present a trivial or arbitrary tree (mirrors the vital-few minimum from feature 001).
- **Disconnected concepts**: A concept with no relationship to any pillar (an island in the graph) —
  it must still appear in the hierarchy (e.g. attached to the nearest pillar or surfaced as unplaced),
  never silently dropped (coverage from US3).
- **Weakly/ambiguously connected concept**: A concept connected to several candidate parents — the
  system must place it under exactly one parent, chosen deterministically, with the reason visible.
- **Flat or fully-connected graph**: Many concepts with uniform connectivity (no clear structure) —
  the hierarchy must degrade gracefully (shallow, wide tree) rather than fabricate depth.
- **Single pillar**: A corpus dominated by one central idea — a single root with everything beneath it
  is acceptable, as long as placements are grounded.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST arrange the workspace's extracted concepts into a hierarchy — a set of root
  "pillar" concepts, each with concepts branching beneath them, to a depth greater than one level where
  the material supports it.
- **FR-002**: The root pillars MUST be the most important concepts by the same graph-derived signals
  used for the flat ranking (centrality + recurrence), so the top of the hierarchy aligns with the
  vital-few pillars from feature 001.
- **FR-003**: Every parent→child placement MUST be derived from the source-grounded concept graph
  (the relationships extracted from the student's notes and/or graph structure). The system MUST NOT
  create a parent→child link that the graph does not support, and MUST NOT invent connections from
  outside the user's material (Source-Faithfulness).
- **FR-004**: Every concept in the hierarchy MUST remain traceable to the source passage(s) it was
  grounded in, identically to the flat concept view.
- **FR-005**: For every placement, the system MUST expose a visible, plain-language reason — for a
  pillar, its importance across the notes; for a child, the grounding connection or proximity that
  places it under its parent (Explainable Intelligence).
- **FR-006**: Every extracted concept MUST appear in the hierarchy exactly once (complete coverage; no
  orphans, no duplicates). A concept that cannot be grounded under any pillar MUST still be surfaced
  (e.g. under the nearest pillar or as an explicitly "unplaced" set), never silently dropped.
- **FR-007**: Each non-root concept MUST have exactly one parent (the structure is a tree/forest, not
  an arbitrary graph), so navigation is unambiguous; the single parent is chosen deterministically when
  several candidates exist.
- **FR-008**: The hierarchy MUST be deterministic and idempotent — the same concept graph MUST always
  produce the same tree, with stable node identity across rebuilds (consistent with how the graph and
  ranking already behave).
- **FR-009**: Students MUST be able to retrieve the hierarchy through the application interface — both
  the overall tree (roots and their descendants) and the subtree rooted at a given concept.
- **FR-010**: When the student adds or removes materials, the hierarchy MUST update to reflect the
  current set of notes, consistent with the existing rebuild of the graph and ranking.
- **FR-011**: When the corpus is too small to form a meaningful hierarchy, the system MUST communicate
  this (as the flat vital-few does) rather than return a trivial or arbitrary tree.
- **FR-012**: The hierarchy MUST stay navigable — neither one flat level with an unmanageable number of
  children, nor an arbitrarily deep chain. The number of children surfaced per node and the depth are
  tunable targets validated via the eval suite, not fixed guarantees.

### Key Entities *(include if feature involves data)*

- **Concept Hierarchy**: The arrangement of a workspace's concepts into rooted trees for one build —
  the set of roots and, for each concept, its parent and children. Belongs to a workspace and
  corresponds to a graph/ranking build (so it is versioned/rebuilt alongside them).
- **Hierarchy Placement (node)**: One concept's position in the hierarchy — its parent (none, if a
  root), its depth, whether it is a root pillar, and the grounded reason for its placement (the signal
  that made it a pillar, or the relationship/proximity that attached it to its parent). References an
  existing **Concept** (feature 001) rather than duplicating it.
- **Concept** / **Relationship** *(from feature 001, reused)*: the source-grounded nodes and edges the
  hierarchy is computed from; unchanged by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The top level of the hierarchy is a small set of pillars (on the order of the vital-few
  size, not the whole corpus), so the entry point stays comprehensible regardless of corpus size (e.g.
  a 200-concept corpus still opens with a handful of pillars, not 40+).
- **SC-002**: 100% of extracted concepts appear in the hierarchy, each exactly once — zero orphans and
  zero duplicates, measured against the full concept list.
- **SC-003**: 0 parent→child links appear that are not grounded in the source concept graph, measured
  against a curated evaluation dataset (the faithfulness bar, matching feature 001's SC-003).
- **SC-004**: In evaluation against a curated dataset, the root pillars match the concepts domain
  reviewers consider the material's main themes, and each child is judged genuinely related to its
  parent, at a target agreement of ≥ 80% (relevance of structure) — validated and tuned via the eval
  suite.
- **SC-005**: For any concept in the hierarchy, the student can reach a supporting source passage in a
  single action.
- **SC-006**: Rebuilding the hierarchy on the same materials produces an identical structure
  (reproducibility), verifiable by building twice and comparing.
- **SC-007**: After reading only the displayed reason for a placement, a new student can restate in
  their own words why a concept is a pillar or why it sits under its parent (qualitative check with
  representative users).

## Assumptions

- **Builds on feature 001.** The source-grounded concept graph, its deterministic signals (centrality,
  recurrence), the persistence/interface architecture, and the per-workspace, single-user, local, and
  backend-first scope are all inherited. This feature adds structure *over* that graph; it does not
  change extraction or the flat ranking.
- **Bridge from the flat vital-few (DS-0004).** The flat vital-few remains the quick "what matters
  most" answer and seeds the hierarchy's roots; broad coverage and depth are this feature's job, which
  is why the flat list stays a fixed small size rather than growing with the corpus.
- **Graph-derived, not LLM-invented structure.** Placement (which concept is a root, which parent a
  concept attaches to) is decided from the graph (importance signals, connectivity/clustering), not by
  asking a model to arrange concepts freely — consistent with Explainable Intelligence and
  Source-Faithfulness. A model may, as in feature 001, phrase the human-readable *reason* for a
  placement it did not decide.
- **Tree/forest, one parent per concept.** For unambiguous navigation the structure is a forest of
  trees (several pillars), each concept under exactly one parent, even though the underlying graph is a
  general graph; the single parent is chosen by a deterministic rule when multiple connections exist.
- **Computed as a batch on rebuild.** Like the flat ranking, the hierarchy is recomputed when the
  corpus changes, not maintained incrementally, keeping it simple to reason about and keep faithful.
- **Depth/branching targets are initial goals to tune via evals**, not contractual guarantees;
  faithfulness (SC-002, SC-003) and reproducibility (SC-006) are the fixed bars.
- **No rich UI in this feature.** v1 delivers the computed, source-linked hierarchy through the
  application interface; interactive visualization/front-end is out of scope (as with feature 001).
