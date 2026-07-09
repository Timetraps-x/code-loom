from __future__ import annotations

from pathlib import Path
from typing import Any

from codeloom.app.constitution import constitution_status
from codeloom.app.init_project import load_project_config
from codeloom.kernel.artifacts import branch_slug, parse_tasks
from codeloom.persistence.sqlite import SQLiteStore
from codeloom.stores.markdown import MarkdownArtifactStore

ARTIFACT_KINDS = ("spec", "plan", "tasks", "ship")


def get_status(cwd: Path, branch_name: str) -> dict[str, Any]:
    repo_path = cwd.resolve()
    config = load_project_config(repo_path)
    slug = branch_slug(branch_name)
    artifacts = MarkdownArtifactStore(repo_path, config.artifact_root, slug)
    store = SQLiteStore(repo_path)
    db_exists = store.db_path.exists()
    result: dict[str, Any] = {
        "status": "ok" if db_exists else "not_initialized",
        "repo_path": str(repo_path),
        "branch_name": branch_name,
        "branch_slug": slug,
        "artifact_root": config.artifact_root,
        "db_path": str(store.db_path),
        "db_exists": db_exists,
        "schema_version": 0,
        "session": None,
        "artifacts": _artifact_statuses(artifacts),
        "constitution": constitution_status(repo_path, config.constitution_path, config.constitution_hash),
        "open_findings": [],
        "latest_attempts": [],
        "errors": [],
    }
    if not db_exists:
        return result

    try:
        result["schema_version"] = store.schema_version()
        session = store.branch_session(branch_name)
        if session is None:
            return result
        result["session"] = _session_summary(session)
        session_id = int(session["id"])
        result["open_findings"] = _open_findings(store.findings(session_id))
        tasks_content = artifacts.read("tasks") or ""
        tasks_by_id = {task.task_id: task for task in parse_tasks(tasks_content)}
        result["latest_attempts"] = _latest_attempts(store.attempts(session_id), tasks_by_id)
    except Exception as exc:
        result["status"] = "failed"
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    return result


def _artifact_statuses(artifacts: MarkdownArtifactStore) -> dict[str, dict[str, Any]]:
    statuses: dict[str, dict[str, Any]] = {}
    for kind in ARTIFACT_KINDS:
        path = artifacts.path_for(kind)
        exists = path.exists()
        statuses[kind] = {
            "path": artifacts.relative(path),
            "exists": exists,
            "hash": artifacts.hash_existing(kind) if exists else None,
        }
    return statuses


def _session_summary(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session.get("id"),
        "recommended_next": session.get("recommended_next"),
        "recommended_task_id": session.get("recommended_task_id"),
        "active_hashes": {
            "spec": session.get("active_spec_hash"),
            "plan": session.get("active_plan_hash"),
            "tasks": session.get("active_tasks_hash"),
            "ship": session.get("active_ship_hash"),
        },
        "updated_at": session.get("updated_at"),
    }


def _open_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": finding.get("id"),
            "attempt_id": finding.get("attempt_id"),
            "kind": finding.get("kind"),
            "severity": finding.get("severity"),
            "message": finding.get("message"),
            "suggested_next": finding.get("suggested_next"),
        }
        for finding in findings
        if finding.get("status") == "open"
    ]


def _latest_attempts(attempts: list[dict[str, Any]], tasks_by_id: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest[str(attempt["task_id"])] = attempt
    return [
        {
            "task_id": attempt.get("task_id"),
            "attempt_no": attempt.get("attempt_no"),
            "lane": tasks_by_id.get(str(attempt.get("task_id"))).lane if tasks_by_id and str(attempt.get("task_id")) in tasks_by_id else None,
            "complexity": tasks_by_id.get(str(attempt.get("task_id"))).complexity if tasks_by_id and str(attempt.get("task_id")) in tasks_by_id else None,
            "status": attempt.get("status"),
            "summary": attempt.get("summary"),
            "updated_at": attempt.get("updated_at"),
        }
        for task_id, attempt in sorted(latest.items())
    ]
