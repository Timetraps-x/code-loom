from __future__ import annotations

import json
from pathlib import Path

import pytest

from codeloom.spec_evals.executor import FixtureExecutor
from codeloom.spec_evals.loader import load_spec_case, load_spec_cases
from codeloom.spec_evals.models import AgentTurn
from codeloom.spec_evals.report import write_run
from codeloom.spec_evals.runner import run_spec_case, run_spec_cases
from codeloom.spec_evals.rubric import RUBRICS


def _responses(final_artifact: str) -> dict[tuple[str, int], str]:
    return {
        ("spec-analyzer", 1): "初稿不使用固定标题。",
        ("spec-reviewer", 1): json.dumps(
            {
                "findings": [
                    {
                        "id": "proof-1",
                        "severity": "major",
                        "claim_or_counterexample": "局部成功不能证明业务结果。",
                        "evidence_basis": "evidence packet",
                        "uncertainty": "没有真实流程观察。",
                        "impact": "Plan 可能把局部成功当作完整结果。",
                        "recommendation": "补充结果与失败证明。",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        ("spec-analyzer", 2): json.dumps(
            {
                "dispositions": [
                    {
                        "finding_id": "proof-1",
                        "action": "accepted",
                        "rationale": "纳入结果和失败证明。",
                    }
                ],
                "final_artifact": final_artifact,
            },
            ensure_ascii=False,
        ),
    }


def test_all_packaged_cases_have_valid_metadata_and_registered_rubric():
    cases = load_spec_cases()

    assert len(cases) == 6
    assert [case.id for case in cases] == sorted(case.id for case in cases)
    assert len({case.source_sha256 for case in cases}) == len(cases)
    assert all(case.id.replace("-", "") for case in cases)
    assert all(case.rubric_id in RUBRICS for case in cases)
    assert all(case.narrative for case in cases)


def test_loader_supports_selected_case_and_rejects_invalid_metadata(tmp_path: Path):
    source = tmp_path / "valid-case.md"
    source.write_text(
        """# Valid\n\n```json spec-eval\n{\"id\": \"valid-case\", \"title\": \"Valid\", \"schema_version\": 1, \"language\": \"en\", \"entry_request\": \"request\", \"evidence_packet\": [\"fact\"], \"review_focus\": [\"scope\"], \"quality_dimensions\": [\"scope\"], \"rubric_id\": \"missing\"}\n```\n\nNarrative.\n""",
        encoding="utf-8",
    )

    case = load_spec_case("valid-case", tmp_path)
    assert case.source_path == str(source)
    assert case.narrative == "# Valid\n\n\n\nNarrative."

    invalid = tmp_path / "invalid-case.md"
    invalid.write_text(
        "```json spec-eval\n{\"id\": \"invalid-case\", \"language\": \"en\"}\n```",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing spec-eval fields"):
        load_spec_case("invalid-case", tmp_path)


def test_runner_keeps_analyzer_reviewer_revision_order_and_inputs():
    case = load_spec_case("owner-rule-conflict")
    final_artifact = "自由格式 Spec artifact：重试与冻结两个方向存在冲突，证据不能决定；需要 Owner 澄清，外部副作用与责任边界待定。"
    executor = FixtureExecutor(_responses(final_artifact))

    result = run_spec_case(case, executor, "run-1")

    assert result.status == "needs_human_review"
    assert [turn.role for turn in result.turns] == ["spec-analyzer", "spec-reviewer", "spec-analyzer"]
    assert executor.invocations[1].draft == "初稿不使用固定标题。"
    assert executor.invocations[2].draft == "初稿不使用固定标题。"
    assert executor.invocations[2].reviewer_findings[0]["id"] == "proof-1"
    assert result.final_artifact == final_artifact
    assert result.dispositions[0].action == "accepted"
    assert result.reviewer_findings[0].uncertainty == "没有真实流程观察。"
    assert result.reviewer_findings[0].impact == "Plan 可能把局部成功当作完整结果。"
    assert result.initial_rubric is not None
    assert all(turn.prompt_sha256 for turn in result.turns)
    assert len(result.metadata["prompt_hashes"]) == 3


def test_runner_accepts_json_code_fences_and_rejects_bad_revision():
    case = load_spec_case("sim-service-term-sync")
    responses = _responses("合法 artifact")
    responses[("spec-reviewer", 1)] = "```json\n{\"findings\": []}\n```"
    responses[("spec-analyzer", 2)] = json.dumps({"dispositions": [], "final_artifact": "合法 artifact"})
    executor = FixtureExecutor(responses)

    result = run_spec_case(case, executor, "run-2")
    assert result.final_artifact == "合法 artifact"
    assert result.reviewer_findings == ()

    bad = FixtureExecutor({("spec-analyzer", 1): "draft", ("spec-reviewer", 1): "{not-json}"})
    failed = run_spec_case(case, bad, "run-3")
    assert failed.status == "execution_error"
    assert "JSONDecodeError" in (failed.error or "")


def test_rubric_failure_is_evaluation_result_not_runtime_gate():
    case = load_spec_case("export-field-correction")
    executor = FixtureExecutor(_responses("unrelated output"))

    run = run_spec_cases((case,), executor, run_id="run-fail")

    assert run.results[0].status == "fail"
    assert run.failed == run.results
    assert run.results[0].rubric.failures


def test_report_writes_isolated_non_overwriting_run(tmp_path: Path):
    case = load_spec_case("non-template-complex-artifact")
    run = run_spec_cases((case,), FixtureExecutor(_responses("final markdown")), run_id="fixed-run")
    root = write_run(run, tmp_path)

    assert root == tmp_path.resolve() / "fixed-run"
    assert (root / "report.json").exists()
    assert (root / "report.md").exists()
    assert (root / case.id / "initial-draft.md").read_text(encoding="utf-8") == "初稿不使用固定标题。"
    assert (root / case.id / "comparison.json").exists()
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    assert report["results"][0]["case"]["source_sha256"] == case.source_sha256
    assert report["results"][0]["initial_rubric"] is not None
    assert (root / case.id / "comparison.json").exists()
    assert report["results"][0]["turns"][0]["prompt_sha256"]

    with pytest.raises(FileExistsError):
        write_run(run, tmp_path)


def test_executor_failure_is_recorded_without_losing_prior_turn():
    case = load_spec_case("owner-rule-conflict")

    class FailingExecutor:
        name = "failing"

        def __init__(self):
            self.calls = 0

        def invoke(self, invocation):
            self.calls += 1
            if self.calls == 1:
                return AgentTurn(role=invocation.role, content="draft", executor=self.name)
            raise RuntimeError("provider unavailable")

    result = run_spec_case(case, FailingExecutor(), "run-error")

    assert result.status == "execution_error"
    assert len(result.turns) == 1
    assert "provider unavailable" in (result.error or "")
