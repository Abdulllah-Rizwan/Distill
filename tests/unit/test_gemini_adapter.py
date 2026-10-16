"""Unit tests for the Gemini adapter (T025/T028), fully offline.

A scripted fake stands in for :class:`~distil.adapters.llm.gemini._client.JsonLLM`, so these tests
exercise the real quote-locating, offset math, chunking, schema parsing, retry/backoff policy, and
wiring guard without a network call or an API key. The guarantee under test is Principle I: every
reference the adapter emits is faithful to the source, and anything the model alters is dropped.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from google.genai import errors
from pydantic import BaseModel

from distil.adapters.llm.gemini import build_gemini_provider
from distil.adapters.llm.gemini._client import with_retries
from distil.adapters.llm.gemini.explainer import GeminiExplainer
from distil.adapters.llm.gemini.extractor import GeminiConceptExtractor, iter_chunks
from distil.adapters.llm.gemini.prompts import (
    ExplanationPayload,
    ExtractedConcept,
    ExtractedRelationship,
    ExtractionPayload,
    RationaleItem,
)
from distil.config import Settings
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.ports.llm import ExplanationRequest


class _ScriptedLLM:
    """A :class:`JsonLLM` whose JSON reply comes from a responder callable; records its calls."""

    def __init__(self, responder: Callable[[str, str], str]) -> None:
        self._responder = responder
        self.calls: list[tuple[str, str]] = []

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        self.calls.append((system_instruction, user_content))
        return self._responder(system_instruction, user_content)


def _material(content: str) -> Material:
    return Material(
        id="m1",
        workspace_id="w1",
        filename="n.txt",
        format=MaterialFormat.TEXT,
        content_text=content,
        content_hash="h",
        status=MaterialStatus.ACCEPTED,
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
    )


# --- Extraction --------------------------------------------------------------------------------


def test_extractor_grounds_quotes_and_drops_unfound() -> None:
    content = "Photosynthesis converts light into energy. Chlorophyll absorbs light."

    def responder(_system: str, _content: str) -> str:
        return ExtractionPayload(
            concepts=[
                ExtractedConcept(label="Photosynthesis", quote="Photosynthesis"),
                ExtractedConcept(label="Chlorophyll", quote="Chlorophyll"),
                ExtractedConcept(label="Ghost", quote="Mitochondria"),  # not in the text → dropped
            ],
            relationships=[
                ExtractedRelationship(
                    source_label="Chlorophyll",
                    target_label="Photosynthesis",
                    kind="used in",
                    quote="Chlorophyll absorbs light",
                ),
            ],
        ).model_dump_json()

    result = GeminiConceptExtractor(_ScriptedLLM(responder)).extract(_material(content))

    assert {c.label for c in result.concepts} == {"Photosynthesis", "Chlorophyll"}
    for mention in result.concepts:
        assert mention.source.is_faithful_to(content)
    assert len(result.relationships) == 1
    rel = result.relationships[0]
    assert (rel.source_label, rel.target_label, rel.kind) == (
        "Chlorophyll",
        "Photosynthesis",
        "used in",
    )
    assert rel.source.is_faithful_to(content)


def test_extractor_computes_absolute_offsets_across_chunks() -> None:
    # Small windows force several chunks; the quote recurs, so offsets must be base + chunk-local.
    content = "The term Osmosis means water movement. " * 5

    def responder(_system: str, user_content: str) -> str:
        concepts = (
            [ExtractedConcept(label="Osmosis", quote="Osmosis")]
            if "Osmosis" in user_content
            else []
        )
        return ExtractionPayload(concepts=concepts).model_dump_json()

    extractor = GeminiConceptExtractor(_ScriptedLLM(responder), max_chars=50, overlap_chars=10)
    result = extractor.extract(_material(content))

    assert {c.label for c in result.concepts} == {"Osmosis"}
    occurrences = {i for i in range(len(content)) if content.startswith("Osmosis", i)}
    for mention in result.concepts:
        assert mention.source.is_faithful_to(content)  # offsets are absolute + correct
        assert mention.source.start_offset in occurrences


def test_extractor_skips_malformed_response() -> None:
    extractor = GeminiConceptExtractor(_ScriptedLLM(lambda _s, _c: "this is not json"))
    result = extractor.extract(_material("Some notes about gravity."))
    assert result.concepts == ()
    assert result.relationships == ()


def test_iter_chunks_preserve_offsets_and_cover_text() -> None:
    text = "word " * 100  # 500 chars
    chunks = list(iter_chunks(text, max_chars=80, overlap_chars=20))
    assert len(chunks) > 1
    for start, chunk in chunks:
        assert text[start : start + len(chunk)] == chunk  # offset is exact
    assert chunks[0][0] == 0
    assert chunks[-1][0] + len(chunks[-1][1]) == len(text)  # last window reaches the end


def test_iter_chunks_single_window_when_short() -> None:
    assert list(iter_chunks("short", max_chars=100, overlap_chars=10)) == [(0, "short")]


# --- Explanation -------------------------------------------------------------------------------


def _request(concept_id: str, label: str, rank: int) -> ExplanationRequest:
    return ExplanationRequest(
        concept_id=concept_id,
        label=label,
        rank=rank,
        signals={"pagerank": 0.3, "degree": 2.0, "recurrence": 3.0, "score": 0.5},
        neighbor_labels=("beta", "gamma"),
        evidence_quotes=("alpha is central",),
    )


def test_explainer_maps_ids_to_sentences_and_drops_empty() -> None:
    def responder(_system: str, _content: str) -> str:
        return ExplanationPayload(
            items=[
                RationaleItem(concept_id="c1", sentence="  Alpha ties beta and gamma together.  "),
                RationaleItem(concept_id="c2", sentence="   "),  # blank → dropped
            ]
        ).model_dump_json()

    client = _ScriptedLLM(responder)
    out = GeminiExplainer(client).explain([_request("c1", "alpha", 1), _request("c2", "beta", 2)])

    assert out == {"c1": "Alpha ties beta and gamma together."}
    assert len(client.calls) == 1  # single batched call


def test_explainer_no_requests_makes_no_call() -> None:
    client = _ScriptedLLM(lambda _s, _c: pytest.fail("should not call the model"))
    assert GeminiExplainer(client).explain([]) == {}
    assert client.calls == []


def test_explainer_malformed_returns_empty() -> None:
    explainer = GeminiExplainer(_ScriptedLLM(lambda _s, _c: "{not valid"))
    assert explainer.explain([_request("c1", "alpha", 1)]) == {}


# --- Retry / backoff policy --------------------------------------------------------------------


def test_with_retries_backs_off_then_succeeds() -> None:
    sleeps: list[float] = []
    attempts = {"n": 0}

    def call() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise errors.ClientError(429, {"error": {"message": "rate limited", "code": 429}})
        return "ok"

    result = with_retries(call, max_retries=4, base_delay=2.0, sleep=sleeps.append)
    assert result == "ok"
    assert attempts["n"] == 3
    assert sleeps == [2.0, 4.0]  # exponential: base * 2**0, base * 2**1


def test_with_retries_reraises_non_retryable_immediately() -> None:
    sleeps: list[float] = []

    def call() -> str:
        raise errors.ClientError(400, {"error": {"message": "bad request", "code": 400}})

    with pytest.raises(errors.ClientError):
        with_retries(call, max_retries=4, base_delay=1.0, sleep=sleeps.append)
    assert sleeps == []


def test_with_retries_gives_up_after_max() -> None:
    sleeps: list[float] = []

    def call() -> str:
        raise errors.ServerError(503, {"error": {"message": "overloaded", "code": 503}})

    with pytest.raises(errors.ServerError):
        with_retries(call, max_retries=2, base_delay=1.0, sleep=sleeps.append)
    assert len(sleeps) == 2  # two retries, then the third failure propagates


# --- Wiring guard ------------------------------------------------------------------------------


def test_build_gemini_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_gemini_provider(Settings(gemini_api_key=""))


def test_build_gemini_provider_returns_both_adapters() -> None:
    extractor, explainer = build_gemini_provider(Settings(gemini_api_key="test-key"))
    assert isinstance(extractor, GeminiConceptExtractor)
    assert isinstance(explainer, GeminiExplainer)
