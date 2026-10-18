"""Composition root: wire adapters behind ports into the application services.

The API layer depends only on :class:`Services`; which adapters fill the ports is decided here.
:func:`get_services` is the production provider FastAPI injects; tests build their own
:class:`Services` with the deterministic LLM fakes and install it via ``app.dependency_overrides``,
so no test ever touches the network or the real model.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from functools import lru_cache

from distil.adapters.graph.networkx.analyzer import NetworkxGraphAnalyzer
from distil.adapters.llm.deepseek import build_deepseek_provider
from distil.adapters.llm.gemini import build_gemini_provider
from distil.adapters.parsing.pdf import PdfParser
from distil.adapters.parsing.text import TextParser
from distil.adapters.persistence.sqlite.repositories import (
    SqliteGraphRepository,
    SqliteMaterialRepository,
    SqliteWorkspaceRepository,
)
from distil.adapters.persistence.sqlite.schema import connect, initialize
from distil.config import Settings, get_settings
from distil.ports.llm import ConceptExtractor, Explainer
from distil.ports.repositories import GraphRepository, MaterialRepository
from distil.services.graph_builder import GraphBuilder
from distil.services.ingestion import IngestionService
from distil.services.pipeline import Pipeline
from distil.services.ranking import RankingService


@dataclass(frozen=True, slots=True)
class Services:
    """The wired core the API talks to. Exposes only what the routers need."""

    materials: MaterialRepository
    graph: GraphRepository
    pipeline: Pipeline


def build_services(
    conn: sqlite3.Connection,
    extractor: ConceptExtractor,
    explainer: Explainer,
) -> Services:
    """Assemble the services over an open SQLite connection and the given LLM adapters."""
    materials = SqliteMaterialRepository(conn)
    graph = SqliteGraphRepository(conn)
    workspaces = SqliteWorkspaceRepository(conn)
    parsers = (TextParser(), PdfParser())
    ingestion = IngestionService(materials, parsers)
    builder = GraphBuilder(extractor, NetworkxGraphAnalyzer())
    ranking = RankingService(explainer)
    pipeline = Pipeline(workspaces, materials, graph, ingestion, builder, ranking)
    return Services(materials=materials, graph=graph, pipeline=pipeline)


def build_llm_provider(settings: Settings) -> tuple[ConceptExtractor, Explainer]:
    """Construct the real LLM adapters behind the LLM ports, per ``settings.llm_provider``.

    Both providers share the same extractor/explainer code; only the underlying :class:`JsonLLM`
    client differs. The chosen provider validates its own API key and shares one client between the
    extractor and explainer. Tests never reach this path — they inject deterministic fakes through
    ``app.dependency_overrides`` — so no test touches the network or the real model (Principle VII).
    """
    if settings.llm_provider == "deepseek":
        return build_deepseek_provider(settings)
    return build_gemini_provider(settings)


@lru_cache(maxsize=1)
def get_services() -> Services:
    """Production provider: one SQLite-backed :class:`Services` wired to the real LLM adapters."""
    settings = get_settings()
    conn = connect(settings.distil_db_path)
    initialize(conn)
    extractor, ranker = build_llm_provider(settings)
    return build_services(conn, extractor, ranker)
