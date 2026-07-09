from __future__ import annotations

from codeloom.prompt_evals.cases import PromptEvalRun


def render_failure_report(run: PromptEvalRun) -> str:
    lines = ["Prompt eval failures:"]
    for result in run.failed + run.partial:
        lines.append(f"- {result.case_id}: {result.status} ({result.score}/{result.max_score})")
        if result.missing_required:
            lines.append("  missing required signals:")
            lines.extend(f"    - {signal}" for signal in result.missing_required)
        if result.forbidden_hits:
            lines.append("  forbidden signals:")
            lines.extend(f"    - {signal}" for signal in result.forbidden_hits)
        if result.missing_surfaces:
            lines.append("  missing surfaces:")
            lines.extend(f"    - {surface}" for surface in result.missing_surfaces)
        if result.surfaces_checked:
            lines.append("  checked surfaces:")
            lines.extend(f"    - {surface}" for surface in result.surfaces_checked)
    if run.skipped:
        lines.append("Skipped cases:")
        lines.extend(f"- {result.case_id}: missing {', '.join(result.missing_surfaces)}" for result in run.skipped)
    return "\n".join(lines)
