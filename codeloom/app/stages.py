from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from codeloom.app.init_project import ProjectConfig, load_project_config
from codeloom.app.request import KernelRequest
from codeloom.app.response import KernelResponse
from codeloom.kernel.artifacts import TaskDefinition, branch_slug, parse_tasks
from codeloom.kernel.attempts import attempt_status
from codeloom.kernel.clients import create_llm_client, create_runtime_client
from codeloom.kernel.drift import detect_plan_or_task_drift
from codeloom.kernel.resolver import ContractRevisionResolver
from codeloom.kernel.verification import ShellVerifier
from codeloom.persistence.sqlite import SQLiteStore
from codeloom.stores.file_evidence import FileEvidenceStore
from codeloom.stores.markdown import MarkdownArtifactStore


@dataclass
class StageContext:
    request: KernelRequest
    config: ProjectConfig
    branch_slug: str
    store: SQLiteStore
    session: dict[str, Any]
    artifacts: MarkdownArtifactStore
    evidence: FileEvidenceStore

@dataclass(frozen=True)
class NextRecommendation:
    command: str | None
    task_id: str | None = None

def _loom_command(command: str) -> str:
    return f"/loom-{command}"

def _artifact_drift_message(kind: str) -> str:
    return f"{kind}.md changed outside registered artifact revision"
ARTIFACT_STAGE_MAIN_AGENTS = {
    "spec": "spec-analyzer",
    "plan": "plan-architect",
    "tasks": "task-planner",
    "ship": "release-analyzer",
}

ARTIFACT_STAGE_REVIEWERS = {
    "spec": "spec-reviewer",
    "plan": "plan-reviewer",
    "tasks": "task-reviewer",
}

def _normalize_command(command: str) -> str:
    if command.startswith("/loom-"):
        return command.removeprefix("/loom-")
    return command.removeprefix("/loom:")


def _normalize_recommendation(command: str) -> str:
    if command.startswith("/loom:"):
        return command.replace("/loom:", "/loom-", 1)
    return command


