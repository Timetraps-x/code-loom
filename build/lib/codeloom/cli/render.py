from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from codeloom.app.response import KernelResponse


def emit_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def emit_kernel_response(response: KernelResponse, json_output: bool) -> None:
    if json_output:
        emit_json(response.to_dict())
        return
    print(render_kernel_response(response))


def emit_data(data: dict[str, Any], json_output: bool, renderer: Callable[[dict[str, Any]], str]) -> None:
    if json_output:
        emit_json(data)
        return
    print(renderer(data))


def _recommended_task_label(task_id: str | None, task_title: str | None) -> str:
    if not task_id:
        return "none"
    if task_title:
        return f"{task_id}-{task_title}"
    return task_id


def render_kernel_response(response: KernelResponse) -> str:
    lines = [
        f"Status: {response.status}",
        f"Message: {response.message}",
    ]
    if response.recommended_next:
        lines.append(f"Recommended next: {response.recommended_next}")
    if response.recommended_task_id:
        task_label = _recommended_task_label(response.recommended_task_id, response.recommended_task_title)
        lines.append(f"Recommended task: {task_label}")
    if response.artifact_paths:
        lines.append("Artifacts:")
        lines.extend(f"  - {path}" for path in response.artifact_paths)
    if response.findings:
        lines.append(f"Findings: {len(response.findings)}")
        for finding in response.findings:
            severity = finding.get("severity", "unknown")
            kind = finding.get("kind", "unknown")
            message = finding.get("message", "")
            next_step = finding.get("suggested_next")
            suffix = f" -> {next_step}" if next_step else ""
            lines.append(f"  - [{severity}/{kind}] {message}{suffix}")
    if response.extras:
        lines.append("Extras:")
        for key, value in response.extras.items():
            lines.append(f"  - {key}: {value}")
    if response.errors:
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in response.errors)
    return "\n".join(lines)


def render_init(data: dict[str, Any]) -> str:
    lines = [
        f"Status: {data['status']}",
        f"Message: {data['message']}",
        f"Project path: {data['project_path']}",
    ]
    integrations = data.get("integrations") or []
    if integrations:
        lines.append(f"Integrations: {', '.join(integrations)}")
    if data.get("language"):
        lines.append(f"Specs language: {data['language']}")
    return "\n".join(lines)


def render_adopt(data: dict[str, Any]) -> str:
    constitution = data.get("constitution") or {}
    lines = [
        f"Status: {data['status']}",
        f"Message: {data['message']}",
        f"Constitution: {constitution.get('path', '')}",
    ]
    current_hash = _short_hash(constitution.get("current_hash"))
    registered_hash = _short_hash(constitution.get("registered_hash"))
    lines.append(f"Seeded: {bool(constitution.get('seeded'))}")
    lines.append(f"Usable: {bool(constitution.get('usable'))}")
    if current_hash:
        lines.append(f"Current hash: {current_hash}")
    if registered_hash:
        lines.append(f"Registered hash: {registered_hash}")
    if data.get("errors"):
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in data["errors"])
    return "\n".join(lines)


def render_status(data: dict[str, Any]) -> str:
    lines = [
        f"Status: {data['status']}",
        f"Branch: {data['branch_name']} ({data['branch_slug']})",
        f"Artifact root: {data['artifact_root']}",
        f"Database: {'present' if data['db_exists'] else 'missing'}",
    ]
    session = data.get("session") or {}
    if session:
        recommended_next = session.get("recommended_next") or "none"
        recommended_task = _recommended_task_label(session.get("recommended_task_id"), session.get("recommended_task_title"))
        lines.append(f"Recommended next: {recommended_next}")
        lines.append(f"Recommended task: {recommended_task}")
        continuation = session.get("continuation") or {}
        if continuation:
            task = f" task={continuation.get('task_id')}" if continuation.get("task_id") else ""
            lines.append(
                f"Continuation: {continuation.get('source_stage')} -> {continuation.get('stage')}{task}: {continuation.get('reason')}"
            )
        active_hashes = session.get("active_hashes") or {}
        if active_hashes:
            lines.append("Active hashes:")
            for key, value in active_hashes.items():
                lines.append(f"  - {key}: {_short_hash(value)}")
    else:
        lines.append("Session: missing")

    constitution = data.get("constitution") or {}
    if constitution:
        if not constitution.get("exists"):
            state = "missing"
        elif constitution.get("seeded"):
            state = "seeded/unadopted"
        elif constitution.get("usable"):
            state = "usable"
        elif constitution.get("registered"):
            state = "changed"
        else:
            state = "unregistered"
        current_hash = _short_hash(constitution.get("current_hash"))
        registered_hash = _short_hash(constitution.get("registered_hash"))
        suffix = f" current={current_hash}" if current_hash else ""
        registered = f" registered={registered_hash}" if registered_hash else ""
        lines.append(f"Constitution: {state}{suffix}{registered} {constitution.get('path')}")

    profile = data.get("project_profile") or {}
    profile_values = [
        *(profile.get("languages") or []),
        *(profile.get("frameworks") or []),
        *(profile.get("modules") or []),
    ]
    if profile_values:
        lines.append(f"Project profile: {', '.join(str(value) for value in profile_values)}")

    lines.append("Artifacts:")
    for kind, artifact in data.get("artifacts", {}).items():
        state = "present" if artifact.get("exists") else "missing"
        content_hash = _short_hash(artifact.get("hash"))
        suffix = f" ({content_hash})" if content_hash else ""
        lines.append(f"  - {kind}: {state}{suffix} {artifact.get('path')}")

    findings = data.get("open_findings") or []
    lines.append(f"Open findings: {len(findings)}")
    for finding in findings:
        lines.append(f"  - [{finding.get('severity')}/{finding.get('kind')}] {finding.get('message')}")

    attempts = data.get("latest_attempts") or []
    lines.append(f"Latest attempts: {len(attempts)}")
    for attempt in attempts:
        summary = attempt.get("summary") or ""
        suffix = f" - {summary}" if summary else ""
        lane = attempt.get("lane") or "?"
        complexity = attempt.get("complexity") or "?"
        effective_status = attempt.get("effective_status")
        blocked_by = attempt.get("blocked_by") or []
        state = f" effective={effective_status}" if effective_status else ""
        blockers = f" blocked_by={','.join(blocked_by)}" if blocked_by else ""
        lines.append(
            f"  - {attempt.get('task_id')} [{lane}/{complexity}] a{attempt.get('attempt_no')}: {attempt.get('status')}{state}{blockers}{suffix}"
        )

    if data.get("errors"):
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in data["errors"])
    return "\n".join(lines)


def render_doctor(data: dict[str, Any]) -> str:
    lines = [f"Status: {data['status']}", "Checks:"]
    for check in data.get("checks", []):
        lines.append(f"  - [{check['status']}] {check['name']}: {check['message']}")
    return "\n".join(lines)
def render_upgrade(data: dict[str, Any]) -> str:
    lines = [
        f"Status: {data['status']}",
        f"Dry run: {data.get('dry_run', False)}",
        f"Bundle version: {data.get('bundle_version', '')}",
        "Resources:",
    ]
    for resource in data.get("resources", []):
        lines.append(
            f"  - [{resource['status']}] {resource['path']}: {resource['message']}"
        )
    if data.get("errors"):
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in data["errors"])
    return "\n".join(lines)





def _short_hash(value: object | None) -> str:
    if not value:
        return ""
    text = str(value)
    return text[:12]
