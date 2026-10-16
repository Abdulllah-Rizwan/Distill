"""Port: graph-signal computation (centrality) over the concept graph."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from distil.domain.concept import Concept
from distil.domain.relationship import Relationship


class GraphAnalyzer(Protocol):
    """Computes centrality signals from the concept graph structure.

    The NetworkX adapter implements this. Recurrence (how many materials a concept spans) is derived
    from the concept's sources at build time, not here — this port is purely structural centrality.
    """

    def compute_signals(
        self,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
    ) -> dict[str, dict[str, float]]:
        """Return ``concept_id -> {signal_name: value}`` (e.g. degree, pagerank)."""
        ...
