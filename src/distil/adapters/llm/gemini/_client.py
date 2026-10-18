"""Gemini-specific :class:`JsonLLM`: one JSON-in/JSON-out call via the google-genai SDK.

The provider-neutral pieces (the :class:`JsonLLM` protocol and the retry/backoff policy) live in
:mod:`distil.adapters.llm.base`; this module holds only what is Gemini-specific — the SDK call,
structured-output plumbing, sampling settings, and which of the SDK's errors are worth retrying.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from distil.adapters.llm.base import LlmUnavailableError, with_retries

# HTTP status codes worth retrying: 429 (rate limited — expected on the free tier) and the transient
# 5xx family (model briefly overloaded or unavailable). A 400/401/403 is our bug or a bad key and is
# never retried.
_RETRYABLE_CODES = frozenset({429, 500, 502, 503, 504})


def is_retryable(exc: BaseException) -> bool:
    """Classify a google-genai error as a transient one worth retrying."""
    return isinstance(exc, errors.APIError) and exc.code in _RETRYABLE_CODES


def _unavailable_message(exc: errors.APIError) -> str:
    """A plain, user-facing reason for a Gemini failure (no SDK internals)."""
    if exc.code == 429:
        return "The language model is over its rate limit or quota right now. Try again later."
    if exc.code in {401, 403}:
        return "The language model rejected the request credentials. Check the configured API key."
    return f"The language model is temporarily unavailable (Gemini error {exc.code}). Try again."


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
        thinking_budget: int = 0,
        max_retries: int = 4,
        base_delay: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        # Gemini 3 "flash" is a thinking model: without this, reasoning tokens are drawn from the
        # same budget as the answer, so a structured-output call can spend the budget thinking and
        # return the JSON truncated (FinishReason.MAX_TOKENS → an unparseable response we drop).
        # Both of our asks — copy verbatim quotes, write one grounded sentence from given facts —
        # are mechanical, so thinking is disabled by default: it removes the truncation, is cheaper,
        # and conserves the free-tier tokens-per-minute budget. Raise it only if evals show a need.
        self._thinking_budget = thinking_budget
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
                    thinking_config=types.ThinkingConfig(thinking_budget=self._thinking_budget),
                ),
            )
            return response.text or ""

        try:
            return with_retries(
                _call,
                is_retryable=is_retryable,
                max_retries=self._max_retries,
                base_delay=self._base_delay,
                sleep=self._sleep,
            )
        except errors.APIError as exc:
            # Retries are exhausted or the error is non-recoverable: surface a clean message.
            raise LlmUnavailableError(_unavailable_message(exc)) from exc
