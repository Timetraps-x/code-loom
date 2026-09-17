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


ARTIFACT_KINDS = ("spec", "plan", "tasks", "ship")


def derive_artifact_states(
    disk_hashes: dict[str, str | None],
    revisions: dict[str, dict[str, object]],
    execution_hash: str | None = None,
    task_error: str | None = None,
) -> dict[str, dict[str, object]]:
    states: dict[str, dict[str, object]] = {}
    latest_hashes = {
        kind: str(revision.get("content_hash")) if revision and revision.get("content_hash") else None
        for kind, revision in ((kind, revisions.get(kind)) for kind in ARTIFACT_KINDS)
    }
    repair_commands = {kind: f"/loom-{kind}" for kind in ARTIFACT_KINDS}
    for kind in ARTIFACT_KINDS:
        disk_hash = disk_hashes.get(kind)
        revision = revisions.get(kind)
        registered_hash = latest_hashes[kind]
        lineage_current = True
        stale_reason: str | None = None
        if kind in {"plan", "tasks", "ship"}:
            lineage_current = bool(
                revision
                and revision.get("based_on_spec_hash") == latest_hashes["spec"]
            )
            if not lineage_current:
                stale_reason = "registered lineage is based on an older spec"
        if kind in {"tasks", "ship"} and lineage_current:
            lineage_current = bool(
                revision
                and revision.get("based_on_plan_hash") == latest_hashes["plan"]
            )
            if not lineage_current:
                stale_reason = "registered lineage is based on an older plan"
        if kind == "ship" and lineage_current:
            lineage_current = bool(
                revision
                and revision.get("based_on_tasks_hash") == latest_hashes["tasks"]
                and (execution_hash is None or revision.get("based_on_execution_hash") == execution_hash)
            )
            if not lineage_current:
                stale_reason = "registered release inputs are no longer current"
        if disk_hash is None:
            state = "missing"
            stale_reason = stale_reason or "working copy is missing"
        elif revision is None:
            state = "unregistered"
            stale_reason = "working copy has no registered revision"
        elif disk_hash != registered_hash:
            state = "stale"
            stale_reason = "working copy differs from the latest registered revision"
        elif not lineage_current:
            state = "stale"
        elif kind == "tasks" and task_error:
            state = "stale"
            stale_reason = task_error
        else:
            state = "current"
        states[kind] = {
            "state": state,
            "disk_hash": disk_hash,
            "registered_revision_id": int(revision["id"]) if revision else None,
            "registered_hash": registered_hash,
            "lineage_current": lineage_current,
            "stale_reason": stale_reason,
            "recovery_command": repair_commands[kind],
        }
    return states


def earliest_artifact_repair(
    states: dict[str, dict[str, object]],
    through: str = "tasks",
) -> str | None:
    limit = ARTIFACT_KINDS.index(through)
    for kind in ARTIFACT_KINDS[: limit + 1]:
        if states[kind]["state"] != "current":
            return str(states[kind]["recovery_command"])
    return None