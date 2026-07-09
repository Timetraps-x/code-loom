from pathlib import PurePosixPath, PureWindowsPath

from codeloom.platform_feedback.models import FeedbackCaseDraft


_SURFACE_KIND_BY_PREFIX = {
    "agent:": "agent",
    "template:": "template",
    "skill_agent_rule:": "skill_agent_rule",
    "skill_content_rule:": "skill_content_rule",
    "skill_argument_rule:": "skill_argument_rule",
}


def draft_to_prompt_contract_payload(draft: FeedbackCaseDraft) -> dict[str, object]:
    surfaces = [_surface_payload(surface) for surface in draft.candidate_prompt_surfaces]
    return {
        "id": _prompt_contract_id(draft.id),
        "title": draft.title,
        "agent": draft.agent,
        "stage": draft.stage,
        "quality_dimensions": list(draft.quality_dimensions),
        "failure_mode": draft.failure_mode,
        "surfaces": [surface for surface in surfaces if surface],
        "badcase": draft.scenario,
        "expected_behavior": draft.expected_behavior,
        "downstream_impact": draft.downstream_impact,
        "required_signals": list(draft.suggested_required_signals),
        "forbidden_signals": list(draft.suggested_forbidden_signals),
        "rubric": ["Derived from a platform feedback draft; review before promoting to active prompt contract coverage."],
    }


def _prompt_contract_id(draft_id: str) -> str:
    if draft_id.startswith("draft."):
        return "feedback." + draft_id[len("draft.") :]
    return "feedback." + draft_id


def _surface_payload(surface: str) -> dict[str, str]:
    for prefix, kind in _SURFACE_KIND_BY_PREFIX.items():
        if surface.startswith(prefix):
            return {"kind": kind, "ref": _normalize_surface_ref(kind, surface[len(prefix) :])}
    return {}


def _normalize_surface_ref(kind: str, ref: str) -> str:
    if kind != "agent":
        return ref

    normalized_ref = ref.replace("\\", "/")
    if "/codeloom/agents/" in normalized_ref or normalized_ref.startswith("codeloom/agents/"):
        return PurePosixPath(normalized_ref).name
    if "\\codeloom\\agents\\" in ref or ref.startswith("codeloom\\agents\\"):
        return PureWindowsPath(ref).name
    return ref
