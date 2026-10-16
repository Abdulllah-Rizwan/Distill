"""SQLite connection + schema initialization.

Single local database as the source of truth (ADR: SQLite + NetworkX for v1). Every derived row is
scoped by ``workspace_id``; value-object lists are stored as JSON text columns (see ``_serde``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS material (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    format          TEXT NOT NULL,
    content_text    TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    status          TEXT NOT NULL,
    rejected_reason TEXT,
    page_map        TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    UNIQUE (workspace_id, content_hash)
);

CREATE TABLE IF NOT EXISTS concept (
    id               TEXT PRIMARY KEY,
    workspace_id     TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    label            TEXT NOT NULL,
    aliases          TEXT NOT NULL DEFAULT '[]',
    sources          TEXT NOT NULL,
    recurrence_count INTEGER NOT NULL,
    centrality       TEXT
);

CREATE TABLE IF NOT EXISTS relationship (
    id                TEXT PRIMARY KEY,
    workspace_id      TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    source_concept_id TEXT NOT NULL,
    target_concept_id TEXT NOT NULL,
    kind              TEXT,
    sources           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ranking_run (
    id             TEXT PRIMARY KEY,
    workspace_id   TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    created_at     TEXT NOT NULL,
    material_count INTEGER NOT NULL,
    vital_few_size INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS vital_few_entry (
    id              TEXT PRIMARY KEY,
    workspace_id    TEXT NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
    ranking_run_id  TEXT NOT NULL REFERENCES ranking_run(id) ON DELETE CASCADE,
    concept_id      TEXT NOT NULL,
    rank            INTEGER NOT NULL,
    signals         TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    evidence        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_material_ws   ON material(workspace_id);
CREATE INDEX IF NOT EXISTS ix_concept_ws    ON concept(workspace_id);
CREATE INDEX IF NOT EXISTS ix_relationship_ws ON relationship(workspace_id);
CREATE INDEX IF NOT EXISTS ix_ranking_run_ws ON ranking_run(workspace_id, created_at);
CREATE INDEX IF NOT EXISTS ix_vfe_run       ON vital_few_entry(ranking_run_id, rank);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open a SQLite connection with row access by name and foreign keys enforced.

    ``db_path`` may be ``":memory:"`` for tests; a file path's parent directory is created.
    """
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they do not already exist."""
    conn.executescript(_SCHEMA)
    conn.commit()