class StageRunner:
    def __init__(self) -> None:
        self.verifier = ShellVerifier()
        self.resolver = ContractRevisionResolver()

    def run(self, request: KernelRequest) -> KernelResponse:
        command = _normalize_command(request.command)
        context = self._context(request)
        if command == "spec":
            return self._run_spec(context)
        if command == "plan":
            return self._run_plan(context)
        if command == "tasks":
            return self._run_tasks(context)
        if command == "do":
            return self._run_do(context)
        if command == "ship":
            return self._run_ship(context)
        return KernelResponse(status="failed", message=f"unknown command: {request.command}", errors=["unknown_command"])

    def _context(self, request: KernelRequest) -> StageContext:
        config = load_project_config(request.cwd)
        slug = branch_slug(request.branch_name)
        store = SQLiteStore(request.cwd)
        session = store.get_or_create_branch_session(request.branch_name, slug, config.artifact_root)
        context = StageContext(
            request=request,
            config=config,
            branch_slug=slug,
            store=store,
            session=session,
            artifacts=MarkdownArtifactStore(request.cwd, config.artifact_root, slug),
            evidence=FileEvidenceStore(request.cwd, slug),
        )
        self._sync_artifact_state(context)
        recommendation = self._derive_recommendation(context)
        if (
            recommendation.command != context.session.get("recommended_next")
            or recommendation.task_id != context.session.get("recommended_task_id")
        ):
            store.update_branch_session(
                int(context.session["id"]),
                recommended_next=recommendation.command,
                recommended_task_id=recommendation.task_id,
            )
            context.session["recommended_next"] = recommendation.command
            context.session["recommended_task_id"] = recommendation.task_id
        return context

    def _artifact_file_stage_kind(self, context: StageContext) -> str | None:
        if not context.request.args.get("artifact_file"):
            return None
        command = _normalize_command(context.request.command)
        if command in {"spec", "plan", "tasks"}:
            return command
        if command == "ship":
            return "ship"
        return None

    def _sync_artifact_state(self, context: StageContext) -> None:
        session_id = int(context.session["id"])
        updates: dict[str, str] = {}
        skip_kind = self._artifact_file_stage_kind(context)

        spec_hash = None if skip_kind == "spec" else self._sync_one_artifact(context, "spec", "active_spec_hash")
        if spec_hash:
            updates["active_spec_hash"] = spec_hash

        current_spec_hash = updates.get("active_spec_hash") or context.session.get("active_spec_hash")
        plan_hash = None
        if skip_kind != "plan":
            plan_hash = self._sync_one_artifact(
                context,
                "plan",
                "active_plan_hash",
                based_on_spec_hash=current_spec_hash,
            )
            if plan_hash:
                updates["active_plan_hash"] = plan_hash

        latest_plan = context.store.latest_artifact_revision(session_id, "plan")
        tasks_hash = None
        if skip_kind != "tasks":
            tasks_hash = self._sync_one_artifact(
                context,
                "tasks",
                "active_tasks_hash",
                based_on_spec_hash=latest_plan["based_on_spec_hash"] if latest_plan else current_spec_hash,
                based_on_plan_hash=updates.get("active_plan_hash") or context.session.get("active_plan_hash"),
            )
            if tasks_hash:
                updates["active_tasks_hash"] = tasks_hash
                tasks_content = context.artifacts.read("tasks") or ""
                self._record_task_snapshots(context, tasks_content, tasks_hash)

        latest_tasks = context.store.latest_artifact_revision(session_id, "tasks")
        ship_hash = None
        if skip_kind != "ship":
            ship_hash = self._sync_one_artifact(
                context,
                "ship",
                "active_ship_hash",
                based_on_spec_hash=latest_tasks["based_on_spec_hash"] if latest_tasks else current_spec_hash,
                based_on_plan_hash=latest_tasks["based_on_plan_hash"] if latest_tasks else context.session.get("active_plan_hash"),
                based_on_tasks_hash=updates.get("active_tasks_hash") or context.session.get("active_tasks_hash"),
            )
            if ship_hash:
                updates["active_ship_hash"] = ship_hash

        if updates:
            context.store.update_branch_session(session_id, **updates)
            context.session.update(updates)

    def _sync_one_artifact(
        self,
        context: StageContext,
        kind: str,
        active_field: str,
        based_on_spec_hash: object | None = None,
        based_on_plan_hash: object | None = None,
        based_on_tasks_hash: object | None = None,
    ) -> str | None:
        content_hash = context.artifacts.hash_existing(kind)
        previous_hash = context.session.get(active_field)
        if content_hash is None or previous_hash == content_hash:
            return None
        path = context.artifacts.path_for(kind)
        session_id = int(context.session["id"])
        context.store.record_artifact_revision(
            session_id,
            kind,
            context.artifacts.relative(path),
            content_hash,
            based_on_spec_hash=str(based_on_spec_hash) if based_on_spec_hash else None,
            based_on_plan_hash=str(based_on_plan_hash) if based_on_plan_hash else None,
            based_on_tasks_hash=str(based_on_tasks_hash) if based_on_tasks_hash else None,
        )
        if previous_hash:
            context.store.add_finding(
                session_id,
                None,
                "artifact_drift",
                "warning",
                _artifact_drift_message(kind),
                None,
            )
        return content_hash

    def _resolve_artifact_drift(self, context: StageContext, kind: str) -> None:
        context.store.resolve_open_findings(
            int(context.session["id"]),
            "artifact_drift",
            _artifact_drift_message(kind),
        )

    def _drift_response(self, context: StageContext, spec_hash: str | None, plan_hash: str | None) -> KernelResponse | None:
        session_id = int(context.session["id"])
        decision = detect_plan_or_task_drift(
            spec_hash,
            plan_hash,
            context.store.latest_artifact_revision(session_id, "plan"),
            context.store.latest_artifact_revision(session_id, "tasks"),
        )
        if decision is None:
            return None
        context.store.update_branch_session(session_id, recommended_next=decision.recommended_next, recommended_task_id=None)
        return KernelResponse(
            status=decision.status,
            message=decision.message,
            recommended_next=decision.recommended_next,
            findings=context.store.findings(session_id),
        )

    def _derive_recommendation(self, context: StageContext) -> NextRecommendation:
        if context.artifacts.read("spec") is None:
            return NextRecommendation(_loom_command("spec"))
        if context.artifacts.read("plan") is None:
            return NextRecommendation(_loom_command("plan"))
        tasks_content = context.artifacts.read("tasks")
        if tasks_content is None:
            return NextRecommendation(_loom_command("tasks"))

        session_id = int(context.session["id"])
        spec_hash = context.artifacts.hash_existing("spec")
        plan_hash = context.artifacts.hash_existing("plan")
        decision = detect_plan_or_task_drift(
            spec_hash,
            plan_hash,
            context.store.latest_artifact_revision(session_id, "plan"),
            context.store.latest_artifact_revision(session_id, "tasks"),
        )
        if decision is not None:
            return NextRecommendation(decision.recommended_next)

        tasks_hash = context.artifacts.hash_existing("tasks")
        if tasks_hash is None:
            return NextRecommendation(_loom_command("tasks"))
        tasks = parse_tasks(tasks_content)
        if not tasks:
            return NextRecommendation(_loom_command("tasks"))

        self._record_task_snapshots(context, tasks_content, tasks_hash)
        blocking = self._open_execution_blocking_findings(context)
        if blocking:
            return self._recommend_from_blocking_findings(context, blocking)

        task = self._select_recommended_task(context, tasks)
        if task is not None:
            return NextRecommendation(self._recommended_do(task.task_id), task.task_id)
        return NextRecommendation(_loom_command("ship"))

    def _recommended_do(self, task_id: str) -> str:
        return f"{_loom_command('do')} {task_id}"

    def _write_runtime_ref(
        self,
        context: StageContext,
        attempt_id: int,
        task_id: str,
        attempt_no: int,
        kind: str,
        filename_kind: str,
        content: str,
    ) -> str | None:
        ref = self._write_attempt_file_if_not_empty(context, task_id, attempt_no, filename_kind, content)
        if ref is not None:
            context.store.add_runtime_ref(attempt_id, kind, ref, _content_hash(context.request.cwd / ref))
        return ref

    def _write_attempt_file_if_not_empty(
        self,
        context: StageContext,
        task_id: str,
        attempt_no: int,
        filename_kind: str,
        content: str,
    ) -> str | None:
        if not content.strip():
            return None
        return context.evidence.write_attempt_file(task_id, attempt_no, filename_kind, content)


    def _open_execution_blocking_findings(self, context: StageContext) -> list[dict[str, Any]]:
        session_id = int(context.session["id"])
        return [
            finding
            for finding in context.store.open_blocking_findings(session_id)
            if finding.get("kind") != "verification_failure"
        ]

    def _recommend_from_blocking_findings(
        self,
        context: StageContext,
        findings: list[dict[str, Any]],
    ) -> NextRecommendation:
        for finding in findings:
            suggested_next = finding.get("suggested_next")
            if not suggested_next:
                continue
            command = _normalize_recommendation(str(suggested_next))
            if command == _loom_command("do"):
                attempt_id = finding.get("attempt_id")
                if attempt_id is None:
                    continue
                attempt = context.store.attempt(int(attempt_id))
                if attempt is None:
                    continue
                task_id = str(attempt["task_id"])
                return NextRecommendation(self._recommended_do(task_id), task_id)
            if command in {_loom_command("spec"), _loom_command("plan"), _loom_command("tasks"), _loom_command("ship")}:
                return NextRecommendation(command)
            if command.startswith(f"{_loom_command('do')} "):
                task_id = command.split(maxsplit=1)[1]
                return NextRecommendation(command, task_id)
        return NextRecommendation(None)

    def _blocking_allows_explicit_retry(
        self,
        context: StageContext,
        findings: list[dict[str, Any]],
        requested_task_id: str | None,
    ) -> bool:
        if not requested_task_id or not findings:
            return False
        for finding in findings:
            recommendation = self._recommend_from_blocking_findings(context, [finding])
            if recommendation.task_id != requested_task_id:
                return False
        return True

    def _supersede_open_findings_for_task(
        self,
        context: StageContext,
        findings: list[dict[str, Any]],
        task_id: str,
    ) -> None:
        for finding in findings:
            recommendation = self._recommend_from_blocking_findings(context, [finding])
            if recommendation.task_id != task_id:
                continue
            attempt_id = finding.get("attempt_id")
            if attempt_id is not None:
                context.store.supersede_open_findings_for_attempt(int(attempt_id))

    def _next_task_recommendation(self, context: StageContext, tasks: list[TaskDefinition]) -> NextRecommendation:
        next_task = self._select_recommended_task(context, tasks)
        if next_task is None:
            return NextRecommendation(_loom_command("ship"))
        return NextRecommendation(self._recommended_do(next_task.task_id), next_task.task_id)


    def _host_artifact_required_response(self, context: StageContext, kind: str) -> KernelResponse | None:
        if context.config.default_runtime != "claude-code" or context.request.args.get("artifact_file"):
            return None

        artifact_path = context.artifacts.relative(context.artifacts.path_for(kind))
        command = _loom_command("ship" if kind == "ship" else kind)
        register_command = f"loom stage {kind} --branch {context.request.branch_name} --arg artifact_file={artifact_path}"
        return KernelResponse(
            status="blocked",
            message=f"{kind} requires a host-authored artifact_file in claude-code mode",
            recommended_next=command,
            artifact_paths=[artifact_path],
            errors=["host_artifact_required"],
            extras={
                "stage": kind,
                "main_agent": ARTIFACT_STAGE_MAIN_AGENTS[kind],
                "reviewer_agent": ARTIFACT_STAGE_REVIEWERS.get(kind),
                "artifact_path": artifact_path,
                "register_command": register_command,
            },
        )


    def _artifact_content(
        self,
        context: StageContext,
        kind: str,
        fallback: Callable[[], str],
    ) -> tuple[str | None, KernelResponse | None]:
        artifact_file = context.request.args.get("artifact_file")
        if not artifact_file:
            return fallback(), None
        path = Path(str(artifact_file))
        if not path.is_absolute():
            path = context.request.cwd / path
        if not path.exists():
            return None, KernelResponse(status="failed", message=f"artifact_file not found: {path}", errors=["missing_artifact_file"])

        resolved_path = path.resolve()
        expected_path = context.artifacts.path_for(kind).resolve()
        if resolved_path != expected_path:
            return None, KernelResponse(
                status="failed",
                message=f"artifact_file must be {context.artifacts.relative(expected_path)}",
                errors=["invalid_artifact_file_location"],
            )
        return resolved_path.read_text(encoding="utf-8"), None

    def _verification_summary_content(self, context: StageContext, task: TaskDefinition) -> tuple[str, KernelResponse | None]:
        summary_file = context.request.args.get("verification_summary_file")
        if summary_file:
            path = Path(str(summary_file))
            if not path.is_absolute():
                path = context.request.cwd / path
            if not path.exists():
                return "", KernelResponse(
                    status="failed",
                    message=f"verification_summary_file not found: {path}",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    errors=["missing_verification_summary_file"],
                )
            try:
                return path.read_text(encoding="utf-8"), None
            except OSError as exc:
                return "", KernelResponse(
                    status="failed",
                    message=f"verification_summary_file cannot be read: {path}: {exc}",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    errors=["invalid_verification_summary_file"],
                )
        return str(context.request.args.get("verification_summary") or ""), None

    def _spec_fallback_input(self, context: StageContext) -> tuple[str, str | None]:
        args = context.request.args
        revision_note = str(args.get("revision_note") or "")
        if revision_note:
            return revision_note, context.artifacts.read("spec")

        requirement = str(args.get("requirement") or "")
        if requirement:
            return requirement, None

        text = str(args.get("text") or "")
        if text:
            return text, context.artifacts.read("spec")

        freeform = self._freeform_spec_arg(args)
        if freeform:
            return freeform, context.artifacts.read("spec")

        return "", None

    def _freeform_spec_arg(self, args: dict[str, str]) -> str:
        known = {"artifact_file", "requirement", "revision_note", "text"}
        bare_parts: list[str] = []
        gap: str | None = None
        for key, value in args.items():
            if key in known:
                continue
            if value:
                if key == "gap":
                    gap = str(value)
                continue
            bare_parts.append(str(key))

        if bare_parts:
            return " ".join(part.strip() for part in bare_parts if part.strip())
        return gap or ""


    def _run_spec(self, context: StageContext) -> KernelResponse:
        blocked = self._host_artifact_required_response(context, "spec")
        if blocked is not None:
            return blocked
        requirement, existing = self._spec_fallback_input(context)
        content, error = self._artifact_content(
            context,
            "spec",
            lambda: create_llm_client().draft_spec(requirement, existing, context.config.spec_language),
        )
        if error is not None:
            return error
        assert content is not None
        path, content_hash = context.artifacts.write("spec", content)
        session_id = int(context.session["id"])
        context.store.record_artifact_revision(session_id, "spec", context.artifacts.relative(path), content_hash)
        self._resolve_artifact_drift(context, "spec")
        context.store.update_branch_session(
            session_id,
            active_stage="spec",
            active_spec_hash=content_hash,
            recommended_next=_loom_command("plan"),
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok",
            message="spec.md generated",
            recommended_next=_loom_command("plan"),
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _run_plan(self, context: StageContext) -> KernelResponse:
        spec = context.artifacts.read("spec")
        if spec is None:
            return KernelResponse(status="failed", message="spec.md is required", recommended_next=_loom_command("spec"), errors=["missing_spec"])
        spec_hash = context.artifacts.hash_existing("spec")
        blocked = self._host_artifact_required_response(context, "plan")
        if blocked is not None:
            return blocked
        constraints = str(context.request.args.get("constraints") or context.request.args.get("revision_note") or "") or None
        content, error = self._artifact_content(
            context,
            "plan",
            lambda: create_llm_client().draft_plan(spec, constraints, context.config.spec_language),
        )
        if error is not None:
            return error
        assert content is not None
        path, content_hash = context.artifacts.write("plan", content)
        session_id = int(context.session["id"])
        context.store.record_artifact_revision(session_id, "plan", context.artifacts.relative(path), content_hash, based_on_spec_hash=spec_hash)
        self._resolve_artifact_drift(context, "plan")
        context.store.update_branch_session(
            session_id,
            active_stage="plan",
            active_spec_hash=spec_hash,
            active_plan_hash=content_hash,
            recommended_next=_loom_command("tasks"),
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok",
            message="plan.md generated",
            recommended_next=_loom_command("tasks"),
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _run_tasks(self, context: StageContext) -> KernelResponse:
        spec = context.artifacts.read("spec")
        plan = context.artifacts.read("plan")
        if spec is None:
            return KernelResponse(status="failed", message="spec.md is required", recommended_next=_loom_command("spec"), errors=["missing_spec"])
        if plan is None:
            return KernelResponse(status="failed", message="plan.md is required", recommended_next=_loom_command("plan"), errors=["missing_plan"])
        blocked = self._host_artifact_required_response(context, "tasks")
        if blocked is not None:
            return blocked
        spec_hash = context.artifacts.hash_existing("spec")
        plan_hash = context.artifacts.hash_existing("plan")
        preference = str(context.request.args.get("preference") or context.request.args.get("revision_note") or "") or None
        content, error = self._artifact_content(
            context,
            "tasks",
            lambda: create_llm_client().draft_tasks(spec, plan, preference, context.config.spec_language),
        )
        if error is not None:
            return error
        assert content is not None
        tasks = parse_tasks(content)
        if not tasks:
            return KernelResponse(
                status="failed",
                message="tasks.md artifact contains no parseable tasks",
                recommended_next=_loom_command("tasks"),
                errors=["invalid_tasks_format"],
            )
        path, tasks_hash = context.artifacts.write("tasks", content)
        session_id = int(context.session["id"])
        context.store.record_artifact_revision(
            session_id,
            "tasks",
            context.artifacts.relative(path),
            tasks_hash,
            based_on_spec_hash=spec_hash,
            based_on_plan_hash=plan_hash,
        )
        self._record_task_snapshots(context, content, tasks_hash)
        self._resolve_artifact_drift(context, "tasks")
        next_task = self._select_recommended_task(context, tasks)
        recommended_next = _loom_command("ship") if next_task is None else self._recommended_do(next_task.task_id)
        recommended_task_id = None if next_task is None else next_task.task_id
        context.store.update_branch_session(
            session_id,
            active_stage="tasks",
            active_spec_hash=spec_hash,
            active_plan_hash=plan_hash,
            active_tasks_hash=tasks_hash,
            recommended_next=recommended_next,
            recommended_task_id=recommended_task_id,
        )
        return KernelResponse(
            status="ok",
            message="tasks.md generated",
            recommended_next=recommended_next,
            recommended_task_id=recommended_task_id,
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _run_do(self, context: StageContext) -> KernelResponse:
        session_id = int(context.session["id"])
        tasks_content = context.artifacts.read("tasks")
        if tasks_content is None:
            return KernelResponse(status="failed", message="tasks.md is required", recommended_next=_loom_command("tasks"), errors=["missing_tasks"])

        spec_hash = context.artifacts.hash_existing("spec")
        plan_hash = context.artifacts.hash_existing("plan")
        tasks_hash = context.artifacts.hash_existing("tasks")
        if tasks_hash is None:
            return KernelResponse(status="failed", message="tasks.md is empty", recommended_next=_loom_command("tasks"), errors=["missing_tasks_hash"])

        drift = self._drift_response(context, spec_hash, plan_hash)
        if drift is not None:
            return drift

        tasks = parse_tasks(tasks_content)
        if not tasks:
            return KernelResponse(status="failed", message="no tasks found", recommended_next=_loom_command("tasks"), errors=["no_tasks"])
        self._record_task_snapshots(context, tasks_content, tasks_hash)

        action = str(context.request.args.get("action") or "").strip().lower()
        if action == "complete":
            return self._run_do_complete(context, tasks, session_id)
        if action == "seal-changes":
            return self._run_do_seal_changes(context, tasks, session_id)
        if action == "review-context":
            return KernelResponse(
                status="failed",
                message="review-context is no longer supported; host must use seal-changes",
                recommended_next=_loom_command("do"),
                errors=["legacy_do_action_not_supported"],
            )
        if action and action != "begin":
            return KernelResponse(status="failed", message=f"unsupported do action: {action}", recommended_next=_loom_command("do"), errors=["unsupported_do_action"])

        requested_task_id = str(context.request.args.get("task_id") or "").strip() or None
        blocking = self._open_execution_blocking_findings(context)
        explicit_retry = action == "begin" or context.config.default_runtime != "claude-code"
        if blocking and not (explicit_retry and self._blocking_allows_explicit_retry(context, blocking, requested_task_id)):
            recommendation = self._recommend_from_blocking_findings(context, blocking)
            return KernelResponse(
                status="blocked",
                message="open blocking finding exists",
                recommended_next=recommendation.command,
                recommended_task_id=recommendation.task_id,
                findings=blocking,
            )

        task = self._select_task(context, tasks)
        if task is None:
            requested = context.request.args.get("task_id")
            if requested:
                return KernelResponse(status="failed", message=f"task not found: {requested}", recommended_next=_loom_command("tasks"), errors=["task_not_found"])
            return KernelResponse(status="ok", message="all tasks already verified", recommended_next=_loom_command("ship"))

        latest_snapshot = context.store.latest_task_snapshot(session_id, task.task_id)
        latest_attempt = context.store.latest_attempt(session_id, task.task_id)
        decision = self.resolver.resolve(task, latest_snapshot, latest_attempt, False)
        if decision.action == "verified":
            recommendation = self._next_task_recommendation(context, tasks)
            return KernelResponse(status="ok", message=decision.message, recommended_next=recommendation.command, recommended_task_id=recommendation.task_id)
        if decision.action in {"blocked", "superseded"}:
            return KernelResponse(status="blocked", message=decision.message, recommended_next=decision.recommended_next)
        if action == "begin":
            if latest_attempt and latest_attempt.get("status") == "running" and latest_attempt.get("task_fingerprint") == task.fingerprint:
                return self._do_begin_response(task, int(latest_attempt["id"]), int(latest_attempt["attempt_no"]))
            if latest_attempt and decision.action in {"retry", "reattempt"}:
                context.store.supersede_open_findings_for_attempt(int(latest_attempt["id"]))
            else:
                self._supersede_open_findings_for_task(context, blocking, task.task_id)
            snapshot = _capture_working_tree_content_snapshot(context.request.cwd)
            if snapshot.get("errors"):
                return KernelResponse(
                    status="blocked",
                    message="attempt start snapshot could not be captured",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    extras=snapshot,
                    errors=list(snapshot["errors"]),
                )
            attempt_no = context.store.next_attempt_no(session_id, task.task_id)
            attempt_id = context.store.create_attempt(
                session_id,
                task.task_id,
                attempt_no,
                context.config.default_runtime,
                spec_hash,
                plan_hash,
                tasks_hash,
                task.fingerprint,
                str(snapshot.get("tree") or ""),
                str(snapshot.get("head") or ""),
                str(snapshot.get("snapshot_semantics") or ""),
                json.dumps(snapshot.get("status_summary") or {}, ensure_ascii=False, sort_keys=True),
            )
            return self._do_begin_response(task, attempt_id, attempt_no)

        if context.config.default_runtime == "claude-code":
            return KernelResponse(
                status="blocked",
                message="claude-code host runtime requires do action=begin and action=complete",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"task_id": task.task_id, "lane": task.lane, "complexity": task.complexity, "main_agent": _do_main_agent(task.lane)},
                errors=["host_runtime_requires_begin_complete"],
            )

        if latest_attempt and latest_attempt.get("status") == "running":
            context.store.update_attempt(int(latest_attempt["id"]), "abandoned", "abandoned during recovery")
        elif latest_attempt and decision.action in {"retry", "reattempt"}:
            context.store.supersede_open_findings_for_attempt(int(latest_attempt["id"]))
        else:
            self._supersede_open_findings_for_task(context, blocking, task.task_id)

        attempt_no = context.store.next_attempt_no(session_id, task.task_id)
        attempt_id = context.store.create_attempt(
            session_id,
            task.task_id,
            attempt_no,
            context.config.default_runtime,
            spec_hash,
            plan_hash,
            tasks_hash,
            task.fingerprint,
        )
        runtime_result = create_runtime_client(context.config.default_runtime).execute(context.request.cwd, task)
        self._write_runtime_ref(context, attempt_id, task.task_id, attempt_no, "stdout", "runtime.stdout.log", runtime_result.stdout)
        self._write_runtime_ref(context, attempt_id, task.task_id, attempt_no, "stderr", "runtime.stderr.log", runtime_result.stderr)

        verification_results = self.verifier.run(context.request.cwd, context.config.commands) if task.lane == "verify" else []
        verification_failed = False
        for index, result in enumerate(verification_results, start=1):
            verify_stdout_ref = self._write_attempt_file_if_not_empty(context, task.task_id, attempt_no, f"verify{index}.stdout.log", result.stdout)
            verify_stderr_ref = self._write_attempt_file_if_not_empty(context, task.task_id, attempt_no, f"verify{index}.stderr.log", result.stderr)
            context.store.record_verification(attempt_id, result.command, result.status, result.exit_code, verify_stdout_ref, verify_stderr_ref)
            if result.status == "failed":
                verification_failed = True

        status = attempt_status(task.lane, runtime_result.success, verification_failed)
        if task.lane == "verify" and status == "verified" and not any(result.status == "passed" for result in verification_results):
            status = "blocked"
        context.store.update_attempt(attempt_id, status, runtime_result.summary)
        if status == "verified":
            context.store.resolve_open_findings_for_attempt(attempt_id, "verification_failure")
        if status in {"failed", "blocked"}:
            context.store.add_finding(
                session_id,
                attempt_id,
                "verification_gap" if status == "blocked" else "verification_failure",
                "blocking",
                f"do attempt {status} for {task.task_id}",
                _loom_command("do"),
            )
        if status in {"failed", "blocked"}:
            recommendation = NextRecommendation(self._recommended_do(task.task_id), task.task_id)
        else:
            next_task = self._select_recommended_task(context, tasks)
            if next_task is None:
                recommendation = NextRecommendation(_loom_command("ship"))
            else:
                recommendation = NextRecommendation(self._recommended_do(next_task.task_id), next_task.task_id)
        context.store.update_branch_session(
            session_id,
            active_stage="do",
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
        )
        return KernelResponse(
            status="ok" if status in {"implemented", "verified"} else status,
            message=runtime_result.summary,
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
        )

    def _do_begin_response(self, task: TaskDefinition, attempt_id: int, attempt_no: int) -> KernelResponse:
        extras: dict[str, Any] = {
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "task_id": task.task_id,
            "task_title": task.title,
            "lane": task.lane,
            "complexity": task.complexity,
            "main_agent": _do_main_agent(task.lane),
            "reviewer_agent": "code-reviewer" if task.lane == "build" else None,
            "task_definition": task.raw,
        }
        if task.lane == "build":
            extras["host_internal_flow"] = {
                "user_visible": False,
                "sequence": ["run_main_agent", "seal_changes", "run_reviewer_agent", "complete_attempt"],
                "after_main_agent": {
                    "internal_action": "seal_changes",
                    "command_args": {"action": "seal-changes", "attempt_id": attempt_id},
                    "before_reviewer_agent": "code-reviewer",
                },
                "complete_requires": ["review_status=pass", "seal_revision=<latest-seal-revision>"],
            }
        return KernelResponse(
            status="ok",
            message="do attempt started",
            recommended_next=self._recommended_do(task.task_id),
            recommended_task_id=task.task_id,
            extras=extras,
        )

    def _run_do_seal_changes(self, context: StageContext, tasks: list[TaskDefinition], session_id: int) -> KernelResponse:
        attempt_id_value = context.request.args.get("attempt_id")
        if attempt_id_value is None:
            return KernelResponse(status="failed", message="attempt_id is required for seal-changes", recommended_next=_loom_command("do"), errors=["missing_attempt_id"])
        try:
            attempt_id = int(str(attempt_id_value))
        except ValueError:
            return KernelResponse(status="failed", message=f"invalid attempt_id: {attempt_id_value}", recommended_next=_loom_command("do"), errors=["invalid_attempt_id"])

        attempt = context.store.attempt(attempt_id)
        if attempt is None:
            return KernelResponse(status="failed", message=f"attempt not found: {attempt_id}", recommended_next=_loom_command("do"), errors=["attempt_not_found"])
        if int(attempt["branch_session_id"]) != session_id:
            return KernelResponse(status="failed", message=f"attempt does not belong to this branch session: {attempt_id}", recommended_next=_loom_command("do"), errors=["attempt_session_mismatch"])
        if attempt.get("status") != "running":
            return KernelResponse(status="failed", message=f"attempt is not running: {attempt_id}", recommended_next=_loom_command("do"), errors=["attempt_not_running"])
        start_tree = str(attempt.get("start_tree") or "")
        if not start_tree:
            return KernelResponse(status="failed", message=f"attempt missing start snapshot: {attempt_id}", recommended_next=_loom_command("do"), errors=["attempt_missing_start_snapshot"])
        task = next((item for item in tasks if item.task_id == attempt.get("task_id")), None)
        if task is None:
            return KernelResponse(status="failed", message=f"task not found for attempt: {attempt.get('task_id')}", recommended_next=_loom_command("tasks"), errors=["task_not_found"])
        if attempt.get("task_fingerprint") != task.fingerprint:
            return KernelResponse(status="failed", message=f"task definition changed during attempt: {task.task_id}", recommended_next=self._recommended_do(task.task_id), recommended_task_id=task.task_id, errors=["task_changed_during_attempt"])

        snapshot = _capture_working_tree_content_snapshot(context.request.cwd)
        if snapshot.get("errors"):
            return KernelResponse(
                status="blocked",
                message="current snapshot could not be captured to seal attempt changes",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras=snapshot,
                errors=list(snapshot["errors"]),
            )
        sealed_tree = str(snapshot.get("tree") or "")
        revision = int(attempt.get("latest_seal_revision") or 0) + 1
        changes = _build_attempt_changes(context.request.cwd, task, attempt, start_tree, sealed_tree, revision, snapshot)
        content = json.dumps(changes, ensure_ascii=False, indent=2, sort_keys=True)
        changes_ref = context.evidence.write_attempt_file(task.task_id, int(attempt["attempt_no"]), "attempt-changes.json", content)
        context.store.replace_runtime_ref(attempt_id, "attempt_changes", changes_ref, _content_hash(context.request.cwd / changes_ref))
        recorded_revision = context.store.record_sealed_changes(attempt_id, sealed_tree, changes_ref)
        sealed_diff_command = f"git diff --no-ext-diff --no-textconv {start_tree} {sealed_tree}"

        return KernelResponse(
            status="ok",
            message="attempt changes sealed",
            recommended_next=self._recommended_do(task.task_id),
            recommended_task_id=task.task_id,
            extras={
                "attempt_id": attempt_id,
                "task_id": task.task_id,
                "attempt_no": int(attempt["attempt_no"]),
                "review_scope": "attempt_scoped",
                "start_tree": start_tree,
                "sealed_tree": sealed_tree,
                "seal_revision": recorded_revision,
                "sealed_changes_ref": changes_ref,
                "sealed_diff_command": sealed_diff_command,
                "reviewer_handoff": {
                    "user_visible": False,
                    "agent": "code-reviewer",
                    "review_scope": "attempt_scoped",
                    "seal_revision": recorded_revision,
                    "sealed_changes_ref": changes_ref,
                    "sealed_diff_command": sealed_diff_command,
                    "do_not_review_full_worktree": True,
                },
            },
        )

    def _build_seal_changes_gate(self, context: StageContext, attempt: dict[str, Any], task: TaskDefinition, attempt_id: int) -> KernelResponse | None:
        latest_revision = int(attempt.get("latest_seal_revision") or 0)
        latest_sealed_tree = str(attempt.get("latest_sealed_tree") or "")
        if latest_revision <= 0 or not latest_sealed_tree:
            return KernelResponse(
                status="blocked",
                message="sealed attempt changes are required before implemented completion",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True)},
                errors=["sealed_changes_missing"],
            )
        if "review_context_revision" in context.request.args:
            return KernelResponse(
                status="failed",
                message="review_context_revision is no longer supported; host must use seal_revision",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["legacy_complete_argument_not_supported"],
            )
        requested_revision_value = context.request.args.get("seal_revision")
        if requested_revision_value is not None:
            try:
                requested_revision = int(str(requested_revision_value))
            except ValueError:
                requested_revision = -1
            if requested_revision != latest_revision:
                return KernelResponse(
                    status="blocked",
                    message="seal revision does not match latest sealed attempt changes",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    extras={"host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True)},
                    errors=["seal_revision_mismatch"],
                )
        review_status = str(context.request.args.get("review_status") or attempt.get("latest_review_status") or "").strip().lower()
        if review_status != "pass":
            if review_status:
                context.store.update_review_status(attempt_id, review_status)
            return KernelResponse(
                status="blocked",
                message="sealed attempt changes have not passed review",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["review_not_passed"],
            )
        snapshot = _capture_working_tree_content_snapshot(context.request.cwd)
        if snapshot.get("errors"):
            extras = dict(snapshot)
            extras["host_recovery"] = self._seal_changes_recovery(attempt_id, rerun_reviewer=True)
            return KernelResponse(
                status="blocked",
                message="current snapshot could not be captured for sealed changes freshness check",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras=extras,
                errors=["sealed_changes_generation_failed"],
            )
        if str(snapshot.get("tree") or "") != latest_sealed_tree:
            return KernelResponse(
                status="blocked",
                message="sealed attempt changes are stale; host should reseal and rerun code-reviewer before completing this attempt",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={
                    "current_tree": snapshot.get("tree"),
                    "latest_sealed_tree": latest_sealed_tree,
                    "host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True),
                },
                errors=["sealed_changes_stale"],
            )
        context.store.update_review_status(attempt_id, "pass")
        return None

    def _seal_changes_recovery(self, attempt_id: int, rerun_reviewer: bool) -> dict[str, Any]:
        return {
            "user_visible": False,
            "internal_action": "seal_changes",
            "command_args": {"action": "seal-changes", "attempt_id": attempt_id},
            "rerun_reviewer": rerun_reviewer,
        }

    def _run_do_complete(self, context: StageContext, tasks: list[TaskDefinition], session_id: int) -> KernelResponse:
        attempt_id_value = context.request.args.get("attempt_id")
        if attempt_id_value is None:
            return KernelResponse(status="failed", message="attempt_id is required for do complete", recommended_next=_loom_command("do"), errors=["missing_attempt_id"])
        try:
            attempt_id = int(str(attempt_id_value))
        except ValueError:
            return KernelResponse(status="failed", message=f"invalid attempt_id: {attempt_id_value}", recommended_next=_loom_command("do"), errors=["invalid_attempt_id"])

        attempt = context.store.attempt(attempt_id)
        if attempt is None:
            return KernelResponse(status="failed", message=f"attempt not found: {attempt_id}", recommended_next=_loom_command("do"), errors=["attempt_not_found"])
        if int(attempt["branch_session_id"]) != session_id:
            return KernelResponse(status="failed", message=f"attempt does not belong to this branch session: {attempt_id}", recommended_next=_loom_command("do"), errors=["attempt_session_mismatch"])
        if attempt.get("status") != "running":
            return KernelResponse(status="failed", message=f"attempt is not running: {attempt_id}", recommended_next=_loom_command("do"), errors=["attempt_not_running"])
        task = next((item for item in tasks if item.task_id == attempt.get("task_id")), None)
        if task is None:
            return KernelResponse(status="failed", message=f"task not found for attempt: {attempt.get('task_id')}", recommended_next=_loom_command("tasks"), errors=["task_not_found"])
        if attempt.get("task_fingerprint") != task.fingerprint:
            return KernelResponse(
                status="failed",
                message=f"task definition changed during attempt: {task.task_id}",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["task_changed_during_attempt"],
            )

        status = str(context.request.args.get("status") or "").strip().lower()
        if status == "success":
            status = "verified" if task.lane == "verify" else "implemented"
        expected_success = "verified" if task.lane == "verify" else "implemented"
        if status not in {expected_success, "failed", "blocked"}:
            return KernelResponse(
                status="failed",
                message=f"invalid completion status for {task.lane} task: {status}",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["invalid_completion_status"],
            )

        final_status = status
        if task.lane == "build" and final_status == "implemented":
            gate = self._build_seal_changes_gate(context, attempt, task, attempt_id)
            if gate is not None:
                return gate
        summary = str(context.request.args.get("summary") or f"Host runtime completed {task.task_id}: {task.title}")
        verification_summary, verification_summary_error = self._verification_summary_content(context, task)
        if verification_summary_error is not None:
            return verification_summary_error
        if task.lane == "verify" and final_status == "verified" and not verification_summary.strip():
            explicit_summary = str(context.request.args.get("summary") or "")
            if explicit_summary.strip():
                verification_summary = explicit_summary
        stdout = str(context.request.args.get("stdout") or "")
        stderr = str(context.request.args.get("stderr") or "")
        attempt_no = int(attempt["attempt_no"])
        self._write_runtime_ref(context, attempt_id, task.task_id, attempt_no, "stdout", "runtime.stdout.log", stdout)
        self._write_runtime_ref(context, attempt_id, task.task_id, attempt_no, "stderr", "runtime.stderr.log", stderr)
        verification_summary_ref = self._write_runtime_ref(
            context,
            attempt_id,
            task.task_id,
            attempt_no,
            "verification_summary",
            "verification-summary.json",
            verification_summary,
        )
        if task.lane == "verify" and verification_summary_ref is not None:
            verification_status = "passed" if final_status == "verified" else final_status
            context.store.record_verification(
                attempt_id,
                "claude-code verification",
                verification_status,
                0 if verification_status == "passed" else None,
                None,
                None,
                summary_ref=verification_summary_ref,
            )
        if task.lane == "verify" and final_status == "verified" and not self._has_verification_evidence(context, attempt_id):
            final_status = "blocked"
            summary = f"{summary}\nMissing verification evidence for {task.task_id}"
        context.store.update_attempt(attempt_id, final_status, summary)

        if final_status in {"failed", "blocked"}:
            context.store.add_finding(
                session_id,
                attempt_id,
                "verification_failure" if final_status == "failed" else "execution_blocked",
                "blocking",
                f"do attempt {final_status} for {task.task_id}",
                _loom_command("do"),
            )
            recommendation = NextRecommendation(self._recommended_do(task.task_id), task.task_id)
        else:
            if final_status == "verified":
                context.store.resolve_open_findings_for_attempt(attempt_id, "verification_failure")
            next_task = self._select_recommended_task(context, tasks)
            recommendation = NextRecommendation(_loom_command("ship")) if next_task is None else NextRecommendation(self._recommended_do(next_task.task_id), next_task.task_id)

        context.store.update_branch_session(
            session_id,
            active_stage="do",
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
        )
        response_status = "ok" if final_status in {"implemented", "verified"} else final_status
        return KernelResponse(
            status=response_status,
            message=summary,
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
            extras={"attempt_id": attempt_id, "task_id": task.task_id, "status": final_status},
        )


    def _run_ship(self, context: StageContext) -> KernelResponse:
        session_id = int(context.session["id"])
        spec_hash = context.artifacts.hash_existing("spec")
        plan_hash = context.artifacts.hash_existing("plan")
        tasks_hash = context.artifacts.hash_existing("tasks")
        drift = self._drift_response(context, spec_hash, plan_hash)
        if drift is not None:
            return drift
        blocked = self._host_artifact_required_response(context, "ship")
        if blocked is not None:
            return blocked
        tasks_content = context.artifacts.read("tasks") or ""
        tasks = parse_tasks(tasks_content)
        if tasks_hash:
            self._record_task_snapshots(context, tasks_content, tasks_hash)
        blocking = context.store.open_blocking_findings(session_id)
        attempts = context.store.attempts(session_id)
        completed_tasks = []
        task_facts = []
        runtime_refs = []
        readiness_blockers = [finding["message"] for finding in blocking]
        verification_warnings = []
        for task in tasks:
            latest = context.store.latest_attempt(session_id, task.task_id)
            completed = bool(latest and self._task_completed(task, latest))
            task_facts.append(
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "lane": task.lane,
                    "complexity": task.complexity,
                    "fingerprint": task.fingerprint,
                    "completed": completed,
                    "latest_attempt_id": latest.get("id") if latest else None,
                    "latest_attempt_no": latest.get("attempt_no") if latest else None,
                    "latest_status": latest.get("status") if latest else None,
                }
            )
            if not completed:
                readiness_blockers.append(f"{task.task_id}: task not completed")
                continue

            completed_tasks.append(task.task_id)
            attempt_id = int(latest["id"])
            refs = self._structured_runtime_refs(context, latest)
            runtime_refs.extend(refs)
            for gap in _runtime_ref_integrity_gaps(context.request.cwd, refs):
                readiness_blockers.append(f"{task.task_id}: {gap}")
                context.store.add_finding(
                    session_id,
                    attempt_id,
                    "evidence_integrity_gap",
                    "blocking",
                    f"{task.task_id}: {gap}",
                    _loom_command("ship"),
                )
            if task.lane == "verify" and not self._has_verification_evidence(context, attempt_id):
                verification_warnings.append(f"{task.task_id}: verification evidence missing")
                readiness_blockers.append(f"{task.task_id}: verification evidence missing")
            elif task.lane == "verify" and any(item["status"] == "skipped_config_missing" for item in context.store.verifications_for_attempt(attempt_id)):
                verification_warnings.append(f"{task.task_id}: verification command missing")
                readiness_blockers.append(f"{task.task_id}: verification command missing")
        all_completed = bool(tasks) and len(completed_tasks) == len(tasks)
        ship_status = "shippable" if all_completed and not readiness_blockers else "blocked"
        facts = {
            "status": ship_status,
            "spec_hash": spec_hash or "",
            "plan_hash": plan_hash or "",
            "tasks_hash": tasks_hash or "",
            "tasks": task_facts,
            "completed_tasks": completed_tasks,
            "verification_summary": self._verification_summary(len(completed_tasks), len(tasks), verification_warnings),
            "open_findings": [finding["message"] for finding in blocking],
            "readiness_blockers": readiness_blockers,
            "runtime_refs": runtime_refs,
            "attempt_count": len(attempts),
        }
        content, error = self._artifact_content(context, "ship", lambda: create_llm_client().draft_ship_summary(facts, context.config.spec_language))
        if error is not None:
            return error
        assert content is not None
        path, ship_hash = context.artifacts.write("ship", content)
        context.store.record_artifact_revision(
            session_id,
            "ship",
            context.artifacts.relative(path),
            ship_hash,
            based_on_spec_hash=spec_hash,
            based_on_plan_hash=plan_hash,
            based_on_tasks_hash=tasks_hash,
        )
        self._resolve_artifact_drift(context, "ship")
        response_status = "ok" if ship_status == "shippable" else "blocked"
        recommendation = NextRecommendation(None) if ship_status == "shippable" else self._derive_recommendation(context)
        context.store.update_branch_session(
            session_id,
            active_stage="ship",
            active_ship_hash=ship_hash,
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
        )
        return KernelResponse(
            status=response_status,
            message=f"release.md generated: {ship_status}",
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
            artifact_paths=[context.artifacts.relative(path)],
            findings=blocking,
        )

    def _verification_summary(self, completed_count: int, task_count: int, warnings: list[str]) -> str:
        summary = f"{completed_count}/{task_count} tasks completed"
        if warnings:
            summary += "\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
        return summary

    def _has_verification_evidence(self, context: StageContext, attempt_id: int) -> bool:
        return any(item.get("status") == "passed" for item in context.store.verifications_for_attempt(attempt_id))

    def _structured_runtime_refs(self, context: StageContext, attempt: dict[str, Any]) -> list[dict[str, Any]]:
        attempt_id = int(attempt["id"])
        return [
            {
                "task_id": attempt.get("task_id"),
                "attempt_no": attempt.get("attempt_no"),
                "kind": ref.get("kind"),
                "path": ref.get("path"),
                "content_hash": ref.get("content_hash"),
                "created_at": ref.get("created_at"),
            }
            for ref in context.store.runtime_refs(attempt_id)
        ]

    def _task_completed(self, task: TaskDefinition, attempt: dict[str, Any]) -> bool:
        status = attempt.get("status")
        if task.lane == "verify":
            return status == "verified" and attempt.get("task_fingerprint") == task.fingerprint
        return status == "implemented" and attempt.get("task_fingerprint") == task.fingerprint


    def _record_task_snapshots(self, context: StageContext, tasks_content: str, tasks_hash: str) -> None:
        session_id = int(context.session["id"])
        for task in parse_tasks(tasks_content):
            context.store.upsert_task_snapshot(session_id, task.task_id, task.fingerprint, tasks_hash, task.title)


    def _select_recommended_task(self, context: StageContext, tasks: list[TaskDefinition]) -> TaskDefinition | None:
        session_id = int(context.session["id"])
        for task in tasks:
            latest = context.store.latest_attempt(session_id, task.task_id)
            if latest and latest.get("status") == "failed" and latest.get("task_fingerprint") == task.fingerprint:
                return task
        for task in tasks:
            latest = context.store.latest_attempt(session_id, task.task_id)
            if latest is None or not self._task_completed(task, latest):
                return task
        return None

    def _select_task(self, context: StageContext, tasks: list[TaskDefinition]) -> TaskDefinition | None:
        requested = context.request.args.get("task_id")
        if requested:
            for task in tasks:
                if task.task_id == requested:
                    return task
            return None
        return self._select_recommended_task(context, tasks)


