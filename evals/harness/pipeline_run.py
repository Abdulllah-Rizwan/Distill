"""Run the real ingestion -> graph -> ranking pipeline for a dataset behind a given LLM.

Uses the production composition root (:func:`build_services`) over an in-memory SQLite database,
with the Gemini extractor/explainer pointed at whatever :class:`JsonLLM` the caller supplies
(recording, replay, or the real client). So the eval exercises the same code the API does — only
the model I/O is swapped at the port.
"""

from __future__ import annotations

from dataclasses import dataclass

from distil.adapters.llm.gemini._client import JsonLLM
from distil.adapters.llm.gemini.explainer import GeminiExplainer
from distil.adapters.llm.gemini.extractor import GeminiConceptExtractor
from distil.adapters.persistence.sqlite.schema import connect, initialize
from distil.api.dependencies import build_services
from distil.domain.concept import Concept
from distil.domain.material import Material
from distil.domain.ranking import VitalFewEntry
from distil.domain.relationship import Relationship
from evals.harness.dataset import Dataset

WORKSPACE = "w_eval"


@dataclass(frozen=True, slots=True)
class PipelineOutput:
    """Everything the scorers need from one pipeline run over a dataset."""

    materials: list[Material]
    concepts: list[Concept]
    relationships: list[Relationship]
    entries: list[VitalFewEntry]

    @property
    def concepts_by_id(self) -> dict[str, Concept]:
        return {c.id: c for c in self.concepts}

    @property
    def vital_few_labels(self) -> tuple[str, ...]:
        """The vital-few concept labels in rank order."""
        by_id = self.concepts_by_id
        ordered = sorted(self.entries, key=lambda e: e.rank)
        return tuple(by_id[e.concept_id].label for e in ordered if e.concept_id in by_id)


def run_pipeline(dataset: Dataset, llm: JsonLLM) -> PipelineOutput:
    """Ingest every note in ``dataset`` and return the resulting graph + vital-few."""
    conn = connect(":memory:")
    initialize(conn)
    services = build_services(conn, GeminiConceptExtractor(llm), GeminiExplainer(llm))
    for note in dataset.notes:
        services.pipeline.ingest(WORKSPACE, note.filename, note.text.encode("utf-8"))

    latest = services.graph.latest_ranking(WORKSPACE)
    return PipelineOutput(
        materials=list(services.materials.list_accepted(WORKSPACE)),
        concepts=list(services.graph.list_concepts(WORKSPACE)),
        relationships=list(services.graph.list_relationships(WORKSPACE)),
        entries=list(latest[1]) if latest is not None else [],
    )
