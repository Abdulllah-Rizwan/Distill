"""Application configuration.

Settings are loaded from environment variables (or a local ``.env`` file) and validated once.
Secrets (the Gemini API key) never have hard-coded defaults and are never committed — see the
project constitution, Principle V. Call :func:`get_settings` to obtain the cached instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["gemini", "deepseek"]


class Settings(BaseSettings):
    """Runtime configuration, sourced from the environment / ``.env``.

    Field names map to upper-case environment variables
    (e.g. ``gemini_api_key`` ← ``GEMINI_API_KEY``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Which LLM backend fills the extractor/explainer ports. Both satisfy the same JsonLLM port, so
    # this is the only switch; each provider's own credentials are read below. Default stays the
    # planned Gemini free tier (see plan.md); set LLM_PROVIDER=deepseek in .env to use DeepSeek
    # (decision-shift DS-0002 — e.g. while the Gemini free-tier daily quota is exhausted).
    llm_provider: LlmProvider = Field(
        default="gemini",
        description="LLM backend behind the extractor/explainer ports: 'gemini' or 'deepseek'.",
    )

    # LLM provider: Gemini (free tier for the MVP; swappable behind the LLM provider port).
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key. Required for real LLM calls; left empty keeps imports "
        "and non-LLM tests working. The Gemini adapter checks it is set before use.",
    )
    gemini_model: str = Field(
        default="gemini-3-flash-preview",
        description="Gemini model id. The planned 'gemini-3-flash' does not exist on the API; "
        "'gemini-3-flash-preview' is the Gemini 3 Flash id this key can call (see decisions.md).",
    )

    # LLM provider: DeepSeek (OpenAI-compatible API; used when llm_provider == 'deepseek').
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API key. Required only when LLM_PROVIDER=deepseek; the DeepSeek "
        "adapter checks it is set before use.",
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek model id. 'deepseek-chat' (DeepSeek-V3, non-reasoning) suits our "
        "mechanical extract/explain asks; 'deepseek-reasoner' is available but unnecessary.",
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="Base URL for the DeepSeek OpenAI-compatible API.",
    )

    # Local persistence (SQLite source of truth for v1).
    distil_db_path: Path = Field(
        default=Path("./data/distil.db"),
        description="Filesystem path to the local SQLite database.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached :class:`Settings`, reading the environment on first call."""
    return Settings()
