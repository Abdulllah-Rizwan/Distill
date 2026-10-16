"""SQLite implementations of the persistence ports. All queries are scoped by ``workspace_id``."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

from distil.adapters.persistence.sqlite._serde import (
    page_map_from_json,
    page_map_to_json,
    sources_from_json,
    sources_to_json,
)
from distil.domain.concept import Concept
from distil.domain.material import Material, MaterialFormat, MaterialStatus
from distil.domain.ranking import RankingRun, VitalFewEntry
from distil.domain.relationship import Relationship
from distil.domain.workspace import Workspace


def _row_to_material(row: sqlite3.Row) -> Material:
    return Material(
        id=row["id"],
        workspace_id=row["workspace_id"],
        filename=row["filename"],
        format=MaterialFormat(row["format"]),
        content_text=row["content_text"],
        content_hash=row["content_hash"],
        status=MaterialStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        page_map=page_map_from_json(row["page_map"]),
        rejected_reason=row["rejected_reason"],
    )


def _row_to_concept(row: sqlite3.Row) -> Concept:
    centrality_raw = row["centrality"]
    return Concept(
        id=row["id"],
        workspace_id=row["workspace_id"],
        label=row["label"],
        sources=sources_from_json(row["sources"]),
        recurrence_count=row["recurrence_count"],
        aliases=tuple(json.loads(row["aliases"])),
        centrality=json.loads(centrality_raw) if centrality_raw is not None else None,
    )


def _row_to_relationship(row: sqlite3.Row) -> Relationship:
    return Relationship(
        id=row["id"],
        workspace_id=row["workspace_id"],
        source_concept_id=row["source_concept_id"],
        target_concept_id=row["target_concept_id"],
        sources=sources_from_json(row["sources"]),
        kind=row["kind"],
    )


class SqliteWorkspaceRepository:
    """:class:`~distil.ports.repositories.WorkspaceRepository` backed by SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def ensure(self, workspace_id: str) -> Workspace:
        existing = self.get(workspace_id)
        if existing is not None:
            return existing
        created_at = datetime.now(UTC)
        # INSERT OR IGNORE keeps this idempotent under the PK even if two calls race.
        self._conn.execute(
            "INSERT OR IGNORE INTO workspace (id, name, created_at) VALUES (?, ?, ?)",
            (workspace_id, workspace_id, created_at.isoformat()),
        )
        self._conn.commit()
        workspace = self.get(workspace_id)
        if workspace is None:  # pragma: no cover - the row was just inserted
            raise RuntimeError(f"Failed to create workspace {workspace_id!r}")
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        row = self._conn.execute("SELECT * FROM workspace WHERE id = ?", (workspace_id,)).fetchone()
        if row is None:
            return None
        return Workspace(
            id=row["id"],
            name=row["name"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SqliteMaterialRepository:
    """:class:`~distil.ports.repositories.MaterialRepository` backed by SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, material: Material) -> None:
        self._conn.execute(
            """INSERT INTO material
               (id, workspace_id, filename, format, content_text, content_hash,
                status, rejected_reason, page_map, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                material.id,
                material.workspace_id,
                material.filename,
                material.format.value,
                material.content_text,
                material.content_hash,
                material.status.value,
                material.rejected_reason,
                page_map_to_json(material.page_map),
                material.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, workspace_id: str, material_id: str) -> Material | None:
        row = self._conn.execute(
            "SELECT * FROM material WHERE workspace_id = ? AND id = ?",
            (workspace_id, material_id),
        ).fetchone()
        return _row_to_material(row) if row is not None else None

    def list_all(self, workspace_id: str) -> list[Material]:
        rows = self._conn.execute(
            "SELECT * FROM material WHERE workspace_id = ? ORDER BY created_at",
            (workspace_id,),
        ).fetchall()
        return [_row_to_material(r) for r in rows]

    def list_accepted(self, workspace_id: str) -> list[Material]:
        rows = self._conn.execute(
            "SELECT * FROM material WHERE workspace_id = ? AND status = ? ORDER BY created_at",
            (workspace_id, MaterialStatus.ACCEPTED.value),
        ).fetchall()
        return [_row_to_material(r) for r in rows]

    def find_by_hash(self, workspace_id: str, content_hash: str) -> Material | None:
        row = self._conn.execute(
            "SELECT * FROM material WHERE workspace_id = ? AND content_hash = ?",
            (workspace_id, content_hash),
        ).fetchone()
        return _row_to_material(row) if row is not None else None

    def delete(self, workspace_id: str, material_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM material WHERE workspace_id = ? AND id = ?",
            (workspace_id, material_id),
        )
        self._conn.commit()
        return cur.rowcount > 0


class SqliteGraphRepository:
    """:class:`~distil.ports.repositories.GraphRepository` backed by SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def replace_graph(
        self,
        workspace_id: str,
        concepts: Sequence[Concept],
        relationships: Sequence[Relationship],
    ) -> None:
        with self._conn:  # transaction: all-or-nothing
            self._conn.execute("DELETE FROM concept WHERE workspace_id = ?", (workspace_id,))
            self._conn.execute("DELETE FROM relationship WHERE workspace_id = ?", (workspace_id,))
            self._conn.executemany(
                """INSERT INTO concept
                   (id, workspace_id, label, aliases, sources, recurrence_count, centrality)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        c.id,
                        c.workspace_id,
                        c.label,
                        json.dumps(list(c.aliases)),
                        sources_to_json(c.sources),
                        c.recurrence_count,
                        json.dumps(c.centrality) if c.centrality is not None else None,
                    )
                    for c in concepts
                ],
            )
            self._conn.executemany(
                """INSERT INTO relationship
                   (id, workspace_id, source_concept_id, target_concept_id, kind, sources)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        r.id,
                        r.workspace_id,
                        r.source_concept_id,
                        r.target_concept_id,
                        r.kind,
                        sources_to_json(r.sources),
                    )
                    for r in relationships
                ],
            )

    def list_concepts(self, workspace_id: str) -> list[Concept]:
        rows = self._conn.execute(
            "SELECT * FROM concept WHERE workspace_id = ? ORDER BY label",
            (workspace_id,),
        ).fetchall()
        return [_row_to_concept(r) for r in rows]

    def get_concept(self, workspace_id: str, concept_id: str) -> Concept | None:
        row = self._conn.execute(
            "SELECT * FROM concept WHERE workspace_id = ? AND id = ?",
            (workspace_id, concept_id),
        ).fetchone()
        return _row_to_concept(row) if row is not None else None

    def list_relationships(self, workspace_id: str) -> list[Relationship]:
        rows = self._conn.execute(
            "SELECT * FROM relationship WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchall()
        return [_row_to_relationship(r) for r in rows]

    def get_relationship(self, workspace_id: str, relationship_id: str) -> Relationship | None:
        row = self._conn.execute(
            "SELECT * FROM relationship WHERE workspace_id = ? AND id = ?",
            (workspace_id, relationship_id),
        ).fetchone()
        return _row_to_relationship(row) if row is not None else None

    def save_ranking(self, run: RankingRun, entries: Sequence[VitalFewEntry]) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT INTO ranking_run
                   (id, workspace_id, created_at, material_count, vital_few_size)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    run.id,
                    run.workspace_id,
                    run.created_at.isoformat(),
                    run.material_count,
                    run.vital_few_size,
                ),
            )
            self._conn.executemany(
                """INSERT INTO vital_few_entry
                   (id, workspace_id, ranking_run_id, concept_id, rank,
                    signals, rationale, evidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        e.id,
                        e.workspace_id,
                        e.ranking_run_id,
                        e.concept_id,
                        e.rank,
                        json.dumps(e.signals),
                        e.rationale,
                        sources_to_json(e.evidence),
                    )
                    for e in entries
                ],
            )

    def latest_ranking(self, workspace_id: str) -> tuple[RankingRun, list[VitalFewEntry]] | None:
        run_row = self._conn.execute(
            "SELECT * FROM ranking_run WHERE workspace_id = ? ORDER BY created_at DESC, rowid DESC "
            "LIMIT 1",
            (workspace_id,),
        ).fetchone()
        if run_row is None:
            return None
        run = RankingRun(
            id=run_row["id"],
            workspace_id=run_row["workspace_id"],
            created_at=datetime.fromisoformat(run_row["created_at"]),
            material_count=run_row["material_count"],
            vital_few_size=run_row["vital_few_size"],
        )
        entry_rows = self._conn.execute(
            "SELECT * FROM vital_few_entry WHERE ranking_run_id = ? ORDER BY rank",
            (run.id,),
        ).fetchall()
        entries = [
            VitalFewEntry(
                id=r["id"],
                workspace_id=r["workspace_id"],
                ranking_run_id=r["ranking_run_id"],
                concept_id=r["concept_id"],
                rank=r["rank"],
                signals=json.loads(r["signals"]),
                rationale=r["rationale"],
                evidence=sources_from_json(r["evidence"]),
            )
            for r in entry_rows
        ]
        return run, entries
