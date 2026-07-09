from datetime import datetime, timezone
from pathlib import Path

from codeloom.platform_feedback.analyzer import draft_cases_from_sessions
from codeloom.platform_feedback.loader import load_feedback_sessions, validate_feedback_sessions
from codeloom.platform_feedback.models import PlatformFeedbackRun, RunMetadata
from codeloom.platform_feedback.version import PLATFORM_FEEDBACK_SCHEMA_VERSION, PLATFORM_FEEDBACK_TOOL_VERSION


def run_platform_feedback(session_dir: Path) -> PlatformFeedbackRun:
    sessions = load_feedback_sessions(session_dir)
    validation_issues = validate_feedback_sessions(sessions)
    drafts = draft_cases_from_sessions(sessions)
    metadata = RunMetadata(
        schema_version=PLATFORM_FEEDBACK_SCHEMA_VERSION,
        tool_version=PLATFORM_FEEDBACK_TOOL_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    return PlatformFeedbackRun(
        sessions=sessions,
        drafts=drafts,
        validation_issues=validation_issues,
        metadata=metadata,
    )
