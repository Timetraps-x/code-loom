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


def test_initialize_adds_content_hash_to_existing_runtime_refs(tmp_path):
    db_dir = tmp_path / ".loom"
    db_dir.mkdir()
    db_path = db_dir / "loom.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE runtime_refs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
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
                recommended_task_id TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(repo_path, branch_name)
);
            """
        )
        conn.execute("PRAGMA user_version = 0")

    store = SQLiteStore(tmp_path)
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(runtime_refs)")}

    assert "content_hash" in columns


def test_initialize_adds_summary_ref_to_existing_verifications(tmp_path):
    db_dir = tmp_path / ".loom"
    db_dir.mkdir()
    db_path = db_dir / "loom.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                command TEXT,
                status TEXT NOT NULL,
                exit_code INTEGER,
                stdout_ref TEXT,
                stderr_ref TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("PRAGMA user_version = 1")

    store = SQLiteStore(tmp_path)
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(verifications)")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "summary_ref" in columns
    assert version == CURRENT_SCHEMA_VERSION


def test_initialize_adds_attempt_start_snapshot_fields_to_existing_attempts(tmp_path):
    db_dir = tmp_path / ".loom"
    db_dir.mkdir()
    db_path = db_dir / "loom.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_session_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                attempt_no INTEGER NOT NULL,
                runtime TEXT NOT NULL,
                based_on_spec_hash TEXT,
                based_on_plan_hash TEXT,
                based_on_tasks_hash TEXT,
                task_fingerprint TEXT,
                status TEXT NOT NULL,
                summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
        conn.execute("PRAGMA user_version = 2")

    store = SQLiteStore(tmp_path)
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(attempts)")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert {"start_tree", "start_head", "snapshot_semantics", "start_status_json", "latest_sealed_tree", "latest_seal_revision", "latest_review_status", "latest_sealed_changes_ref"} <= columns
    assert version == CURRENT_SCHEMA_VERSION


def test_initialize_backfills_legacy_review_context_fields_into_seal_fields(tmp_path):
    db_dir = tmp_path / ".loom"
    db_dir.mkdir()
    db_path = db_dir / "loom.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE attempts (
                id INTEGER PRIMARY KEY,
                branch_session_id INTEGER NOT NULL,
                task_id TEXT NOT NULL,
                attempt_no INTEGER NOT NULL,
                runtime TEXT NOT NULL,
                latest_review_tree TEXT,
                latest_review_context_revision INTEGER NOT NULL DEFAULT 0,
                latest_review_status TEXT,
                latest_changes_ref TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO attempts (
                id, branch_session_id, task_id, attempt_no, runtime,
                latest_review_tree, latest_review_context_revision,
                latest_review_status, latest_changes_ref, status, created_at
            ) VALUES (1, 1, 'T1', 1, 'claude-code', 'legacy-tree', 3, 'pass', '.loom/runs/master/T1-a001-attempt-changes.json', 'running', '2026-01-01T00:00:00+00:00')
            """
        )
        conn.execute("PRAGMA user_version = 4")

    store = SQLiteStore(tmp_path)
    store.initialize()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT latest_sealed_tree, latest_seal_revision, latest_review_status, latest_sealed_changes_ref
            FROM attempts WHERE id = 1
            """
        ).fetchone()

    assert row == ("legacy-tree", 3, "pass", ".loom/runs/master/T1-a001-attempt-changes.json")