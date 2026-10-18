"""Shared LLM-adapter plumbing, independent of any specific provider.

The extractor and explainer adapters depend only on the narrow :class:`JsonLLM` protocol — one
JSON-in / JSON-out call — so the same adapter code runs against any backend that satisfies it
(Gemini, DeepSeek, or a deterministic test fake). The retry/backoff *policy* also lives here, kept
provider-agnostic: each concrete client supplies a predicate that classifies its own SDK's errors as
retryable or not, so the exponential-backoff loop is unit-tested once and reused everywhere.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel


class LlmUnavailableError(Exception):
    """The LLM provider could not be reached, or returned an error retries could not recover.

    Carries a plain, user-facing message (no stack traces or provider internals). The API maps it to
    a 503 so an upload fails cleanly with a clear reason — rate limit, out of credit, timeout, or a
    provider outage — instead of surfacing a raw SDK/HTTP exception as an opaque 500.
    """


class JsonLLM(Protocol):
    """The one capability the adapters need: send a prompt, get a JSON string back."""

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        """Return the model's response as a JSON string shaped by ``response_schema``."""
        ...


def with_retries[T](
    call: Callable[[], T],
    *,
    is_retryable: Callable[[BaseException], bool],
    max_retries: int,
    base_delay: float,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run ``call``, retrying on errors ``is_retryable`` classifies as transient.

    The backoff policy is separated from any SDK call so it can be unit-tested with a fake ``call``
    and a no-op ``sleep`` — no network, no real waiting. ``is_retryable`` decouples the policy from
    the provider: each client passes a predicate over its own exception type (e.g. retry on HTTP
    429/5xx, never on a 4xx auth/validation/out-of-credit error). A retryable error past
    ``max_retries`` is re-raised so the caller still sees a real failure.
    """
    attempt = 0
    while True:
        try:
            return call()
        except Exception as exc:
            if not is_retryable(exc) or attempt >= max_retries:
                raise
            sleep(base_delay * (2**attempt))
            attempt += 1