def _do_main_agent(lane: str) -> str:
    return "verifier" if lane == "verify" else "builder"


def _capture_working_tree_content_snapshot(repo_path: Path) -> dict[str, Any]:
    lines, status_error = _git_status_lines(repo_path)
    result: dict[str, Any] = {
        "snapshot_semantics": "working_tree_content",
        "modifies_real_index": False,
        "ignored_included": False,
        "status_summary": {"git_status_short": lines},
        "errors": [],
    }
    if status_error:
        result["errors"].append(status_error)
        return result
    if any(line[:2].strip() == "U" or "U" in line[:2] for line in lines):
        result["errors"].append("snapshot_conflicted_index")
        return result
    try:
        sparse = subprocess.run(["git", "config", "--bool", "core.sparseCheckout"], cwd=repo_path, capture_output=True, text=True)
        if sparse.returncode == 0 and sparse.stdout.strip().lower() == "true":
            result["errors"].append("snapshot_sparse_checkout_unsupported")
            return result
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, capture_output=True, text=True)
        if head.returncode != 0:
            result["errors"].append(head.stderr.strip() or "snapshot_head_unavailable")
            return result
        with TemporaryDirectory(prefix="codeloom-index-") as tmp_dir:
            index_path = str(Path(tmp_dir) / "index")
            env = os.environ | {"GIT_INDEX_FILE": index_path}
            read_tree = subprocess.run(["git", "read-tree", "HEAD"], cwd=repo_path, env=env, capture_output=True, text=True)
            if read_tree.returncode != 0:
                result["errors"].append(read_tree.stderr.strip() or "snapshot_read_tree_failed")
                return result
            add = subprocess.run(["git", "add", "-A"], cwd=repo_path, env=env, capture_output=True, text=True)
            if add.returncode != 0:
                result["errors"].append(add.stderr.strip() or "snapshot_add_failed")
                return result
            remove_runtime = subprocess.run(["git", "rm", "-r", "--cached", "--ignore-unmatch", ".loom"], cwd=repo_path, env=env, capture_output=True, text=True)
            if remove_runtime.returncode != 0:
                result["errors"].append(remove_runtime.stderr.strip() or "snapshot_remove_runtime_failed")
                return result
            write_tree = subprocess.run(["git", "write-tree"], cwd=repo_path, env=env, capture_output=True, text=True)
            if write_tree.returncode != 0:
                result["errors"].append(write_tree.stderr.strip() or "snapshot_write_tree_failed")
                return result
    except FileNotFoundError:
        result["errors"].append("git executable not found")
        return result
    result["head"] = head.stdout.strip()
    result["tree"] = write_tree.stdout.strip()
    return result


