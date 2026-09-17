from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from codeloom.app.constitution import constitution_status
from codeloom.app.init_project import ProjectConfig, load_project_config
from codeloom.app.request import KernelRequest
from codeloom.app.response import KernelResponse
from codeloom.kernel.artifacts import (
    TaskDefinition,
    TaskPacket,
    branch_slug,
    parse_tasks,
    task_identity_errors,
    task_relation_errors,
)
from codeloom.kernel.attempts import attempt_status
from codeloom.kernel.snapshots import capture_repository_snapshot, git_environment
from codeloom.kernel.clients import create_llm_client, create_runtime_client
from codeloom.kernel.drift import derive_artifact_states, detect_plan_or_task_drift, earliest_artifact_repair
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
    artifact_contents: dict[str, str | None] = field(default_factory=dict)
    artifact_hashes: dict[str, str | None] = field(default_factory=dict)
    parsed_tasks: list[TaskDefinition] | None = None
    parsed_tasks_hash: str | None = None
    task_snapshots_recorded: set[str] = field(default_factory=set)
    latest_attempts_by_task: dict[str, dict[str, Any]] | None = None
    effective_attempts_by_task: dict[str, dict[str, Any]] | None = None
    latest_artifact_revisions: dict[str, dict[str, Any]] | None = None

@dataclass(frozen=True)
class NextRecommendation:
    command: str | None
    task_id: str | None = None
    task_title: str | None = None

def _loom_command(command: str) -> str:
    return f"/loom-{command}"

def _artifact_drift_message(kind: str) -> str:
    return f"{kind}.md changed outside registered artifact revision"
