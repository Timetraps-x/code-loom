from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from codeloom.persistence.migrations import CURRENT_SCHEMA_VERSION, SCHEMA


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path.resolve()
        self.db_path = self.repo_path / ".loom" / "loom.db"

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            for statement in SCHEMA:
                conn.execute(statement)
            self._migrate_branch_sessions(conn)
            self._migrate_attempts(conn)
            self._migrate_runtime_refs(conn)
            self._migrate_verifications(conn)
            conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")

    def schema_version(self) -> int:
        if not self.db_path.exists():
            return 0
        with self.connect() as conn:
            row = conn.execute("PRAGMA user_version").fetchone()
        return int(row[0] or 0)

    def branch_session(self, branch_name: str) -> dict[str, Any] | None:
        if not self.db_path.exists():
            return None
        try:
            with self.connect() as conn:
                row = conn.execute(
                    "SELECT * FROM branch_sessions WHERE repo_path = ? AND branch_name = ?",
                    (str(self.repo_path), branch_name),
                ).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(row) if row else None

    def _migrate_branch_sessions(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(branch_sessions)").fetchall()}
        if "recommended_task_id" not in columns:
            conn.execute("ALTER TABLE branch_sessions ADD COLUMN recommended_task_id TEXT")

    def _migrate_attempts(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)").fetchall()}
        for column in ("start_tree", "start_head", "snapshot_semantics", "start_status_json", "latest_review_status", "latest_sealed_tree", "latest_sealed_changes_ref"):
            if columns and column not in columns:
                conn.execute(f"ALTER TABLE attempts ADD COLUMN {column} TEXT")
        if columns and "latest_seal_revision" not in columns:
            conn.execute("ALTER TABLE attempts ADD COLUMN latest_seal_revision INTEGER NOT NULL DEFAULT 0")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)").fetchall()}
        if {"latest_review_tree", "latest_review_context_revision", "latest_changes_ref"} <= columns:
            conn.execute(
                """
                UPDATE attempts
                SET latest_sealed_tree = COALESCE(latest_sealed_tree, latest_review_tree),
                    latest_seal_revision = CASE
                        WHEN latest_seal_revision = 0 THEN COALESCE(latest_review_context_revision, 0)
                        ELSE latest_seal_revision
                    END,
                    latest_sealed_changes_ref = COALESCE(latest_sealed_changes_ref, latest_changes_ref)
                """
            )

    def _migrate_runtime_refs(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(runtime_refs)").fetchall()}
        if columns and "content_hash" not in columns:
            conn.execute("ALTER TABLE runtime_refs ADD COLUMN content_hash TEXT")

    def _migrate_verifications(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(verifications)").fetchall()}
        if columns and "summary_ref" not in columns:
            conn.execute("ALTER TABLE verifications ADD COLUMN summary_ref TEXT")

    def get_or_create_branch_session(self, branch_name: str, branch_slug: str, artifact_root: str) -> dict[str, Any]:
        self.initialize()
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO branch_sessions
                    (repo_path, branch_name, branch_slug, artifact_root, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(self.repo_path), branch_name, branch_slug, artifact_root, now),
            )
            conn.execute(
                """
                UPDATE branch_sessions
                SET branch_slug = ?, artifact_root = ?, updated_at = ?
                WHERE repo_path = ? AND branch_name = ?
                """,
                (branch_slug, artifact_root, now, str(self.repo_path), branch_name),
            )
            row = conn.execute(
                "SELECT * FROM branch_sessions WHERE repo_path = ? AND branch_name = ?",
                (str(self.repo_path), branch_name),
            ).fetchone()
        return dict(row)

    def update_branch_session(self, session_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utc_now()
        names = ", ".join(f"{name} = ?" for name in fields)
        values = list(fields.values()) + [session_id]
        with self.connect() as conn:
            conn.execute(f"UPDATE branch_sessions SET {names} WHERE id = ?", values)

    def record_artifact_revision(
        self,
        session_id: int,
        kind: str,
        path: str,
        content_hash: str,
        based_on_spec_hash: str | None = None,
        based_on_plan_hash: str | None = None,
        based_on_tasks_hash: str | None = None,
    ) -> int:
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT id, based_on_spec_hash, based_on_plan_hash, based_on_tasks_hash FROM artifact_revisions
                WHERE branch_session_id = ? AND kind = ? AND content_hash = ?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, kind, content_hash),
            ).fetchone()
            if existing and (
                existing["based_on_spec_hash"] == based_on_spec_hash
                and existing["based_on_plan_hash"] == based_on_plan_hash
                and existing["based_on_tasks_hash"] == based_on_tasks_hash
            ):
                return int(existing["id"])
            cursor = conn.execute(
                """
                INSERT INTO artifact_revisions
                    (branch_session_id, kind, path, content_hash, based_on_spec_hash,
                     based_on_plan_hash, based_on_tasks_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    kind,
                    path,
                    content_hash,
                    based_on_spec_hash,
                    based_on_plan_hash,
                    based_on_tasks_hash,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def latest_artifact_revision(self, session_id: int, kind: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM artifact_revisions
                WHERE branch_session_id = ? AND kind = ?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, kind),
            ).fetchone()
        return dict(row) if row else None

    def upsert_task_snapshot(
        self,
        session_id: int,
        task_id: str,
        task_fingerprint: str,
        tasks_hash: str,
        title: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO task_snapshots
                    (branch_session_id, task_id, task_fingerprint, tasks_hash, title, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, task_id, task_fingerprint, tasks_hash, title, utc_now()),
            )

    def task_snapshots(self, session_id: int, tasks_hash: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM task_snapshots WHERE branch_session_id = ?"
        params: list[Any] = [session_id]
        if tasks_hash is not None:
            query += " AND tasks_hash = ?"
            params.append(tasks_hash)
        query += " ORDER BY task_id, id DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def latest_task_snapshot(self, session_id: int, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM task_snapshots
                WHERE branch_session_id = ? AND task_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, task_id),
            ).fetchone()
        return dict(row) if row else None

    def next_attempt_no(self, session_id: int, task_id: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT MAX(attempt_no) AS attempt_no FROM attempts WHERE branch_session_id = ? AND task_id = ?",
                (session_id, task_id),
            ).fetchone()
        return int(row["attempt_no"] or 0) + 1

    def create_attempt(
        self,
        session_id: int,
        task_id: str,
        attempt_no: int,
        runtime: str,
        spec_hash: str | None,
        plan_hash: str | None,
        tasks_hash: str | None,
        task_fingerprint: str | None,
        start_tree: str | None = None,
        start_head: str | None = None,
        snapshot_semantics: str | None = None,
        start_status_json: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO attempts
                    (branch_session_id, task_id, attempt_no, runtime, based_on_spec_hash,
                     based_on_plan_hash, based_on_tasks_hash, task_fingerprint, start_tree,
                     start_head, snapshot_semantics, start_status_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
                """,
                (
                    session_id,
                    task_id,
                    attempt_no,
                    runtime,
                    spec_hash,
                    plan_hash,
                    tasks_hash,
                    task_fingerprint,
                    start_tree,
                    start_head,
                    snapshot_semantics,
                    start_status_json,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def update_attempt(self, attempt_id: int, status: str, summary: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE attempts SET status = ?, summary = ?, updated_at = ? WHERE id = ?",
                (status, summary, utc_now(), attempt_id),
            )

    def record_sealed_changes(self, attempt_id: int, sealed_tree: str, changes_ref: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT latest_seal_revision FROM attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            revision = int(row["latest_seal_revision"] or 0) + 1
            conn.execute(
                """
                UPDATE attempts
                SET latest_sealed_tree = ?, latest_seal_revision = ?, latest_review_status = ?, latest_sealed_changes_ref = ?, updated_at = ?
                WHERE id = ?
                """,
                (sealed_tree, revision, "pending", changes_ref, utc_now(), attempt_id),
            )
            return revision

    def update_review_status(self, attempt_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE attempts SET latest_review_status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), attempt_id),
            )

    def supersede_attempt(self, attempt_id: int, summary: str | None = None) -> None:
        self.update_attempt(attempt_id, "superseded", summary)

    def latest_attempt(self, session_id: int, task_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM attempts
                WHERE branch_session_id = ? AND task_id = ?
                ORDER BY attempt_no DESC LIMIT 1
                """,
                (session_id, task_id),
            ).fetchone()
        return dict(row) if row else None

    def attempt(self, attempt_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
        return dict(row) if row else None

    def attempts(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM attempts WHERE branch_session_id = ? ORDER BY task_id, attempt_no",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def record_verification(
        self,
        attempt_id: int,
        command: str | None,
        status: str,
        exit_code: int | None,
        stdout_ref: str | None,
        stderr_ref: str | None,
        summary_ref: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO verifications
                    (attempt_id, command, status, exit_code, stdout_ref, stderr_ref, summary_ref, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (attempt_id, command, status, exit_code, stdout_ref, stderr_ref, summary_ref, utc_now()),
            )
            return int(cursor.lastrowid)

    def verifications_for_attempt(self, attempt_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM verifications WHERE attempt_id = ? ORDER BY id",
                (attempt_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_finding(
        self,
        session_id: int,
        attempt_id: int | None,
        kind: str,
        severity: str,
        message: str,
        suggested_next: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO findings
                    (branch_session_id, attempt_id, kind, severity, status, message, suggested_next, created_at)
                VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
                """,
                (session_id, attempt_id, kind, severity, message, suggested_next, utc_now()),
            )
            return int(cursor.lastrowid)

    def supersede_open_findings_for_attempt(self, attempt_id: int) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE findings SET status = 'superseded' WHERE attempt_id = ? AND status = 'open'",
                (attempt_id,),
            )

    def resolve_open_findings_for_attempt(self, attempt_id: int, kind: str | None = None) -> None:
        query = "UPDATE findings SET status = 'resolved' WHERE attempt_id = ? AND status = 'open'"
        params: list[Any] = [attempt_id]
        if kind is not None:
            query += " AND kind = ?"
            params.append(kind)
        with self.connect() as conn:
            conn.execute(query, params)

    def resolve_open_findings(self, session_id: int, kind: str, message: str | None = None) -> None:
        query = "UPDATE findings SET status = 'resolved' WHERE branch_session_id = ? AND kind = ? AND status = 'open'"
        params: list[Any] = [session_id, kind]
        if message is not None:
            query += " AND message = ?"
            params.append(message)
        with self.connect() as conn:
            conn.execute(query, params)

    def open_blocking_findings(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM findings
                WHERE branch_session_id = ? AND status = 'open' AND severity = 'blocking'
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def findings(self, session_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM findings WHERE branch_session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_runtime_ref(self, attempt_id: int, kind: str, path: str, content_hash: str | None = None) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (attempt_id, kind, path, content_hash, utc_now()),
            )
            return int(cursor.lastrowid)

    def replace_runtime_ref(self, attempt_id: int, kind: str, path: str, content_hash: str | None = None) -> int:
        with self.connect() as conn:
            conn.execute("DELETE FROM runtime_refs WHERE attempt_id = ? AND kind = ?", (attempt_id, kind))
            cursor = conn.execute(
                """
                INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (attempt_id, kind, path, content_hash, utc_now()),
            )
            return int(cursor.lastrowid)

    def runtime_refs(self, attempt_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runtime_refs WHERE attempt_id = ? ORDER BY id",
                (attempt_id,),
            ).fetchall()
        return [dict(row) for row in rows]
