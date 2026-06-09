from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
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

class StageRunner:
    def __init__(self) -> None:
        self.verifier = ShellVerifier()
        self.resolver = ContractRevisionResolver()

    def run(self, request: KernelRequest) -> KernelResponse:
        command = request.command.removeprefix("/loom:")
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

    def _sync_artifact_state(self, context: StageContext) -> None:
        session_id = int(context.session["id"])
        updates: dict[str, str] = {}

        spec_hash = self._sync_one_artifact(context, "spec", "active_spec_hash")
        if spec_hash:
            updates["active_spec_hash"] = spec_hash

        current_spec_hash = updates.get("active_spec_hash") or context.session.get("active_spec_hash")
        plan_hash = self._sync_one_artifact(
            context,
            "plan",
            "active_plan_hash",
            based_on_spec_hash=current_spec_hash,
        )
        if plan_hash:
            updates["active_plan_hash"] = plan_hash

        latest_plan = context.store.latest_artifact_revision(session_id, "plan")
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
                f"{kind}.md changed outside registered artifact revision",
                None,
            )
        return content_hash

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
            return NextRecommendation("/loom:spec")
        if context.artifacts.read("plan") is None:
            return NextRecommendation("/loom:plan")
        tasks_content = context.artifacts.read("tasks")
        if tasks_content is None:
            return NextRecommendation("/loom:tasks")

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
            return NextRecommendation("/loom:tasks")
        tasks = parse_tasks(tasks_content)
        if not tasks:
            return NextRecommendation("/loom:tasks")

        self._record_task_snapshots(context, tasks_content, tasks_hash)
        self._supersede_stale_task_state(context, tasks)
        blocking = self._open_execution_blocking_findings(context)
        if blocking:
            return self._recommend_from_blocking_findings(context, blocking)

        task = self._select_recommended_task(context, tasks)
        if task is not None:
            return NextRecommendation(self._recommended_do(task.task_id), task.task_id)
        return NextRecommendation("/loom:ship")

    def _recommended_do(self, task_id: str) -> str:
        return f"/loom:do {task_id}"

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
            command = str(suggested_next)
            if command == "/loom:do":
                attempt_id = finding.get("attempt_id")
                if attempt_id is None:
                    continue
                attempt = context.store.attempt(int(attempt_id))
                if attempt is None:
                    continue
                task_id = str(attempt["task_id"])
                return NextRecommendation(self._recommended_do(task_id), task_id)
            if command in {"/loom:spec", "/loom:plan", "/loom:tasks", "/loom:ship"}:
                return NextRecommendation(command)
            if command.startswith("/loom:do "):
                task_id = command.split(maxsplit=1)[1]
                return NextRecommendation(command, task_id)
        return NextRecommendation(None)

    def _supersede_stale_task_state(self, context: StageContext, tasks: list[TaskDefinition]) -> None:
        session_id = int(context.session["id"])
        current = {task.task_id: task for task in tasks}
        for attempt in context.store.attempts(session_id):
            if attempt.get("status") == "superseded":
                continue
            task = current.get(str(attempt.get("task_id")))
            fingerprint = attempt.get("task_fingerprint")
            if task is None:
                attempt_id = int(attempt["id"])
                context.store.supersede_attempt(attempt_id, "task no longer exists in tasks.md")
                context.store.supersede_open_findings_for_attempt(attempt_id)
            elif fingerprint is not None and fingerprint != task.fingerprint:
                attempt_id = int(attempt["id"])
                context.store.supersede_attempt(attempt_id, "task definition changed")
                context.store.supersede_open_findings_for_attempt(attempt_id)

    def _candidate_content(
        self,
        context: StageContext,
        fallback: Callable[[], str],
    ) -> tuple[str | None, KernelResponse | None]:
        content_file = context.request.args.get("content_file")
        if not content_file:
            return fallback(), None
        path = Path(str(content_file))
        if not path.is_absolute():
            path = context.request.cwd / path
        if not path.exists():
            return None, KernelResponse(status="failed", message=f"content_file not found: {path}", errors=["missing_content_file"])
        return path.read_text(encoding="utf-8"), None

    def _run_spec(self, context: StageContext) -> KernelResponse:
        args = context.request.args
        requirement = str(args.get("requirement") or args.get("revision_note") or args.get("text") or "")
        existing = context.artifacts.read("spec") if args.get("revision_note") else None
        content, error = self._candidate_content(context, lambda: create_llm_client().draft_spec(requirement, existing))
        if error is not None:
            return error
        assert content is not None
        path, content_hash = context.artifacts.write("spec", content)
        session_id = int(context.session["id"])
        context.store.record_artifact_revision(session_id, "spec", context.artifacts.relative(path), content_hash)
        context.store.update_branch_session(
            session_id,
            active_stage="spec",
            active_spec_hash=content_hash,
            recommended_next="/loom:plan",
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok",
            message="spec.md generated",
            recommended_next="/loom:plan",
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _run_plan(self, context: StageContext) -> KernelResponse:
        spec = context.artifacts.read("spec")
        if spec is None:
            return KernelResponse(status="failed", message="spec.md is required", recommended_next="/loom:spec", errors=["missing_spec"])
        spec_hash = context.artifacts.hash_existing("spec")
        constraints = str(context.request.args.get("constraints") or context.request.args.get("revision_note") or "") or None
        content, error = self._candidate_content(context, lambda: create_llm_client().draft_plan(spec, constraints))
        if error is not None:
            return error
        assert content is not None
        path, content_hash = context.artifacts.write("plan", content)
        session_id = int(context.session["id"])
        context.store.record_artifact_revision(session_id, "plan", context.artifacts.relative(path), content_hash, based_on_spec_hash=spec_hash)
        context.store.update_branch_session(
            session_id,
            active_stage="plan",
            active_spec_hash=spec_hash,
            active_plan_hash=content_hash,
            recommended_next="/loom:tasks",
            recommended_task_id=None,
        )
        return KernelResponse(
            status="ok",
            message="plan.md generated",
            recommended_next="/loom:tasks",
            artifact_paths=[context.artifacts.relative(path)],
        )

    def _run_tasks(self, context: StageContext) -> KernelResponse:
        spec = context.artifacts.read("spec")
        plan = context.artifacts.read("plan")
        if spec is None:
            return KernelResponse(status="failed", message="spec.md is required", recommended_next="/loom:spec", errors=["missing_spec"])
        if plan is None:
            return KernelResponse(status="failed", message="plan.md is required", recommended_next="/loom:plan", errors=["missing_plan"])
        spec_hash = context.artifacts.hash_existing("spec")
        plan_hash = context.artifacts.hash_existing("plan")
        preference = str(context.request.args.get("preference") or context.request.args.get("revision_note") or "") or None
        content, error = self._candidate_content(context, lambda: create_llm_client().draft_tasks(spec, plan, preference))
        if error is not None:
            return error
        assert content is not None
        tasks = parse_tasks(content)
        if not tasks:
            return KernelResponse(
                status="failed",
                message="tasks.md candidate contains no parseable tasks",
                recommended_next="/loom:tasks",
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
        recommended_task_id = tasks[0].task_id if tasks else None
        recommended_next = self._recommended_do(recommended_task_id) if recommended_task_id else "/loom:do"
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
            return KernelResponse(status="failed", message="tasks.md is required", recommended_next="/loom:tasks", errors=["missing_tasks"])

        spec_hash = context.artifacts.hash_existing("spec")
        plan_hash = context.artifacts.hash_existing("plan")
        tasks_hash = context.artifacts.hash_existing("tasks")
        if tasks_hash is None:
            return KernelResponse(status="failed", message="tasks.md is empty", recommended_next="/loom:tasks", errors=["missing_tasks_hash"])

        drift = self._drift_response(context, spec_hash, plan_hash)
        if drift is not None:
            return drift

        tasks = parse_tasks(tasks_content)
        if not tasks:
            return KernelResponse(status="failed", message="no tasks found", recommended_next="/loom:tasks", errors=["no_tasks"])
        self._record_task_snapshots(context, tasks_content, tasks_hash)
        self._supersede_stale_task_state(context, tasks)

        blocking = self._open_execution_blocking_findings(context)
        if blocking:
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
                return KernelResponse(status="failed", message=f"task not found: {requested}", recommended_next="/loom:tasks", errors=["task_not_found"])
            return KernelResponse(status="ok", message="all tasks already verified", recommended_next="/loom:ship")

        latest_snapshot = context.store.latest_task_snapshot(session_id, task.task_id)
        latest_attempt = context.store.latest_attempt(session_id, task.task_id)
        decision = self.resolver.resolve(task, latest_snapshot, latest_attempt, False)
        if decision.action == "verified":
            return KernelResponse(status="ok", message=decision.message, recommended_next=decision.recommended_next)
        if decision.action in {"blocked", "superseded"}:
            return KernelResponse(status="blocked", message=decision.message, recommended_next=decision.recommended_next)
        if latest_attempt and latest_attempt.get("status") == "running":
            context.store.update_attempt(int(latest_attempt["id"]), "abandoned", "abandoned during recovery")
        elif latest_attempt and decision.action in {"retry", "reattempt"}:
            context.store.supersede_open_findings_for_attempt(int(latest_attempt["id"]))

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
        diff_ref = context.evidence.write_attempt_file(task.task_id, attempt_no, "diff.patch", runtime_result.diff)
        stdout_ref = context.evidence.write_attempt_file(task.task_id, attempt_no, "runtime.stdout.log", runtime_result.stdout)
        stderr_ref = context.evidence.write_attempt_file(task.task_id, attempt_no, "runtime.stderr.log", runtime_result.stderr)
        context.store.add_runtime_ref(attempt_id, "diff", diff_ref)
        context.store.add_runtime_ref(attempt_id, "stdout", stdout_ref)
        context.store.add_runtime_ref(attempt_id, "stderr", stderr_ref)

        verification_results = self.verifier.run(context.request.cwd, context.config.commands)
        verification_failed = False
        for index, result in enumerate(verification_results, start=1):
            verify_stdout_ref = context.evidence.write_attempt_file(task.task_id, attempt_no, f"verify{index}.stdout.log", result.stdout)
            verify_stderr_ref = context.evidence.write_attempt_file(task.task_id, attempt_no, f"verify{index}.stderr.log", result.stderr)
            context.store.record_verification(attempt_id, result.command, result.status, result.exit_code, verify_stdout_ref, verify_stderr_ref)
            if result.status == "failed":
                verification_failed = True

        status = attempt_status(runtime_result.success, verification_failed)
        context.store.update_attempt(attempt_id, status, runtime_result.summary)
        if status == "verified":
            context.store.resolve_open_findings_for_attempt(attempt_id, "verification_failure")
        if status == "failed":
            context.store.add_finding(
                session_id,
                attempt_id,
                "verification_failure",
                "blocking",
                f"verification failed for {task.task_id}",
                "/loom:do",
            )
        if status == "failed":
            recommendation = NextRecommendation(self._recommended_do(task.task_id), task.task_id)
        else:
            next_task = self._select_recommended_task(context, tasks)
            if next_task is None:
                recommendation = NextRecommendation("/loom:ship")
            else:
                recommendation = NextRecommendation(self._recommended_do(next_task.task_id), next_task.task_id)
        context.store.update_branch_session(
            session_id,
            active_stage="do",
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
        )
        return KernelResponse(
            status="ok" if status == "verified" else "failed",
            message=runtime_result.summary,
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
        )

    def _run_ship(self, context: StageContext) -> KernelResponse:
        session_id = int(context.session["id"])
        spec_hash = context.artifacts.hash_existing("spec")
        plan_hash = context.artifacts.hash_existing("plan")
        tasks_hash = context.artifacts.hash_existing("tasks")
        drift = self._drift_response(context, spec_hash, plan_hash)
        if drift is not None:
            return drift
        tasks_content = context.artifacts.read("tasks") or ""
        tasks = parse_tasks(tasks_content)
        if tasks_hash:
            self._record_task_snapshots(context, tasks_content, tasks_hash)
        self._supersede_stale_task_state(context, tasks)
        blocking = context.store.open_blocking_findings(session_id)
        attempts = context.store.attempts(session_id)
        completed_tasks = []
        runtime_refs = []
        verification_warnings = []
        for task in tasks:
            latest = context.store.latest_attempt(session_id, task.task_id)
            if latest and latest.get("status") == "verified":
                completed_tasks.append(task.task_id)
                attempt_id = int(latest["id"])
                runtime_refs.extend(ref["path"] for ref in context.store.runtime_refs(attempt_id))
                if any(item["status"] == "skipped_config_missing" for item in context.store.verifications_for_attempt(attempt_id)):
                    verification_warnings.append(f"{task.task_id}: verification command missing")
        all_verified = bool(tasks) and len(completed_tasks) == len(tasks)
        ship_status = "shippable" if all_verified and not blocking else "blocked"
        facts = {
            "status": ship_status,
            "spec_hash": spec_hash or "",
            "plan_hash": plan_hash or "",
            "tasks_hash": tasks_hash or "",
            "completed_tasks": completed_tasks,
            "verification_summary": self._verification_summary(len(completed_tasks), len(tasks), verification_warnings),
            "open_findings": [finding["message"] for finding in blocking],
            "runtime_refs": runtime_refs,
            "attempt_count": len(attempts),
        }
        content, error = self._candidate_content(context, lambda: create_llm_client().draft_ship_summary(facts))
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
            message=f"ship.md generated: {ship_status}",
            recommended_next=recommendation.command,
            recommended_task_id=recommendation.task_id,
            artifact_paths=[context.artifacts.relative(path)],
            findings=blocking,
        )

    def _verification_summary(self, completed_count: int, task_count: int, warnings: list[str]) -> str:
        summary = f"{completed_count}/{task_count} tasks verified"
        if warnings:
            summary += "\nWarnings:\n" + "\n".join(f"- {warning}" for warning in warnings)
        return summary


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
            if latest is None or latest.get("status") != "verified" or latest.get("task_fingerprint") != task.fingerprint:
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
