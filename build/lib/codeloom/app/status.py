from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codeloom.app.constitution import constitution_status
from codeloom.app.init_project import load_project_config
from codeloom.kernel.artifacts import branch_slug, parse_tasks, task_identity_errors, task_relation_errors
from codeloom.kernel.drift import derive_artifact_states
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
        "project_profile": {
            "languages": list(config.languages),
            "frameworks": list(config.frameworks),
            "modules": list(config.modules),
            "commands": dict(config.commands),
        },
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
        session_id = int(session["id"])
        revisions = store.latest_artifact_revisions(session_id)
        tasks_by_id: dict[str, Any] = {}
        task_error = None
        tasks_content = artifacts.read("tasks")
        if tasks_content is not None:
            contract_errors = task_identity_errors(tasks_content) + task_relation_errors(tasks_content)
            if contract_errors:
                task_error = ", ".join(contract_errors)
            else:
                tasks = parse_tasks(tasks_content)
                if tasks:
                    tasks_by_id = {task.task_id: task for task in tasks}
                else:
                    task_error = "tasks.md contains no parseable tasks"
        states = derive_artifact_states(
            {kind: result["artifacts"][kind]["hash"] for kind in ARTIFACT_KINDS},
            revisions,
            task_error=task_error,
        )
        for kind, state in states.items():
            result["artifacts"][kind].update(state)
            result["artifacts"][kind]["content_current"] = bool(
                state["registered_hash"] and state["registered_hash"] == state["disk_hash"]
            )
        latest_ship = revisions.get("ship")
        result["artifacts"]["ship"]["registered_execution_hash"] = (
            latest_ship.get("based_on_execution_hash") if latest_ship else None
        )
        result["session"] = _session_summary(session, tasks_by_id)
        result["open_findings"] = _open_findings(store.findings(session_id))
        result["latest_attempts"] = _latest_attempts(store.attempts(session_id), tasks_by_id, branch_name)
        if task_error:
            result["errors"].append(task_error)
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


def _session_summary(session: dict[str, Any], tasks_by_id: dict[str, Any]) -> dict[str, Any]:
    recommended_task_id = session.get("recommended_task_id")
    recommended_task = tasks_by_id.get(str(recommended_task_id)) if recommended_task_id else None
    return {
        "id": session.get("id"),
        "recommended_next": session.get("recommended_next"),
        "recommended_task_id": recommended_task_id,
        "recommended_task_title": recommended_task.title if recommended_task else None,
        "continuation": {
            "source_stage": session.get("continuation_source_stage"),
            "stage": session.get("continuation_stage"),
            "reason": session.get("continuation_reason"),
            "attempt_id": session.get("continuation_attempt_id"),
            "task_id": session.get("continuation_task_id"),
        } if session.get("continuation_stage") else None,
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


def _latest_attempts(attempts: list[dict[str, Any]], tasks_by_id: dict[str, Any] | None = None, branch_name: str = "") -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        latest[str(attempt["task_id"])] = attempt

    tasks = list((tasks_by_id or {}).values())
    explicit_relations = any(task.relations_declared for task in tasks)
    effective: dict[str, dict[str, Any]] = {}
    projections: dict[str, dict[str, Any]] = {}
    for index, task in enumerate(tasks):
        attempt = latest.get(task.task_id)
        input_ids = (
            tuple(dict.fromkeys((*task.depends_on, *task.validates)))
            if explicit_relations
            else (() if index == 0 else (tasks[index - 1].task_id,))
        )
        blocked_by = [task_id for task_id in input_ids if task_id not in effective]
        recorded_inputs = _json_object((attempt or {}).get("input_attempts_json"))
        expected_inputs = {task_id: int(effective[task_id]["id"]) for task_id in input_ids if task_id in effective}
        expected_status = "verified" if task.lane == "verify" else "implemented"
        inputs_match = (
            not explicit_relations and (attempt or {}).get("input_attempts_json") is None
        ) or (len(expected_inputs) == len(input_ids) and recorded_inputs == expected_inputs)
        is_effective = bool(
            attempt
            and attempt.get("task_fingerprint") == task.fingerprint
            and attempt.get("status") == expected_status
            and inputs_match
        )
        if is_effective:
            effective[task.task_id] = attempt
            effective_status = "effective"
        elif attempt and attempt.get("status") in {"running", "completing"}:
            effective_status = "active"
        elif blocked_by:
            effective_status = "blocked"
        elif attempt and attempt.get("status") == expected_status:
            effective_status = "stale"
        else:
            effective_status = str((attempt or {}).get("status") or "pending")
        projections[task.task_id] = {
            "effective_status": effective_status,
            "blocked_by": blocked_by,
        }

    return [
        {
            "task_id": attempt.get("task_id"),
            "attempt_no": attempt.get("attempt_no"),
            "lane": tasks_by_id.get(str(attempt.get("task_id"))).lane if tasks_by_id and str(attempt.get("task_id")) in tasks_by_id else None,
            "complexity": tasks_by_id.get(str(attempt.get("task_id"))).complexity if tasks_by_id and str(attempt.get("task_id")) in tasks_by_id else None,
            "status": attempt.get("status"),
            "effective_status": projections.get(task_id, {}).get("effective_status"),
            "blocked_by": projections.get(task_id, {}).get("blocked_by", []),
            "input_attempts": _json_object(attempt.get("input_attempts_json")),
            "completion_status": attempt.get("completion_status"),
            "completion_candidate_ref": attempt.get("completion_candidate_ref"),
            "completion_candidate_hash": attempt.get("completion_candidate_hash"),
            "completion_candidate_available": attempt.get("completion_candidate_json") is not None or bool(attempt.get("completion_candidate_ref")),
            "recovery_command": (
                f"/loom-do {attempt.get('task_id')}"
                if attempt.get("status") in {"running", "completing"}
                else None
            ),
            "unlock_command": (
                f"loom stage do --branch {branch_name} --arg action=unlock --arg attempt_id={attempt.get('id')}"
                if attempt.get("status") in {"running", "completing"}
                else None
            ),
            "summary": attempt.get("summary"),
            "updated_at": attempt.get("updated_at"),
        }
        for task_id, attempt in sorted(latest.items())
    ]


def _json_object(value: object | None) -> dict[str, Any]:
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
