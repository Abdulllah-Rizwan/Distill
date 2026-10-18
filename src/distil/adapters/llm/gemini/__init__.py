"""Gemini LLM provider: the provider-neutral adapters over a Gemini-backed :class:`JsonLLM`.

One shared :class:`GeminiClient` backs both adapters so the API key, model id, and rate-limit
backoff are configured once. :func:`build_gemini_provider` is the single entry point the composition
root calls; it fails loudly if the API key is missing rather than deferring to an opaque 401 on the
first real request.
"""

from __future__ import annotations

from distil.adapters.llm.explainer import JsonExplainer
from distil.adapters.llm.extractor import JsonConceptExtractor
from distil.adapters.llm.gemini._client import GeminiClient
from distil.config import Settings
from distil.ports.llm import ConceptExtractor, Explainer

__all__ = [
    "GeminiClient",
    "build_gemini_provider",
]


def build_gemini_provider(settings: Settings) -> tuple[ConceptExtractor, Explainer]:
    """Construct the extractor and explainer over one shared Gemini client.

    Raises :class:`ValueError` when ``GEMINI_API_KEY`` is unset, so a misconfigured deployment is
    caught at wiring time with a clear message (Principle V — secrets come from the environment and
    are never defaulted or committed).
    """
    if not settings.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Provide it via the environment or a local .env file "
            "before serving the API against the real model."
        )
    client = GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
    return JsonConceptExtractor(client), JsonExplainer(client)
