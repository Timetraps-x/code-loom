from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from codeloom.app.claude_plugin import _agent_rule, _content_rule
from codeloom.kernel.artifacts import TaskDefinition
from codeloom.runtime_clients.claude_code import _task_prompt


@dataclass(frozen=True)
class PromptEvalCase:
    name: str
    surface: str
    badcase: str
    required_guardrails: tuple[str, ...]


def _agent_prompt(name: str) -> str:
    return resources.files("codeloom.agents").joinpath(name).read_text(encoding="utf-8")


def _assert_guardrails(case: PromptEvalCase) -> None:
    missing = [guardrail for guardrail in case.required_guardrails if guardrail not in case.surface]
    assert not missing, f"{case.name} missing guardrails for badcase '{case.badcase}': {missing}"


def test_spec_prompt_eval_good_and_bad_cases():
    analyzer = _agent_prompt("spec-analyzer.md")
    reviewer = _agent_prompt("spec-reviewer.md")

    for expected in (
        "observable acceptance criteria",
        "support, optimize, improve, or complete without concrete evidence",
        "Which facts are observed, which are inferred",
        "owner-bearing decisions cannot be guessed",
    ):
        assert expected in analyzer

    for expected in (
        "observable and executable",
        "support, optimize, improve, or complete without concrete evidence",
        "Owner-bearing questions are not hidden",
        "Technical solution details do not replace requirement meaning",
    ):
        assert expected in reviewer


def test_plan_and_tasks_prompt_eval_stage_projection_cases():
    plan = _agent_prompt("plan-architect.md")
    task_planner = _agent_prompt("task-planner.md")
    task_reviewer = _agent_prompt("task-reviewer.md")

    for expected in (
        "without owning task slicing",
        "writing task slicing rationale",
        "creating builder instructions",
        "defining do-stage execution boundaries",
        "Design facts written in the existing plan section where they belong",
    ):
        assert expected in plan

    forbidden_plan_phrases = (
        "Define task slicing basis",
        "Prepare executable task groups",
        "Reduce work into task boundaries",
        "## 12. 任务拆分依据",
        "任务就绪",
    )
    for phrase in forbidden_plan_phrases:
        assert phrase not in plan

    for expected in (
        "You own execution slicing",
        "design facts distributed across `plan.md` sections",
        "Do not copy large plan sections",
        "micromanage function names, local variables, or line-level edits",
        "Do extract enough execution context",
        "builder`, `code-reviewer`, and `verifier` can execute or review the current task without rereading the whole plan",
    ):
        assert expected in task_planner

    for expected in (
        "Plan design facts that affect execution are projected",
        "Tasks do not copy large plan sections",
        "micromanage function names, local variables, line-level edits",
        "Tasks provide enough execution context",
        "without rereading the whole plan",
    ):
        assert expected in task_reviewer