def _build_attempt_changes(
    repo_path: Path,
    task: TaskDefinition,
    attempt: dict[str, Any],
    start_tree: str,
    sealed_tree: str,
    seal_revision: int,
    sealed_snapshot: dict[str, Any],
) -> dict[str, Any]:
    files = _diff_name_status(repo_path, start_tree, sealed_tree)
    numstat = _diff_numstat(repo_path, start_tree, sealed_tree)
    raw = _diff_raw(repo_path, start_tree, sealed_tree)
    for item in files:
        stats = numstat.get(item["path"], {})
        raw_entry = raw.get(item["path"], {})
        item["category"] = _change_category(item["path"])
        item["additions"] = stats.get("additions", 0)
        item["deletions"] = stats.get("deletions", 0)
        item["binary"] = stats.get("binary", False)
        item["old_mode"] = raw_entry.get("old_mode")
        item["new_mode"] = raw_entry.get("new_mode")
        item["old_oid"] = raw_entry.get("old_oid")
        item["new_oid"] = raw_entry.get("new_oid")
    summary = {
        "files_changed": len(files),
        "added_files": sum(1 for item in files if str(item["status"]).startswith("A")),
        "modified_files": sum(1 for item in files if str(item["status"]).startswith("M")),
        "deleted_files": sum(1 for item in files if str(item["status"]).startswith("D")),
        "renamed_files": sum(1 for item in files if str(item["status"]).startswith("R")),
        "additions": sum(int(item.get("additions") or 0) for item in files),
        "deletions": sum(int(item.get("deletions") or 0) for item in files),
        "binary_files": sum(1 for item in files if item.get("binary")),
    }
    try:
        start_status = json.loads(str(attempt.get("start_status_json") or "{}"))
    except json.JSONDecodeError:
        start_status = {}
    return {
        "kind": "attempt_changes",
        "version": 2,
        "task_id": task.task_id,
        "attempt_no": int(attempt["attempt_no"]),
        "seal_revision": seal_revision,
        "scope": "attempt",
        "snapshot_semantics": "working_tree_content",
        "diff_source": {
            "start_tree": start_tree,
            "sealed_tree": sealed_tree,
            "patch_persisted": False,
            "tree_objects_long_term_reliable": False,
        },
        "files": files,
        "summary": summary,
        "status_summary": {
            "start": start_status,
            "sealed": sealed_snapshot.get("status_summary") or {},
        },
        "review": {
            "scope": "attempt_scoped",
            "status": "pending",
            "patch_persisted": False,
        },
        "errors": [],
    }


