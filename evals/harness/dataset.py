"""Eval dataset loading — synthetic notes plus ground truth, a versioned project asset.

A dataset is a directory ``evals/datasets/<name>/`` containing:

* ``dataset.json`` — metadata and ground truth (``important_concepts``, ``min_relevance``);
* ``notes/*.md`` or ``*.txt`` — the synthetic study notes fed through the pipeline.

The content is synthetic and non-sensitive on purpose: it is committed and reproducible, carries a
known right answer to score against, and is safe to send to the Gemini free tier (Principle V).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
_NOTE_SUFFIXES = {".md", ".txt"}


@dataclass(frozen=True, slots=True)
class Note:
    """One synthetic note file: its name and its full text."""

    filename: str
    text: str


@dataclass(frozen=True, slots=True)
class Dataset:
    """A curated eval case: the notes to ingest and what a good result should look like."""

    name: str
    description: str
    notes: tuple[Note, ...]
    important_concepts: tuple[str, ...]
    min_relevance: float

    @property
    def important_keys(self) -> set[str]:
        """Normalized important-concept labels, for case-insensitive overlap scoring."""
        return {c.strip().casefold() for c in self.important_concepts}


def load_dataset(path: Path) -> Dataset:
    """Load the dataset rooted at ``path`` (its ``dataset.json`` plus ``notes/``)."""
    meta = json.loads((path / "dataset.json").read_text(encoding="utf-8"))
    notes_dir = path / "notes"
    notes = tuple(
        Note(filename=p.name, text=p.read_text(encoding="utf-8"))
        for p in sorted(notes_dir.iterdir())
        if p.suffix in _NOTE_SUFFIXES
    )
    if not notes:
        raise ValueError(f"Dataset {path.name!r} has no notes under notes/")
    return Dataset(
        name=str(meta.get("name", path.name)),
        description=str(meta.get("description", "")),
        notes=notes,
        important_concepts=tuple(meta.get("important_concepts", [])),
        min_relevance=float(meta.get("min_relevance", 0.6)),
    )


def discover_datasets(root: Path = DATASETS_DIR) -> list[Path]:
    """Return every dataset directory under ``root`` (those with a ``dataset.json``)."""
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if (p / "dataset.json").exists())
