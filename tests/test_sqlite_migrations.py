from __future__ import annotations

import sqlite3

from codeloom.persistence.migrations import CURRENT_SCHEMA_VERSION
from codeloom.persistence.sqlite import SQLiteStore


def test_initialize_sets_schema_version(tmp_path):
    store = SQLiteStore(tmp_path)
    store.initialize()

    assert store.schema_version() == CURRENT_SCHEMA_VERSION


def test_initialize_adds_recommended_task_id_to_existing_db(tmp_path):
    db_dir = tmp_path / ".loom"
    db_dir.mkdir()
    db_path = db_dir / "loom.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE branch_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_path TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                branch_slug TEXT NOT NULL,
                artifact_root TEXT NOT NULL,
                active_stage TEXT,
                active_spec_hash TEXT,
                active_plan_hash TEXT,
                active_tasks_hash TEXT,
                active_ship_hash TEXT,
                recommended_next TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(repo_path, branch_name)
            )
            """
        )
        conn.execute("PRAGMA user_version = 0")

    store = SQLiteStore(tmp_path)
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(branch_sessions)")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "recommended_task_id" in columns
    assert version == CURRENT_SCHEMA_VERSION
