"""Thin wrapper around the google-genai SDK: one JSON-in/JSON-out call with retry and backoff.

Both adapters (extractor, explainer) talk to the model through :class:`GeminiClient`, so the model
id, sampling settings, structured-output plumbing, and the free-tier rate-limit backoff live in one
place. The adapters depend on the narrow :class:`JsonLLM` protocol, which lets tests inject a
deterministic fake and never touch the network (Principle VII — fast, free, offline tests).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

# HTTP status codes worth retrying: 429 (rate limited — expected on the free tier) and the transient
# 5xx family (model briefly overloaded or unavailable). A 400/401/403 is our bug or a bad key and is
# never retried.
_RETRYABLE_CODES = frozenset({429, 500, 502, 503, 504})


class JsonLLM(Protocol):
    """The one capability the adapters need: send a prompt, get a JSON string back."""

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        """Return the model's response as a JSON string constrained to ``response_schema``."""
        ...


def with_retries[T](
    call: Callable[[], T],
    *,
    max_retries: int,
    base_delay: float,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run ``call``, retrying on retryable API errors with exponential backoff.

    Separated from the SDK call so the backoff policy can be unit-tested with a fake ``call`` and a
    no-op ``sleep`` — no network, no real waiting. Non-retryable errors propagate immediately; a
    retryable error past ``max_retries`` is re-raised so the caller still sees a real failure.
    """
    attempt = 0
    while True:
        try:
            return call()
        except errors.APIError as exc:
            if exc.code not in _RETRYABLE_CODES or attempt >= max_retries:
                raise
            sleep(base_delay * (2**attempt))
            attempt += 1


class GeminiClient:
    """Concrete :class:`JsonLLM` backed by Gemini structured output.

    Sampling is pinned to ``temperature=0`` so the prose is as stable as the model allows; the
    ranking order itself is deterministic code elsewhere, so any residual variance only affects
    wording, never which concepts surface or in what order.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        max_retries: int = 4,
        base_delay: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._sleep = sleep

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        def _call() -> str:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=self._temperature,
                    max_output_tokens=self._max_output_tokens,
                ),
            )
            return response.text or ""

        return with_retries(
            _call, max_retries=self._max_retries, base_delay=self._base_delay, sleep=self._sleep
        )
