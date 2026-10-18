"""DeepSeek-specific :class:`JsonLLM` over DeepSeek's OpenAI-compatible chat API.

DeepSeek exposes an OpenAI-style ``/chat/completions`` endpoint, so this is a thin ``httpx`` POST —
no extra SDK dependency, and the exact request we send stays visible and reviewable here
(Principle IV). Two deliberate differences from the Gemini client:

* **JSON mode, not server-side schema.** DeepSeek supports a JSON-object ``response_format`` but not
  strict JSON-schema enforcement, so we hand the model the expected schema in the system
  prompt and still validate the response against the Pydantic model on our side (the extractor and
  explainer already do this and drop anything malformed — Principle I, defence in depth).
* **temperature 0** for the steadiest output the model allows; ordering is deterministic code
  elsewhere, so any residual variance only touches wording.

Retries reuse the shared backoff policy: HTTP 429 and transient 5xx (and transport errors) are
retried; 4xx propagate immediately — including 402, which DeepSeek returns when the account is out
of credit, so that surfaces as a clear failure rather than a silent retry loop.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

import httpx
from pydantic import BaseModel

from distil.adapters.llm.base import LlmUnavailableError, with_retries

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_DEFAULT_BASE_URL = "https://api.deepseek.com"


def is_retryable(exc: BaseException) -> bool:
    """Retry transient transport errors and HTTP 429/5xx; never 4xx (incl. 402 out-of-credit)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return isinstance(exc, httpx.TransportError)


def _unavailable_message(exc: httpx.HTTPError) -> str:
    """A plain, user-facing reason for a DeepSeek failure (no SDK/HTTP internals)."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return "The language model is over its rate limit right now. Try again later."
        if code == 402:
            return "The language model account is out of credit. Top up the DeepSeek balance."
        if code in {401, 403}:
            return "The language model rejected the request credentials. Check the configured key."
        return f"The language model is temporarily unavailable (DeepSeek HTTP {code}). Try again."
    return "The language model could not be reached (connection or timeout). Try again."


def _extract_content(data: object) -> str:
    """Pull ``choices[0].message.content`` out of a chat-completions response, defensively.

    The body is untrusted JSON, so every hop is type-checked; anything unexpected yields an empty
    string, which the adapters treat as a malformed response and drop (never a crash on a bad body).
    """
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


class DeepSeekClient:
    """Concrete :class:`JsonLLM` backed by DeepSeek's OpenAI-compatible chat completions."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = _DEFAULT_BASE_URL,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        max_retries: int = 4,
        base_delay: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def generate_json(
        self, *, system_instruction: str, user_content: str, response_schema: type[BaseModel]
    ) -> str:
        # DeepSeek's JSON mode guarantees valid JSON but not a particular shape, so the schema is
        # handed to the model in the prompt (and re-validated on our side). The word "json" must
        # appear in the prompt for JSON mode to engage, which the schema instruction satisfies.
        schema = json.dumps(response_schema.model_json_schema(), ensure_ascii=False)
        system = (
            f"{system_instruction}\n\n"
            "Return a single JSON object (no prose, no markdown code fences) that conforms to "
            f"this JSON schema:\n{schema}"
        )
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }

        def _call() -> str:
            response = self._client.post("/chat/completions", json=body)
            response.raise_for_status()
            return _extract_content(response.json())

        try:
            return with_retries(
                _call,
                is_retryable=is_retryable,
                max_retries=self._max_retries,
                base_delay=self._base_delay,
                sleep=self._sleep,
            )
        except httpx.HTTPError as exc:
            # Retries are exhausted or the error is non-recoverable: surface a clean message.
            raise LlmUnavailableError(_unavailable_message(exc)) from exc
