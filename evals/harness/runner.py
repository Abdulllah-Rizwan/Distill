"""Run one dataset end-to-end: build the LLM (live or replay), run the pipeline, score, report."""

from __future__ import annotations

from pathlib import Path

from distil.adapters.llm.gemini._client import GeminiClient, JsonLLM
from distil.config import Settings
from evals.harness.dataset import load_dataset
from evals.harness.faithfulness import score_faithfulness
from evals.harness.pipeline_run import run_pipeline
from evals.harness.recording import (
    RecordingLLM,
    ReplayLLM,
    load_fixtures,
    save_fixtures,
)
from evals.harness.relevance import score_relevance
from evals.harness.report import DatasetReport

FIXTURES_FILE = "fixtures.json"


def run_dataset(path: Path, *, live: bool, settings: Settings) -> DatasetReport:
    """Score the dataset at ``path``; record fixtures from the real model when ``live`` is set."""
    dataset = load_dataset(path)
    fixtures_path = path / FIXTURES_FILE

    recorder: RecordingLLM | None = None
    llm: JsonLLM
    if live:
        recorder = RecordingLLM(
            GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
        )
        llm = recorder
    else:
        llm = ReplayLLM(load_fixtures(fixtures_path))

    output = run_pipeline(dataset, llm)
    faithfulness = score_faithfulness(
        output.materials, output.concepts, output.relationships, output.entries
    )
    relevance = score_relevance(llm, dataset, output.vital_few_labels)

    if recorder is not None:
        save_fixtures(fixtures_path, recorder.recorded)

    return DatasetReport(
        name=dataset.name,
        faithfulness=faithfulness,
        relevance=relevance,
        min_relevance=dataset.min_relevance,
        vital_few_labels=output.vital_few_labels,
    )
