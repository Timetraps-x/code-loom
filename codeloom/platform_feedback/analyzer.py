import re

from codeloom.platform_feedback.models import FeedbackCaseDraft, FeedbackSession
from codeloom.platform_feedback.taxonomy import SUGGESTED_SIGNALS_BY_DIMENSION


TASK_CONTEXT_LEAK_FAILURE_MODE = "task_context_leaked_into_constitution"

TASK_CONTEXT_LEAK_REQUIRED_SIGNALS = (
    "constitution is a stable project rulebook / quality baseline",
    "separate stable project guidance from temporary task context",
    "capture only project constraints reusable across future unrelated tasks",
    "route task details to spec.md, plan.md, tasks.md, or task evidence",
    "summarize task-specific evidence as boundary categories without copying concrete values",
)

TASK_CONTEXT_LEAK_FORBIDDEN_PATTERNS = (
    r"\b[A-Z]+-\d+\b",
    r"/[A-Za-z0-9_{}./:-]+",
    r"\b[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)* Phase \d+\b",
    r"\bmigration phase [^,.;，。]+",
    r"\b[\w-]+\.(?:md|yml|yaml|json)\b",
)

TASK_CONTEXT_LEAK_FORBIDDEN_PHRASES = (
    "acceptance criteria",
    "stage-agent execution instructions",
)


def draft_cases_from_sessions(sessions: tuple[FeedbackSession, ...]) -> tuple[FeedbackCaseDraft, ...]:
    drafts: list[FeedbackCaseDraft] = []
    for session in sessions:
        for observation in session.observations:
            draft_id = f"draft.{_slug(session.id)}.{_slug(observation.id)}"
            drafts.append(
                FeedbackCaseDraft(
                    id=draft_id,
                    title=observation.summary,
                    source_session_id=session.id,
                    source_observation_id=observation.id,
                    project=session.project,
                    stage=observation.stage,
                    agent=observation.agent,
                    quality_dimensions=observation.quality_dimensions,
                    failure_mode=observation.failure_mode,
                    scenario=observation.actual_behavior,
                    expected_behavior=observation.expected_behavior,
                    evidence=observation.evidence,
                    downstream_impact=observation.downstream_impact,
                    candidate_prompt_surfaces=observation.candidate_prompt_surfaces,
                    suggested_required_signals=_suggest_required_signals(
                        observation.quality_dimensions,
                        observation.expected_behavior,
                        observation.failure_mode,
                    ),
                    suggested_forbidden_signals=_suggest_forbidden_signals(
                        observation.failure_mode,
                        observation.actual_behavior,
                    ),
                )
            )
    return tuple(drafts)


def _suggest_required_signals(dimensions: tuple[str, ...], expected_behavior: str, failure_mode: str) -> tuple[str, ...]:
    signals: list[str] = []
    for dimension in dimensions:
        _append_unique(signals, SUGGESTED_SIGNALS_BY_DIMENSION.get(dimension, ()))

    if failure_mode == TASK_CONTEXT_LEAK_FAILURE_MODE:
        _append_unique(signals, TASK_CONTEXT_LEAK_REQUIRED_SIGNALS)

    expected = " ".join(expected_behavior.split())
    if 0 < len(expected) <= 120:
        _append_unique(signals, (expected,))
    return tuple(signals)


def _suggest_forbidden_signals(failure_mode: str, actual_behavior: str) -> tuple[str, ...]:
    if failure_mode != TASK_CONTEXT_LEAK_FAILURE_MODE:
        return ()

    signals: list[str] = []
    for pattern in TASK_CONTEXT_LEAK_FORBIDDEN_PATTERNS:
        _append_unique(signals, tuple(match.group(0).strip() for match in re.finditer(pattern, actual_behavior)))

    lower_behavior = actual_behavior.lower()
    for phrase in TASK_CONTEXT_LEAK_FORBIDDEN_PHRASES:
        if phrase in lower_behavior:
            _append_unique(signals, (phrase,))
    return tuple(signals)


def _append_unique(signals: list[str], candidates: tuple[str, ...]) -> None:
    for signal in candidates:
        if signal not in signals:
            signals.append(signal)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "unnamed"
