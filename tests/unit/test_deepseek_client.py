"""Unit tests for the DeepSeek :class:`JsonLLM` client, fully offline via ``httpx.MockTransport``.

No network and no API key: a mock transport inspects the request we build and returns canned
responses, so these pin the request shape (JSON mode, schema in the prompt, auth header), the
response parsing, and the retry policy (retry 429, never retry 402 out-of-credit).
"""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel

from distil.adapters.llm.base import LlmUnavailableError
from distil.adapters.llm.deepseek import build_deepseek_provider
from distil.adapters.llm.deepseek._client import DeepSeekClient, is_retryable
from distil.adapters.llm.explainer import JsonExplainer
from distil.adapters.llm.extractor import JsonConceptExtractor
from distil.config import Settings


class _Schema(BaseModel):
    answer: str


def _client(handler: httpx.MockTransport) -> DeepSeekClient:
    return DeepSeekClient(
        api_key="test-key",
        model="deepseek-chat",
        transport=handler,
        base_delay=0.0,
        sleep=lambda _seconds: None,
    )


def _ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": '{"answer": "hi"}'}}]})


def test_generate_json_builds_openai_shaped_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return _ok_response(request)

    out = _client(httpx.MockTransport(handler)).generate_json(
        system_instruction="Extract concepts.",
        user_content="PASSAGE: cells make energy",
        response_schema=_Schema,
    )

    assert out == '{"answer": "hi"}'
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-chat"
    assert body["temperature"] == 0.0
    assert body["response_format"] == {"type": "json_object"}
    messages = body["messages"]
    assert isinstance(messages, list)
    system_msg = messages[0]["content"]
    # JSON mode requires "json" in the prompt, and we hand the model the expected schema.
    assert "json" in system_msg.lower()
    assert "Extract concepts." in system_msg
    assert "answer" in system_msg  # the schema's property leaked into the prompt
    assert messages[1] == {"role": "user", "content": "PASSAGE: cells make energy"}


def test_generate_json_retries_on_429_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return _ok_response(request)

    out = _client(httpx.MockTransport(handler)).generate_json(
        system_instruction="s", user_content="u", response_schema=_Schema
    )
    assert out == '{"answer": "hi"}'
    assert attempts["n"] == 3


def test_generate_json_does_not_retry_on_402_out_of_credit() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(402, json={"error": {"message": "Insufficient Balance"}})

    with pytest.raises(LlmUnavailableError, match="out of credit"):
        _client(httpx.MockTransport(handler)).generate_json(
            system_instruction="s", user_content="u", response_schema=_Schema
        )
    assert attempts["n"] == 1  # 402 not retried; surfaced as a clean LlmUnavailableError


def test_generate_json_returns_empty_on_missing_choices() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    out = _client(httpx.MockTransport(handler)).generate_json(
        system_instruction="s", user_content="u", response_schema=_Schema
    )
    assert out == ""  # the extractor/explainer treat this as malformed and drop it


def test_is_retryable_classifies_status_and_transport_errors() -> None:
    request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
    retryable = httpx.Response(503, request=request)
    not_retryable = httpx.Response(402, request=request)
    assert is_retryable(httpx.HTTPStatusError("x", request=request, response=retryable))
    assert not is_retryable(httpx.HTTPStatusError("x", request=request, response=not_retryable))
    assert is_retryable(httpx.ConnectError("boom"))
    assert not is_retryable(ValueError("unrelated"))


def test_build_deepseek_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        build_deepseek_provider(Settings(llm_provider="deepseek", deepseek_api_key=""))


def test_build_deepseek_provider_returns_both_adapters() -> None:
    extractor, explainer = build_deepseek_provider(
        Settings(llm_provider="deepseek", deepseek_api_key="test-key")
    )
    assert isinstance(extractor, JsonConceptExtractor)
    assert isinstance(explainer, JsonExplainer)
