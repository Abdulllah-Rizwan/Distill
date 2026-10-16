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
from distil.adapters.parsing.pdf import PdfParser
from distil.adapters.parsing.text import TextParser
from distil.adapters.persistence.sqlite.repositories import (
    SqliteGraphRepository,
    SqliteMaterialRepository,
    SqliteWorkspaceRepository,
)
from distil.adapters.persistence.sqlite.schema import connect, initialize
from distil.config import Settings, get_settings
from distil.ports.llm import ConceptExtractor, Ranker
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
    ranker: Ranker,
) -> Services:
    """Assemble the services over an open SQLite connection and the given LLM adapters."""
    materials = SqliteMaterialRepository(conn)
    graph = SqliteGraphRepository(conn)
    workspaces = SqliteWorkspaceRepository(conn)
    parsers = (TextParser(), PdfParser())
    ingestion = IngestionService(materials, parsers)
    builder = GraphBuilder(extractor, NetworkxGraphAnalyzer())
    ranking = RankingService(ranker)
    pipeline = Pipeline(workspaces, materials, graph, ingestion, builder, ranking)
    return Services(materials=materials, graph=graph, pipeline=pipeline)


def build_llm_provider(settings: Settings) -> tuple[ConceptExtractor, Ranker]:
    """Construct the real LLM adapters (Gemini).

    Not implemented yet: the Gemini extractor and ranker (tasks T025/T028) are the next chunk, built
    after their prompts are reviewed (Principle IV — understand before adopt). Until then the
    production app cannot serve the LLM-backed routes; the test suite injects deterministic fakes
    through ``app.dependency_overrides`` and never reaches this path.
    """
    raise NotImplementedError(
        "The Gemini LLM adapter is not implemented yet. Build the extractor/ranker in "
        "distil.adapters.llm.gemini (tasks T025/T028) before serving the API against a real model."
    )


@lru_cache(maxsize=1)
def get_services() -> Services:
    """Production provider: one SQLite-backed :class:`Services` wired to the real LLM adapters."""
    settings = get_settings()
    conn = connect(settings.distil_db_path)
    initialize(conn)
    extractor, ranker = build_llm_provider(settings)
    return build_services(conn, extractor, ranker)
