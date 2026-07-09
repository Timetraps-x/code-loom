import json
from pathlib import Path
from typing import Any

from codeloom.platform_feedback.models import (
    FeedbackEvidenceRef,
    FeedbackObservation,
    FeedbackSession,
    ProjectMetadata,
    ValidationIssue,
)
from codeloom.platform_feedback.taxonomy import FAILURE_MODES, QUALITY_DIMENSIONS


def load_feedback_sessions(session_dir: Path) -> tuple[FeedbackSession, ...]:
    sessions: list[FeedbackSession] = []
    for path in sorted(session_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in _session_items(data):
            sessions.append(_session_from_dict(item))
    return tuple(sessions)


def validate_feedback_session(session: FeedbackSession) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    prefix = f"session:{session.id}"

    _require(issues, prefix, "id", session.id)
    _require(issues, prefix, "title", session.title)
    _require(issues, prefix, "source", session.source)

    if not session.project.languages and not session.project.frameworks:
        issues.append(ValidationIssue(f"{prefix}.project", "project must declare at least one language or framework"))

    if not session.observations:
        issues.append(ValidationIssue(f"{prefix}.observations", "session must contain at least one observation"))

    for index, observation in enumerate(session.observations):
        obs_path = f"{prefix}.observations[{index}]"
        _require(issues, obs_path, "id", observation.id)
        _require(issues, obs_path, "summary", observation.summary)
        _require(issues, obs_path, "stage", observation.stage)
        _require(issues, obs_path, "agent", observation.agent)
        _require(issues, obs_path, "failure_mode", observation.failure_mode)
        _require(issues, obs_path, "actual_behavior", observation.actual_behavior)
        _require(issues, obs_path, "expected_behavior", observation.expected_behavior)

        if not observation.quality_dimensions:
            issues.append(ValidationIssue(f"{obs_path}.quality_dimensions", "observation must declare at least one quality dimension"))

        for dimension in observation.quality_dimensions:
            if dimension not in QUALITY_DIMENSIONS:
                issues.append(ValidationIssue(f"{obs_path}.quality_dimensions", f"unknown quality dimension: {dimension}", "warning"))

        if observation.failure_mode and observation.failure_mode not in FAILURE_MODES:
            issues.append(ValidationIssue(f"{obs_path}.failure_mode", f"unknown failure mode: {observation.failure_mode}", "warning"))

        if not observation.evidence:
            issues.append(ValidationIssue(f"{obs_path}.evidence", "observation has no evidence refs", "warning"))

    return tuple(issues)


def validate_feedback_sessions(sessions: tuple[FeedbackSession, ...]) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    for session in sessions:
        issues.extend(validate_feedback_session(session))
    return tuple(issues)


def _session_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and "sessions" in data:
        raw = data["sessions"]
        return raw if isinstance(raw, list) else []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _session_from_dict(data: dict[str, Any]) -> FeedbackSession:
    return FeedbackSession(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        source=str(data.get("source", "")),
        project=_project_from_dict(data.get("project", {})),
        observations=tuple(_observation_from_dict(item) for item in data.get("observations", [])),
        tags=_strings(data.get("tags", [])),
        captured_at=str(data.get("captured_at", "")),
    )


def _project_from_dict(data: Any) -> ProjectMetadata:
    data = data if isinstance(data, dict) else {}
    return ProjectMetadata(
        languages=_strings(data.get("languages", [])),
        frameworks=_strings(data.get("frameworks", [])),
        project_type=str(data.get("project_type", "")),
        runtime=str(data.get("runtime", "")),
        architecture_notes=_strings(data.get("architecture_notes", [])),
    )


def _observation_from_dict(data: dict[str, Any]) -> FeedbackObservation:
    return FeedbackObservation(
        id=str(data.get("id", "")),
        summary=str(data.get("summary", "")),
        stage=str(data.get("stage", "")),
        agent=str(data.get("agent", "")),
        quality_dimensions=_strings(data.get("quality_dimensions", [])),
        failure_mode=str(data.get("failure_mode", "")),
        actual_behavior=str(data.get("actual_behavior", "")),
        expected_behavior=str(data.get("expected_behavior", "")),
        evidence=tuple(_evidence_from_dict(item) for item in data.get("evidence", [])),
        downstream_impact=str(data.get("downstream_impact", "")),
        candidate_prompt_surfaces=_strings(data.get("candidate_prompt_surfaces", [])),
    )


def _evidence_from_dict(data: dict[str, Any]) -> FeedbackEvidenceRef:
    return FeedbackEvidenceRef(
        kind=str(data.get("kind", "")),
        ref=str(data.get("ref", "")),
        note=str(data.get("note", "")),
    )


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _require(issues: list[ValidationIssue], prefix: str, field: str, value: str) -> None:
    if not value:
        issues.append(ValidationIssue(f"{prefix}.{field}", f"missing required field: {field}"))
