from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from codeloom.app.claude_plugin import _agent_rule, _argument_rule, _content_rule



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
        "Observable acceptance criteria and verification hints",
        "Do not convert vague words such as `support`, `optimize`, `improve`, or `complete` into specific behavior without evidence",
        "Separate known facts, safe inferences, and owner decisions to confirm",
        "Do not treat inferred facts as known facts",
        "Do not hide owner decisions inside requirements",
        "Do not leave a question open if it can be resolved from current evidence",
        "Do not push owner-bearing requirement decisions into planning",
        "Hand it off to `plan-architect` only when it does not change spec correctness",
    ):
        assert expected in analyzer

    for expected in (
        "bounded specialist reviewer supporting `spec-analyzer`",
        "Produce findings, evidence, uncertainty, and impact",
        "Observable acceptance criteria and verification hints",
        "Vague verbs such as `support`, `optimize`, `improve`, or `complete` are not used without concrete evidence",
        "Technical solution details do not replace requirement meaning",
        "Do not turn missing evidence into a positive claim",
        "Questions the main agent may need to ask",
    ):
        assert expected in reviewer


def test_plan_and_tasks_prompt_eval_stage_projection_cases():
    plan = _agent_prompt("plan-architect.md")
    task_planner = _agent_prompt("task-planner.md")
    task_reviewer = _agent_prompt("task-reviewer.md")

    for expected in (
        "You own the system design facts captured in `plan.md`",
        "without redefining requirements",
        "Do not write task slicing rationale",
        "do-stage boundaries",
        "Do not delegate architecture direction",
        "Explicit task-planning readiness",
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
        "You own the translation from `plan.md` design facts",
        "Every executable task must be either",
        "Do not copy large plan sections",
        "Do not micromanage function names, local variables, line-level edits",
        "Do extract enough execution context from `plan.md`",
        "without rereading the whole plan",
        "checklist-adjacent metadata",
        "Do not rely on Delivery Map, section headings, or Task Notes to provide Kernel metadata",
        "Task List metadata is the runtime source of truth",
        "`Lane`, `Complexity`, and `Revision` metadata",
        "preserve a task's `Revision` unless",
        "Do not bump `Revision`",
    ):
        assert expected in task_planner

    for expected in (
        "bounded specialist reviewer supporting `task-planner`",
        "only build or verify tasks",
        "Grouped verification is allowed",
        "every parseable task line has immediate `Lane`, `Complexity`, and `Revision` metadata",
        "Kernel routing may call the wrong agent",
        "preserve `Revision` unless execution boundary",
        "without copying large plan sections",
        "micromanaging function names, local variables, line-level edits",
        "Questions the main agent may need to ask",
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
        PromptEvalCase(
            name="tasks_maintains_revision_metadata",
            surface=prompt,
            badcase="tasks stage rewrites task notes but forgets to preserve or bump Revision",
            required_guardrails=(
                "`Lane`, `Complexity`, and `Revision`",
                "New tasks start at `Revision: 1`",
                "preserve a task's `Revision` unless",
                "increment `Revision` by 1",
                "Do not bump `Revision`",
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


def test_artifact_stage_skill_prompt_eval_requires_host_handoff():
    for command in ("spec", "plan", "tasks", "ship"):
        prompt = _content_rule(command)
        for expected in (
            "stage main agent",
            "before running the Kernel registration command",
            "user-facing Markdown",
            "Write the artifact directly",
            "--arg artifact_file=specs/<branch-slug>/",
            "do not run the Kernel artifact stage without `artifact_file`",
        ):
            assert expected in prompt


def test_loom_spec_skill_prompt_eval_respec_argument_cases():
    prompt = _argument_rule("spec")

    for expected in (
        "never pass bare user text",
        "unsupported keys such as `gap`",
        "no current `spec.md` exists",
        "--arg requirement=<text>",
        "current `spec.md` already exists",
        "--arg revision_note=<text>",
        "Preserve explicit `requirement=`, `revision_note=`, `text=`, or `artifact_file=`",
    ):
        assert expected in prompt


def test_artifact_stage_skill_prompt_eval_routes_owner_questions_before_kernel():
    for command in ("spec", "plan", "tasks", "ship"):
        prompt = _agent_rule(command)

        for expected in (
            "owner-bearing uncertainty",
            "use AskUserQuestion before running the Kernel stage",
            "do not guess business semantics, risk acceptance, or long-term technical direction",
        ):
            assert expected in prompt


def test_stage_main_agent_prompt_eval_ask_user_question_bad_cases():
    cases = (
        PromptEvalCase(
            name="spec_blocks_owner_bearing_requirement_ambiguity",
            surface=_agent_prompt("spec-analyzer.md"),
            badcase="spec agent guesses business semantics or acceptance criteria",
            required_guardrails=(
                "bounded clarification",
                "requirement ownership",
                "acceptance criteria",
                "public contract meaning",
                "data meaning",
                "hard risk decision",
            ),
        ),
        PromptEvalCase(
            name="plan_blocks_owner_bearing_technical_or_risk_choice",
            surface=_agent_prompt("plan-architect.md"),
            badcase="plan agent chooses architecture direction or production risk acceptance for the owner",
            required_guardrails=(
                "bounded clarification",
                "owner-bearing technical choices",
                "architecture direction",
                "production risk acceptance",
            ),
        ),
        PromptEvalCase(
            name="tasks_blocks_owner_bearing_slicing_decision",
            surface=_agent_prompt("task-planner.md"),
            badcase="task planner turns owner-bearing slicing uncertainty into executable tasks",
            required_guardrails=(
                "Owner-bearing decisions should be resolved with AskUserQuestion",
                "missing facts are needed before safe slicing",
                "Do not encode fact-gathering work as a parseable task",
            ),
        ),
        PromptEvalCase(
            name="ship_blocks_missing_release_owner_decisions",
            surface=_agent_prompt("release-analyzer.md"),
            badcase="release analyzer guesses approval, timing, rollback ownership, or coordination",
            required_guardrails=(
                "bounded clarification",
                "missing owner approval",
                "risk acceptance",
                "release timing",
                "rollback ownership",
                "external deployment coordination",
                "Do not guess missing owner decisions",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_review_and_do_agents_prompt_eval_ask_user_question_bad_cases():
    cases = (
        PromptEvalCase(
            name="reviewers_route_questions_to_main_agent",
            surface="\n".join(
                (
                    _agent_prompt("spec-reviewer.md"),
                    _agent_prompt("plan-reviewer.md"),
                    _agent_prompt("task-reviewer.md"),
                )
            ),
            badcase="reviewer directly asks the user instead of returning questions for the main agent",
            required_guardrails=("Questions the main agent may need to ask",),
        ),
        PromptEvalCase(
            name="builder_blocks_owner_decision_for_host",
            surface=_agent_prompt("builder.md"),
            badcase="builder asks the user directly or silently expands the task boundary",
            required_guardrails=(
                "Do not ask the user directly from this agent",
                "owner-bearing decision that crosses the current task boundary",
                "stop as blocked",
                "exact question the host should ask via AskUserQuestion",
                "smallest upstream artifact that needs revision",
            ),
        ),
        PromptEvalCase(
            name="code_reviewer_blocks_owner_decision_for_builder_or_host",
            surface=_agent_prompt("code-reviewer.md"),
            badcase="code reviewer turns product, contract, data, or risk decision into local review advice",
            required_guardrails=(
                "Do not ask the user directly",
                "owner-bearing product, contract, data, or risk acceptance decisions",
                "mark it as blocked",
                "exact question for `builder` or the host to route through AskUserQuestion",
                "Local code-quality recommendations should not become user questions",
            ),
        ),
        PromptEvalCase(
            name="verifier_distinguishes_missing_evidence_from_owner_decision",
            surface=_agent_prompt("verifier.md"),
            badcase="verifier guesses acceptance or risk when evidence is missing",
            required_guardrails=(
                "Do not ask the user directly from this agent",
                "verification cannot proceed because evidence is missing",
                "return blocked with the missing evidence",
                "owner-bearing acceptance, risk, or release decision",
                "exact question the host should ask via AskUserQuestion",
                "smallest evidence or upstream artifact gap",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_ask_user_question_prompt_eval_non_blocking_counter_cases():
    cases = (
        PromptEvalCase(
            name="builder_keeps_task_local_choices_local",
            surface=_agent_prompt("builder.md"),
            badcase="builder asks the user to choose a local implementation detail inside the task boundary",
            required_guardrails=(
                "When the task leaves local choices open",
                "choose within the task boundary",
                "Continue locally only for implementation choices inside the current task boundary",
            ),
        ),
        PromptEvalCase(
            name="code_reviewer_keeps_code_quality_advice_local",
            surface=_agent_prompt("code-reviewer.md"),
            badcase="code reviewer asks the user to decide normal maintainability or regression advice",
            required_guardrails=(
                "Check likely correctness, security, maintainability, and regression risks",
                "Return findings to `builder` for absorption",
                "Local code-quality recommendations should not become user questions",
            ),
        ),
        PromptEvalCase(
            name="verifier_missing_evidence_is_not_user_decision",
            surface=_agent_prompt("verifier.md"),
            badcase="verifier turns missing logs or validation output into a user decision",
            required_guardrails=(
                "if evidence is insufficient, return blocked with the missing evidence",
                "verification cannot proceed because evidence is missing",
                "return blocked with the missing evidence",
            ),
        ),
        PromptEvalCase(
            name="release_analyzer_does_not_create_extra_approval_system",
            surface=_agent_prompt("release-analyzer.md"),
            badcase="release analyzer asks for extra approval when evidence is sufficient",
            required_guardrails=(
                "Do not turn release analysis into a new review or approval system",
                "Do not ask for extra approval when evidence is sufficient",
                "Do not guess missing owner decisions",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)

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
                "execution boundary",
                "complete the attempt as `blocked` instead of expanding the task",
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


def test_loom_do_skill_prompt_eval_host_handoff_cases():
    prompt = _agent_rule("do")

    for expected in (
        "do not run `loom stage do` as a one-shot execution command",
        "action=begin",
        "extras.attempt_id",
        "extras.main_agent",
        "builder` is the build-lane main agent",
        "verifier` is the verify-lane main agent",
        "action=complete",
        "status=<implemented|verified|failed|blocked>",
        "Build attempts must complete as `implemented`, `failed`, or `blocked`",
        "Verify attempts must complete as `verified`, `failed`, or `blocked`",
        "put the verification evidence summary in `summary`",
        "verification_summary_file=<path>",
    ):
        assert expected in prompt

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
        "Answer only the delegated factual question",
        "then stop",
        "bounded specialist evidence agent supporting a CodeLoom main agent",
        "codebase mode",
        "external mode",
        "Do not decide the final requirement, design, task split",
        "Do not turn missing evidence into a positive claim",
        "If the delegated scope is insufficient",
    ):
        assert expected in scout

def test_prompt_eval_rejects_old_smallest_implementation_bias():
    surfaces = {
        "builder": _agent_prompt("builder.md"),
        "code-reviewer": _agent_prompt("code-reviewer.md"),
        "loom-do": _agent_rule("do"),
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


def test_coding_goal_prompt_guardrails_cover_bad_cases():
    builder = _agent_prompt("builder.md")
    reviewer = _agent_prompt("code-reviewer.md")
    verifier = _agent_prompt("verifier.md")
    release = _agent_prompt("release-analyzer.md")
    task_planner = _agent_prompt("task-planner.md")
    plan_architect = _agent_prompt("plan-architect.md")
    codebase_scout = _agent_prompt("codebase-scout.md")

    for expected in (
        "current task as the direct execution boundary",
        "Keep the main business flow readable",
        "reasonable content density",
        "artificial short methods",
        "repeated `collectXxx(...)` helper traversals",
        "stable reusable capability",
        "one-off pages, buttons, tasks",
        "concise behavior names",
        "full assertion, scenario sentence, or cause-effect explanation",
        "Do not add null checks, fallback branches, helpers, managers, adapters, or wrappers",
        "real boundary, business state, or current complexity reduction",
        "Return implementation evidence without claiming full verification",
    ):
        assert expected in builder

    for expected in (
        "codebase-scout",
        "narrow read-only repository facts inside the current task boundary",
        "generic `scout` only when artifact/runtime/external evidence is needed",
    ):
        assert expected in builder

    for expected in (
        "readability_risk",
        "content_density_risk",
        "invariant_risk",
        "over_abstraction",
        "cosmetic_extraction",
        "repeated_traversal",
        "n_plus_one_query",
        "query_naming_risk",
        "full-sentence method or test names",
        "concise behavior names",
        "meaningless_defense",
        "evidence_integrity_gap",
    ):
        assert expected in reviewer

    for expected in (
        "verified / failed / blocked / not verified",
        "No evidence means not verified",
        "Do not broaden verification to the whole plan",
        "status: verified | failed | blocked",
        "not_verified | not_applicable",
        "not workflow routing authority",
        "next_action_hint",
    ):
        assert expected in verifier

    for expected in (
        "codebase-scout",
        "relevant tests, assertions, code paths, or existing verification conventions inside the current task boundary",
        "Do not broaden verification to the whole plan",
    ):
        assert expected in verifier

    for expected in (
        "bounded specialist codebase evidence agent supporting a CodeLoom do-stage main agent",
        "Answer only the delegated codebase fact question",
        "reusable data-access capabilities",
        "SQL/query naming conventions",
        "visible N+1 or repeated-query risks",
        "Do not run commands",
        "Do not decide verification status",
        "Do not decide task status",
        "Do not broaden the current task boundary",
        "Do not push uncertainty to `builder`, `verifier`, or later stages as if it were resolved evidence",
    ):
        assert expected in codebase_scout

    for expected in (
        "runtime evidence refs",
        "not-verified items",
        "Do not invent evidence",
        "risk acceptance",
        "produce a blocked or partial `release.md`",
        "readiness blockers",
        "you do not own the actual release decision",
    ):
        assert expected in release

    for expected in (
        "complexity",
        "verify task",
        "build task",
        "coding-quality constraints",
        "verification coverage map",
        "grouped verification changes verification coverage, not build task granularity",
        "do not merge build tasks merely because they share a grouped verify task",
        "full verify task set collectively covers requested behavior and material impacted regression surfaces",
        "stable reusable capability",
        "one-off business scenarios",
        "without rereading the whole plan",
        "do not make those the default task boundary",
        "checklist-adjacent metadata",
        "Task Notes are agent/human context only",
    ):
        assert expected in task_planner

    for expected in (
        "Main business flow readability",
        "visible business/data flow",
        "real boundary, reuse pressure, or current complexity reduction",
        "real complexity isolation",
        "stable capability names",
        "only when touched by the requirement or observed system facts",
    ):
        assert expected in plan_architect