from __future__ import annotations

import hashlib
import json
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
            conn.execute("BEGIN IMMEDIATE")
            for statement in SCHEMA:
                conn.execute(statement)
            self._migrate_branch_sessions(conn)
            self._migrate_artifact_revisions(conn)
            self._migrate_task_snapshots(conn)
            self._migrate_attempts(conn)
            self._migrate_runtime_refs(conn)
            self._migrate_verifications(conn)
            self._migrate_review_records(conn)
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
        for column in (
            "continuation_source_stage",
            "continuation_stage",
            "continuation_reason",
            "continuation_attempt_id",
            "continuation_task_id",
        ):
            if column not in columns:
                column_type = "INTEGER" if column == "continuation_attempt_id" else "TEXT"
                conn.execute(f"ALTER TABLE branch_sessions ADD COLUMN {column} {column_type}")

    def _migrate_artifact_revisions(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(artifact_revisions)").fetchall()}
        if columns and "based_on_execution_hash" not in columns:
            conn.execute("ALTER TABLE artifact_revisions ADD COLUMN based_on_execution_hash TEXT")


    def _migrate_task_snapshots(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(task_snapshots)").fetchall()}
        for column in ("task_packet_hash", "task_packet_ref", "task_packet_version"):
            if columns and column not in columns:
                conn.execute(f"ALTER TABLE task_snapshots ADD COLUMN {column} TEXT")


    def _migrate_attempts(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)").fetchall()}
        for column in ("start_tree", "start_head", "snapshot_semantics", "start_status_json", "snapshot_repositories_json", "latest_review_status", "latest_sealed_tree", "latest_sealed_changes_ref"):
            if columns and column not in columns:
                conn.execute(f"ALTER TABLE attempts ADD COLUMN {column} TEXT")
        if columns and "latest_seal_revision" not in columns:
            conn.execute("ALTER TABLE attempts ADD COLUMN latest_seal_revision INTEGER NOT NULL DEFAULT 0")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(attempts)").fetchall()}
        for column in (
            "task_packet_hash",
            "task_packet_ref",
            "task_packet_version",
            "input_attempts_json",
            "completion_token",
            "completion_status",
            "completion_summary",
            "completion_candidate_ref",
            "completion_candidate_hash",
            "task_packet_json",
            "completion_candidate_json",
        ):
            if columns and column not in columns:
                conn.execute(f"ALTER TABLE attempts ADD COLUMN {column} TEXT")
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
        for column in ("summary_ref", "summary_text", "summary_hash"):
            if columns and column not in columns:
                conn.execute(f"ALTER TABLE verifications ADD COLUMN {column} TEXT")

    def _migrate_review_records(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"]: row for row in conn.execute("PRAGMA table_info(review_records)").fetchall()}
        if "summary_json" not in columns:
            conn.execute("ALTER TABLE review_records ADD COLUMN summary_json TEXT")
        if columns["summary_ref"]["notnull"]:
            conn.execute("ALTER TABLE review_records RENAME TO review_records_legacy")
            conn.execute(next(statement for statement in SCHEMA if "CREATE TABLE IF NOT EXISTS review_records" in statement))
            fields = "id, attempt_id, seal_revision, sealed_tree, status, review_scope, summary_ref, summary_hash, summary_json, created_at"
            conn.execute(f"INSERT INTO review_records ({fields}) SELECT {fields} FROM review_records_legacy")
            conn.execute("DROP TABLE review_records_legacy")

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
        based_on_execution_hash: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO artifact_revisions
                    (branch_session_id, kind, path, content_hash, based_on_spec_hash,
                     based_on_plan_hash, based_on_tasks_hash, based_on_execution_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    kind,
                    path,
                    content_hash,
                    based_on_spec_hash,
                    based_on_plan_hash,
                    based_on_tasks_hash,
                    based_on_execution_hash,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    @staticmethod
    def artifact_input_token(snapshot: dict[str, Any]) -> str:
        payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def artifact_input_snapshot(
        self,
        session_id: int,
        kind: str,
        execution_hash: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            return self._artifact_input_snapshot(conn, session_id, kind, execution_hash)

    def _artifact_input_snapshot(
        self,
        conn: sqlite3.Connection,
        session_id: int,
        kind: str,
        execution_hash: str | None = None,
    ) -> dict[str, Any]:
        upstream = {
            "spec": (),
            "plan": ("spec",),
            "tasks": ("spec", "plan"),
            "ship": ("spec", "plan", "tasks"),
        }[kind]
        snapshot: dict[str, Any] = {"stage": kind, "upstream": {}}
        for upstream_kind in upstream:
            row = conn.execute(
                """
                SELECT id, content_hash FROM artifact_revisions
                WHERE branch_session_id = ? AND kind = ?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, upstream_kind),
            ).fetchone()
            snapshot["upstream"][upstream_kind] = (
                {"revision_id": int(row["id"]), "content_hash": str(row["content_hash"])}
                if row
                else None
            )
        if kind == "ship":
            snapshot["execution_hash"] = execution_hash
        return snapshot

    def register_artifact_if_inputs_current(
        self,
        session_id: int,
        kind: str,
        path: str,
        content_hash: str,
        expected_input_token: str | None,
        execution_hash: str | None = None,
    ) -> dict[str, Any]:
        active_field = {
            "spec": "active_spec_hash",
            "plan": "active_plan_hash",
            "tasks": "active_tasks_hash",
            "ship": "active_ship_hash",
        }[kind]
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            snapshot = self._artifact_input_snapshot(conn, session_id, kind, execution_hash)
            current_token = self.artifact_input_token(snapshot)
            if kind != "spec" and expected_input_token != current_token:
                conn.rollback()
                return {"status": "inputs_changed", "input_snapshot": snapshot, "input_token": current_token}

            upstream = snapshot["upstream"]
            based_on_spec_hash = (upstream.get("spec") or {}).get("content_hash")
            based_on_plan_hash = (upstream.get("plan") or {}).get("content_hash")
            based_on_tasks_hash = (upstream.get("tasks") or {}).get("content_hash")
            cursor = conn.execute(
                """
                INSERT INTO artifact_revisions
                    (branch_session_id, kind, path, content_hash, based_on_spec_hash,
                     based_on_plan_hash, based_on_tasks_hash, based_on_execution_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    kind,
                    path,
                    content_hash,
                    based_on_spec_hash,
                    based_on_plan_hash,
                    based_on_tasks_hash,
                    execution_hash if kind == "ship" else None,
                    utc_now(),
                ),
            )
            now = utc_now()
            conn.execute(
                f"UPDATE branch_sessions SET active_stage = ?, {active_field} = ?, updated_at = ? WHERE id = ?",
                (kind, content_hash, now, session_id),
            )
            conn.execute(
                """
                UPDATE branch_sessions
                SET continuation_source_stage = NULL, continuation_stage = NULL,
                    continuation_reason = NULL, continuation_attempt_id = NULL,
                    continuation_task_id = NULL, updated_at = ?
                WHERE id = ? AND continuation_stage = ?
                """,
                (now, session_id, kind),
            )
            conn.commit()
            return {
                "status": "registered",
                "revision_id": int(cursor.lastrowid),
                "input_snapshot": snapshot,
                "input_token": current_token,
                "based_on_spec_hash": based_on_spec_hash,
                "based_on_plan_hash": based_on_plan_hash,
                "based_on_tasks_hash": based_on_tasks_hash,
            }

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

    def latest_artifact_revisions(self, session_id: int) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifact_revisions WHERE branch_session_id = ? ORDER BY kind, id DESC",
                (session_id,),
            ).fetchall()
        for row in rows:
            revision = dict(row)
            latest.setdefault(str(revision["kind"]), revision)
        return latest

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

    def upsert_task_snapshots(
        self,
        session_id: int,
        snapshots: list[tuple[str, str, str, str, str | None, str | None, str | None]],
    ) -> None:
        if not snapshots:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO task_snapshots
                    (branch_session_id, task_id, task_fingerprint, tasks_hash, title,
                     task_packet_hash, task_packet_ref, task_packet_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        task_id,
                        fingerprint,
                        tasks_hash,
                        title,
                        packet_hash,
                        packet_ref,
                        packet_version,
                        utc_now(),
                    )
                    for task_id, fingerprint, tasks_hash, title, packet_hash, packet_ref, packet_version in snapshots
                ],
            )

    def latest_attempts_by_task(self, session_id: int) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for attempt in self.attempts(session_id):
            latest[attempt["task_id"]] = attempt
        return latest

    def runtime_refs_for_attempts(self, attempt_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        grouped = {attempt_id: [] for attempt_id in attempt_ids}
        if not attempt_ids:
            return grouped
        placeholders = ", ".join("?" for _ in attempt_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM runtime_refs WHERE attempt_id IN ({placeholders}) ORDER BY attempt_id, id",
                attempt_ids,
            ).fetchall()
        for row in rows:
            grouped[int(row["attempt_id"])].append(dict(row))
        return grouped

    def verifications_for_attempts(self, attempt_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        grouped = {attempt_id: [] for attempt_id in attempt_ids}
        if not attempt_ids:
            return grouped
        placeholders = ", ".join("?" for _ in attempt_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM verifications WHERE attempt_id IN ({placeholders}) ORDER BY attempt_id, id",
                attempt_ids,
            ).fetchall()
        for row in rows:
            grouped[int(row["attempt_id"])].append(dict(row))
        return grouped

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

    def task_snapshots_by_task(self, session_id: int, tasks_hash: str) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for snapshot in self.task_snapshots(session_id, tasks_hash):
            latest.setdefault(str(snapshot["task_id"]), snapshot)
        return latest

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
        task_packet_hash: str | None = None,
        task_packet_ref: str | None = None,
        task_packet_version: str | None = None,
        input_attempts_json: str | None = None,
        snapshot_repositories_json: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO attempts
                    (branch_session_id, task_id, attempt_no, runtime, based_on_spec_hash,
                     based_on_plan_hash, based_on_tasks_hash, task_fingerprint, start_tree,
                     start_head, snapshot_semantics, start_status_json, task_packet_hash,
                     task_packet_ref, task_packet_version, input_attempts_json, snapshot_repositories_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
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
                    task_packet_hash,
                    task_packet_ref,
                    task_packet_version,
                    input_attempts_json,
                    snapshot_repositories_json,
                    utc_now(),
                ),
            )
            return int(cursor.lastrowid)

    def active_attempt(self, session_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM attempts
                WHERE branch_session_id = ? AND status IN ('running', 'completing')
                ORDER BY id DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def start_or_resume_attempt(
        self,
        session_id: int,
        task_id: str,
        runtime: str,
        spec_hash: str | None,
        plan_hash: str | None,
        tasks_hash: str | None,
        task_fingerprint: str,
        current_task_fingerprints: dict[str, str],
        current_task_inputs: dict[str, str],
        start_tree: str | None,
        start_head: str | None,
        snapshot_semantics: str | None,
        start_status_json: str | None,
        task_packet_hash: str,
        task_packet_ref: str | None,
        task_packet_version: str,
        input_attempts_json: str,
        task_packet_json: str | None = None,
        snapshot_repositories_json: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute(
                "SELECT * FROM attempts WHERE branch_session_id = ? AND status IN ('running', 'completing') ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if active is not None:
                return dict(active), False
            row = conn.execute(
                "SELECT MAX(attempt_no) AS attempt_no FROM attempts WHERE branch_session_id = ? AND task_id = ?",
                (session_id, task_id),
            ).fetchone()
            attempt_no = int(row["attempt_no"] or 0) + 1
            now = utc_now()
            cursor = conn.execute(
                """
                INSERT INTO attempts
                    (branch_session_id, task_id, attempt_no, runtime, based_on_spec_hash,
                     based_on_plan_hash, based_on_tasks_hash, task_fingerprint, start_tree,
                     start_head, snapshot_semantics, start_status_json, task_packet_hash,
                     task_packet_ref, task_packet_version, input_attempts_json, task_packet_json, snapshot_repositories_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
                """,
                (session_id, task_id, attempt_no, runtime, spec_hash, plan_hash, tasks_hash,
                 task_fingerprint, start_tree, start_head, snapshot_semantics, start_status_json,
                 task_packet_hash, task_packet_ref, task_packet_version, input_attempts_json, task_packet_json, snapshot_repositories_json, now),
            )
            attempt_id = int(cursor.lastrowid)
            if task_packet_ref is not None:
                conn.execute(
                    "INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at) VALUES (?, 'task_packet', ?, ?, ?)",
                    (attempt_id, task_packet_ref, task_packet_hash, now),
                )
            created = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
            conn.commit()
        return dict(created), True

    def attach_task_packet(self, attempt_id: int, packet_ref: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE attempts SET task_packet_ref = ?, updated_at = ? WHERE id = ?",
                (packet_ref, utc_now(), attempt_id),
            )

    def update_attempt(self, attempt_id: int, status: str, summary: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE attempts SET status = ?, summary = ?, updated_at = ? WHERE id = ?",
                (status, summary, utc_now(), attempt_id),
            )

    def unlock_do_attempt(
        self,
        session_id: int,
        attempt_id: int | None = None,
        completed_status: str | None = None,
        manual_summary: str | None = None,
    ) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            session = conn.execute("SELECT * FROM branch_sessions WHERE id = ?", (session_id,)).fetchone()
            if session is None:
                conn.rollback()
                return {"result": "not_found"}

            target_id = attempt_id
            if target_id is None and session["continuation_source_stage"] == "do":
                target_id = session["continuation_attempt_id"]
            if target_id is None:
                active = conn.execute(
                    """
                    SELECT id FROM attempts
                    WHERE branch_session_id = ? AND status IN ('running', 'completing')
                    ORDER BY id DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                target_id = int(active["id"]) if active else None
            if target_id is None:
                conn.rollback()
                return {"result": "not_found"}

            attempt = conn.execute("SELECT * FROM attempts WHERE id = ?", (target_id,)).fetchone()
            if attempt is None:
                conn.rollback()
                return {"result": "not_found", "attempt_id": target_id}
            if int(attempt["branch_session_id"]) != session_id:
                conn.rollback()
                return {"result": "session_mismatch", "attempt_id": target_id}

            previous_status = str(attempt["status"])
            manual_completion = completed_status in {"implemented", "verified"}
            releasable_statuses = {"running", "completing"}
            if manual_completion:
                releasable_statuses.update({"blocked", "failed"})
            status_released = previous_status in releasable_statuses
            continuation_cleared = bool(
                session["continuation_source_stage"] == "do"
                and session["continuation_attempt_id"] == target_id
            )
            now = utc_now()
            if status_released:
                existing_summary = str(attempt["summary"] or "").strip()
                if manual_completion:
                    marker = f"manually marked {completed_status} by explicit user action"
                    if manual_summary:
                        marker = f"{marker}: {manual_summary.strip()}"
                    next_status = str(completed_status)
                else:
                    marker = "mechanically unlocked by explicit user action; no completion asserted"
                    next_status = "blocked"
                summary = f"{existing_summary}\n{marker}" if existing_summary else marker
                placeholders = ", ".join("?" for _ in releasable_statuses)
                conn.execute(
                    f"UPDATE attempts SET status = ?, summary = ?, updated_at = ? "
                    f"WHERE id = ? AND branch_session_id = ? AND status IN ({placeholders})",
                    (next_status, summary, now, target_id, session_id, *sorted(releasable_statuses)),
                )
            if continuation_cleared:
                conn.execute(
                    """
                    UPDATE branch_sessions
                    SET continuation_source_stage = NULL, continuation_stage = NULL,
                        continuation_reason = NULL, continuation_attempt_id = NULL,
                        continuation_task_id = NULL, updated_at = ?
                    WHERE id = ? AND continuation_source_stage = 'do' AND continuation_attempt_id = ?
                    """,
                    (now, session_id, target_id),
                )
            if not status_released and not continuation_cleared:
                conn.commit()
                return {
                    "result": "already_inactive",
                    "attempt_id": target_id,
                    "previous_status": previous_status,
                    "status": previous_status,
                    "continuation_cleared": False,
                }
            conn.commit()
            return {
                "result": "completed" if manual_completion and status_released else "unlocked",
                "attempt_id": target_id,
                "previous_status": previous_status,
                "status": str(completed_status) if manual_completion and status_released else ("blocked" if status_released else previous_status),
                "continuation_cleared": continuation_cleared,
            }


    def complete_attempt_if_running(self, attempt_id: int, status: str, summary: str | None = None) -> bool:
        with self.connect() as conn:
            cursor = conn.execute(
                "UPDATE attempts SET status = ?, summary = ?, updated_at = ? WHERE id = ? AND status = 'running'",
                (status, summary, utc_now(), attempt_id),
            )
        return cursor.rowcount == 1

    def claim_attempt_completion(
        self,
        attempt_id: int,
        token: str,
        final_status: str,
        summary: str,
        candidate_ref: str | None,
        candidate_hash: str,
        candidate_json: str | None = None,
    ) -> str:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
            if row is None:
                return "missing"
            if candidate_hash != token:
                return "conflict"
            if candidate_json is not None and hashlib.sha256(candidate_json.encode("utf-8")).hexdigest() != token:
                return "conflict"
            if row["status"] == "running":
                conn.execute(
                    """
                    UPDATE attempts
                    SET status = 'completing', completion_token = ?, completion_status = ?,
                        completion_summary = ?, completion_candidate_ref = ?,
                        completion_candidate_hash = ?, completion_candidate_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (token, final_status, summary, candidate_ref, candidate_hash, candidate_json, utc_now(), attempt_id),
                )
                return "claimed"
            if row["status"] == "completing":
                if row["completion_token"] != token:
                    return "conflict"
                conn.execute(
                    """UPDATE attempts SET completion_candidate_ref = ?, completion_candidate_hash = ?,
                       completion_candidate_json = ?, updated_at = ? WHERE id = ?""",
                    (candidate_ref, candidate_hash, candidate_json, utc_now(), attempt_id),
                )
                return "resume"
            result = (
                "completed"
                if row["status"] == final_status and (row["completion_token"] is None or row["completion_token"] == token)
                else "conflict"
            )
            return result

    def finalize_attempt_completion(
        self,
        attempt_id: int,
        token: str,
        final_status: str,
        summary: str,
        runtime_refs: list[tuple[str, str, str]],
        verification: tuple[str, str, int | None, str | None, str | None] | None,
        finding: tuple[int, str, str, str, str | None] | None,
    ) -> bool:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status, completion_token FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
            if row is None or row["status"] != "completing" or row["completion_token"] != token:
                conn.rollback()
                return False
            for kind, path, content_hash in runtime_refs:
                conn.execute("DELETE FROM runtime_refs WHERE attempt_id = ? AND kind = ?", (attempt_id, kind))
                conn.execute(
                    "INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                    (attempt_id, kind, path, content_hash, utc_now()),
                )
            if verification is not None:
                command, status, exit_code, summary_ref, summary_text = verification
                conn.execute("DELETE FROM verifications WHERE attempt_id = ? AND command = ?", (attempt_id, command))
                conn.execute(
                    """
                    INSERT INTO verifications
                        (attempt_id, command, status, exit_code, stdout_ref, stderr_ref, summary_ref, summary_text, summary_hash, created_at)
                    VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
                    """,
                    (attempt_id, command, status, exit_code, summary_ref, summary_text,
                     hashlib.sha256(summary_text.encode("utf-8")).hexdigest() if summary_text is not None else None, utc_now()),
                )
            if finding is not None:
                session_id, kind, severity, message, suggested_next = finding
                conn.execute(
                    """
                    INSERT INTO findings
                        (branch_session_id, attempt_id, kind, severity, status, message, suggested_next, created_at)
                    VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
                    """,
                    (session_id, attempt_id, kind, severity, message, suggested_next, utc_now()),
                )
            conn.execute(
                """
                UPDATE attempts
                SET status = ?, summary = ?, completion_status = ?, completion_summary = ?, updated_at = ?
                WHERE id = ? AND status = 'completing' AND completion_token = ?
                """,
                (final_status, summary, final_status, summary, utc_now(), attempt_id, token),
            )
            conn.commit()
            return True

    def record_sealed_changes(self, attempt_id: int, sealed_tree: str) -> tuple[int, bool]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT latest_sealed_tree, latest_seal_revision FROM attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                raise ValueError(f"attempt not found: {attempt_id}")
            revision = int(row["latest_seal_revision"] or 0)
            if revision > 0 and row["latest_sealed_tree"] == sealed_tree:
                conn.commit()
                return revision, False
            revision += 1
            conn.execute(
                """
                UPDATE attempts
                SET latest_sealed_tree = ?, latest_seal_revision = ?, latest_review_status = 'pending',
                    latest_sealed_changes_ref = NULL, updated_at = ?
                WHERE id = ?
                """,
                (sealed_tree, revision, utc_now(), attempt_id),
            )
            conn.commit()
            return revision, True

    def attach_sealed_changes(
        self,
        attempt_id: int,
        seal_revision: int,
        sealed_tree: str,
        changes_ref: str | None,
        changes_hash: str,
        manifest_json: str | None = None,
    ) -> bool:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT latest_sealed_tree, latest_seal_revision FROM attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if (
                row is None
                or int(row["latest_seal_revision"] or 0) != seal_revision
                or row["latest_sealed_tree"] != sealed_tree
            ):
                conn.rollback()
                return False
            if manifest_json is not None:
                conn.execute(
                    """INSERT INTO sealed_changes (attempt_id, seal_revision, sealed_tree, manifest_json, content_hash)
                       VALUES (?, ?, ?, ?, ?) ON CONFLICT(attempt_id, seal_revision) DO UPDATE SET
                       manifest_json = excluded.manifest_json, content_hash = excluded.content_hash""",
                    (attempt_id, seal_revision, sealed_tree, manifest_json, changes_hash),
                )
            if changes_ref is not None:
                conn.execute(
                    "DELETE FROM runtime_refs WHERE attempt_id = ? AND kind = 'attempt_changes'", (attempt_id,),
                )
                conn.execute(
                    "INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at) VALUES (?, 'attempt_changes', ?, ?, ?)",
                    (attempt_id, changes_ref, changes_hash, utc_now()),
                )
            conn.execute(
                "UPDATE attempts SET latest_sealed_changes_ref = ?, updated_at = ? WHERE id = ?",
                (changes_ref, utc_now(), attempt_id),
            )
            conn.commit()
            return True

    def sealed_changes_for_attempt(self, attempt_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sealed_changes WHERE attempt_id = ? ORDER BY seal_revision", (attempt_id,),
            ).fetchall()
        return [dict(row) for row in rows]


    def update_review_status(self, attempt_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE attempts SET latest_review_status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), attempt_id),
            )

    def record_review(
        self,
        attempt_id: int,
        seal_revision: int,
        sealed_tree: str,
        status: str,
        summary_ref: str | None,
        summary_hash: str,
        summary_json: str | None = None,
    ) -> int:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM review_records WHERE attempt_id = ? AND seal_revision = ?",
                (attempt_id, seal_revision),
            ).fetchone()
            if existing is not None:
                if existing["sealed_tree"] == sealed_tree and existing["status"] == status:
                    conn.commit()
                    return int(existing["id"])
                conn.rollback()
                raise ValueError("review_already_recorded")
            if summary_ref is not None:
                conn.execute(
                    "INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at) VALUES (?, 'review_summary', ?, ?, ?)",
                    (attempt_id, summary_ref, summary_hash, utc_now()),
                )
            cursor = conn.execute(
                """
                INSERT INTO review_records
                    (attempt_id, seal_revision, sealed_tree, status, review_scope, summary_ref, summary_hash, summary_json, created_at)
                VALUES (?, ?, ?, ?, 'attempt_scoped', ?, ?, ?, ?)
                """,
                (attempt_id, seal_revision, sealed_tree, status, summary_ref, summary_hash, summary_json, utc_now()),
            )
            conn.execute(
                "UPDATE attempts SET latest_review_status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), attempt_id),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def review_for_seal(self, attempt_id: int, seal_revision: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_records WHERE attempt_id = ? AND seal_revision = ?",
                (attempt_id, seal_revision),
            ).fetchone()
        return dict(row) if row else None

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
