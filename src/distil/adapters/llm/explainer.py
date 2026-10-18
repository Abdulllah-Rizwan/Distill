"""LLM-backed rationale writing (fills :class:`Explainer`, task T028).

Provider-agnostic: it drives any backend behind the :class:`JsonLLM` port. The ranking service has
already chosen and ordered the vital-few concepts and computed their signals; this adapter only
writes the human-readable "why". It is handed the rank, the signals, the neighbour labels, and
verbatim source quotes, and returns one sentence per concept in a single batched call. It cannot
change rank or signals — those never round-trip through the model — so the explanation can never
silently contradict the ranking (Principle II). A concept the model omits is filled with a
deterministic fallback sentence by the service, so the view is always complete.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import ValidationError

from distil.adapters.llm.base import JsonLLM
from distil.adapters.llm.prompts import (
    EXPLANATION_SYSTEM_INSTRUCTION,
    ExplanationPayload,
)
from distil.ports.llm import ExplanationRequest


def _request_payload(request: ExplanationRequest) -> dict[str, object]:
    """The facts the model is allowed to use for one concept, as plain JSON-ready data."""
    return {
        "id": request.concept_id,
        "label": request.label,
        "rank": request.rank,
        "signals": {name: round(value, 4) for name, value in request.signals.items()},
        "neighbors": list(request.neighbor_labels),
        "quotes": list(request.evidence_quotes),
    }


class JsonExplainer:
    """Writes the vital-few rationales using any model behind :class:`JsonLLM`."""

    def __init__(self, client: JsonLLM) -> None:
        self._client = client

    def explain(self, requests: Sequence[ExplanationRequest]) -> dict[str, str]:
        if not requests:
            return {}

        user_content = json.dumps([_request_payload(r) for r in requests], ensure_ascii=False)
        raw = self._client.generate_json(
            system_instruction=EXPLANATION_SYSTEM_INSTRUCTION,
            user_content=user_content,
            response_schema=ExplanationPayload,
        )
        try:
            payload = ExplanationPayload.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError):
            # Nothing usable came back; return empty so the service fills every concept with its
            # deterministic fallback rather than failing the request.
            return {}

        return {
            item.concept_id: item.sentence.strip()
            for item in payload.items
            if item.sentence.strip()
        }
