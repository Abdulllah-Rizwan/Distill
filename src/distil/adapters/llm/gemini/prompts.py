"""Prompts and structured-output schemas for the Gemini adapter — the contract with the model.

These live in source (not a config file or a notebook) on purpose: the exact words we send the model
are part of the system's behaviour and must be reviewable, diffable, and testable like any other
code (Principle VII — verified reliability). Two deliberately narrow asks, mirroring the LLM ports:

* **Extraction** (:data:`EXTRACTION_SYSTEM_INSTRUCTION`) — the model returns each concept/relation
  with a *verbatim quote* copied from the passage. It never invents character offsets; our adapter
  locates the quote in the text and computes the span, then the provenance gate re-verifies it. This
  is the whole source-faithfulness trick: the model is good at copying text and bad at counting
  characters, so we do the counting (Principle I).
* **Explanation** (:data:`EXPLANATION_SYSTEM_INSTRUCTION`) — given concepts the ranking service has
  *already* chosen and ordered, plus their signals, neighbours, and source quotes, the model writes
  one honest sentence each. It is handed the numbers; it cannot recompute or reorder them
  (Principle II — explainable, not black-box).

The Pydantic models below are passed to Gemini as ``response_schema`` so the model is constrained to
return exactly this shape (structured output), and we validate the response against them again on
our side before trusting a single field.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# --- Extraction --------------------------------------------------------------------------------

EXTRACTION_SYSTEM_INSTRUCTION = """\
You extract the key concepts and their relationships from a student's study notes. You work ONLY \
from the text provided in the passage — never from outside knowledge.

Rules:
1. A "concept" is a specific idea, term, or topic that the text is about.
2. For every concept, copy a "quote": a span of text, VERBATIM and character-for-character \
from the passage, that names or defines the concept.
   - Copy it exactly: same spelling, casing, punctuation, and whitespace.
   - Do NOT paraphrase, translate, summarise, or fix typos in the quote.
   - The quote must be text that actually appears in the passage.
   - If you cannot find an exact supporting quote, DO NOT include the concept.
3. Extract a "relationship" only when the passage states a connection between two concepts you \
have already extracted. Give:
   - source_label and target_label: the two concepts' labels (exactly as you wrote them),
   - kind: a short word or phrase for the relation taken from the text (e.g. "causes", "is a", \
"used in"), or null if the text implies a link without naming it,
   - quote: the VERBATIM span asserting the connection (same copy rules as above).
4. Do not invent concepts or links the passage does not support. Prefer fewer, well-grounded items \
over broad coverage."""


class ExtractedConcept(BaseModel):
    """One concept the model found, with the verbatim span that supports it."""

    label: str = Field(description="A short name for the concept.")
    quote: str = Field(description="Verbatim text copied exactly from the passage.")


class ExtractedRelationship(BaseModel):
    """A stated connection between two extracted concepts."""

    source_label: str = Field(description="Label of the concept the relationship starts from.")
    target_label: str = Field(description="Label of the concept the relationship points to.")
    quote: str = Field(description="Verbatim span asserting the connection.")
    kind: str | None = Field(
        default=None,
        description="Short relation word from the text (e.g. 'causes'), or null if unnamed.",
    )


class ExtractionPayload(BaseModel):
    """The whole structured result of one extraction call."""

    concepts: list[ExtractedConcept] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


def extraction_user_content(passage: str) -> str:
    """Wrap one chunk of the material as the user turn for an extraction call."""
    return f"PASSAGE:\n{passage}"


# --- Explanation -------------------------------------------------------------------------------

EXPLANATION_SYSTEM_INSTRUCTION = """\
You explain WHY each concept below is one of the most important in a student's notes. The ranking \
is already decided — you only write the explanation.

For each concept you are given its id, label, rank (its fixed position), signals (recurrence = how \
many of the student's materials it appears in, degree = how many other concepts it directly \
connects to, and a score), neighbors (the labels of concepts it directly connects to), and quotes \
(verbatim snippets from the student's own notes).

Write ONE plain, student-friendly sentence per concept explaining its importance.

Rules:
1. Use ONLY the facts provided — the signals, the neighbor labels, and the quotes. Do not add \
facts, definitions, or study advice from outside.
2. Ground the sentence in concrete numbers and names: how many materials it recurs across, and \
which concepts it connects to.
3. Do not restate the score or the word "PageRank"; explain in human terms ("ties together X and \
Y", "comes up again and again across your notes").
4. Do not change the order or mention other concepts' ranks.

Return one item per concept, each with the concept's id and your one-sentence explanation."""


class RationaleItem(BaseModel):
    """One concept's written rationale, keyed back to the concept id we supplied."""

    concept_id: str = Field(description="The id of the concept this sentence explains.")
    sentence: str = Field(description="One plain-language sentence on why the concept matters.")


class ExplanationPayload(BaseModel):
    """The whole structured result of the single batched explanation call."""

    items: list[RationaleItem] = Field(default_factory=list)
