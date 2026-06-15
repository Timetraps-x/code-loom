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


def render_kernel_response(response: KernelResponse) -> str:
    lines = [
        f"Status: {response.status}",
        f"Message: {response.message}",
    ]
    if response.recommended_next:
        lines.append(f"Recommended next: {response.recommended_next}")
    if response.recommended_task_id:
        lines.append(f"Recommended task: {response.recommended_task_id}")
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
        recommended_task = session.get("recommended_task_id") or "none"
        lines.append(f"Recommended next: {recommended_next}")
        lines.append(f"Recommended task: {recommended_task}")
        active_hashes = session.get("active_hashes") or {}
        if active_hashes:
            lines.append("Active hashes:")
            for key, value in active_hashes.items():
                lines.append(f"  - {key}: {_short_hash(value)}")
    else:
        lines.append("Session: missing")

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
        lines.append(f"  - {attempt.get('task_id')} a{attempt.get('attempt_no')}: {attempt.get('status')}{suffix}")

    if data.get("errors"):
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in data["errors"])
    return "\n".join(lines)


def render_doctor(data: dict[str, Any]) -> str:
    lines = [f"Status: {data['status']}", "Checks:"]
    for check in data.get("checks", []):
        lines.append(f"  - [{check['status']}] {check['name']}: {check['message']}")
    return "\n".join(lines)


def _short_hash(value: object | None) -> str:
    if not value:
        return ""
    text = str(value)
    return text[:12]
