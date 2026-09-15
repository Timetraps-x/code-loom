from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from codeloom.spec_evals.models import SpecEvalRun, SpecEvalResult


def write_run(run: SpecEvalRun, output_dir: Path) -> Path:
    root = Path(output_dir).resolve() / run.run_id
    root.mkdir(parents=True, exist_ok=False)
    results: list[SpecEvalResult] = []
    for result in run.results:
        result_root = root / result.case.id
        result_root.mkdir()
        paths = {
            "initial_draft": _write_text(result_root / "initial-draft.md", _turn_content(result, "spec-analyzer", 0)),
            "reviewer_findings": _write_text(result_root / "reviewer-findings.json", _json(result.reviewer_findings)),
            "dispositions": _write_text(result_root / "dispositions.json", _json(result.dispositions)),
            "comparison": _write_text(result_root / "comparison.json", _json(_comparison(result))),
            "final_artifact": _write_text(result_root / "final-spec.md", result.final_artifact),
        }
        updated = replace(result, output_paths=paths)
        results.append(updated)
        (result_root / "result.json").write_text(json.dumps(_result_dict(updated), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    completed_run = replace(run, results=tuple(results))
    (root / "report.json").write_text(json.dumps(completed_run.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "report.md").write_text(render_run(completed_run), encoding="utf-8")
    return root


def render_run(run: SpecEvalRun) -> str:
    lines = [
        f"# Spec Evaluation Run {run.run_id}",
        "",
        f"- executor: {run.metadata.get('executor', '')}",
        f"- package_version: {run.metadata.get('package_version', '')}",
        f"- passed: {len(run.passed)}",
        f"- failed: {len(run.failed)}",
        f"- needs_human_review: {len(run.needs_human_review)}",
        "",
    ]
    for result in run.results:
        lines.extend([f"## {result.case.id}", "", f"- status: `{result.status}`"])
        if result.error:
            lines.append(f"- error: {result.error}")
        if result.rubric.failures:
            lines.append("- failures:")
            lines.extend(f"  - {failure}" for failure in result.rubric.failures)
        if result.rubric.manual_review:
            lines.append("- manual_review:")
            lines.extend(f"  - {item}" for item in result.rubric.manual_review)
        comparison = _comparison(result)
        if result.initial_rubric is not None:
            lines.append(f"- resolved_failures: {len(comparison['resolved_failures'])}")
            lines.append(f"- introduced_failures: {len(comparison['introduced_failures'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _turn_content(result: SpecEvalResult, role: str, occurrence: int) -> str:
    matches = [turn.content for turn in result.turns if turn.role == role]
    return matches[occurrence] if len(matches) > occurrence else ""


def _write_text(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return path.name


def _json(value: Any) -> str:
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        value = [item.to_dict() if hasattr(item, "to_dict") else item.__dict__ for item in value]
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _comparison(result: SpecEvalResult) -> dict[str, list[str]]:
    initial = set(result.initial_rubric.failures) if result.initial_rubric else set()
    final = set(result.rubric.failures)
    return {
        "resolved_failures": sorted(initial - final),
        "introduced_failures": sorted(final - initial),
        "remaining_failures": sorted(final),
    }


def _result_dict(result: SpecEvalResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "case_id": result.case.id,
        "status": result.status,
        "error": result.error,
        "rubric": {
            "rubric_id": result.rubric.rubric_id,
            "failures": list(result.rubric.failures),
            "manual_review": list(result.rubric.manual_review),
        },
        "initial_rubric": None
        if result.initial_rubric is None
        else {
            "rubric_id": result.initial_rubric.rubric_id,
            "failures": list(result.initial_rubric.failures),
            "manual_review": list(result.initial_rubric.manual_review),
        },
        "comparison": _comparison(result),
        "turns": [turn.__dict__ for turn in result.turns],
        "reviewer_findings": [finding.to_dict() for finding in result.reviewer_findings],
        "dispositions": [disposition.to_dict() for disposition in result.dispositions],
        "output_paths": result.output_paths,
        "metadata": result.metadata,
    }
