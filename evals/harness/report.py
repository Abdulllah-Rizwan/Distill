"""Eval results: per-dataset report, threshold gating, and human-readable formatting.

The gate encodes the constitution: faithfulness must be 100% (Principle I, never waived) and
relevance must meet the dataset's ``min_relevance``. :func:`overall_passed` drives the harness exit
code, so the same check serves local runs and the release gate (T051).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from evals.harness.faithfulness import FaithfulnessResult
from evals.harness.relevance import RelevanceResult


@dataclass(frozen=True, slots=True)
class DatasetReport:
    """The combined faithfulness + relevance outcome for one dataset."""

    name: str
    faithfulness: FaithfulnessResult
    relevance: RelevanceResult
    min_relevance: float
    vital_few_labels: tuple[str, ...]

    @property
    def relevance_passed(self) -> bool:
        return self.relevance.score >= self.min_relevance

    @property
    def passed(self) -> bool:
        return self.faithfulness.passed and self.relevance_passed


def overall_passed(reports: Sequence[DatasetReport]) -> bool:
    """True only if every dataset passed both gates."""
    return all(r.passed for r in reports)


def format_report(reports: Sequence[DatasetReport]) -> str:
    """Render the reports as a compact, aligned text block."""
    lines: list[str] = []
    for r in reports:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"=== {r.name} — {status} ===")

        f = r.faithfulness
        f_mark = "ok" if f.passed else "FAIL"
        lines.append(
            f"  faithfulness: {f.score:6.1%} ({f.grounded}/{f.total} spans grounded) [{f_mark}]"
        )
        for violation in f.violations[:5]:
            lines.append(f"      - {violation}")
        if len(f.violations) > 5:
            lines.append(f"      ... and {len(f.violations) - 5} more")

        rel = r.relevance
        r_mark = "ok" if r.relevance_passed else f"FAIL (< {r.min_relevance:.2f})"
        lines.append(f"  relevance:    {rel.score:6.2f} [{r_mark}]")
        lines.append(f"      judge: {rel.justification}")
        lines.append(
            f"      vs important_concepts: precision {rel.precision:.2f}, recall {rel.recall:.2f}"
        )
        lines.append(f"      vital-few: {', '.join(r.vital_few_labels) or '(empty)'}")
        lines.append("")

    overall = "PASS" if overall_passed(reports) else "FAIL"
    lines.append(f"OVERALL: {overall} ({sum(r.passed for r in reports)}/{len(reports)} datasets)")
    return "\n".join(lines)
