from collections import defaultdict

from codeloom.platform_feedback.models import FeedbackCaseDraft, PlatformFeedbackRun, ValidationIssue


def render_platform_feedback_report(run: PlatformFeedbackRun) -> str:
    errors = [issue for issue in run.validation_issues if issue.severity == "error"]
    warnings = [issue for issue in run.validation_issues if issue.severity != "error"]

    lines = [
        "# Platform Feedback Report",
        "",
        "## Summary",
        f"- schema_version: {run.metadata.schema_version}",
        f"- tool_version: {run.metadata.tool_version}",
        f"- sessions: {len(run.sessions)}",
        f"- observations: {sum(len(session.observations) for session in run.sessions)}",
        f"- generated_drafts: {len(run.drafts)}",
        f"- validation_errors: {len(errors)}",
        f"- validation_warnings: {len(warnings)}",
        "",
    ]

    lines.extend(_issues_section("Validation errors", errors))
    lines.extend(_issues_section("Validation warnings", warnings))
    lines.extend(_draft_group_section("Drafts by quality dimension", _drafts_by_dimension(run.drafts)))
    lines.extend(_draft_group_section("Drafts by stage / agent", _drafts_by_stage_agent(run.drafts)))
    lines.extend(["## Generated draft cases", ""])
    for draft in run.drafts:
        dimensions = ", ".join(draft.quality_dimensions)
        lines.append(f"- `{draft.id}` — {draft.title} ({draft.stage}/{draft.agent}; {dimensions})")
    return "\n".join(lines).rstrip() + "\n"


def _issues_section(title: str, issues: list[ValidationIssue]) -> list[str]:
    lines = [f"## {title}", ""]
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(f"- `{issue.path}`: {issue.message}")
    lines.append("")
    return lines


def _draft_group_section(title: str, groups: dict[str, list[FeedbackCaseDraft]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not groups:
        lines.append("- none")
    else:
        for key in sorted(groups):
            draft_ids = ", ".join(f"`{draft.id}`" for draft in groups[key])
            lines.append(f"- {key}: {draft_ids}")
    lines.append("")
    return lines


def _drafts_by_dimension(drafts: tuple[FeedbackCaseDraft, ...]) -> dict[str, list[FeedbackCaseDraft]]:
    groups: dict[str, list[FeedbackCaseDraft]] = defaultdict(list)
    for draft in drafts:
        for dimension in draft.quality_dimensions:
            groups[dimension].append(draft)
    return groups


def _drafts_by_stage_agent(drafts: tuple[FeedbackCaseDraft, ...]) -> dict[str, list[FeedbackCaseDraft]]:
    groups: dict[str, list[FeedbackCaseDraft]] = defaultdict(list)
    for draft in drafts:
        groups[f"{draft.stage}/{draft.agent}"].append(draft)
    return groups
