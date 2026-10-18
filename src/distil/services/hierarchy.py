"""Hierarchy service: arrange the concept graph into a navigable, source-grounded forest.

Pure and deterministic (research.md D6): no I/O, no LLM call. Roots are the vital-few pillars (from
the ranking service); every other concept is attached to its single nearest pillar via a **real
relationship edge** using a layered breadth-first traversal, so each parent→child link is grounded
by construction (Principle I). Concepts with no path to a pillar head their own component; concepts
with no edges at all are surfaced as ``unplaced``, never linked by invention (research.md D1–D4).

Same graph in → same forest out: every selection and traversal step is fully ordered by composite
score, then label, then (stable, DS-0003) concept id.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from distil.domain.concept import Concept
from distil.domain.hierarchy import ConceptHierarchy, HierarchyNode
from distil.domain.relationship import Relationship
from distil.services.ranking import (
    MIN_CONCEPTS_FOR_VITAL_FEW,
    composite_scores,
    vital_few_size,
)


class HierarchyService:
    """Builds a :class:`ConceptHierarchy` from a workspace's concepts + relationships."""

    def build(
        self,
        workspace_id: str,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
    ) -> ConceptHierarchy:
        concepts = list(concepts)
        total = len(concepts)
        by_id = {c.id: c for c in concepts}
        scores = composite_scores(concepts)

        # Too small to organise — surface everything as unplaced (the endpoint adds an explanatory
        # note). Coverage still holds: unplaced == all concepts (FR-011).
        if total < MIN_CONCEPTS_FOR_VITAL_FEW:
            return ConceptHierarchy(
                workspace_id=workspace_id,
                roots=(),
                nodes={},
                unplaced=self._ordered(list(by_id), scores, by_id),
                total_concepts=total,
            )

        adjacency, edge_of, degree = self._graph(by_id, relationships)

        # Roots: the vital-few pillars first (by score), then a secondary root for every component
        # with no pillar and >= 2 members (research.md D1).
        ordered = self._ordered(list(by_id), scores, by_id)
        pillars = list(ordered[: vital_few_size(total)])
        pillar_set = set(pillars)
        secondary = self._secondary_roots(by_id, adjacency, pillar_set, scores)
        roots = pillars + secondary

        parent, depth, grounding_rel = self._bfs_forest(roots, adjacency, edge_of, scores, by_id)

        # Children of each placed node, ordered deterministically.
        children: dict[str, list[str]] = defaultdict(list)
        for cid, pid in parent.items():
            if pid is not None:
                children[pid].append(cid)
        for pid in children:
            children[pid] = list(self._ordered(children[pid], scores, by_id))

        nodes: dict[str, HierarchyNode] = {}
        for cid in parent:  # every concept reached (roots + BFS-placed)
            pid = parent[cid]
            rel = grounding_rel.get(cid)
            is_pillar = cid in pillar_set
            nodes[cid] = HierarchyNode(
                concept_id=cid,
                parent_concept_id=pid,
                depth=depth[cid],
                is_pillar=is_pillar,
                children=tuple(children.get(cid, ())),
                placement_reason=self._reason(cid, pid, is_pillar, by_id, degree, rel),
                grounding=rel.sources if rel is not None else (),
                grounding_edge_id=rel.id if rel is not None else None,
            )

        unplaced = tuple(cid for cid in ordered if cid not in nodes)
        return ConceptHierarchy(
            workspace_id=workspace_id,
            roots=tuple(roots),
            nodes=nodes,
            unplaced=unplaced,
            total_concepts=total,
        )

    def subtree(self, hierarchy: ConceptHierarchy, concept_id: str) -> HierarchyNode | None:
        """The node rooted at ``concept_id`` (with its descendants reachable via ``children``)."""
        return hierarchy.nodes.get(concept_id)

    # --- internals ---------------------------------------------------------------------------

    @staticmethod
    def _ordered(
        ids: Sequence[str], scores: dict[str, float], by_id: dict[str, Concept]
    ) -> tuple[str, ...]:
        """Deterministic order: highest composite score first, ties by label then id."""
        return tuple(sorted(ids, key=lambda cid: (-scores[cid], by_id[cid].label, cid)))

    @staticmethod
    def _graph(
        by_id: dict[str, Concept], relationships: Sequence[Relationship]
    ) -> tuple[dict[str, set[str]], dict[tuple[str, str], Relationship], dict[str, int]]:
        """Undirected adjacency, a per-pair grounding edge, and each concept's degree.

        When several relationships connect the same pair, the one with the smallest id is the
        grounding edge (deterministic). Self-loops and edges to unknown concepts are ignored.
        """
        adjacency: dict[str, set[str]] = {cid: set() for cid in by_id}
        edge_of: dict[tuple[str, str], Relationship] = {}
        for rel in sorted(relationships, key=lambda r: r.id):
            a, b = rel.source_concept_id, rel.target_concept_id
            if a == b or a not in by_id or b not in by_id:
                continue
            adjacency[a].add(b)
            adjacency[b].add(a)
            key = (a, b) if a < b else (b, a)
            edge_of.setdefault(key, rel)  # smallest-id relationship wins (sorted above)
        degree = {cid: len(neighbors) for cid, neighbors in adjacency.items()}
        return adjacency, edge_of, degree

    def _secondary_roots(
        self,
        by_id: dict[str, Concept],
        adjacency: dict[str, set[str]],
        pillar_set: set[str],
        scores: dict[str, float],
    ) -> list[str]:
        """Top-scoring concept of each pillar-less component of size >= 2 (research.md D1/D4)."""
        seen: set[str] = set()
        secondary: list[str] = []
        for cid in self._ordered(list(by_id), scores, by_id):
            if cid in seen:
                continue
            component = self._component(cid, adjacency)
            seen |= component
            if len(component) < 2 or component & pillar_set:
                continue  # singletons → unplaced; components with a pillar are already rooted
            top = self._ordered(list(component), scores, by_id)[0]
            secondary.append(top)
        return secondary

    @staticmethod
    def _component(start: str, adjacency: dict[str, set[str]]) -> set[str]:
        """All concepts reachable from ``start`` over undirected edges."""
        seen = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for nb in adjacency[node]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        return seen

    def _bfs_forest(
        self,
        roots: Sequence[str],
        adjacency: dict[str, set[str]],
        edge_of: dict[tuple[str, str], Relationship],
        scores: dict[str, float],
        by_id: dict[str, Concept],
    ) -> tuple[dict[str, str | None], dict[str, int], dict[str, Relationship]]:
        """Layered multi-source BFS from ``roots``; each non-root takes its single best parent.

        Processing one distance-layer at a time guarantees "nearest root"; when a concept is reached
        from several parents in the same layer, the best parent wins by (score, label, id) — fully
        deterministic (research.md D2/D3).
        """
        parent: dict[str, str | None] = dict.fromkeys(roots)
        depth: dict[str, int] = dict.fromkeys(roots, 0)
        grounding_rel: dict[str, Relationship] = {}
        visited = set(roots)
        frontier = list(roots)

        while frontier:
            proposals: dict[str, list[str]] = defaultdict(list)
            for u in frontier:
                for v in adjacency[u]:
                    if v not in visited:
                        proposals[v].append(u)
            placed_now: list[str] = []
            for v in sorted(proposals):
                best = min(proposals[v], key=lambda p: (-scores[p], by_id[p].label, p))
                parent[v] = best
                depth[v] = depth[best] + 1
                key = (v, best) if v < best else (best, v)
                grounding_rel[v] = edge_of[key]
                visited.add(v)
                placed_now.append(v)
            frontier = list(self._ordered(placed_now, scores, by_id))

        return parent, depth, grounding_rel

    @staticmethod
    def _reason(
        cid: str,
        pid: str | None,
        is_pillar: bool,
        by_id: dict[str, Concept],
        degree: dict[str, int],
        rel: Relationship | None,
    ) -> str:
        """A deterministic, source-true placement reason (research.md D7 — no LLM call)."""
        concept = by_id[cid]
        if pid is None:
            lead = "A core idea" if is_pillar else "Heads a group of related concepts"
            return (
                f"{lead}: recurs across {concept.recurrence_count} of your materials and links to "
                f"{degree[cid]} other concept(s) in your notes."
            )
        parent_label = by_id[pid].label
        quote = rel.sources[0].quote if rel is not None and rel.sources else ""
        relation = f" ({rel.kind})" if rel is not None and rel.kind else ""
        return f"Linked to {parent_label!r}{relation} — your notes: {quote!r}."
