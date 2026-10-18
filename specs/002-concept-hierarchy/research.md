# Phase 0 Research — Concept Hierarchy

All decisions below are deterministic, graph-grounded, and reuse feature 001. There are no open
`NEEDS CLARIFICATION` items (the spec carried none). Format per decision: **Decision / Rationale /
Alternatives considered.**

## D1 — Roots are the vital-few pillars (plus a root per otherwise-rootless component)

**Decision**: The primary roots of the forest are the **vital-few concepts** from feature 001's
ranking (top by composite score, sized by `vital_few_size`, DS-0004). If a connected component of the
relationship graph contains no pillar, its highest-scoring concept becomes a **secondary root** so
that component still forms a tree. Truly isolated concepts (no edges) are not forced under a pillar;
they are surfaced as `unplaced` (see D4).

**Rationale**: This makes the hierarchy's top level *be* the explainable 80/20 the student already
trusts (SC-001, and the "bridge from DS-0004" in the spec), and guarantees every connected concept
descends from some root. Secondary roots keep coverage honest without inventing cross-component links.

**Alternatives considered**:
- *Community detection (Louvain / greedy modularity) to discover roots* — more "organic" clusters, but
  non-trivial, less explainable ("why is this the root?"), and can drift from the vital-few the student
  already saw. Deferred; could refine root grouping later if evals show the pillars cluster poorly.