def _diff_name_status(repo_path: Path, start_tree: str, sealed_tree: str) -> list[dict[str, Any]]:
    output, error = _git_diff_z(repo_path, "--name-status", start_tree, sealed_tree)
    if error:
        return []
    tokens = [token for token in output.split("\0") if token]
    files: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        status = tokens[index]
        index += 1
        if status.startswith(("R", "C")) and index + 1 < len(tokens):
            old_path = tokens[index]
            path = tokens[index + 1]
            index += 2
        elif index < len(tokens):
            old_path = None
            path = tokens[index]
            index += 1
        else:
            break
        files.append({"path": path, "old_path": old_path, "status": status})
    return files


def _diff_raw(repo_path: Path, start_tree: str, sealed_tree: str) -> dict[str, dict[str, str]]:
    output, error = _git_diff_z(repo_path, "--raw", start_tree, sealed_tree)
    if error:
        return {}
    tokens = [token for token in output.split("\0") if token]
    raw: dict[str, dict[str, str]] = {}
    index = 0
    while index < len(tokens):
        header = tokens[index]
        index += 1
        if not header.startswith(":") or index >= len(tokens):
            continue
        parts = header[1:].split()
        if len(parts) < 5:
            continue
        old_mode, new_mode, old_oid, new_oid, status = parts[:5]
        if status.startswith(("R", "C")) and index + 1 < len(tokens):
            index += 1
            path = tokens[index]
            index += 1
        else:
            path = tokens[index]
            index += 1
        raw[path] = {"old_mode": old_mode, "new_mode": new_mode, "old_oid": old_oid, "new_oid": new_oid}
    return raw


