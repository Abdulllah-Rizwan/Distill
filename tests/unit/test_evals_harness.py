"""Deterministic tests for the eval harness — no network, no quota.

A schema-routing fake stands in for the LLM at the ``JsonLLM`` port, so these exercise the real
pipeline (extraction -> merge -> graph -> ranking) plus the faithfulness/relevance scorers, the
record/replay machinery, dataset loading, and the pass/fail gate — all offline and reproducible.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from evals.harness.dataset import Dataset, Note, load_dataset
from evals.harness.faithfulness import FaithfulnessResult, score_faithfulness
from evals.harness.pipeline_run import run_pipeline
from evals.harness.recording import (
    ReplayLLM,
    fixture_key,
    load_fixtures,
    save_fixtures,
)
from evals.harness.relevance import JudgeVerdict, RelevanceResult, score_relevance
from evals.harness.report import DatasetReport, overall_passed
from pydantic import BaseModel

from distil.domain.concept import Concept
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.source_reference import SourceReference

NOTE_TEXT = (
    "Mitochondria produce energy. Energy powers the cell. "
    "The cell contains mitochondria, ribosomes, and a nucleus. The nucleus stores DNA."
)

_EXTRACTION_JSON = json.dumps(
    {
        "concepts": [
            {"label": "mitochondria", "quote": "Mitochondria"},
            {"label": "energy", "quote": "energy"},
            {"label": "cell", "quote": "cell"},
            {"label": "ribosomes", "quote": "ribosomes"},
            {"label": "nucleus", "quote": "nucleus"},
            {"label": "DNA", "quote": "DNA"},
        ],
        "relationships": [
            {
                "source_label": "mitochondria",
                "target_label": "energy",
                "quote": "Mitochondria produce energy",
                "kind": "produce",
            },
            {
                "source_label": "nucleus",
                "target_label": "DNA",
                "quote": "The nucleus stores DNA",
                "kind": "stores",
            },
        ],
    }
)


class _SchemaRoutingLLM:
    """A JsonLLM whose canned reply is chosen by the response schema's name."""

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        name = response_schema.__name__
        if name == "ExtractionPayload":
            return _EXTRACTION_JSON
        if name == "ExplanationPayload":
            return '{"items": []}'  # empty -> ranking service uses its deterministic fallback
        if name == "JudgeVerdict":
            return '{"score": 0.8, "justification": "surfaces the central concepts"}'
        raise AssertionError(f"unexpected schema {name!r}")


def _dataset() -> Dataset:
    return Dataset(
        name="t",
        description="",
        notes=(Note(filename="n.md", text=NOTE_TEXT),),
        important_concepts=("mitochondria", "energy", "cell"),
        min_relevance=0.6,
    )


# --- end-to-end: real pipeline + scorers behind the fake ---------------------------------------


def test_pipeline_output_is_fully_faithful_and_ranked() -> None:
    output = run_pipeline(_dataset(), _SchemaRoutingLLM())

    assert len(output.concepts) == 6
    assert output.entries, "6 concepts should clear the vital-few threshold"

    result = score_faithfulness(
        output.materials, output.concepts, output.relationships, output.entries
    )
    assert result.passed
    assert result.score == 1.0
    assert result.total > 0  # concepts + relationships + evidence all checked


def test_relevance_uses_judge_score_and_overlap() -> None:
    output = run_pipeline(_dataset(), _SchemaRoutingLLM())
    relevance = score_relevance(_SchemaRoutingLLM(), _dataset(), output.vital_few_labels)

    assert relevance.score == pytest.approx(0.8)
    assert 0.0 <= relevance.precision <= 1.0
    assert 0.0 <= relevance.recall <= 1.0


# --- faithfulness scorer catches ungrounded spans ----------------------------------------------


def test_faithfulness_flags_a_tampered_quote() -> None:
    material = Material(
        id="m1",
        workspace_id="w1",
        filename="n.txt",
        format=MaterialFormat.TEXT,
        content_text="abc",
        content_hash="h",
        status=MaterialStatus.ACCEPTED,
        created_at=datetime(2026, 10, 17, tzinfo=UTC),
    )
    bad = Concept(
        id="c1",
        workspace_id="w1",
        label="x",
        sources=(SourceReference(material_id="m1", start_offset=0, end_offset=3, quote="xyz"),),
        recurrence_count=1,
    )
    result = score_faithfulness([material], [bad], [], [])
    assert not result.passed
    assert result.score == 0.0
    assert len(result.violations) == 1


# --- record / replay ---------------------------------------------------------------------------


def test_replay_returns_recorded_and_raises_on_miss() -> None:
    key = fixture_key("sys", "user", JudgeVerdict)
    replay = ReplayLLM({key: '{"score": 0.5, "justification": "x"}'})

    got = replay.generate_json(
        system_instruction="sys", user_content="user", response_schema=JudgeVerdict
    )
    assert json.loads(got)["score"] == 0.5

    with pytest.raises(LookupError):
        replay.generate_json(
            system_instruction="other", user_content="user", response_schema=JudgeVerdict
        )


def test_fixture_save_load_round_trip(tmp_path: Path) -> None:
    fixtures = {"a": '{"x": 1}', "b": "raw"}
    path = tmp_path / "fixtures.json"
    save_fixtures(path, fixtures)
    assert load_fixtures(path) == fixtures
    assert load_fixtures(tmp_path / "missing.json") == {}


# --- dataset loading ---------------------------------------------------------------------------


def test_load_dataset_reads_notes_and_metadata(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "01.md").write_text("hello", encoding="utf-8")
    (tmp_path / "dataset.json").write_text(
        json.dumps({"name": "d", "important_concepts": ["a"], "min_relevance": 0.7}),
        encoding="utf-8",
    )
    dataset = load_dataset(tmp_path)
    assert dataset.name == "d"
    assert dataset.notes[0].text == "hello"
    assert dataset.min_relevance == 0.7
    assert dataset.important_keys == {"a"}


# --- gating ------------------------------------------------------------------------------------


def _report(faith_ok: bool, relevance: float) -> DatasetReport:
    return DatasetReport(
        name="d",
        faithfulness=FaithfulnessResult(
            total=1, grounded=1 if faith_ok else 0, violations=() if faith_ok else ("bad",)
        ),
        relevance=RelevanceResult(score=relevance, justification="", precision=1.0, recall=1.0),
        min_relevance=0.6,
        vital_few_labels=("a",),
    )


def test_gate_requires_both_faithfulness_and_relevance() -> None:
    assert _report(faith_ok=True, relevance=0.6).passed
    assert not _report(faith_ok=False, relevance=0.9).passed  # faithfulness is non-negotiable
    assert not _report(faith_ok=True, relevance=0.59).passed  # below threshold
    assert overall_passed([_report(True, 0.7), _report(True, 0.6)])
    assert not overall_passed([_report(True, 0.7), _report(False, 0.9)])