ARTIFACT_STAGE_MAIN_ROLES = {
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

STAGE_POSITIONS = {stage: index for index, stage in enumerate(("spec", "plan", "tasks", "do", "ship"))}
CONTINUATION_ROUTES = {
    "spec": {"spec"},
    "plan": {"spec", "plan"},
    "tasks": {"plan", "tasks"},
    "do": {"spec", "plan", "tasks"},
    "ship": {"spec", "plan", "tasks"},
}


def _normalize_command(command: str) -> str:
    if command.startswith("/loom-"):
        return command.removeprefix("/loom-")
    return command.removeprefix("/loom:")


def _task_contract_errors(content: str) -> list[str]:
    return task_identity_errors(content) + task_relation_errors(content)


class StageRunner:
    def __init__(self) -> None:
        self.verifier = ShellVerifier()
        self.resolver = ContractRevisionResolver()

    def run(self, request: KernelRequest) -> KernelResponse:
        command = _normalize_command(request.command)
        action = str(request.args.get("action") or "").strip().lower()
        context = self._context(request)
        if command == "do" and action == "unlock":
            return self._run_do_unlock(context)
        if command == "do" and (
            action in {"complete", "seal-changes", "record-review", "route"}
            or (action in {"", "begin"} and context.store.active_attempt(int(context.session["id"])) is not None)
        ):
            return self._run_do(context)
        redirected = self._continuation_redirect(context, command)
        if redirected is not None:
            return redirected
        self._refresh_recommendation(context)
        if command != "do" and command in CONTINUATION_ROUTES and action == "route":
            return self._run_continuation_route(context, command)
        if command != "do" and command in CONTINUATION_ROUTES and action:
            return KernelResponse(
                status="failed",
                message=f"unsupported {command} action: {action}",
                recommended_next=_loom_command(command),
                errors=["unsupported_stage_action"],
            )
        if command == "spec" and "gap" in request.args:
            return KernelResponse(
                status="failed",
                message="unsupported spec argument: gap; use requirement, revision_note, text, or action=route",
                recommended_next=_loom_command("spec"),
                errors=["unsupported_stage_argument"],
            )
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
        return StageContext(
            request=request,
            config=config,
            branch_slug=slug,
            store=store,
            session=session,
            artifacts=MarkdownArtifactStore(request.cwd, config.artifact_root, slug),
            evidence=FileEvidenceStore(request.cwd, slug),
        )

    def _refresh_recommendation(self, context: StageContext) -> NextRecommendation:
        recommendation = self._derive_recommendation(context)
        if (
            recommendation.command != context.session.get("recommended_next")
            or recommendation.task_id != context.session.get("recommended_task_id")
        ):
            context.store.update_branch_session(
                int(context.session["id"]),
                recommended_next=recommendation.command,
                recommended_task_id=recommendation.task_id,
            )
            context.session["recommended_next"] = recommendation.command
            context.session["recommended_task_id"] = recommendation.task_id
        return recommendation

    def _continuation_redirect(self, context: StageContext, command: str) -> KernelResponse | None:
        target = str(context.session.get("continuation_stage") or "")
        if target not in STAGE_POSITIONS or command not in STAGE_POSITIONS:
            return None
        source = str(context.session.get("continuation_source_stage") or "")
        if source == "do" and command == "do":
            root_task_id = str(context.session.get("continuation_task_id") or "")
            requested_task_id = str(context.request.args.get("task_id") or "")
            attempt_value = context.request.args.get("attempt_id")
            if not requested_task_id and attempt_value is not None:
                try:
                    attempt = context.store.attempt(int(str(attempt_value)))
                except ValueError:
                    attempt = None
                requested_task_id = str((attempt or {}).get("task_id") or "")
            tasks_content = self._artifact_text(context, "tasks") or ""
            if requested_task_id and not _task_contract_errors(tasks_content):
                tasks = self._current_tasks(context)
                if requested_task_id not in self._affected_task_ids(tasks, root_task_id):
                    return None
        if STAGE_POSITIONS[command] <= STAGE_POSITIONS[target]:
            return None
        reason = str(context.session.get("continuation_reason") or "")
        return KernelResponse(
            status="noop",
            message=f"continue at {target} before {command}: {reason}",
            recommended_next=_loom_command(target),
            extras={
                "continuation_source_stage": source,
                "continuation_stage": target,
                "continuation_reason": reason,
                "continuation_attempt_id": context.session.get("continuation_attempt_id"),
                "continuation_task_id": context.session.get("continuation_task_id"),
            },
        )

    def _run_continuation_route(self, context: StageContext, source: str) -> KernelResponse:
        target = str(context.request.args.get("target_stage") or "").strip().lower()
        reason = str(context.request.args.get("reason") or "").strip()
        if context.request.args.get("artifact_file"):
            return KernelResponse(
                status="failed",
                message="artifact_file cannot be supplied with action=route",
                recommended_next=_loom_command(source),
                errors=["invalid_continuation_route"],
            )
        if target not in CONTINUATION_ROUTES[source] or not reason:
            return KernelResponse(
                status="failed",
                message=f"{source} action=route requires target_stage in {sorted(CONTINUATION_ROUTES[source])} and a non-empty reason",
                recommended_next=_loom_command(source),
                errors=["invalid_continuation_route"],
            )
        if source == "ship":
            tasks = self._current_tasks(context)
            if not tasks or len(self._effective_attempts(context, tasks)) != len(tasks):
                recommendation = self._derive_recommendation(context)
                return KernelResponse(
                    status="blocked",
                    message="Ship cannot route an upstream delivery gap before Do is complete",
                    recommended_next=recommendation.command,
                    recommended_task_id=recommendation.task_id,
                    recommended_task_title=recommendation.task_title,
                    errors=["ship_prerequisites_incomplete"],
                )

        session_id = int(context.session["id"])
        recommendation = _loom_command(target)
        context.store.update_branch_session(
            session_id,
            continuation_source_stage=source,
            continuation_stage=target,
            continuation_reason=reason,
            continuation_attempt_id=None,
            continuation_task_id=None,
            active_stage=source,
            recommended_next=recommendation,
            recommended_task_id=None,
        )
        context.session.update({
            "continuation_source_stage": source,
            "continuation_stage": target,
            "continuation_reason": reason,
            "continuation_attempt_id": None,
            "continuation_task_id": None,
            "active_stage": source,
            "recommended_next": recommendation,
            "recommended_task_id": None,
        })
        return KernelResponse(
            status="ok",
            message=f"{source} will continue at {target}: {reason}",
            recommended_next=recommendation,
            extras={
                "continuation_source_stage": source,
                "continuation_stage": target,
                "continuation_reason": reason,
            },
        )

    def _artifact_text(self, context: StageContext, kind: str) -> str | None:
        if kind not in context.artifact_contents:
            context.artifact_contents[kind] = context.artifacts.read(kind)
        return context.artifact_contents[kind]

    def _artifact_hash(self, context: StageContext, kind: str) -> str | None:
        if kind not in context.artifact_hashes:
            content = self._artifact_text(context, kind)
            context.artifact_hashes[kind] = None if content is None else MarkdownArtifactStore.content_hash(content)
        return context.artifact_hashes[kind]

    def _current_tasks(self, context: StageContext) -> list[TaskDefinition]:
        tasks_hash = self._artifact_hash(context, "tasks")
        if tasks_hash is None:
            return []
        if context.parsed_tasks_hash != tasks_hash:
            context.parsed_tasks = parse_tasks(self._artifact_text(context, "tasks") or "")
            context.parsed_tasks_hash = tasks_hash
        return context.parsed_tasks or []

    def _cache_artifact(self, context: StageContext, kind: str, content: str, content_hash: str) -> None:
        context.artifact_contents[kind] = content
        context.artifact_hashes[kind] = content_hash
        if kind == "tasks":
            context.parsed_tasks = None
            context.parsed_tasks_hash = None

    def _latest_artifact_revisions(self, context: StageContext) -> dict[str, dict[str, Any]]:
        if context.latest_artifact_revisions is None:
            context.latest_artifact_revisions = context.store.latest_artifact_revisions(int(context.session["id"]))
        return context.latest_artifact_revisions
    def _artifact_states(self, context: StageContext, execution_hash: str | None = None) -> dict[str, dict[str, object]]:
        task_error = None
        tasks_content = self._artifact_text(context, "tasks")
        if tasks_content is not None:
            errors = _task_contract_errors(tasks_content)
            if errors:
                task_error = ", ".join(errors)
            elif not self._current_tasks(context):
                task_error = "tasks.md contains no parseable tasks"
        return derive_artifact_states(
            {kind: self._artifact_hash(context, kind) for kind in ("spec", "plan", "tasks", "ship")},
            self._latest_artifact_revisions(context),
            execution_hash,
            task_error,
        )

    def _stage_input(
        self,
        context: StageContext,
        kind: str,
        execution_hash: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        snapshot = context.store.artifact_input_snapshot(int(context.session["id"]), kind, execution_hash)
        return snapshot, context.store.artifact_input_token(snapshot)

    def _artifact_input_args(
        self,
        context: StageContext,
        kind: str,
        execution_hash: str | None = None,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        if kind == "spec":
            return {}, {}
        snapshot, token = self._stage_input(context, kind, execution_hash)
        args = {"input_token": token}
        if execution_hash is not None:
            args["ship_input_hash"] = execution_hash
        return args, {"input_snapshot": snapshot, "input_token": token}

    def _register_artifact(
        self,
        context: StageContext,
        kind: str,
        path: Path,
        content_hash: str,
        expected_token: str | None = None,
        execution_hash: str | None = None,
    ) -> tuple[dict[str, Any] | None, KernelResponse | None]:
        expected_token = expected_token or str(context.request.args.get("input_token") or "") or None
        if kind != "spec" and expected_token is None and context.request.args.get("artifact_file"):
            args, extras = self._artifact_input_args(context, kind, execution_hash)
            artifact_path, handoff = self._artifact_handoff(context, kind, args, extras)
            return None, KernelResponse(
                status="failed",
                message=f"{kind} registration requires the frozen input token from its handoff",
                recommended_next=_loom_command("ship" if kind == "ship" else kind),
                artifact_paths=[artifact_path],
                errors=["missing_stage_input_token"],
                extras=handoff,
            )
        if kind != "spec" and expected_token is None:
            _, expected_token = self._stage_input(context, kind, execution_hash)
        result = context.store.register_artifact_if_inputs_current(
            int(context.session["id"]),
            kind,
            context.artifacts.relative(path),
            content_hash,
            expected_token,
            execution_hash,
        )
        if result["status"] == "inputs_changed":
            register_args = {"input_token": str(result["input_token"])}
            if execution_hash is not None:
                register_args["ship_input_hash"] = execution_hash
            artifact_path, extras = self._artifact_handoff(
                context,
                kind,
                register_args,
                {"input_snapshot": result["input_snapshot"], "input_token": result["input_token"]},
            )
            return None, KernelResponse(
                status="noop",
                message=f"{kind} inputs changed while the artifact was being authored; reauthor from the refreshed handoff",
                recommended_next=_loom_command("ship" if kind == "ship" else kind),
                artifact_paths=[artifact_path],
                errors=[f"{kind}_inputs_changed"],
                extras={
                    **extras,
                    "host_recovery": {"user_visible": False, "internal_action": f"reauthor_{kind}"},
                },
            )
        context.latest_artifact_revisions = None
        context.session[f"active_{kind}_hash"] = content_hash
        context.session["active_stage"] = kind
        if context.session.get("continuation_stage") == kind:
            for field in (
                "continuation_source_stage",
                "continuation_stage",
                "continuation_reason",
                "continuation_attempt_id",
                "continuation_task_id",
            ):
                context.session[field] = None
        return result, None

    def _resolve_artifact_drift(self, context: StageContext, kind: str) -> None:
        context.store.resolve_open_findings(
            int(context.session["id"]),
            "artifact_drift",
            _artifact_drift_message(kind),
        )

    def _lineage_advisories(self, context: StageContext, spec_hash: str | None, plan_hash: str | None) -> list[dict[str, str]]:
        revisions = self._latest_artifact_revisions(context)
        decision = detect_plan_or_task_drift(
            spec_hash,
            plan_hash,
            revisions.get("plan"),
            revisions.get("tasks"),
        )
        if decision is None:
            return []
        return [{
            "message": decision.message,
            "recommended_next": decision.recommended_next,
            "scope": "artifact_lineage",
        }]

    def _drift_response(
        self,
        context: StageContext,
        spec_hash: str | None,
        plan_hash: str | None,
    ) -> KernelResponse | None:
        advisories = self._lineage_advisories(context, spec_hash, plan_hash)
        if not advisories:
            return None
        advisory = advisories[0]
        session_id = int(context.session["id"])
        context.store.update_branch_session(
            session_id,
            recommended_next=advisory["recommended_next"],
            recommended_task_id=None,
        )
        return KernelResponse(
            status="noop",
            message=advisory["message"],
            recommended_next=advisory["recommended_next"],
            findings=context.store.findings(session_id),
        )

    def _derive_recommendation(self, context: StageContext) -> NextRecommendation:
        active_attempt = context.store.active_attempt(int(context.session["id"]))
        if active_attempt is not None:
            task_id = str(active_attempt["task_id"])
            return NextRecommendation(self._recommended_do(task_id), task_id)

        continuation = str(context.session.get("continuation_stage") or "")
        if continuation in CONTINUATION_ROUTES:
            return NextRecommendation(_loom_command(continuation))

        states = self._artifact_states(context)
        repair = earliest_artifact_repair(states, "tasks")
        if repair is not None:
            return NextRecommendation(repair)

        tasks = self._current_tasks(context)
        tasks_hash = self._artifact_hash(context, "tasks")
        if not tasks or tasks_hash is None:
            return NextRecommendation(_loom_command("tasks"))
        task = self._select_recommended_task(context, tasks)
        if task is not None:
            return NextRecommendation(self._recommended_do(task.task_id), task.task_id, task.title)
        ship_packet = self._build_ship_packet(context, tasks)
        ship_input_hash = self._ship_input_hash(ship_packet)
        ship_states = self._artifact_states(context, ship_input_hash)
        if ship_states["ship"]["state"] == "current":
            return NextRecommendation(None)
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


    def _next_task_recommendation(self, context: StageContext, tasks: list[TaskDefinition]) -> NextRecommendation:
        next_task = self._select_recommended_task(context, tasks)
        if next_task is None:
            return NextRecommendation(_loom_command("ship"))
        return NextRecommendation(self._recommended_do(next_task.task_id), next_task.task_id, next_task.title)

    def _project_profile(self, context: StageContext) -> dict[str, Any]:
        return {
            "languages": list(context.config.languages),
            "frameworks": list(context.config.frameworks),
            "modules": list(context.config.modules),
            "commands": dict(context.config.commands),
        }

    def _constitution_projection(self, context: StageContext) -> dict[str, Any]:
        status = constitution_status(
            context.request.cwd,
            context.config.constitution_path,
            context.config.constitution_hash,
        )
        status["advisory"] = None if status["usable"] else "continue_without_constitution"
        return status

    def _artifact_handoff(
        self,
        context: StageContext,
        kind: str,
        register_args: dict[str, str] | None = None,
        handoff_extras: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        artifact_path = context.artifacts.relative(context.artifacts.path_for(kind))
        register_command = f"loom stage {kind} --branch {context.request.branch_name} --arg artifact_file={artifact_path}"
        for name, value in (register_args or {}).items():
            register_command += f" --arg {name}={value}"
        extras = {
            "handoff": "author_artifact",
            "stage": kind,
            "main_role": ARTIFACT_STAGE_MAIN_ROLES[kind],
            "reviewer_agent": ARTIFACT_STAGE_REVIEWERS.get(kind),
            "artifact_path": artifact_path,
            "register_command": register_command,
            "constitution": self._constitution_projection(context),
            "project_profile": self._project_profile(context),
        }
        extras.update(handoff_extras or {})
        return artifact_path, extras

    def _host_artifact_handoff_response(
        self,
        context: StageContext,
        kind: str,
        register_args: dict[str, str] | None = None,
        handoff_extras: dict[str, Any] | None = None,
    ) -> KernelResponse | None:
        if context.config.default_runtime != "claude-code" or context.request.args.get("artifact_file"):
            return None

        artifact_path, extras = self._artifact_handoff(context, kind, register_args, handoff_extras)
        command = _loom_command("ship" if kind == "ship" else kind)
        return KernelResponse(
            status="noop",
            message=f"{kind} is ready for host artifact authoring",
            recommended_next=command,
            artifact_paths=[artifact_path],
            extras=extras,
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
        artifact_path, extras = self._artifact_handoff(context, kind)
        path = Path(str(artifact_file))
        if not path.is_absolute():
            path = context.request.cwd / path
        if not path.exists():
            return None, KernelResponse(
                status="failed",
                message=f"artifact_file not found: {path}",
                recommended_next=_loom_command("ship" if kind == "ship" else kind),
                artifact_paths=[artifact_path],
                errors=["missing_artifact_file"],
                extras=extras,
            )

        resolved_path = path.resolve()
        expected_path = context.artifacts.path_for(kind).resolve()
        if resolved_path != expected_path:
            return None, KernelResponse(
                status="failed",
                message=f"artifact_file must be {artifact_path}",
                recommended_next=_loom_command("ship" if kind == "ship" else kind),
                artifact_paths=[artifact_path],
                errors=["invalid_artifact_file_location"],
                extras=extras,
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

    def _review_summary_content(
        self,
        context: StageContext,
        task: TaskDefinition,
        status: str,
        seal_revision: int,
    ) -> tuple[str, KernelResponse | None]:
        summary = str(context.request.args.get("review_summary") or context.request.args.get("summary") or "").strip()
        if summary:
            return json.dumps(
                {
                    "result_type": "review_result",
                    "status": status,
                    "review_scope": "attempt_scoped",
                    "seal_revision": seal_revision,
                    "summary": summary,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ), None
        return "", KernelResponse(
            status="failed",
            message="record-review requires a non-empty review_summary",
            recommended_next=self._recommended_do(task.task_id),
            recommended_task_id=task.task_id,
            errors=["missing_review_summary"],
        )

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
        known = {"action", "artifact_file", "gap", "reason", "requirement", "revision_note", "target_stage", "text"}
        bare_parts: list[str] = []
        for key, value in args.items():
            if key in known:
                continue
            if value:
                continue
            bare_parts.append(str(key))

        return " ".join(part.strip() for part in bare_parts if part.strip())


    def _run_spec(self, context: StageContext) -> KernelResponse:
        handoff = self._host_artifact_handoff_response(context, "spec")
        if handoff is not None:
            return handoff
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
        _, registration_error = self._register_artifact(context, "spec", path, content_hash)
        if registration_error is not None:
            return registration_error
        self._resolve_artifact_drift(context, "spec")
        context.store.update_branch_session(
            int(context.session["id"]),
            recommended_next=_loom_command("plan"),
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok",
            message="spec.md registered",
            recommended_next=_loom_command("plan"),
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _run_plan(self, context: StageContext) -> KernelResponse:
        states = self._artifact_states(context)
        repair = earliest_artifact_repair(states, "spec")
        if repair is not None:
            return KernelResponse(
                status="noop",
                message="plan authoring requires the current registered spec",
                recommended_next=repair,
                errors=["plan_input_not_authoritative"],
                extras={"artifact_states": states},
            )
        spec = self._artifact_text(context, "spec") or ""
        input_snapshot, input_token = self._stage_input(context, "plan")
        handoff = self._host_artifact_handoff_response(
            context,
            "plan",
            {"input_token": input_token},
            {"input_snapshot": input_snapshot, "input_token": input_token},
        )
        if handoff is not None:
            return handoff
        spec_hash = str(self._latest_artifact_revisions(context)["spec"]["content_hash"])
        constraints = str(context.request.args.get("constraints") or context.request.args.get("revision_note") or "") or None
        content, error = self._artifact_content(
            context,
            "plan",
            lambda: create_llm_client().draft_plan(
                spec,
                constraints,
                context.config.spec_language,
                spec_hash,
            ),
        )
        if error is not None:
            return error
        assert content is not None
        path, content_hash = context.artifacts.write("plan", content)
        registration_token = (
            str(context.request.args.get("input_token") or "")
            if context.request.args.get("artifact_file")
            else input_token
        )
        _, registration_error = self._register_artifact(
            context, "plan", path, content_hash, expected_token=registration_token
        )
        if registration_error is not None:
            return registration_error
        self._resolve_artifact_drift(context, "plan")
        context.store.update_branch_session(
            int(context.session["id"]),
            recommended_next=_loom_command("tasks"),
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok",
            message="plan.md registered",
            recommended_next=_loom_command("tasks"),
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _run_tasks(self, context: StageContext) -> KernelResponse:
        states = self._artifact_states(context)
        repair = earliest_artifact_repair(states, "plan")
        if repair is not None:
            return KernelResponse(
                status="noop",
                message="tasks authoring requires the current registered spec and plan",
                recommended_next=repair,
                errors=["tasks_input_not_authoritative"],
                extras={"artifact_states": states},
            )
        spec = self._artifact_text(context, "spec") or ""
        plan = self._artifact_text(context, "plan") or ""
        input_snapshot, input_token = self._stage_input(context, "tasks")
        handoff = self._host_artifact_handoff_response(
            context,
            "tasks",
            {"input_token": input_token},
            {"input_snapshot": input_snapshot, "input_token": input_token},
        )
        if handoff is not None:
            return handoff
        preference = str(context.request.args.get("preference") or context.request.args.get("revision_note") or "") or None
        content, error = self._artifact_content(
            context,
            "tasks",
            lambda: create_llm_client().draft_tasks(spec, plan, preference, context.config.spec_language),
        )
        if error is not None:
            return error
        assert content is not None
        identity_errors = _task_contract_errors(content)
        if identity_errors:
            return KernelResponse(
                status="failed",
                message="tasks.md contains conflicting or unsupported execution identity metadata",
                recommended_next=_loom_command("tasks"),
                errors=identity_errors,
            )
        tasks = parse_tasks(content)
        if not tasks:
            return KernelResponse(
                status="failed",
                message="tasks.md artifact contains no parseable tasks",
                recommended_next=_loom_command("tasks"),
                errors=["invalid_tasks_format"],
            )
        path, tasks_hash = context.artifacts.write("tasks", content)
        self._cache_artifact(context, "tasks", content, tasks_hash)
        registration_token = (
            str(context.request.args.get("input_token") or "")
            if context.request.args.get("artifact_file")
            else input_token
        )
        _, registration_error = self._register_artifact(
            context, "tasks", path, tasks_hash, expected_token=registration_token
        )
        if registration_error is not None:
            return registration_error
        self._record_task_snapshots(context, tasks, tasks_hash)
        self._resolve_artifact_drift(context, "tasks")
        recommendation = self._next_task_recommendation(context, tasks)
        context.store.update_branch_session(
            int(context.session["id"]),
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
        )
        return KernelResponse(
            status="ok",
            message="tasks.md registered",
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
            recommended_task_title=recommendation.task_title,
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _unlock_command(self, context: StageContext, attempt_id: int) -> str:
        return (
            f"loom stage do --branch {context.request.branch_name} "
            f"--arg action=unlock --arg attempt_id={attempt_id}"
        )

    def _run_do_unlock(self, context: StageContext) -> KernelResponse:
        attempt_value = context.request.args.get("attempt_id")
        completed_status = str(context.request.args.get("status") or "").strip().lower() or None
        if completed_status is not None and completed_status not in {"implemented", "verified"}:
            return KernelResponse(
                status="failed",
                message="unlock status must be implemented or verified",
                recommended_next=_loom_command("do"),
                errors=["invalid_unlock_status"],
            )
        if completed_status is not None and attempt_value is None:
            return KernelResponse(
                status="failed",
                message="attempt_id is required when manually completing an unlocked attempt",
                recommended_next=_loom_command("do"),
                errors=["missing_attempt_id"],
            )
        try:
            attempt_id = int(str(attempt_value)) if attempt_value is not None else None
        except ValueError:
            return KernelResponse(
                status="failed",
                message=f"invalid attempt_id: {attempt_value}",
                recommended_next=_loom_command("do"),
                errors=["invalid_attempt_id"],
            )
        result = context.store.unlock_do_attempt(
            int(context.session["id"]),
            attempt_id,
            completed_status,
            str(context.request.args.get("summary") or "").strip() or None,
        )
        outcome = str(result["result"])
        status = {
            "completed": "ok",
            "unlocked": "ok",
            "already_inactive": "noop",
            "not_found": "failed",
            "session_mismatch": "failed",
        }[outcome]
        messages = {
            "completed": f"Do attempt manually recorded as {completed_status} by explicit user action",
            "unlocked": "Do mechanical block released; no completion was asserted",
            "already_inactive": "Do attempt is already inactive and has no matching continuation",
            "not_found": "no Do attempt is available to unlock",
            "session_mismatch": "attempt does not belong to this branch session",
        }
        errors = [] if outcome in {"completed", "unlocked", "already_inactive"} else [f"unlock_{outcome}"]
        recommendation = NextRecommendation(_loom_command("do"))
        if outcome == "completed":
            refreshed_session = context.store.branch_session(context.request.branch_name)
            if refreshed_session is not None:
                context.session = refreshed_session
            recommendation = self._refresh_recommendation(context)
        return KernelResponse(
            status=status,
            message=messages[outcome],
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
            recommended_task_title=recommendation.task_title,
            errors=errors,
            extras={"unlock_result": outcome, **{key: value for key, value in result.items() if key != "result"}},
        )

    def _load_attempt_task(
        self,
        context: StageContext,
        attempt: dict[str, Any],
    ) -> tuple[TaskDefinition | None, KernelResponse | None]:
        attempt_id = int(attempt["id"])
        packet_ref = str(attempt.get("task_packet_ref") or "")
        try:
            content = attempt.get("task_packet_json")
            if content is None:
                if not packet_ref:
                    raise ValueError("task packet is missing")
                resolved = (context.request.cwd / packet_ref).resolve()
                if not resolved.is_relative_to(context.evidence.root.resolve()):
                    raise ValueError("task packet is outside the evidence root")
                content = resolved.read_text(encoding="utf-8")
            packet = TaskPacket.from_canonical_json(content)
            if packet.content_hash != attempt.get("task_packet_hash"):
                raise ValueError("task packet hash does not match the attempt")
            if packet.version != str(attempt.get("task_packet_version") or ""):
                raise ValueError("task packet version does not match the attempt")
            if packet.task_id != str(attempt.get("task_id")) or packet.task_fingerprint != attempt.get("task_fingerprint"):
                raise ValueError("task packet identity does not match the attempt")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return None, KernelResponse(
                status="blocked",
                message=f"frozen Task Packet is unavailable for attempt {attempt_id}: {exc}",
                recommended_next=self._recommended_do(str(attempt.get("task_id") or "")),
                recommended_task_id=str(attempt.get("task_id") or "") or None,
                errors=["task_packet_integrity_error"],
                extras={
                    "attempt_id": attempt_id,
                    "unlock_command": self._unlock_command(context, attempt_id),
                },
            )
        return TaskDefinition(
            task_id=packet.task_id,
            title=packet.title,
            raw=packet.raw,
            fingerprint=packet.task_fingerprint,
            lane=packet.lane,
            complexity=packet.complexity,
            revision=packet.revision,
            depends_on=packet.depends_on,
            validates=packet.validates,
            covered_by=packet.covered_by,
            relations_declared=bool(packet.depends_on or packet.validates or packet.covered_by),
        ), None

    def _recovery_tasks(
        self,
        context: StageContext,
        attempt: dict[str, Any],
        frozen_task: TaskDefinition,
    ) -> list[TaskDefinition]:
        states = self._artifact_states(context)
        if (
            states["tasks"]["state"] == "current"
            and states["tasks"]["registered_hash"] == attempt.get("based_on_tasks_hash")
        ):
            tasks = self._current_tasks(context)
            if any(
                task.task_id == frozen_task.task_id and task.fingerprint == frozen_task.fingerprint
                for task in tasks
            ):
                return tasks
        return [frozen_task]


    def _run_do(self, context: StageContext) -> KernelResponse:
        session_id = int(context.session["id"])
        action = str(context.request.args.get("action") or "").strip().lower()
        if action == "review-context":
            return KernelResponse(
                status="failed",
                message="review-context is no longer supported; host must use seal-changes",
                recommended_next=_loom_command("do"),
                errors=["legacy_do_action_not_supported"],
            )
        if action not in {"", "begin", "retry", "complete", "seal-changes", "record-review", "route"}:
            return KernelResponse(status="failed", message=f"unsupported do action: {action}", recommended_next=_loom_command("do"), errors=["unsupported_do_action"])

        requested_task_id = str(context.request.args.get("task_id") or "").strip() or None
        attempt: dict[str, Any] | None = None
        attempt_value = context.request.args.get("attempt_id")
        if action in {"complete", "seal-changes", "record-review", "route"}:
            if attempt_value is None:
                return KernelResponse(
                    status="failed",
                    message=f"attempt_id is required for do {action}",
                    recommended_next=_loom_command("do"),
                    errors=["missing_attempt_id"],
                )
            try:
                attempt_id = int(str(attempt_value))
            except ValueError:
                return KernelResponse(
                    status="failed",
                    message="attempt_id must be an integer",
                    recommended_next=_loom_command("do"),
                    errors=["invalid_attempt_id"],
                )
            attempt = context.store.attempt(attempt_id)
            if attempt is None:
                return KernelResponse(
                    status="failed",
                    message=f"attempt {attempt_id} was not found",
                    recommended_next=_loom_command("do"),
                    errors=["attempt_not_found"],
                )
        active_attempt = context.store.active_attempt(session_id)
        if attempt is not None and action in {"complete", "seal-changes", "record-review", "route"}:
            if int(attempt["branch_session_id"]) != session_id:
                return KernelResponse(status="failed", message="attempt does not belong to this branch session", recommended_next=_loom_command("do"), errors=["attempt_session_mismatch"])
            frozen_task, packet_error = self._load_attempt_task(context, attempt)
            if packet_error is not None:
                return packet_error
            assert frozen_task is not None
            frozen_tasks = self._recovery_tasks(context, attempt, frozen_task)
            if action == "complete":
                return self._run_do_complete(context, frozen_tasks, session_id)
            if action == "seal-changes":
                return self._run_do_seal_changes(context, frozen_tasks, session_id)
            if action == "record-review":
                return self._run_do_record_review(context, frozen_tasks, session_id)
            return self._run_do_route(context, frozen_tasks, session_id)

        if active_attempt is not None and action in {"", "begin"}:
            active_task, packet_error = self._load_attempt_task(context, active_attempt)
            if packet_error is not None:
                return packet_error
            assert active_task is not None
            if requested_task_id and requested_task_id != active_task.task_id:
                return KernelResponse(
                    status="blocked",
                    message=f"attempt {active_attempt['id']} for {active_task.task_id} must finish before {requested_task_id}",
                    recommended_next=self._recommended_do(active_task.task_id),
                    recommended_task_id=active_task.task_id,
                    recommended_task_title=active_task.title,
                    extras={"active_attempt_id": int(active_attempt["id"]), "requested_task_id": requested_task_id},
                    errors=["active_attempt_exists"],
                )
            if active_attempt.get("status") == "completing":
                candidate_ref = active_attempt.get("completion_candidate_ref")
                return KernelResponse(
                    status="ok",
                    message="do attempt completion is ready to resume",
                    recommended_next=self._recommended_do(active_task.task_id),
                    recommended_task_id=active_task.task_id,
                    recommended_task_title=active_task.title,
                    extras={
                        "attempt_id": int(active_attempt["id"]),
                        "task_id": active_task.task_id,
                        "status": "completing",
                        "completion_token": active_attempt.get("completion_token"),
                        "completion_status": active_attempt.get("completion_status"),
                        "completion_summary": active_attempt.get("completion_summary"),
                        "completion_candidate_ref": candidate_ref,
                        "completion_candidate_hash": active_attempt.get("completion_candidate_hash"),
                        "host_recovery": {
                            "user_visible": False,
                            "internal_action": "resume_complete" if active_attempt.get("completion_candidate_json") is not None or candidate_ref else "resubmit_completion_candidate",
                            "command_args": {"action": "complete", "attempt_id": int(active_attempt["id"])},
                        },
                    },
                )
            return self._do_begin_response(
                context,
                active_task,
                int(active_attempt["id"]),
                int(active_attempt["attempt_no"]),
                active_attempt,
                resumed=True,
            )

        states = self._artifact_states(context)
        repair = earliest_artifact_repair(states, "tasks")
        if repair is not None:
            return KernelResponse(
                status="noop",
                message="new Do attempt requires current registered Spec, Plan, and Tasks inputs",
                recommended_next=repair,
                errors=["do_inputs_not_authoritative"],
                extras={"artifact_states": states, "blocked_new_attempt": True},
            )
        tasks_content = self._artifact_text(context, "tasks") or ""
        tasks = self._current_tasks(context)
        tasks_hash = self._artifact_hash(context, "tasks")
        if not tasks or tasks_hash is None:
            return KernelResponse(status="failed", message="no tasks found", recommended_next=_loom_command("tasks"), errors=["no_tasks"])
        self._record_task_snapshots(context, tasks, tasks_hash)
        revisions = self._latest_artifact_revisions(context)
        spec_hash = str(revisions["spec"]["content_hash"])
        plan_hash = str(revisions["plan"]["content_hash"])

        task = self._select_task(context, tasks)
        if task is None:
            if requested_task_id:
                return KernelResponse(status="failed", message=f"task not found: {requested_task_id}", recommended_next=_loom_command("tasks"), errors=["task_not_found"])
            return KernelResponse(status="ok", message="all tasks already verified", recommended_next=_loom_command("ship"))

        effective_attempts = self._effective_attempts(context, tasks)
        if task.task_id in effective_attempts and action != "retry":
            recommendation = self._next_task_recommendation(context, tasks)
            return KernelResponse(
                status="ok",
                message=f"task already {effective_attempts[task.task_id]['status']}",
                recommended_next=recommendation.command,
                recommended_task_id=recommendation.task_id,
                recommended_task_title=recommendation.task_title,
                extras={"task_id": task.task_id, "effective_attempt_id": effective_attempts[task.task_id]["id"], "skipped": True},
            )

        blockers = self._task_blockers(context, tasks, task)
        if blockers:
            root = self._root_task_blockers(context, tasks, task)[0]
            root_task = next(item for item in tasks if item.task_id == root)
            return KernelResponse(
                status="blocked",
                message=f"task {task.task_id} requires current result from {', '.join(blockers)}",
                recommended_next=self._recommended_do(root),
                recommended_task_id=root,
                recommended_task_title=root_task.title,
                extras={
                    "root_task_id": root,
                    "blocked_task_id": task.task_id,
                    "blocked_by": list(blockers),
                    "affected_task_ids": list(self._affected_task_ids(tasks, root)),
                },
                errors=["task_prerequisite_incomplete"],
            )

        latest_snapshot = context.store.latest_task_snapshot(session_id, task.task_id)
        latest_attempt = context.store.latest_attempt(session_id, task.task_id)
        decision = self.resolver.resolve(task, latest_snapshot, latest_attempt, False)
        if action != "retry" and decision.action == "verified":
            recommendation = self._next_task_recommendation(context, tasks)
            return KernelResponse(status="ok", message=decision.message, recommended_next=recommendation.command, recommended_task_id=recommendation.task_id, recommended_task_title=recommendation.task_title)
        if decision.action in {"blocked", "superseded"}:
            return KernelResponse(status="blocked", message=decision.message, recommended_next=decision.recommended_next)
        if action == "retry":
            retry_error = self._do_retry_error(context, tasks, task, session_id)
            if retry_error is not None:
                return retry_error
        if action in {"begin", "retry"}:
            if context.config.git_repositories_error:
                snapshot = {"errors": [context.config.git_repositories_error]}
            elif context.config.git_repositories is not None:
                snapshot = capture_repository_snapshot(context.request.cwd, context.config.git_repositories)
            else:
                snapshot = _capture_working_tree_content_snapshot(context.request.cwd)
            if snapshot.get("errors"):
                return KernelResponse(
                    status="blocked",
                    message="attempt start snapshot could not be captured",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    recommended_task_title=task.title,
                    extras=snapshot,
                    errors=list(snapshot["errors"]),
                )
            attempt, created = self._start_attempt(
                context,
                tasks,
                task,
                spec_hash,
                plan_hash,
                tasks_hash,
                snapshot,
            )
            active_task = next(item for item in tasks if item.task_id == attempt["task_id"])
            if active_task.task_id != task.task_id:
                return KernelResponse(
                    status="blocked",
                    message=f"attempt {attempt['id']} for {active_task.task_id} must finish before {task.task_id}",
                    recommended_next=self._recommended_do(active_task.task_id),
                    recommended_task_id=active_task.task_id,
                    recommended_task_title=active_task.title,
                    extras={"active_attempt_id": int(attempt["id"]), "requested_task_id": task.task_id},
                    errors=["active_attempt_exists"],
                )
            if created and latest_attempt is not None:
                context.store.supersede_attempt(int(latest_attempt["id"]), "superseded by a new task attempt")
                context.store.supersede_open_findings_for_attempt(int(latest_attempt["id"]))
            return self._do_begin_response(
                context,
                active_task,
                int(attempt["id"]),
                int(attempt["attempt_no"]),
                attempt,
                resumed=not created,
            )

        if context.config.default_runtime == "claude-code":
            return KernelResponse(
                status="blocked",
                message="claude-code host runtime requires do action=begin and action=complete",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"task_id": task.task_id, "lane": task.lane, "complexity": task.complexity, "main_role": _do_main_role(task.lane)},
                errors=["host_runtime_requires_begin_complete"],
            )

        attempt, created = self._start_attempt(
            context,
            tasks,
            task,
            spec_hash,
            plan_hash,
            tasks_hash,
            {},
        )
        active_task = next(item for item in tasks if item.task_id == attempt["task_id"])
        if active_task.task_id != task.task_id:
            return KernelResponse(
                status="blocked",
                message=f"attempt {attempt['id']} for {active_task.task_id} must finish before {task.task_id}",
                recommended_next=self._recommended_do(active_task.task_id),
                recommended_task_id=active_task.task_id,
                recommended_task_title=active_task.title,
                errors=["active_attempt_exists"],
            )
        if created and latest_attempt is not None:
            context.store.supersede_attempt(int(latest_attempt["id"]), "superseded by a new task attempt")
            context.store.supersede_open_findings_for_attempt(int(latest_attempt["id"]))
        attempt_id = int(attempt["id"])
        attempt_no = int(attempt["attempt_no"])
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
        self._invalidate_latest_attempts(context)
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
        recommendation = self._next_task_recommendation(context, tasks)
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
            recommended_task_title=recommendation.task_title,
        )

    def _do_begin_response(
        self,
        context: StageContext,
        task: TaskDefinition,
        attempt_id: int,
        attempt_no: int,
        attempt: dict[str, Any] | None = None,
        resumed: bool = False,
    ) -> KernelResponse:
        packet = TaskPacket.from_task(task)
        packet_ref = str((attempt or {}).get("task_packet_ref") or "")
        packet_hash = str((attempt or {}).get("task_packet_hash") or packet.content_hash)
        packet_version = str((attempt or {}).get("task_packet_version") or packet.version)
        extras: dict[str, Any] = {
            "attempt_id": attempt_id,
            "attempt_no": attempt_no,
            "task_id": task.task_id,
            "task_title": task.title,
            "lane": task.lane,
            "complexity": task.complexity,
            "main_role": _do_main_role(task.lane),
            "reviewer_agent": "code-reviewer" if task.lane == "build" else None,
            "task_definition": task.raw,
            "task_packet": packet.payload(),
            "task_packet_hash": packet_hash,
            "task_packet_ref": packet_ref or None,
            "task_packet_version": packet_version,
            "resumed": resumed,
            "constitution": self._constitution_projection(context),
            "project_profile": self._project_profile(context),
            "lineage_advisories": [],
        }
        if task.lane == "build":
            extras["sealed_evidence"] = self._sealed_evidence(context, attempt_id)
            extras["host_internal_flow"] = {
                "user_visible": False,
                "sequence": ["run_main_role", "seal_changes", "run_reviewer_agent", "record_review", "complete_attempt"],
                "after_main_role": {
                    "internal_action": "seal_changes",
                    "command_args": {"action": "seal-changes", "attempt_id": attempt_id},
                    "before_reviewer_agent": "code-reviewer",
                },
                "after_reviewer_agent": {"internal_action": "record-review", "before_complete_attempt": True},
                "complete_requires": ["recorded_review_pass_for_latest_seal"],
            }
        return KernelResponse(
            status="ok",
            message="do attempt resumed" if resumed else "do attempt started",
            recommended_next=self._recommended_do(task.task_id),
            recommended_task_id=task.task_id,
            extras=extras,
        )

    def _sealed_evidence(self, context: StageContext, attempt_id: int) -> list[dict[str, Any]]:
        attempt = context.store.attempt(attempt_id) or {}
        seals = context.store.sealed_changes_for_attempt(attempt_id)
        revisions = {row["seal_revision"] for row in seals}
        legacy_refs = [ref for ref in context.store.runtime_refs(attempt_id) if ref["kind"] == "attempt_changes"]
        latest_ref = attempt.get("latest_sealed_changes_ref")
        if latest_ref and not any(ref["path"] == latest_ref for ref in legacy_refs):
            legacy_refs.append({"path": latest_ref, "content_hash": None})
        errors: list[dict[str, Any]] = []
        for ref in legacy_refs:
            if ref["path"] == latest_ref and attempt.get("latest_seal_revision") in revisions:
                continue
            try:
                path = (context.request.cwd / ref["path"]).resolve()
                if not path.is_relative_to(context.evidence.root.resolve()):
                    raise ValueError("sealed changes outside evidence root")
                content = path.read_bytes().decode("utf-8")
                if hashlib.sha256(content.encode("utf-8")).hexdigest() != ref["content_hash"]:
                    raise ValueError("sealed changes hash mismatch")
                manifest = json.loads(content)
                revision = int(manifest["seal_revision"])
                if revision not in revisions:
                    seals.append({"attempt_id": attempt_id, "seal_revision": revision,
                                  "sealed_tree": manifest["diff_source"]["sealed_tree"],
                                  "manifest_json": content, "content_hash": ref["content_hash"]})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                current = ref["path"] == latest_ref and attempt.get("latest_seal_revision") not in revisions
                errors.append({"attempt_id": attempt_id, "seal_revision": attempt.get("latest_seal_revision", 0) if current else 0,
                               "source_ref": ref["path"], "optional_history": not current, "integrity_error": str(exc)})
        result = []
        for seal in sorted(seals, key=lambda item: item["seal_revision"])[-2:]:
            seal = dict(seal)
            reading_review = False
            try:
                if hashlib.sha256(seal["manifest_json"].encode("utf-8")).hexdigest() != seal["content_hash"]:
                    raise ValueError("sealed changes hash mismatch")
                manifest = json.loads(seal["manifest_json"])
                if (manifest["task_id"] != attempt.get("task_id")
                        or manifest["attempt_no"] != attempt.get("attempt_no")
                        or manifest["seal_revision"] != seal["seal_revision"]
                        or manifest["diff_source"]["start_tree"] != attempt.get("start_tree")
                        or manifest["diff_source"]["sealed_tree"] != seal["sealed_tree"]
                        or (seal["seal_revision"] == attempt.get("latest_seal_revision")
                            and seal["sealed_tree"] != attempt.get("latest_sealed_tree"))):
                    raise ValueError("sealed changes identity mismatch")
                review = context.store.review_for_seal(attempt_id, int(seal["seal_revision"]))
                if review is not None:
                    reading_review = True
                    review_content = review.get("summary_json")
                    if review_content is None:
                        path = (context.request.cwd / str(review.get("summary_ref") or "")).resolve()
                        if not path.is_relative_to(context.evidence.root.resolve()):
                            raise ValueError("review summary outside evidence root")
                        review_content = path.read_bytes().decode("utf-8")
                    if hashlib.sha256(review_content.encode("utf-8")).hexdigest() != review["summary_hash"]:
                        raise ValueError("review summary hash mismatch")
                    review["summary_json"] = review_content
                seal["review"] = review
            except (OSError, ValueError, KeyError, TypeError) as exc:
                seal.pop("manifest_json", None)
                seal["integrity_error"] = f"review evidence: {exc}" if reading_review else str(exc)
            result.append(seal)
        return result + errors


    def _start_attempt(
        self,
        context: StageContext,
        tasks: list[TaskDefinition],
        task: TaskDefinition,
        spec_hash: str | None,
        plan_hash: str | None,
        tasks_hash: str,
        snapshot: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        packet = TaskPacket.from_task(task)
        current_task_inputs = {
            item.task_id: self._input_attempts_json(context, tasks, item)
            for item in tasks
        }
        attempt, created = context.store.start_or_resume_attempt(
            int(context.session["id"]),
            task.task_id,
            context.config.default_runtime,
            spec_hash,
            plan_hash,
            tasks_hash,
            task.fingerprint,
            {item.task_id: item.fingerprint for item in tasks},
            current_task_inputs,
            str(snapshot.get("tree") or ""),
            str(snapshot.get("head") or ""),
            str(snapshot.get("snapshot_semantics") or ""),
            json.dumps(snapshot.get("status_summary") or {}, ensure_ascii=False, sort_keys=True),
            packet.content_hash,
            None,
            packet.version,
            current_task_inputs[task.task_id],
            packet.canonical_json(),
            snapshot_repositories_json=(
                json.dumps(snapshot["repositories"], sort_keys=True) if "repositories" in snapshot else None
            ),
        )
        self._invalidate_latest_attempts(context)
        return attempt, created

    def _do_retry_error(
        self,
        context: StageContext,
        tasks: list[TaskDefinition],
        task: TaskDefinition,
        session_id: int,
    ) -> KernelResponse | None:
        cause_value = context.request.args.get("cause_attempt_id")
        summary = str(context.request.args.get("summary") or "").strip()
        if task.lane != "build" or cause_value is None or not summary:
            return KernelResponse(
                status="failed",
                message="do retry requires a build task, cause_attempt_id, and non-empty summary",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["invalid_do_retry"],
            )
        try:
            cause_attempt_id = int(str(cause_value))
        except ValueError:
            cause_attempt_id = 0
        cause = context.store.attempt(cause_attempt_id)
        cause_task = next((item for item in tasks if cause and item.task_id == cause.get("task_id")), None)
        latest_cause = None if cause_task is None else context.store.latest_attempt(session_id, cause_task.task_id)
        effective_target = self._effective_attempts(context, tasks).get(task.task_id)
        try:
            cause_inputs = json.loads(str((cause or {}).get("input_attempts_json") or "{}"))
        except json.JSONDecodeError:
            cause_inputs = {}
        valid_cause = (
            cause is not None
            and int(cause["branch_session_id"]) == session_id
            and cause.get("status") == "failed"
            and cause_task is not None
            and cause_task.lane == "verify"
            and cause.get("task_fingerprint") == cause_task.fingerprint
            and latest_cause is not None
            and int(latest_cause["id"]) == cause_attempt_id
            and task.task_id in self._task_input_ids(tasks, cause_task)
            and effective_target is not None
            and cause_inputs.get(task.task_id) == int(effective_target["id"])
        )
        if not valid_cause:
            return KernelResponse(
                status="failed",
                message="do retry cause must be the current failed Verify attempt that consumed this Build result",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["invalid_retry_cause"],
            )
        return None

    def _affected_task_ids(self, tasks: list[TaskDefinition], root_task_id: str) -> tuple[str, ...]:
        if not any(task.relations_declared for task in tasks):
            root_index = next((index for index, task in enumerate(tasks) if task.task_id == root_task_id), len(tasks))
            return tuple(task.task_id for task in tasks[root_index:])
        affected = {root_task_id}
        changed = True
        while changed:
            changed = False
            for task in tasks:
                if task.task_id in affected:
                    continue
                if affected.intersection((*task.depends_on, *task.validates)):
                    affected.add(task.task_id)
                    changed = True
        return tuple(task.task_id for task in tasks if task.task_id in affected)

    def _run_do_route(
        self,
        context: StageContext,
        tasks: list[TaskDefinition],
        session_id: int,
    ) -> KernelResponse:
        attempt_value = context.request.args.get("attempt_id")
        target = str(context.request.args.get("target_stage") or "").strip().lower()
        reason = str(context.request.args.get("reason") or "").strip()
        try:
            attempt_id = int(str(attempt_value or ""))
        except ValueError:
            attempt_id = 0
        attempt = context.store.attempt(attempt_id)
        if target not in CONTINUATION_ROUTES["do"] or not reason or attempt is None:
            return KernelResponse(
                status="failed",
                message="do action=route requires a current Do attempt, target_stage in ['plan', 'spec', 'tasks'], and a non-empty reason",
                recommended_next=_loom_command("do"),
                errors=["invalid_continuation_route"],
            )
        if int(attempt["branch_session_id"]) != session_id:
            return KernelResponse(status="failed", message="attempt does not belong to this branch session", recommended_next=_loom_command("do"), errors=["attempt_session_mismatch"])
        task = next((item for item in tasks if item.task_id == attempt.get("task_id")), None)
        if task is None or attempt.get("task_fingerprint") != task.fingerprint:
            return KernelResponse(status="failed", message="task changed during Do continuation", recommended_next=_loom_command("tasks"), errors=["task_changed_during_attempt"])
        latest_attempt = context.store.latest_attempt(session_id, task.task_id)
        if latest_attempt is None or int(latest_attempt["id"]) != attempt_id:
            return KernelResponse(status="failed", message="Do continuation attempt is no longer current", recommended_next=self._recommended_do(task.task_id), errors=["attempt_not_current"])
        if attempt.get("status") == "running":
            if not context.store.complete_attempt_if_running(attempt_id, "blocked", reason):
                attempt = context.store.attempt(attempt_id) or attempt
        if attempt.get("status") not in {"running", "blocked"}:
            return KernelResponse(status="failed", message="Do continuation attempt is not routable", recommended_next=self._recommended_do(task.task_id), errors=["attempt_not_running"])
        context.store.update_branch_session(
            session_id,
            continuation_source_stage="do",
            continuation_stage=target,
            continuation_reason=reason,
            continuation_attempt_id=attempt_id,
            continuation_task_id=task.task_id,
            active_stage="do",
            recommended_next=_loom_command(target),
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok",
            message=f"do task {task.task_id} will continue at {target}: {reason}",
            recommended_next=_loom_command(target),
            extras={
                "continuation_source_stage": "do",
                "continuation_stage": target,
                "continuation_reason": reason,
                "continuation_attempt_id": attempt_id,
                "continuation_task_id": task.task_id,
                "affected_task_ids": list(self._affected_task_ids(tasks, task.task_id)),
            },
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

        snapshot = _capture_attempt_snapshot(context.request.cwd, attempt)
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
        try:
            changes = _build_attempt_changes(
                context.request.cwd, task, attempt, start_tree, sealed_tree, 0, snapshot,
            )
        except ValueError as exc:
            return KernelResponse(
                status="blocked", message="attempt diff could not be generated",
                recommended_next=self._recommended_do(task.task_id),
                errors=["sealed_diff_generation_failed"], extras={"detail": str(exc)},
            )
        recorded_revision, seal_created = context.store.record_sealed_changes(attempt_id, sealed_tree)
        changes["seal_revision"] = recorded_revision
        content = json.dumps(changes, ensure_ascii=False, indent=2, sort_keys=True)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not context.store.attach_sealed_changes(
            attempt_id,
            recorded_revision,
            sealed_tree,
            None,
            content_hash,
            content,
        ):
            return KernelResponse(
                status="blocked",
                message="a newer attempt seal replaced this seal before its changes were attached",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True)},
                errors=["seal_concurrent_update"],
            )
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
                "seal_reused": not seal_created,
                "prior_sealed_evidence": [seal for seal in self._sealed_evidence(context, attempt_id) if seal["seal_revision"] != recorded_revision],
                "sealed_changes": changes,
                "sealed_changes_hash": content_hash,
                "sealed_diff_command": sealed_diff_command,
                "sealed_diff_cwd": str(context.request.cwd.resolve()),
                "reviewer_handoff": {
                    "user_visible": False,
                    "agent": "code-reviewer",
                    "review_scope": "attempt_scoped",
                    "seal_revision": recorded_revision,
                    "changes_source": "extras.sealed_changes",
                    "sealed_diff_command": sealed_diff_command,
                    "sealed_diff_cwd": str(context.request.cwd.resolve()),
                    "do_not_review_full_worktree": True,
                },
            },
        )

    def _run_do_record_review(self, context: StageContext, tasks: list[TaskDefinition], session_id: int) -> KernelResponse:
        attempt_id_value = context.request.args.get("attempt_id")
        if attempt_id_value is None:
            return KernelResponse(status="failed", message="attempt_id is required for record-review", recommended_next=_loom_command("do"), errors=["missing_attempt_id"])
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
            return KernelResponse(status="failed", message=f"task definition changed during attempt: {task.task_id}", recommended_next=self._recommended_do(task.task_id), recommended_task_id=task.task_id, errors=["task_changed_during_attempt"])
        try:
            seal_revision = int(str(context.request.args.get("seal_revision") or ""))
        except ValueError:
            seal_revision = 0
        latest_revision = int(attempt.get("latest_seal_revision") or 0)
        sealed_tree = str(attempt.get("latest_sealed_tree") or "")
        if seal_revision <= 0 or seal_revision != latest_revision or not sealed_tree:
            return KernelResponse(
                status="blocked",
                message="review must be recorded for the latest sealed attempt changes",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True)},
                errors=["seal_revision_mismatch"],
            )
        status = str(context.request.args.get("status") or "").strip().lower()
        if status not in {"pass", "changes_requested", "blocked"}:
            return KernelResponse(
                status="failed",
                message=f"invalid review status: {status}",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["invalid_review_status"],
            )
        existing = context.store.review_for_seal(attempt_id, seal_revision)
        if existing is not None:
            if existing.get("status") == status and existing.get("sealed_tree") == sealed_tree:
                return KernelResponse(
                    status="ok",
                    message="review already recorded for latest sealed attempt changes",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    extras={"attempt_id": attempt_id, "seal_revision": seal_revision, "review_record_id": existing["id"]},
                )
            return KernelResponse(
                status="failed",
                message="review verdict is already recorded for this sealed revision",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["review_already_recorded"],
            )
        summary, summary_error = self._review_summary_content(context, task, status, seal_revision)
        if summary_error is not None:
            return summary_error
        summary_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()
        try:
            review_record_id = context.store.record_review(
                attempt_id,
                seal_revision,
                sealed_tree,
                status,
                None,
                summary_hash,
                summary,
            )
        except ValueError as exc:
            if str(exc) != "review_already_recorded":
                raise
            return KernelResponse(
                status="failed",
                message="review verdict is already recorded for this sealed revision",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["review_already_recorded"],
            )
        recorded_review = context.store.review_for_seal(attempt_id, seal_revision)
        authoritative_summary_ref = (recorded_review or {}).get("summary_ref")
        return KernelResponse(
            status="ok",
            message="attempt review recorded",
            recommended_next=self._recommended_do(task.task_id),
            recommended_task_id=task.task_id,
            extras={
                "attempt_id": attempt_id,
                "task_id": task.task_id,
                "seal_revision": seal_revision,
                "sealed_tree": sealed_tree,
                "review_record_id": review_record_id,
                "review_summary_ref": authoritative_summary_ref,
                "review_scope": "attempt_scoped",
                "status": status,
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
        seal = next((item for item in self._sealed_evidence(context, attempt_id) if item["seal_revision"] == latest_revision), None)
        if seal is None or seal.get("integrity_error"):
            return KernelResponse(
                status="blocked", message="sealed evidence is unavailable or corrupt",
                recommended_next=self._recommended_do(task.task_id), recommended_task_id=task.task_id,
                extras=({"unlock_command": self._unlock_command(context, attempt_id)}
                        if seal and str(seal.get("integrity_error", "")).startswith("review")
                        else {"host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True)}),
                errors=["sealed_evidence_integrity_error"],
            )
        review = context.store.review_for_seal(attempt_id, latest_revision)
        if review is None:
            return KernelResponse(
                status="blocked",
                message="latest sealed attempt changes have not been recorded as reviewed",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True)},
                errors=["review_not_recorded"],
            )
        if review.get("status") != "pass":
            return KernelResponse(
                status="blocked",
                message="sealed attempt changes have not passed review",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["review_not_passed"],
            )
        if review.get("review_scope") != "attempt_scoped" or review.get("sealed_tree") != latest_sealed_tree:
            return KernelResponse(
                status="blocked",
                message="recorded review does not match latest sealed attempt changes",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"host_recovery": self._seal_changes_recovery(attempt_id, rerun_reviewer=True)},
                errors=["review_record_mismatch"],
            )
        snapshot = _capture_attempt_snapshot(context.request.cwd, attempt)
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
        return None

    def _seal_changes_recovery(self, attempt_id: int, rerun_reviewer: bool) -> dict[str, Any]:
        return {
            "user_visible": False,
            "internal_action": "seal_changes",
            "command_args": {"action": "seal-changes", "attempt_id": attempt_id},
            "rerun_reviewer": rerun_reviewer,
        }

    def _load_completion_candidate(
        self,
        context: StageContext,
        attempt: dict[str, Any],
    ) -> tuple[dict[str, str] | None, str | None]:
        content = attempt.get("completion_candidate_json")
        candidate_hash = str(attempt.get("completion_candidate_hash") or "")
        if not candidate_hash:
            return None, "completion_candidate_missing"
        if content is None:
            candidate_ref = str(attempt.get("completion_candidate_ref") or "")
            if not candidate_ref:
                return None, "completion_candidate_missing"
            candidate_path = (context.request.cwd / candidate_ref).resolve()
            if not candidate_path.is_relative_to(context.evidence.root.resolve()):
                return None, "completion_candidate_invalid_path"
            try:
                content = candidate_path.read_text(encoding="utf-8")
            except OSError:
                return None, "completion_candidate_unreadable"
        try:
            candidate = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            return None, "completion_candidate_unreadable"
        fields = {"status", "summary", "stdout", "stderr", "verification_summary"}
        if isinstance(candidate, dict) and candidate.get("version") == "2":
            fields |= {"version", "stdout_hash", "stderr_hash"}
        if not isinstance(candidate, dict) or set(candidate) != fields:
            return None, "completion_candidate_invalid"
        if any(not isinstance(candidate[field], str) for field in fields):
            return None, "completion_candidate_invalid"
        canonical = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if (
            hashlib.sha256(content.encode("utf-8")).hexdigest() != candidate_hash
            or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != candidate_hash
            or attempt.get("completion_token") != candidate_hash
        ):
            return None, "completion_candidate_hash_mismatch"
        if candidate.get("version") == "2":
            for kind in ("stdout", "stderr"):
                ref = candidate[kind]
                if not ref:
                    if candidate[f"{kind}_hash"]:
                        return None, "completion_candidate_invalid"
                    continue
                path = (context.request.cwd / ref).resolve()
                if not path.is_relative_to(context.evidence.root.resolve()):
                    return None, "completion_log_invalid_path"
                try:
                    if _content_hash(path) != candidate[f"{kind}_hash"]:
                        return None, "completion_log_hash_mismatch"
                except OSError:
                    return None, "completion_log_unreadable"
        return candidate, None

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
        try:
            recorded_inputs = json.loads(str(attempt.get("input_attempts_json") or "{}"))
        except json.JSONDecodeError:
            recorded_inputs = None
        if not isinstance(recorded_inputs, dict):
            return KernelResponse(
                status="failed",
                message=f"frozen task inputs are invalid for attempt: {task.task_id}",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["attempt_inputs_invalid"],
            )
        for input_task_id, input_attempt_id in recorded_inputs.items():
            try:
                input_attempt = context.store.attempt(int(input_attempt_id))
            except (TypeError, ValueError):
                input_attempt = None
            if (
                input_attempt is None
                or int(input_attempt["branch_session_id"]) != session_id
                or str(input_attempt["task_id"]) != str(input_task_id)
                or input_attempt.get("status") not in {"implemented", "verified"}
            ):
                return KernelResponse(
                    status="failed",
                    message=f"frozen input attempt is unavailable: {input_task_id}",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    errors=["attempt_input_unavailable"],
                )

        candidate_arg_names = {
            "status",
            "summary",
            "stdout",
            "stderr",
            "verification_summary",
            "verification_summary_file",
        }
        has_candidate_args = any(name in context.request.args for name in candidate_arg_names)
        candidate: dict[str, str] | None = None
        if attempt.get("status") != "running" and not has_candidate_args and (attempt.get("completion_candidate_json") is not None or attempt.get("completion_candidate_ref")):
            candidate, candidate_error = self._load_completion_candidate(context, attempt)
            if candidate_error is not None:
                return KernelResponse(
                    status="blocked",
                    message=f"stored completion candidate cannot be recovered: {candidate_error}",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    extras={
                        "completion_candidate_ref": attempt.get("completion_candidate_ref"),
                        "host_recovery": {
                            "user_visible": False,
                            "internal_action": "resubmit_completion_candidate",
                            "requires": "original_completion_candidate",
                        },
                    },
                    errors=[candidate_error],
                )

        if candidate is None:
            status = str(context.request.args.get("status") or "").strip().lower()
            if status == "success":
                status = "verified" if task.lane == "verify" else "implemented"
            summary = str(context.request.args.get("summary") or f"Host runtime completed {task.task_id}: {task.title}")
            verification_summary = ""
            if task.lane == "verify":
                verification_summary, verification_summary_error = self._verification_summary_content(context, task)
                if verification_summary_error is not None:
                    return verification_summary_error
            candidate = {
                "status": status,
                "summary": summary,
                "stdout": str(context.request.args.get("stdout") or ""),
                "stderr": str(context.request.args.get("stderr") or ""),
                "verification_summary": verification_summary,
            }
            if attempt.get("completion_candidate_json") is not None or not attempt.get("completion_candidate_ref"):
                candidate["version"] = "2"
                for kind in ("stdout", "stderr"):
                    output = candidate[kind]
                    digest = hashlib.sha256(output.encode("utf-8")).hexdigest() if output else ""
                    candidate[f"{kind}_hash"] = digest
                    candidate[kind] = context.evidence.attempt_file_ref(
                        task.task_id, int(attempt["attempt_no"]), f"runtime.{kind}-{digest}.log",
                    ) if output else ""

        final_status = candidate["status"]
        summary = candidate["summary"]
        verification_summary = candidate["verification_summary"]
        expected_success = "verified" if task.lane == "verify" else "implemented"
        if final_status not in {expected_success, "failed", "blocked"}:
            return KernelResponse(
                status="failed",
                message=f"invalid completion status for {task.lane} task: {final_status}",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["invalid_completion_status"],
            )
        if task.lane == "verify" and final_status == "verified" and not verification_summary.strip():
            return KernelResponse(
                status="blocked",
                message="verified completion requires a non-empty verification summary",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                extras={"host_recovery": {"user_visible": False, "requires": "verification_summary"}},
                errors=["missing_verification_evidence"],
            )
        candidate_content = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        completion_token = hashlib.sha256(candidate_content.encode("utf-8")).hexdigest()
        if attempt.get("status") not in {"running", "completing"}:
            stored_token = attempt.get("completion_token")
            if attempt.get("status") == final_status and (stored_token is None or stored_token == completion_token):
                recommendation = self._next_task_recommendation(context, tasks)
                return KernelResponse(
                    status="ok",
                    message=str(attempt.get("summary") or f"attempt already completed: {task.task_id}"),
                    recommended_next=recommendation.command,
                    recommended_task_id=recommendation.task_id,
                    recommended_task_title=recommendation.task_title,
                    extras={"attempt_id": attempt_id, "task_id": task.task_id, "status": final_status, "idempotent": True},
                )
            return KernelResponse(
                status="failed",
                message=f"attempt has a different completion candidate: {attempt_id}",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["completion_conflict"],
            )

        if task.lane == "build" and final_status == "implemented":
            gate = self._build_seal_changes_gate(context, attempt, task, attempt_id)
            if gate is not None:
                return gate
        if candidate.get("version") == "2" and has_candidate_args:
            for kind in ("stdout", "stderr"):
                output = str(context.request.args.get(kind) or "")
                if output:
                    context.evidence.write_attempt_file(
                        task.task_id, int(attempt["attempt_no"]), f"runtime.{kind}-{candidate[f'{kind}_hash']}.log", output,
                    )
        candidate_ref = attempt.get("completion_candidate_ref") if candidate.get("version") != "2" else None
        if candidate_ref and has_candidate_args and completion_token == attempt.get("completion_token"):
            legacy_path = (context.request.cwd / candidate_ref).resolve()
            if not legacy_path.is_relative_to(context.evidence.root.resolve()):
                return KernelResponse(status="blocked", message="invalid legacy completion path", errors=["completion_candidate_invalid_path"])
            legacy_path.write_text(candidate_content, encoding="utf-8", newline="")
        claim = context.store.claim_attempt_completion(
            attempt_id,
            completion_token,
            final_status,
            summary,
            candidate_ref,
            completion_token,
            candidate_content if candidate.get("version") == "2" else None,
        )
        if claim == "completed":
            self._invalidate_latest_attempts(context)
            recommendation = self._next_task_recommendation(context, tasks)
            completed_attempt = context.store.attempt(attempt_id) or attempt
            return KernelResponse(
                status="ok",
                message=str(completed_attempt.get("summary") or summary),
                recommended_next=recommendation.command,
                recommended_task_id=recommendation.task_id,
                recommended_task_title=recommendation.task_title,
                extras={"attempt_id": attempt_id, "task_id": task.task_id, "status": final_status, "idempotent": True},
            )
        if claim not in {"claimed", "resume"}:
            return KernelResponse(
                status="failed",
                message=f"attempt has a different completion candidate: {attempt_id}",
                recommended_next=self._recommended_do(task.task_id),
                recommended_task_id=task.task_id,
                errors=["completion_conflict"],
            )

        attempt_no = int(attempt["attempt_no"])
        runtime_refs: list[tuple[str, str, str]] = []
        for kind in ("stdout", "stderr"):
            if candidate.get("version") == "2":
                if candidate[kind]:
                    runtime_refs.append((kind, candidate[kind], candidate[f"{kind}_hash"]))
            else:
                ref = self._write_attempt_file_if_not_empty(
                    context, task.task_id, attempt_no, f"runtime.{kind}.log", candidate[kind],
                )
                if ref is not None:
                    runtime_refs.append((kind, ref, _content_hash(context.request.cwd / ref)))
        verification = None
        if task.lane == "verify" and verification_summary.strip():
            verification_status = "passed" if final_status == "verified" else final_status
            verification = (
                "claude-code verification", verification_status,
                0 if verification_status == "passed" else None, None, verification_summary,
            )
        finding = None
        if final_status in {"failed", "blocked"}:
            finding = (
                session_id,
                "verification_failure" if final_status == "failed" else "execution_blocked",
                "blocking",
                f"do attempt {final_status} for {task.task_id}",
                _loom_command("do"),
            )
        if not context.store.finalize_attempt_completion(
            attempt_id,
            completion_token,
            final_status,
            summary,
            runtime_refs,
            verification,
            finding,
        ):
            completed_attempt = context.store.attempt(attempt_id)
            if completed_attempt is None or completed_attempt.get("status") != final_status:
                return KernelResponse(
                    status="failed",
                    message=f"attempt completion could not be finalized: {attempt_id}",
                    recommended_next=self._recommended_do(task.task_id),
                    recommended_task_id=task.task_id,
                    errors=["completion_conflict"],
                )
        self._invalidate_latest_attempts(context)
        if final_status == "verified":
            context.store.resolve_open_findings_for_attempt(attempt_id, "verification_failure")
        recommendation = self._next_task_recommendation(context, tasks)
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
            recommended_task_title=recommendation.task_title,
            extras={"attempt_id": attempt_id, "task_id": task.task_id, "status": final_status},
        )


    def _run_ship(self, context: StageContext) -> KernelResponse:
        session_id = int(context.session["id"])
        states = self._artifact_states(context)
        repair = earliest_artifact_repair(states, "tasks")
        if repair is not None:
            return KernelResponse(
                status="blocked",
                message="Ship requires current registered Spec, Plan, and Tasks inputs",
                recommended_next=repair,
                errors=["ship_prerequisites_incomplete"],
                extras={"artifact_states": states},
            )
        revisions = self._latest_artifact_revisions(context)
        spec_hash = str(revisions["spec"]["content_hash"])
        plan_hash = str(revisions["plan"]["content_hash"])
        tasks_hash = str(revisions["tasks"]["content_hash"])
        tasks = self._current_tasks(context)
        if not tasks:
            return KernelResponse(
                status="blocked",
                message="Ship requires parseable current tasks before release analysis",
                recommended_next=_loom_command("tasks"),
                errors=["ship_prerequisites_incomplete"],
            )
        effective_attempts = self._effective_attempts(context, tasks)
        if len(effective_attempts) != len(tasks):
            recommendation = self._next_task_recommendation(context, tasks)
            return KernelResponse(
                status="blocked",
                message="Ship requires every current Build and Verify task to be complete",
                recommended_next=recommendation.command,
                recommended_task_id=recommendation.task_id,
                recommended_task_title=recommendation.task_title,
                errors=["ship_prerequisites_incomplete"],
                extras={
                    "mechanical_state": "incomplete",
                    "tasks": self._ship_task_facts(context, tasks),
                },
            )

        context.store.resolve_open_findings(session_id, "evidence_integrity_gap")
        ship_packet = self._build_ship_packet(context, tasks)
        ship_input_hash = self._ship_input_hash(ship_packet)
        latest_ship = context.store.latest_artifact_revision(session_id, "ship")
        current_ship_hash = context.artifacts.hash_existing("ship")
        if (
            not context.request.args
            and latest_ship
            and latest_ship.get("based_on_execution_hash") == ship_input_hash
            and latest_ship.get("content_hash") == current_ship_hash
        ):
            context.store.update_branch_session(
                session_id,
                active_stage="ship",
                active_ship_hash=current_ship_hash,
                recommended_next=None,
                recommended_task_id=None,
            )
            return KernelResponse(
                status="ok" if ship_packet["status"] == "ready" else "blocked",
                message=f"release.md is current: {ship_packet['status']}",
                recommended_next=None,
                artifact_paths=[context.artifacts.relative(context.artifacts.path_for("ship"))],
                findings=list(ship_packet["open_findings"]),
                extras={
                    "mechanical_state": "complete",
                    "release_status": ship_packet["status"],
                    "ship_input_hash": ship_input_hash,
                    "idempotent": True,
                },
            )
        input_snapshot, input_token = self._stage_input(context, "ship", ship_input_hash)
        handoff = self._host_artifact_handoff_response(
            context,
            "ship",
            {"ship_input_hash": ship_input_hash, "input_token": input_token},
            {
                "ship_packet": ship_packet,
                "ship_input_hash": ship_input_hash,
                "input_snapshot": input_snapshot,
                "input_token": input_token,
                "mechanical_state": "complete",
            },
        )
        if handoff is not None:
            return handoff

        content, error = self._artifact_content(
            context,
            "ship",
            lambda: create_llm_client().draft_ship_summary(
                ship_packet | {"ship_input_hash": ship_input_hash},
                context.config.spec_language,
            ),
        )
        if error is not None:
            return error
        assert content is not None

        if context.request.args.get("artifact_file"):
            submitted_hash = str(context.request.args.get("ship_input_hash") or "")
            if submitted_hash != ship_input_hash:
                artifact_path, extras = self._artifact_handoff(
                    context,
                    "ship",
                    {"ship_input_hash": ship_input_hash, "input_token": input_token},
                    {
                        "ship_packet": ship_packet,
                        "ship_input_hash": ship_input_hash,
                        "input_snapshot": input_snapshot,
                        "input_token": input_token,
                        "mechanical_state": "complete",
                        "host_recovery": {
                            "user_visible": False,
                            "internal_action": "reauthor_release",
                        },
                    },
                )
                return KernelResponse(
                    status="noop",
                    message="Ship inputs changed before release.md registration",
                    recommended_next=_loom_command("ship"),
                    artifact_paths=[artifact_path],
                    errors=["ship_inputs_changed"],
                    extras=extras,
                )

        path, ship_hash = context.artifacts.write("ship", content)
        self._cache_artifact(context, "ship", content, ship_hash)
        registration_token = (
            str(context.request.args.get("input_token") or "")
            if context.request.args.get("artifact_file")
            else input_token
        )
        _, registration_error = self._register_artifact(
            context,
            "ship",
            path,
            ship_hash,
            expected_token=registration_token,
            execution_hash=ship_input_hash,
        )
        if registration_error is not None:
            return registration_error
        self._resolve_artifact_drift(context, "ship")
        readiness_blockers = list(ship_packet["readiness_blockers"])
        ship_status = "ready" if not readiness_blockers else "blocked"
        context.store.update_branch_session(
            session_id,
            recommended_next=None,
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok" if ship_status == "ready" else "blocked",
            message=f"release.md generated: {ship_status}",
            recommended_next=None,
            artifact_paths=[context.artifacts.relative(path)],
            findings=list(ship_packet["open_findings"]),
            extras={
                "mechanical_state": "complete",
                "release_status": ship_status,
                "ship_input_hash": ship_input_hash,
            },
        )

    def _build_ship_packet(self, context: StageContext, tasks: list[TaskDefinition]) -> dict[str, Any]:
        session_id = int(context.session["id"])
        effective_attempts = self._effective_attempts(context, tasks)
        completed_attempt_ids = [int(effective_attempts[task.task_id]["id"]) for task in tasks if task.task_id in effective_attempts]
        refs_by_attempt = context.store.runtime_refs_for_attempts(completed_attempt_ids)
        verifications_by_attempt = context.store.verifications_for_attempts(completed_attempt_ids)
        blocking = context.store.open_blocking_findings(session_id)
        runtime_refs: list[dict[str, Any]] = []
        verification_facts: list[dict[str, Any]] = []
        review_facts: list[dict[str, Any]] = []
        sealed_facts: list[dict[str, Any]] = []
        readiness_blockers = [str(finding["message"]) for finding in blocking]
        verification_warnings: list[str] = []

        for task in tasks:
            attempt = effective_attempts.get(task.task_id)
            if attempt is None:
                readiness_blockers.append(f"{task.task_id}: task not completed")
                continue
            attempt_id = int(attempt["id"])
            current_revision = int(attempt.get("latest_seal_revision") or 0)
            db_seals = context.store.sealed_changes_for_attempt(attempt_id)
            current_in_db = any(seal["seal_revision"] == current_revision for seal in db_seals)
            current_review = context.store.review_for_seal(attempt_id, current_revision)
            current_review_ref = (current_review or {}).get("summary_ref")
            required_refs = [ref for ref in refs_by_attempt[attempt_id]
                             if not (ref["kind"] == "attempt_changes" and current_in_db)
                             and not (ref["kind"] == "review_summary" and ref["path"] != current_review_ref)]
            refs = self._structured_runtime_refs(attempt, required_refs)
            runtime_refs.extend(refs)
            for gap in _runtime_ref_integrity_gaps(context.request.cwd, refs):
                readiness_blockers.append(f"{task.task_id}: {gap}")
            if attempt.get("task_packet_json") is not None:
                _, packet_error = self._load_attempt_task(context, attempt)
                if packet_error is not None:
                    readiness_blockers.append(f"{task.task_id}: frozen task packet integrity error")
            sealed_evidence = self._sealed_evidence(context, attempt_id)
            if current_revision and not any(seal["seal_revision"] == current_revision for seal in sealed_evidence):
                readiness_blockers.append(f"{task.task_id}: current sealed evidence missing")
            for seal in sealed_evidence:
                if seal.get("integrity_error") and seal.get("seal_revision") == current_revision:
                    readiness_blockers.append(f"{task.task_id}: {seal['integrity_error']}")
                if seal.get("seal_revision") == attempt.get("latest_seal_revision"):
                    sealed_facts.append({"task_id": task.task_id, **{key: value for key, value in seal.items() if key != "review"}})
                    if seal.get("review") is not None:
                        review_facts.append({"task_id": task.task_id, **seal["review"]})
            rows = verifications_by_attempt[attempt_id]
            for row in rows:
                summary_text = row.get("summary_text")
                if summary_text is not None and hashlib.sha256(summary_text.encode("utf-8")).hexdigest() != row.get("summary_hash"):
                    readiness_blockers.append(f"{task.task_id}: verification summary hash mismatch")
            verification_facts.extend(
                {
                    "id": row.get("id"),
                    "task_id": task.task_id,
                    "attempt_id": attempt_id,
                    "command": row.get("command"),
                    "status": row.get("status"),
                    "exit_code": row.get("exit_code"),
                    "summary_ref": row.get("summary_ref"),
                    "summary_text": row.get("summary_text"),
                    "summary_hash": row.get("summary_hash"),
                    "created_at": row.get("created_at"),
                }
                for row in rows
            )
            if task.lane == "verify" and not self._has_verification_evidence(rows):
                warning = f"{task.task_id}: verification evidence missing"
                verification_warnings.append(warning)
                readiness_blockers.append(warning)
            elif task.lane == "verify" and any(row["status"] == "skipped_config_missing" for row in rows):
                warning = f"{task.task_id}: verification command missing"
                verification_warnings.append(warning)
                readiness_blockers.append(warning)

        return {
            "version": "1",
            "status": "ready" if len(effective_attempts) == len(tasks) and not readiness_blockers else "blocked",
            "mechanical_state": "complete" if len(effective_attempts) == len(tasks) else "incomplete",
            "spec_hash": self._artifact_hash(context, "spec") or "",
            "plan_hash": self._artifact_hash(context, "plan") or "",
            "tasks_hash": self._artifact_hash(context, "tasks") or "",
            "tasks": self._ship_task_facts(context, tasks),
            "completed_tasks": [task.task_id for task in tasks if task.task_id in effective_attempts],
            "verification_summary": self._verification_summary(len(effective_attempts), len(tasks), verification_warnings),
            "verifications": verification_facts,
            "reviews": review_facts,
            "sealed_changes": sealed_facts,
            "open_findings": [
                {
                    "id": finding.get("id"),
                    "attempt_id": finding.get("attempt_id"),
                    "kind": finding.get("kind"),
                    "severity": finding.get("severity"),
                    "message": finding.get("message"),
                    "suggested_next": finding.get("suggested_next"),
                }
                for finding in blocking
            ],
            "readiness_blockers": list(dict.fromkeys(readiness_blockers)),
            "runtime_refs": runtime_refs,
        }

    def _ship_task_facts(self, context: StageContext, tasks: list[TaskDefinition]) -> list[dict[str, Any]]:
        effective_attempts = self._effective_attempts(context, tasks)
        latest_attempts = self._latest_attempts(context)
        facts: list[dict[str, Any]] = []
        for task in tasks:
            effective = effective_attempts.get(task.task_id)
            latest = latest_attempts.get(task.task_id)
            facts.append(
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "lane": task.lane,
                    "complexity": task.complexity,
                    "revision": task.revision,
                    "fingerprint": task.fingerprint,
                    "effective": effective is not None,
                    "effective_attempt_id": effective.get("id") if effective else None,
                    "effective_attempt_no": effective.get("attempt_no") if effective else None,
                    "effective_status": effective.get("status") if effective else "stale" if latest else "pending",
                    "completion_token": effective.get("completion_token") if effective else None,
                    "blocked_by": list(self._task_blockers(context, tasks, task)),
                    "latest_attempt_id": latest.get("id") if latest else None,
                    "latest_attempt_no": latest.get("attempt_no") if latest else None,
                    "latest_status": latest.get("status") if latest else None,
                }
            )
        return facts

    def _ship_input_hash(self, packet: dict[str, Any]) -> str:
        content = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _verification_summary(self, completed_count: int, task_count: int, warnings: list[str]) -> str:
        summary = f"{completed_count}/{task_count} tasks completed"
        if warnings:
            summary += "\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
        return summary

    def _has_verification_evidence(self, verifications: list[dict[str, Any]]) -> bool:
        return any(item.get("status") == "passed" for item in verifications)

    def _structured_runtime_refs(self, attempt: dict[str, Any], refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "task_id": attempt.get("task_id"),
                "attempt_no": attempt.get("attempt_no"),
                "kind": ref.get("kind"),
                "path": ref.get("path"),
                "content_hash": ref.get("content_hash"),
                "created_at": ref.get("created_at"),
            }
            for ref in refs
        ]

    def _record_task_snapshots(self, context: StageContext, tasks: list[TaskDefinition], tasks_hash: str) -> None:
        if tasks_hash in context.task_snapshots_recorded:
            return
        context.store.upsert_task_snapshots(
            int(context.session["id"]),
            [
                (
                    task.task_id,
                    task.fingerprint,
                    tasks_hash,
                    task.title,
                    TaskPacket.from_task(task).content_hash,
                    None,
                    TaskPacket.from_task(task).version,
                )
                for task in tasks
            ],
        )
        context.task_snapshots_recorded.add(tasks_hash)

    def _latest_attempts(self, context: StageContext) -> dict[str, dict[str, Any]]:
        if context.latest_attempts_by_task is None:
            context.latest_attempts_by_task = context.store.latest_attempts_by_task(int(context.session["id"]))
        return context.latest_attempts_by_task

    def _task_input_ids(self, tasks: list[TaskDefinition], task: TaskDefinition) -> tuple[str, ...]:
        if any(item.relations_declared for item in tasks):
            return tuple(dict.fromkeys((*task.depends_on, *task.validates)))
        index = tasks.index(task)
        return () if index == 0 else (tasks[index - 1].task_id,)

    def _effective_attempts(self, context: StageContext, tasks: list[TaskDefinition]) -> dict[str, dict[str, Any]]:
        if context.effective_attempts_by_task is not None:
            return context.effective_attempts_by_task
        latest_attempts = self._latest_attempts(context)
        effective: dict[str, dict[str, Any]] = {}
        explicit_relations = any(task.relations_declared for task in tasks)
        for task in tasks:
            attempt = latest_attempts.get(task.task_id)
            if attempt is None or attempt.get("task_fingerprint") != task.fingerprint:
                continue
            expected_status = "verified" if task.lane == "verify" else "implemented"
            if attempt.get("status") != expected_status:
                continue
            input_ids = self._task_input_ids(tasks, task)
            raw_inputs = attempt.get("input_attempts_json")
            if explicit_relations or raw_inputs is not None:
                try:
                    recorded_inputs = json.loads(str(raw_inputs or "{}"))
                except json.JSONDecodeError:
                    continue
                expected_inputs = {
                    input_id: int(effective[input_id]["id"])
                    for input_id in input_ids
                    if input_id in effective
                }
                if len(expected_inputs) != len(input_ids) or recorded_inputs != expected_inputs:
                    continue
            effective[task.task_id] = attempt
        context.effective_attempts_by_task = effective
        return effective

    def _task_blockers(
        self,
        context: StageContext,
        tasks: list[TaskDefinition],
        task: TaskDefinition,
    ) -> tuple[str, ...]:
        effective = self._effective_attempts(context, tasks)
        return tuple(task_id for task_id in self._task_input_ids(tasks, task) if task_id not in effective)

    def _root_task_blockers(
        self,
        context: StageContext,
        tasks: list[TaskDefinition],
        task: TaskDefinition,
    ) -> tuple[str, ...]:
        by_id = {item.task_id: item for item in tasks}

        def roots(current: TaskDefinition, visiting: set[str]) -> tuple[str, ...]:
            found: list[str] = []
            for task_id in self._task_blockers(context, tasks, current):
                if task_id in visiting:
                    found.append(task_id)
                    continue
                prerequisite = by_id.get(task_id)
                nested = () if prerequisite is None else roots(prerequisite, visiting | {task_id})
                found.extend(nested or (task_id,))
            return tuple(dict.fromkeys(found))

        return roots(task, {task.task_id})

    def _input_attempts_json(
        self,
        context: StageContext,
        tasks: list[TaskDefinition],
        task: TaskDefinition,
    ) -> str:
        effective = self._effective_attempts(context, tasks)
        inputs = {
            task_id: int(effective[task_id]["id"]) if task_id in effective else None
            for task_id in self._task_input_ids(tasks, task)
        }
        return json.dumps(inputs, ensure_ascii=False, sort_keys=True)

    def _invalidate_latest_attempts(self, context: StageContext) -> None:
        context.latest_attempts_by_task = None
        context.effective_attempts_by_task = None

    def _select_recommended_task(self, context: StageContext, tasks: list[TaskDefinition]) -> TaskDefinition | None:
        effective = self._effective_attempts(context, tasks)
        latest_attempts = self._latest_attempts(context)
        retry_candidate: TaskDefinition | None = None
        for task in tasks:
            if task.task_id in effective or self._task_blockers(context, tasks, task):
                continue
            latest = latest_attempts.get(task.task_id)
            if latest and latest.get("task_fingerprint") == task.fingerprint and latest.get("status") in {"failed", "blocked"}:
                retry_candidate = retry_candidate or task
                continue
            return task
        return retry_candidate

    def _select_task(self, context: StageContext, tasks: list[TaskDefinition]) -> TaskDefinition | None:
        requested = str(context.request.args.get("task_id") or "").strip()
        if requested:
            return next((task for task in tasks if task.task_id == requested), None)
        return self._select_recommended_task(context, tasks)


def _do_main_role(lane: str) -> str:
    return "verifier" if lane == "verify" else "builder"


def _capture_attempt_snapshot(repo_path: Path, attempt: dict[str, Any]) -> dict[str, Any]:
    frozen = attempt.get("snapshot_repositories_json")
    if frozen is None:
        if attempt.get("snapshot_semantics") == "repository_content_v1":
            return {"errors": ["frozen repository scope missing"]}
        return _capture_working_tree_content_snapshot(repo_path)
    try:
        scope = json.loads(frozen)
        if (not isinstance(scope, dict) or scope.get("version") != 1
                or not isinstance(scope.get("roots"), list)
                or attempt.get("snapshot_semantics") != "repository_content_v1"):
            raise ValueError("invalid frozen repository scope")
        return capture_repository_snapshot(repo_path, tuple(scope["roots"]))
    except (ValueError, TypeError) as exc:
        return {"errors": [f"frozen repository scope: {exc}"]}


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
        sparse = subprocess.run(["git", "config", "--bool", "core.sparseCheckout"], cwd=repo_path, env=git_environment(), capture_output=True, text=True)
        if sparse.returncode == 0 and sparse.stdout.strip().lower() == "true":
            result["errors"].append("snapshot_sparse_checkout_unsupported")
            return result
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_path, env=git_environment(), capture_output=True, text=True)
        if head.returncode != 0:
            result["errors"].append(head.stderr.strip() or "snapshot_head_unavailable")
            return result
        with TemporaryDirectory(prefix="codeloom-index-") as tmp_dir:
            index_path = str(Path(tmp_dir) / "index")
            env = git_environment(Path(index_path))
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
        "snapshot_semantics": sealed_snapshot.get("snapshot_semantics", "working_tree_content"),
        "repositories": sealed_snapshot.get("repositories"),
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
        raise ValueError(error)
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
        raise ValueError(error)
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
        raise ValueError(error)
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
            env=git_environment(),
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
        status = subprocess.run(["git", "status", "--short"], cwd=repo_path, env=git_environment(), capture_output=True, text=True)
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