def _diff_numstat(repo_path: Path, start_tree: str, sealed_tree: str) -> dict[str, dict[str, Any]]:
    output, error = _git_diff_z(repo_path, "--numstat", start_tree, sealed_tree)
    if error:
        return {}
    stats: dict[str, dict[str, Any]] = {}
    for token in [item for item in output.split("\0") if item]:
        parts = token.split("\t")
        if len(parts) < 3:
            continue
        additions_text, deletions_text, path = parts[0], parts[1], parts[-1]
        binary = additions_text == "-" or deletions_text == "-"
        stats[path] = {
            "additions": 0 if binary else int(additions_text),
            "deletions": 0 if binary else int(deletions_text),
            "binary": binary,
        }
    return stats


def _git_diff_z(repo_path: Path, mode: str, start_tree: str, sealed_tree: str) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--no-textconv", mode, "-z", start_tree, sealed_tree],
            cwd=repo_path,
            capture_output=True,
        )
    except FileNotFoundError:
        return "", "git executable not found"
    if result.returncode != 0:
        return "", result.stderr.decode("utf-8", errors="replace").strip() or f"git diff exited with {result.returncode}"
    return result.stdout.decode("utf-8", errors="replace"), None


def _collect_host_diff(repo_path: Path) -> str:
    try:
        diff = subprocess.run(["git", "diff", "--"], cwd=repo_path, capture_output=True, text=True)
        status = subprocess.run(["git", "status", "--short"], cwd=repo_path, capture_output=True, text=True)
    except FileNotFoundError:
        return ""
    chunks: list[str] = []
    if diff.returncode == 0 and diff.stdout.strip():
        chunks.append(diff.stdout.strip())
    if status.returncode == 0:
        untracked = [line[3:].strip() for line in status.stdout.splitlines() if line.startswith("?? ")]
        if untracked:
            chunks.append("Untracked files:\n" + "\n".join(f"- {path}" for path in untracked))
    return "\n\n".join(chunks).strip()


