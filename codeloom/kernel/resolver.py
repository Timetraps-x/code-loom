from __future__ import annotations

from dataclasses import dataclass

from codeloom.kernel.artifacts import TaskDefinition


@dataclass(frozen=True)
class ResolverDecision:
    action: str
    message: str
    recommended_next: str | None = None


class ContractRevisionResolver:
    def resolve(
        self,
        task: TaskDefinition | None,
        latest_snapshot: dict[str, object] | None,
        latest_attempt: dict[str, object] | None,
        has_open_blocking_finding: bool,
    ) -> ResolverDecision:
        if has_open_blocking_finding:
            return ResolverDecision("blocked", "open blocking finding exists", None)
        if task is None:
            return ResolverDecision("superseded", "task does not exist", "/loom-tasks")
        if latest_attempt and latest_attempt.get("task_fingerprint") != task.fingerprint:
            return ResolverDecision("reattempt", "task definition changed since latest attempt", "/loom-do")
        if latest_snapshot and latest_snapshot.get("task_fingerprint") != task.fingerprint:
            return ResolverDecision("reattempt", "task definition changed", "/loom-do")
        if not latest_attempt:
            return ResolverDecision("execute", "no previous attempt", "/loom-do")
        status = latest_attempt.get("status")
        if status == "running":
            return ResolverDecision("continue", "latest attempt is still running", "/loom-do")
        if status == "failed":
            return ResolverDecision("retry", "latest attempt failed", "/loom-do")
        if status == "verified" or (status == "implemented" and task.lane == "build"):
            return ResolverDecision("verified", f"task already {status}", "/loom-ship")
        return ResolverDecision("execute", f"latest attempt status is {status}", "/loom-do")
