"""Record/replay at the LLM port, so the evals are deterministic and free day-to-day.

The extractor, explainer, and judge all depend only on ``JsonLLM.generate_json``. We interpose
at that one seam:

* :class:`RecordingLLM` wraps the real client, returns its responses, and remembers each one keyed
  by a hash of the exact inputs (used under ``--live``).
* :class:`ReplayLLM` returns previously recorded responses and never touches the network (default).

This runs the *real* extraction/graph/ranking code against fixed model output, so a change in our
code moves the score while the model's words stay constant — and re-recording with ``--live`` is the
deliberate act that re-checks a prompt or model change (Principle VII).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from distil.adapters.llm.gemini._client import JsonLLM


def fixture_key(system_instruction: str, user_content: str, schema: type[BaseModel]) -> str:
    """A stable hash of everything that determines a model response, for fixture lookup."""
    digest = hashlib.sha256()
    for part in (schema.__name__, system_instruction, user_content):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


class ReplayLLM:
    """A :class:`JsonLLM` that returns recorded responses; errors if an input was never recorded."""

    def __init__(self, fixtures: dict[str, str]) -> None:
        self._fixtures = fixtures

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        key = fixture_key(system_instruction, user_content, response_schema)
        try:
            return self._fixtures[key]
        except KeyError:
            raise LookupError(
                "No recorded model response for this input. Re-run the harness with --live to "
                "record fixtures (after a prompt/model change, or for a new dataset)."
            ) from None


class RecordingLLM:
    """Wraps a real :class:`JsonLLM`, returning and recording each response keyed by its inputs."""

    def __init__(self, inner: JsonLLM) -> None:
        self._inner = inner
        self.recorded: dict[str, str] = {}

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        response = self._inner.generate_json(
            system_instruction=system_instruction,
            user_content=user_content,
            response_schema=response_schema,
        )
        key = fixture_key(system_instruction, user_content, response_schema)
        self.recorded[key] = response
        return response


def load_fixtures(path: Path) -> dict[str, str]:
    """Load recorded fixtures from ``path`` (empty if the file does not exist yet)."""
    if not path.exists():
        return {}
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def save_fixtures(path: Path, fixtures: dict[str, str]) -> None:
    """Write ``fixtures`` to ``path`` as sorted, human-diffable JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(fixtures, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
