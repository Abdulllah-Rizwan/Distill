"""NetworkX implementation of the GraphAnalyzer port.

Computes structural centrality signals (degree + PageRank) over the concept graph. Pure compute —
it reads concepts/relationships and returns per-concept signals; it persists nothing.
"""

from __future__ import annotations

from collections.abc import Sequence

import networkx as nx

from distil.domain.concept import Concept
from distil.domain.relationship import Relationship


class NetworkxGraphAnalyzer:
    """Satisfies :class:`~distil.ports.graph.GraphAnalyzer`."""

    def compute_signals(
        self,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
    ) -> dict[str, dict[str, float]]:
        graph: nx.Graph[str] = nx.Graph()
        graph.add_nodes_from(c.id for c in concepts)
        for rel in relationships:
            graph.add_edge(rel.source_concept_id, rel.target_concept_id)

        node_count = graph.number_of_nodes()
        if node_count == 0:
            return {}

        degrees = dict(graph.degree())
        if graph.number_of_edges() > 0:
            pagerank = nx.pagerank(graph)
        else:
            # No edges: PageRank is uniform; spell it out rather than call into an empty graph.
            pagerank = dict.fromkeys(graph.nodes, 1.0 / node_count)

        return {
            node: {"degree": float(degrees[node]), "pagerank": float(pagerank[node])}
            for node in graph.nodes
        }