def _collect_host_change_inventory(repo_path: Path, task_id: str, attempt_no: int) -> str:
    lines, _ = _git_status_lines(repo_path)
    return json.dumps(_inventory_from_git_status_lines(task_id, attempt_no, lines), ensure_ascii=False, indent=2, sort_keys=True)


def _collect_host_git_status_snapshot(repo_path: Path, task_id: str, attempt_no: int, phase: str) -> str:
    lines, error = _git_status_lines(repo_path)
    snapshot: dict[str, Any] = {
        "task_id": task_id,
        "attempt_no": attempt_no,
        "phase": phase,
        "cwd": str(repo_path),
        "git_status_short": lines,
        "inventory": _inventory_from_git_status_lines(task_id, attempt_no, lines),
    }
    if error:
        snapshot["error"] = error
    return json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)


def _git_status_lines(repo_path: Path) -> tuple[list[str], str | None]:
    try:
        status = subprocess.run(["git", "status", "--short"], cwd=repo_path, capture_output=True, text=True)
    except FileNotFoundError:
        return [], "git executable not found"
    if status.returncode != 0:
        error = status.stderr.strip() or f"git status exited with {status.returncode}"
        return [], error
    return [line for line in status.stdout.splitlines() if line.strip()], None


def _inventory_from_git_status_lines(task_id: str, attempt_no: int, lines: list[str]) -> dict[str, Any]:
    inventory: dict[str, Any] = {
        "task_id": task_id,
        "attempt_no": attempt_no,
        "tracked_modified": [],
        "tracked_deleted": [],
        "untracked_new": [],
        "renamed": [],
        "categories": {"code": [], "sql": [], "config": [], "ui": [], "doc": [], "unknown": []},
    }
    for line in lines:
        marker = line[:2]
        path = line[3:].strip() if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
            inventory["renamed"].append(path)
        elif marker == "??":
            inventory["untracked_new"].append(path)
        elif "D" in marker:
            inventory["tracked_deleted"].append(path)
        else:
            inventory["tracked_modified"].append(path)
        inventory["categories"][_change_category(path)].append(path)
    return inventory


def _change_category(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".sql":
        return "sql"
    if suffix in {".yml", ".yaml", ".json", ".toml", ".ini", ".env", ".properties"}:
        return "config"
    if suffix in {".html", ".css", ".scss", ".vue", ".tsx", ".jsx", ".jsp"}:
        return "ui"
    if suffix in {".md", ".rst", ".txt"}:
        return "doc"
    if suffix:
        return "code"
    return "unknown"


def _content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_ref_integrity_gaps(repo_path: Path, refs: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    for ref in refs:
        path_value = ref.get("path")
        expected_hash = ref.get("content_hash")
        if not path_value or not expected_hash:
            gaps.append(f"runtime ref missing hash: {ref.get('kind') or 'unknown'}")
            continue
        path = repo_path / str(path_value)
        if not path.exists():
            gaps.append(f"runtime ref missing file: {path_value}")
            continue
        actual_hash = _content_hash(path)
        if actual_hash != expected_hash:
            gaps.append(f"runtime ref hash mismatch: {path_value}")
    return gaps
