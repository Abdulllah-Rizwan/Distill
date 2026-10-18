"""DeepSeek LLM provider: the provider-neutral adapters over a DeepSeek-backed :class:`JsonLLM`.

One shared :class:`DeepSeekClient` backs both adapters so the API key, base URL, and model id are
configured once. :func:`build_deepseek_provider` is the entry point the composition root calls when
``LLM_PROVIDER=deepseek``; it fails loudly if the API key is missing rather than deferring to an
opaque 401 on the first real request.
"""

from __future__ import annotations

from distil.adapters.llm.deepseek._client import DeepSeekClient
from distil.adapters.llm.explainer import JsonExplainer
from distil.adapters.llm.extractor import JsonConceptExtractor
from distil.config import Settings
from distil.ports.llm import ConceptExtractor, Explainer

__all__ = [
    "DeepSeekClient",
    "build_deepseek_provider",
]


def build_deepseek_provider(settings: Settings) -> tuple[ConceptExtractor, Explainer]:
    """Construct the extractor and explainer over one shared DeepSeek client.

    Raises :class:`ValueError` when ``DEEPSEEK_API_KEY`` is unset, so a misconfigured deployment is
    caught at wiring time with a clear message (Principle V — secrets come from the environment and
    are never defaulted or committed).
    """
    if not settings.deepseek_api_key:
        raise ValueError(
            "DEEPSEEK_API_KEY is not set. Provide it via the environment or a local .env file "
            "before serving the API against the real model."
        )
    client = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
    )
    return JsonConceptExtractor(client), JsonExplainer(client)
