"""Relevance scoring for the vital-few: an LLM judge plus a deterministic overlap check.

Relevance asks whether the 80/20 surfaced the concepts that actually matter in the notes. The judge
(the same model, recorded/replayed like any other call) rates the produced shortlist against the
notes; we also report precision/recall against the dataset's curated ``important_concepts`` as a
deterministic cross-check. When the two disagree, the judge score is what gates — but faithfulness
always outranks relevance (Principle VII / AI Quality standards).

The judge prompt lives here in source so a change to how we score is reviewable and diffable.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from distil.adapters.llm.gemini._client import JsonLLM
from evals.harness.dataset import Dataset

JUDGE_SYSTEM_INSTRUCTION = """\
You are grading a study tool. Given a student's notes and a ranked shortlist the tool calls the
"most important" concepts, rate how well that shortlist captures what genuinely matters.

Give a single score from 0.0 to 1.0:
- 1.0 = the shortlist is exactly the central, recurring ideas a student should focus on.
- around 0.5 = a mix of genuinely important concepts and filler.
- 0.0 = the shortlist is mostly incidental details, examples, proper nouns, or section headings
  rather than the core concepts.

Judge ONLY against the notes provided. Reward concepts that are central and recur across the notes;
penalize noise (one-off examples, company/product names, slide headings) and penalize missing the
clearly central ideas. Then write ONE sentence justifying the score."""


class JudgeVerdict(BaseModel):
    """The judge's structured output."""

    score: float = Field(description="0.0-1.0: how well the shortlist captures the key concepts.")
    justification: str = Field(description="One sentence explaining the score.")


@dataclass(frozen=True, slots=True)
class RelevanceResult:
    """The judge's score plus the deterministic overlap with curated important concepts."""

    score: float
    justification: str
    precision: float
    recall: float


def _judge_user_content(dataset: Dataset, vital_few_labels: tuple[str, ...]) -> str:
    notes = "\n\n---\n\n".join(f"[{n.filename}]\n{n.text.strip()}" for n in dataset.notes)
    if vital_few_labels:
        shortlist = "\n".join(f"{i}. {label}" for i, label in enumerate(vital_few_labels, start=1))
    else:
        shortlist = "(empty — the tool produced no vital-few)"
    return f"NOTES:\n{notes}\n\nRANKED VITAL-FEW SHORTLIST:\n{shortlist}"


def score_relevance(
    llm: JsonLLM, dataset: Dataset, vital_few_labels: tuple[str, ...]
) -> RelevanceResult:
    """Score the shortlist with the LLM judge and the deterministic important-concept overlap."""
    raw = llm.generate_json(
        system_instruction=JUDGE_SYSTEM_INSTRUCTION,
        user_content=_judge_user_content(dataset, vital_few_labels),
        response_schema=JudgeVerdict,
    )
    verdict = JudgeVerdict.model_validate_json(raw)
    score = max(0.0, min(1.0, verdict.score))

    produced = {label.strip().casefold() for label in vital_few_labels}
    important = dataset.important_keys
    hits = len(produced & important)
    precision = hits / len(produced) if produced else 0.0
    recall = hits / len(important) if important else 0.0

    return RelevanceResult(
        score=score,
        justification=verdict.justification.strip(),
        precision=precision,
        recall=recall,
    )
