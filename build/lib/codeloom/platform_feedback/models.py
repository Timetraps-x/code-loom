from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectMetadata:
    languages: tuple[str, ...]
    frameworks: tuple[str, ...] = ()
    project_type: str = ""
    runtime: str = ""
    architecture_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedbackEvidenceRef:
    kind: str
    ref: str
    note: str = ""


@dataclass(frozen=True)
class FeedbackObservation:
    id: str
    summary: str
    stage: str
    agent: str
    quality_dimensions: tuple[str, ...]
    failure_mode: str
    actual_behavior: str
    expected_behavior: str
    evidence: tuple[FeedbackEvidenceRef, ...] = ()
    downstream_impact: str = ""
    candidate_prompt_surfaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedbackSession:
    id: str
    title: str
    source: str
    project: ProjectMetadata
    observations: tuple[FeedbackObservation, ...]
    tags: tuple[str, ...] = ()
    captured_at: str = ""


@dataclass(frozen=True)
class FeedbackCaseDraft:
    id: str
    title: str
    source_session_id: str
    source_observation_id: str
    project: ProjectMetadata
    stage: str
    agent: str
    quality_dimensions: tuple[str, ...]
    failure_mode: str
    scenario: str
    expected_behavior: str
    evidence: tuple[FeedbackEvidenceRef, ...]
    downstream_impact: str = ""
    candidate_prompt_surfaces: tuple[str, ...] = ()
    suggested_required_signals: tuple[str, ...] = ()
    suggested_forbidden_signals: tuple[str, ...] = ()
    status: str = "draft"


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class RunMetadata:
    schema_version: str
    tool_version: str
    generated_at: str


@dataclass(frozen=True)
class PlatformFeedbackRun:
    sessions: tuple[FeedbackSession, ...]
    drafts: tuple[FeedbackCaseDraft, ...]
    validation_issues: tuple[ValidationIssue, ...]
    metadata: RunMetadata