- *A single synthetic super-root* — artificial; it is not a real concept from the notes, so it would
  be an ungrounded node (violates Principle I's spirit).

## D2 — Parenting is a breadth-first forest over the undirected relationship graph

**Decision**: Treat relationships as **undirected edges** for structure. From the set of roots, run a
**multi-source breadth-first traversal**: each non-root concept's parent is the neighbour through which
it is first reached (fewest hops from the nearest root). This yields a real tree where **every
parent→child link is an existing edge**.

**Rationale**: BFS gives the shortest, most direct grounding path from a pillar to each concept, so a
concept sits under the pillar it is most closely connected to — intuitive for study navigation and
trivially faithful (links are edges). It is O(V+E), deterministic, and simple to explain and test.

**Alternatives considered**:
- *Directed edges (use relationship direction)* — relationship `kind`/direction is extracted but noisy
  and often semantically arbitrary (e.g. "A relates-to B"); forcing direction would drop valid
  structural links. We keep direction as *display* metadata on the edge, not as the tree's spine.
- *Max-weight spanning / highest-scoring-neighbour attachment* — attach each concept to its
  highest-scoring graph neighbour. Simpler per-node but can create long sideways chains and cycles to
  resolve; BFS-from-roots gives a cleaner, shallower, root-anchored tree.

## D3 — Exactly one parent per concept, with deterministic tie-breaking

**Decision**: Each non-root concept has **exactly one parent** (strict forest, FR-007). When BFS
reaches a concept from several equally-near candidates in the same layer, break ties by: (1) higher
parent composite score, then (2) parent label (lexicographic), then (3) parent concept id. Children of
a node are ordered by composite score desc, then label.

**Rationale**: A single parent makes navigation unambiguous and the structure a true tree. Fully
specifying tie-breaks (score → label → id, all deterministic given DS-0003 stable ids) guarantees
reproducibility (SC-006) — the same graph always yields byte-identical structure.

**Alternatives considered**:
- *DAG (allow multiple parents)* — truer to the graph, but ambiguous to navigate and to render as a
  "tree", and harder to eval. The full many-to-many relationships remain available via the 001 graph
  endpoints (US2); the hierarchy is the *navigable* projection.

## D4 — Disconnected / isolated concepts are surfaced, never invented into the tree

**Decision**: Concepts with **no path to any pillar** root their own component (D1 secondary root).
Concepts with **no edges at all** cannot be grounded under any parent, so they are returned in an
explicit `unplaced` list (not attached to a pillar). Everything extracted appears exactly once:
either in a tree or in `unplaced` (FR-006, SC-002).

**Rationale**: Attaching an edge-less concept to a pillar would be an **ungrounded link** — exactly
what Principle I forbids. Surfacing them as `unplaced` is the honest alternative and still satisfies
100% coverage. It also gives a useful signal (isolated concepts often = extraction noise, feeding the
separate extraction-quality work).

**Alternatives considered**:
- *Attach orphans to the nearest pillar by label/embedding similarity* — introduces a non-graph,
  potentially ungrounded link; rejected on faithfulness grounds for v1.

## D5 — Compute on read; do not persist the hierarchy

**Decision**: Build the hierarchy **on demand** from the persisted concepts + relationships when the
endpoint is called. Do **not** add a table or rebuild step.

**Rationale**: The hierarchy is a pure, cheap (O(V+E)) function of data already stored and already
rebuilt on every change — persisting it would duplicate state and add rebuild wiring for no benefit
(Principle VI/YAGNI). Compute-on-read is automatically consistent and "current" (FR-010) and
idempotent (FR-008). If profiling ever shows it matters, caching is a later, contained addition.

**Alternatives considered**:
- *Persist a `hierarchy_node` table built during the pipeline rebuild* — mirrors the ranking, but adds
  schema + migration + rebuild code for a computation that is far cheaper than the LLM steps around it.
  Rejected for v1; revisit only if a real performance need appears.

## D6 — The builder is a pure service, not a NetworkX adapter method

**Decision**: Implement the forest build in `services/hierarchy.py` as plain-Python BFS over an
adjacency map built from the stored relationships. Reuse `ranking.composite_scores` and
`vital_few_size` for root selection. Do **not** route it through the NetworkX `GraphAnalyzer`.

**Rationale**: BFS over an adjacency dict is a few lines and fully deterministic; keeping it a pure
service (like `RankingService`) makes it unit-testable with no adapter, keeps the determinism obvious,
and avoids widening the graph port for one traversal (Principle VI/VIII consistency). NetworkX stays
where it earns its keep — PageRank/degree in the analyzer.

**Alternatives considered**:
- *Add `compute_hierarchy` to the NetworkX `GraphAnalyzer` port* — consistent with signals living
  there, but couples a trivial traversal to the graph adapter and makes pure unit testing need the
  adapter. Rejected; the pure service is simpler and better isolated.

## D7 — Placement rationales are deterministic (no LLM call added)

**Decision**: Generate each placement's "why" deterministically: for a child, from the **grounding
edge** (relationship `kind` if present + the source quote) and the hop relationship to its parent; for
a pillar, from its importance signals (recurrence + degree), reusing the ranking's rationale style. No
new model call.

**Rationale**: The structure is deterministic, so its explanation can be too — this keeps the view
fully faithful, reproducible, and **free of extra LLM/credit spend** (a live constraint). It mirrors
feature 001's deterministic fallback rationale.

**Alternatives considered**:
- *Use the `Explainer` LLM port to phrase placement reasons* — nicer prose, but costs quota per build,
  adds non-determinism to the text, and is unnecessary for a clear structural reason. Explicitly
  **deferred**: can be layered on later behind the existing port, exactly as the ranking explainer is.

## D8 — Natural depth/branching in v1 (no artificial caps yet)

**Decision**: Let depth and branching fall out of the BFS forest in v1; do not cap children-per-node
or max depth. Expose the shape through the API and **measure** it via the eval harness; add bounds
only if evals/eyeballing show pathological shapes (FR-012 is a tunable target, not a v1 guarantee).

**Rationale**: YAGNI — caps are a tuning knob that needs data to set well; the local lecture run is the
first place to observe real shapes. Introducing caps now would be speculative complexity.

**Alternatives considered**:
- *Cap children to N and spill the rest into a "more" bucket* — reasonable for UI later, but premature
  without seeing real distributions and without a UI; deferred to tuning.
