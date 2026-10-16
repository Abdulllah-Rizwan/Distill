"""Integration tests: SQLite repositories enforce workspace isolation (Principle V) and
round-trip domain objects faithfully. Uses a real in-memory SQLite DB (no mocks)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from distil.adapters.persistence.sqlite.repositories import (
    SqliteGraphRepository,
    SqliteMaterialRepository,
)
from distil.adapters.persistence.sqlite.schema import connect, initialize
from distil.domain.concept import Concept
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.ranking import RankingRun, VitalFewEntry
from distil.domain.source_reference import SourceReference

_NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = connect(":memory:")
    initialize(connection)
    for ws in ("w_a", "w_b"):
        connection.execute(
            "INSERT INTO workspace (id, name, created_at) VALUES (?, ?, ?)",
            (ws, ws, _NOW.isoformat()),
        )
    connection.commit()
    yield connection
    connection.close()


def _material(ws: str, mid: str, *, content: str = "hello world", chash: str = "h1") -> Material:
    return Material(
        id=mid,
        workspace_id=ws,
        filename=f"{mid}.md",
        format=MaterialFormat.MARKDOWN,
        content_text=content,
        content_hash=chash,
        status=MaterialStatus.ACCEPTED,
        created_at=_NOW,
    )


def _concept(ws: str, cid: str, label: str, material_id: str) -> Concept:
    return Concept(
        id=cid,
        workspace_id=ws,
        label=label,
        sources=(
            SourceReference(material_id=material_id, start_offset=0, end_offset=5, quote="hello"),
        ),
        recurrence_count=1,
    )


def test_material_repo_isolates_and_roundtrips(conn: sqlite3.Connection) -> None:
    repo = SqliteMaterialRepository(conn)
    repo.add(_material("w_a", "m_a", chash="ha"))
    repo.add(_material("w_b", "m_b", chash="hb"))

    assert [m.id for m in repo.list_all("w_a")] == ["m_a"]
    assert [m.id for m in repo.list_all("w_b")] == ["m_b"]
    # No cross-workspace reads.
    assert repo.get("w_b", "m_a") is None
    got = repo.get("w_a", "m_a")
    assert got is not None and got.content_text == "hello world"  # round-trip intact


def test_material_dedup_and_delete_are_workspace_scoped(conn: sqlite3.Connection) -> None:
    repo = SqliteMaterialRepository(conn)
    repo.add(_material("w_a", "m_a", chash="dup"))
    repo.add(_material("w_b", "m_b", chash="dup"))  # same hash, different workspace: allowed

    assert repo.find_by_hash("w_a", "dup") is not None
    assert repo.find_by_hash("w_a", "dup").id == "m_a"  # type: ignore[union-attr]
    # Deleting in one workspace leaves the other untouched.
    assert repo.delete("w_a", "m_a") is True
    assert repo.find_by_hash("w_a", "dup") is None
    assert repo.find_by_hash("w_b", "dup") is not None


def test_graph_repo_isolates_concepts(conn: sqlite3.Connection) -> None:
    mats = SqliteMaterialRepository(conn)
    mats.add(_material("w_a", "m_a", chash="ha"))
    mats.add(_material("w_b", "m_b", chash="hb"))
    graph = SqliteGraphRepository(conn)
    graph.replace_graph("w_a", [_concept("w_a", "c_a", "Alpha", "m_a")], [])
    graph.replace_graph("w_b", [_concept("w_b", "c_b", "Beta", "m_b")], [])

    assert [c.label for c in graph.list_concepts("w_a")] == ["Alpha"]
    assert graph.get_concept("w_b", "c_a") is None
    # Source references survive the round-trip.
    restored = graph.get_concept("w_a", "c_a")
    assert restored is not None and restored.sources[0].quote == "hello"


def test_latest_ranking_is_scoped_and_ordered(conn: sqlite3.Connection) -> None:
    graph = SqliteGraphRepository(conn)
    run = RankingRun(
        id="r_a", workspace_id="w_a", created_at=_NOW, material_count=1, vital_few_size=2
    )
    entries = [
        VitalFewEntry(
            id="e1",
            workspace_id="w_a",
            ranking_run_id="r_a",
            concept_id="c1",
            rank=2,
            signals={"pagerank": 0.1},
            rationale="second",
            evidence=(
                SourceReference(material_id="m_a", start_offset=0, end_offset=5, quote="hello"),
            ),
        ),
        VitalFewEntry(
            id="e2",
            workspace_id="w_a",
            ranking_run_id="r_a",
            concept_id="c2",
            rank=1,
            signals={"pagerank": 0.3},
            rationale="first",
            evidence=(
                SourceReference(material_id="m_a", start_offset=0, end_offset=5, quote="hello"),
            ),
        ),
    ]
    graph.save_ranking(run, entries)

    assert graph.latest_ranking("w_b") is None  # isolation
    result = graph.latest_ranking("w_a")
    assert result is not None
    _, got_entries = result
    assert [e.rank for e in got_entries] == [1, 2]  # ordered by rank
