from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriftDecision:
    status: str
    message: str
    recommended_next: str


def detect_plan_or_task_drift(
    spec_hash: str | None,
    plan_hash: str | None,
    latest_plan_revision: dict[str, object] | None,
    latest_tasks_revision: dict[str, object] | None,
) -> DriftDecision | None:
    if spec_hash and latest_plan_revision and latest_plan_revision.get("based_on_spec_hash") != spec_hash:
        return DriftDecision("noop", "plan.md is based on an older spec.md", "/loom-plan")
    if plan_hash and latest_tasks_revision and latest_tasks_revision.get("based_on_plan_hash") != plan_hash:
        return DriftDecision("noop", "tasks.md is based on an older plan.md", "/loom-tasks")
    if spec_hash and latest_tasks_revision and latest_tasks_revision.get("based_on_spec_hash") != spec_hash:
        return DriftDecision("noop", "tasks.md is based on an older spec.md", "/loom-tasks")
    return None
