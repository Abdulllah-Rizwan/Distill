"""Entry point: ``python -m evals.harness`` — score every dataset and gate on the result.

Default is a replay run (deterministic, free, offline) using recorded fixtures. ``--live`` re-hits
the real Gemini model and re-records the fixtures — the deliberate step after a prompt/model change
(Principle VII). The process exits non-zero when any gate fails, so CI and the release gate (T051)
can depend on it.
"""

from __future__ import annotations

import argparse
import sys

from distil.config import get_settings
from evals.harness.dataset import discover_datasets
from evals.harness.report import format_report, overall_passed
from evals.harness.runner import run_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.harness")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call the real Gemini model and re-record fixtures (needs GEMINI_API_KEY).",
    )
    parser.add_argument(
        "--dataset",
        help="Run only the dataset with this name (default: all discovered datasets).",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    if args.live and not settings.gemini_api_key:
        print("--live needs GEMINI_API_KEY (set it in .env or the environment).", file=sys.stderr)
        return 2

    paths = discover_datasets()
    if args.dataset:
        paths = [p for p in paths if p.name == args.dataset]
    if not paths:
        print("No datasets found under evals/datasets/.", file=sys.stderr)
        return 2

    reports = [run_dataset(p, live=args.live, settings=settings) for p in paths]
    print(format_report(reports))
    return 0 if overall_passed(reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