def test_loom_tasks_skill_prompt_eval_assignment_cases():
    prompt = _content_rule("tasks")

    cases = (
        PromptEvalCase(
            name="tasks_blocks_owner_or_missing_facts",
            surface=prompt,
            badcase="tasks stage turns missing facts into research Tn items",
            required_guardrails=(
                "Missing facts that block safe slicing",
                "returned as blocked",
                "do not create scout, research",
            ),
        ),
        PromptEvalCase(
            name="tasks_avoids_plan_copy_and_micro_management",
            surface=prompt,
            badcase="tasks artifact copies plan text and specifies function-level edits",
            required_guardrails=(
                "Do not copy large plan sections",
                "micromanage function names, local variables, or line-level edits",
                "Extract enough execution context from plan design facts",
                "only non-blocking known constraints, risk notes, and validation notes belong in task context",
            ),
        ),
        PromptEvalCase(
            name="tasks_requires_natural_grouped_verification",
            surface=prompt,
            badcase="verify task becomes unrelated mega-batch",
            required_guardrails=(
                "multiple naturally related build tasks",
                "covered tasks, risks, and expected evidence",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_stage_content_rule_uses_project_artifact_language():
    prompt = _content_rule("plan")

    for expected in (
        ".loom/project.yml",
        "specs.language",
        "default to English (`en`)",
        "The template controls structure",
        "controls the artifact's prose language",
    ):
        assert expected in prompt


def test_builder_prompt_eval_good_cases():
    prompt = _agent_prompt("builder.md")

    for expected in (
        "Implement the build task completely within its stated scope",
        "Treat the current task as the direct execution boundary",
        "Use `spec.md` or `plan.md` only when the task references a specific section or explicit pointer",
        "existing-code consistency, correctness, performance, maintainability, change cost, and verification cost",
        "code-reviewer",
        "Return implementation evidence without claiming full verification",
    ):
        assert expected in prompt


def test_builder_prompt_eval_bad_cases():
    prompt = _agent_prompt("builder.md")
    cases = (
        PromptEvalCase(
            name="do_not_bypass_tasks_boundary",
            surface=prompt,
            badcase="builder reinterprets plan.md into a broader execution scope than the current task",
            required_guardrails=(
                "Treat the current task as the direct execution boundary",
                "Bypassing the current task boundary by reinterpreting `spec.md` or `plan.md`",
            ),
        ),
        PromptEvalCase(
            name="do_not_optimize_for_tiny_patch",
            surface=prompt,
            badcase="builder implements only the smallest patch and leaves task-scoped user behavior incomplete",
            required_guardrails=(
                "Implement the build task completely within its stated scope",
                "without claiming full verification",
            ),
        ),
        PromptEvalCase(
            name="open_local_choice_requires_balanced_judgment",
            surface=prompt,
            badcase="task leaves SQL aggregation open and builder chooses easiest code path without performance or cost reasoning",
            required_guardrails=(
                "When the task leaves local choices open",
                "existing-code consistency, correctness, performance, maintainability, change cost, and verification cost",
            ),
        ),
        PromptEvalCase(
            name="major_semantic_change_blocks",
            surface=prompt,
            badcase="builder discovers the implementation would change public API, data semantics, or major UI flow",
            required_guardrails=(
                "public contracts, data model semantics, major UI flow, preserved design constraints, or later task boundaries",
                "stop as blocked and report which upstream artifact needs revision",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_code_reviewer_prompt_eval_bad_cases():
    prompt = _agent_prompt("code-reviewer.md")
    cases = (
        PromptEvalCase(
            name="review_catches_task_boundary_bypass",
            surface=prompt,
            badcase="builder bypassed tasks.md by reinterpreting spec.md or plan.md into a different execution scope",
            required_guardrails=("current task boundary", "reinterpreting `spec.md` or `plan.md`"),
        ),
        PromptEvalCase(
            name="review_classifies_missing_constraints_and_verification_gaps",
            surface=prompt,
            badcase="builder missed a preserved constraint or left verification coverage unclear",
            required_guardrails=(
                "missing_preserved_constraint",
                "verification_gap",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_loom_do_skill_prompt_eval_bad_cases():
    prompt = _agent_rule("do")
    cases = (
        PromptEvalCase(
            name="skill_routes_build_to_builder",
            surface=prompt,
            badcase="host treats every do task as generic implementation plus verification",
            required_guardrails=("For build tasks", "builder", "For verify tasks", "verifier"),
        ),
        PromptEvalCase(
            name="skill_blocks_boundary_expansion",
            surface=prompt,
            badcase="builder changes data model semantics during do execution",
            required_guardrails=(
                "current task is the direct execution boundary",
                "report blocked instead of expanding the task",
                "preserved design constraints",
            ),
        ),
        PromptEvalCase(
            name="skill_requires_review_after_modification",
            surface=prompt,
            badcase="builder modifies files and closes attempt without independent review",
            required_guardrails=("After file modifications", "code-reviewer", "before closing the build attempt"),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_claude_runtime_prompt_eval_lane_cases():
    build_task = TaskDefinition("T1", "Implement report query", "- [ ] T1: Implement report query\n  - Notes: preserve task context", "fp-build", "build")
    verify_task = TaskDefinition("T2", "Verify report query", "- [ ] T2: Verify report query", "fp-verify", "verify")

    build_prompt = _task_prompt(build_task)
    verify_prompt = _task_prompt(verify_task)

    for expected in (
        "Task lane: build",
        "Execute this build task within the current task boundary",
        "Use spec.md or plan.md only when the task references a specific section or explicit pointer",
        "existing-code consistency, correctness, performance, maintainability, change cost, and verification cost",
        "preserved design constraints, or later task boundaries, stop as blocked",
        "Use code-reviewer before closing the build attempt when files change",
        "Task definition:",
        "Notes: preserve task context",
        "run loom stage commands from inside this task",
    ):
        assert expected in build_prompt

    assert "Task lane: verify" in verify_prompt
    assert "Report pass, fail, or blocked with evidence" in verify_prompt
    assert "expected evidence from the task notes" in verify_prompt


def test_verifier_and_scout_prompt_eval_boundary_cases():
    verifier = _agent_prompt("verifier.md")
    scout = _agent_prompt("scout.md")

    for expected in (
        "Verify the current verify task",
        "Do not broaden verification to the whole plan",
        "return blocked with the missing evidence",
        "do not guess when evidence is insufficient",
    ):
        assert expected in verifier

    for expected in (
        "Answer one bounded factual question",
        "then stop",
        "External open-source, technical, or domain consensus for one local choice",
        "Do not",
        "Decide the final requirement, design, task split",
    ):
        assert expected in scout

def test_prompt_eval_rejects_old_smallest_implementation_bias():
    surfaces = {
        "builder": _agent_prompt("builder.md"),
        "code-reviewer": _agent_prompt("code-reviewer.md"),
        "loom-do": _agent_rule("do"),
        "claude-runtime-build": _task_prompt(
            TaskDefinition("T1", "Implement behavior", "- [ ] T1: Implement behavior", "fp", "build")
        ),
    }
    forbidden = (
        "Make the smallest implementation necessary",
        "smallest implementation",
        "smallest relevant local checks",
        "smallest change",
    )

    for surface_name, surface in surfaces.items():
        for phrase in forbidden:
            assert phrase not in surface, f"{surface_name} still contains biased phrase: {phrase}"
