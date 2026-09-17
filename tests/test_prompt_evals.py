from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from codeloom.app.claude_plugin import _adopt_skill_content, _argument_rule, _content_rule, _main_role_rule, _skill_content
from codeloom.prompt_evals.supplement import missing_prompt_eval_case_drafts, write_missing_prompt_eval_cases


@dataclass(frozen=True)
class PromptEvalCase:
    name: str
    surface: str
    badcase: str
    required_guardrails: tuple[str, ...]


MAIN_ROLE_PROMPTS = {
    "spec-analyzer.md",
    "plan-architect.md",
    "task-planner.md",
    "builder.md",
    "verifier.md",
    "release-analyzer.md",
}


def _prompt(name: str) -> str:
    package = "codeloom.roles" if name in MAIN_ROLE_PROMPTS else "codeloom.agents"
    return resources.files(package).joinpath(name).read_text(encoding="utf-8")


def _assert_guardrails(case: PromptEvalCase) -> None:
    missing = [guardrail for guardrail in case.required_guardrails if guardrail not in case.surface]
    assert not missing, f"{case.name} missing guardrails for badcase '{case.badcase}': {missing}"


def test_adopt_agent_prompt_keeps_semantics_strong_without_delegation_gate():
    prompt = _prompt("adopt-expert.md")

    for expected in (
        "whole-project evidence",
        "A large majority pattern is not automatically a positive convention",
        "Current requirements, task details, untracked work, and target-state designs",
        "Delegation is optional",
        "If no delegation channel is available, continue with bounded direct investigation",
        "Keep commands out of the constitution",
        "Every non-empty value needs a locatable evidence source",
        "Never mix these suggestions into the constitution candidate",
    ):
        assert expected in prompt

    for forbidden in ("SQLite", "Kernel", "workflow state", "loom adopt --constitution"):
        assert forbidden not in prompt


def test_adopt_host_prompt_separates_outputs_and_uses_configured_path():
    prompt = _adopt_skill_content("loom-adopt", "Adopt project", "optional guidance")

    for expected in (
        "configured `constitution.path`",
        "do not assume `.loom/constitution.md`",
        "Child-agent delegation is optional",
        "absence of a delegation channel is not itself a blocker",
        "Write only the returned constitution candidate to the exact configured constitution path",
        "Treat the returned project profile independently",
        "never append them to the constitution",
        "loom adopt --constitution <exact-configured-path>",
    ):
        assert expected in prompt


def test_stage_host_prompts_consume_only_usable_constitution():
    artifact_prompt = _content_rule("plan")
    do_prompt = _main_role_rule("do")

    for prompt in (artifact_prompt, do_prompt):
        assert "extras.constitution.path" in prompt
        assert "extras.constitution.usable" in prompt
        assert "without treating Adopt as a prerequisite" in prompt or "do not turn Adopt into a prerequisite" in prompt
    assert "extras.project_profile" in artifact_prompt
    assert "extras.project_profile" in do_prompt


def test_prompt_eval_supplementer_writes_missing_case_drafts(tmp_path):
    missing = missing_prompt_eval_case_drafts(tmp_path)
    output_path = tmp_path / "suggested_cases.json"

    report = write_missing_prompt_eval_cases(tmp_path, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert not report.complete
    assert missing
    assert payload["cases"]
    assert payload["cases"][0]["id"] == missing[0].id
    assert payload["cases"][0]["surfaces"]


def test_spec_analyzer_prompt_recovers_real_requirements():
    analyzer = _prompt("spec-analyzer.md")

    for expected in (
        "You own the requirement semantics captured in `spec.md`",
        "incomplete, mixed, conflicting, or solution-biased human input",
        "A human request is evidence about a need, not a finished requirement",
        "A material promise is one whose omission or reinterpretation changes whether the requested result is true",
        "Seek discriminating evidence",
        "what the source proves, what it does not prove",
        "compare the current reality with the required reality",
        "false completion",
        "Every material promise receives an evidence-backed judgment",
        "Do not emit a generic unknown",
        "Retain an evidence gap only after targeted investigation",
        "the required result remains decidable without it",
        "If the missing fact prevents a correct requirement decision, stop with the needed evidence",
        "An evidence gap describes current reality; it does not replace the requirement judgment for a material promise",
        "Goal, Way, and Proof as reasoning lenses, not required headings",
        "An unproven proposed method is not an Owner choice",
        "A proposed method plus missing evidence is not a pair of credible requirement directions",
        "Request one Owner decision only",
        "Produce a coherent, user-facing `spec.md`",
        "Only an Owner or another accepted governing source",
        "none creates requirement authority by itself",
        "leave mechanism selection to Plan",
        "steady-state requests not perform a full-table query",
        "ordinary implementation alternatives or Plan-owned lifecycle",
        "proportionate, readable coverage",
        "same authority and disposition may be synthesized",
        "Do not produce technical architecture",
    ):
        assert expected in analyzer


def test_spec_reviewer_requires_identified_candidate_and_material_challenge():
    reviewer = _prompt("spec-reviewer.md")

    for expected in (
        "exact delegated candidate text and supplied candidate identity",
        "candidate anchor",
        "accepted obligation or confirmed fact with a source that actually establishes that authority",
        "candidate-conforming failure",
        "Missing evidence alone is not a finding",
        "scoped_evidence_limit",
        "re-review only prior material finding closure",
        "no_material_challenge",
        "cannot establish requirement authority by themselves",
        "authority or provenance is unclear",
        "Do not treat omission of a candidate lifecycle",
        "does not create an Owner direction",
        "instead of manufacturing a conflict",
        "leave the final requirement judgment to `spec-analyzer`",
    ):
        assert expected in reviewer


def test_spec_role_prompts_keep_workflow_mechanics_out_of_semantic_roles():
    surface = "\n".join((_prompt("spec-analyzer.md"), _prompt("spec-reviewer.md")))

    for forbidden in ("Kernel", "SQLite", "artifact_file", "AskUserQuestion", "temporary Claude Code child agent"):
        assert forbidden not in surface


def test_spec_host_projection_preserves_main_ownership_and_exact_review_handoff():
    prompt = _main_role_rule("spec")

    for expected in (
        "extras.main_role=spec-analyzer",
        "read `references/main-role.md`",
        "Do not invoke `spec-analyzer` as a Claude Code Agent",
        "current Main owns this stage's semantic analysis",
        "one bounded question",
        "compute its SHA-256",
        "Supply the exact candidate body",
        "treat `spec-reviewer` as advisory only",
        "supply the previous and new identities",
        "When the loaded role concludes that its own clarification gate is met",
        "use AskUserQuestion before registration",
        "investigable fact or ordinary reversible technical choice",
        "extras.register_command",
    ):
        assert expected in prompt


def test_spec_template_is_flexible_decision_projection():
    template = resources.files("codeloom.templates").joinpath("spec-template.md").read_text(encoding="utf-8")

    for expected in (
        "flexible decision projection, not a mandatory checklist or semantic schema",
        "in whatever order and shape serves the demand",
        "Current problem and branch commitment",
        "Decision basis",
        "Relevant operating behavior",
        "Way boundaries",
        "Complex-demand coverage, when useful",
        "Proof direction",
        "Design freedom",
        "Prose, lists, tables, or a short narrative are all valid",
        "Current code, a page, a local test, or a historical record proves only the local fact it observes",
        "A business object is not a table",
        "A page, API 200, compile, screenshot, mock, or isolated test does not by itself prove",
        "Readable commitment anchors, when useful",
        "`C:<meaningful-slug>` example",
        "Anchors are optional navigation aids",
        "not IDs, a schema, or a cross-revision lineage protocol",
    ):
        assert expected in template

    for forbidden in (
        "Candidate Goal Slices",
        "Current Release Goal",
        "now / later / out",
        "| ID | Requirement / Rule | Priority |",
        "| ID | Observable Result | Evidence Strength | Verification Hint |",
        "write None",
        "write N/A",
    ):
        assert forbidden not in template


def test_plan_and_tasks_roles_preserve_properties_and_reasonable_design():
    plan = _prompt("plan-architect.md")
    plan_reviewer = _prompt("plan-reviewer.md")
    plan_skill = _skill_content("loom-plan", "plan", "description", "constraints=<text>")
    task_planner = _prompt("task-planner.md")
    task_reviewer = _prompt("task-reviewer.md")

    for expected in (
        "Account for every material accepted property",
        "accepted property or hard constraint from a confirmed fact and a candidate mechanism",
        "Read-only consumption, derived status, paths, search",
        "complete and proportionate design",
        "adequacy and necessity",
        "retain, extend, correct, replace, or add",
        "Duplicate protection needs a residual failure",
        "Existing complexity is not justified merely because it already exists",
        "Mechanism deletion must not silently become property deletion",
        "data actually published and consumed",
        "startup | refresh | write | request | background",
        "O(1) reference access does not make an entire request O(1)",
        "Class, method, field, and DTO naming",
        "not a required property ledger",
        "repeated mechanism blacklists",
        "The theoretical possibility",
    ):
        assert expected in plan

    for expected in (
        "exact candidate text and supplied identity",
        "minimum complete and proportionate design obligations",
        "non-optional obligation",
        "smallest candidate-conforming counterexample",
        "not a full alternative design",
        "parallel set of tables, fields, DTOs, APIs, Jobs, components, state machines",
        "retained or extended existing mechanism",
        "replacement loses an accepted property or proof",
        "O(1) reference access does not hide",
        "validate A but publish or consume B",
        "not stage approval",
        "Review only finding closure, the real delta",
        "Missing ideal evidence is not a challenge",
    ):
        assert expected in plan_reviewer

    assert "use its clarification gate rather than a generic `unclear input` rule" in plan_skill
    assert "If required user input is unclear" not in plan_skill
    assert "accepted property or hard constraint from a confirmed fact" not in plan_skill

    for expected in (
        "accepted business and technical properties, selected mechanisms",
        "source-derived property",
        "A generic instruction to “follow the Plan”, “optimize performance”, or “add caching”",
        "startup, refresh, write, request, or background time",
        "execution-critical information only in later notes or maps",
        "Revision protects execution meaning",
    ):
        assert expected in task_planner

    for expected in (
        "exact candidate text and supplied candidate identity",
        "exact packet/relation anchor",
        "accepted property or confirmed fact with its source",
        "candidate-conforming downstream failure",
        "Review only finding closure, those changes",
        "scoped evidence limit",
    ):
        assert expected in task_reviewer

    for prompt in (plan, plan_reviewer, task_planner, task_reviewer):
        for forbidden in ("Kernel", "SQLite", "artifact_file", "temporary Claude Code child agent"):
            assert forbidden not in prompt


def test_tasks_skill_keeps_semantics_in_role_and_parser_contract_in_host():
    host = _content_rule("tasks")
    role = _prompt("task-planner.md")

    for expected in (
        "- [ ] T1: <task title>",
        "only `build` or `verify` lanes",
        "Lane`, `Complexity`, and `Revision`",
        "Task-local semantic context remains opaque to Kernel",
    ):
        assert expected in host

    for forbidden in (
        "startup/request placement",
        "accepted result, selected mechanism",
        "property the implementation must establish",
        "generic phrases such as",
    ):
        assert forbidden not in host

    for expected in (
        "accepted result and selected design",
        "startup, refresh, write, request, or background time",
        "Do not hide a real design gap in a research/build/verify task",
        "increment only the affected packet's Revision",
    ):
        assert expected in role

def test_tasks_reviewer_projection_uses_exact_candidate_identity():
    tasks_prompt = _main_role_rule("tasks")
    content_prompt = _content_rule("tasks")

    for expected in (
        "compute its SHA-256",
        "handoff input identity",
        "Supply the exact candidate body",
        "input_missing_or_mismatched",
        "previous and new identities",
        "Review only finding closure and that delta",
        "do not decide readiness or workflow state",
    ):
        assert expected in tasks_prompt

    for expected in (
        "user-facing Markdown",
        "exact repository-relative `extras.artifact_path`",
        "exact `extras.register_command`",
        "Do not reconstruct the artifact path or registration command",
    ):
        assert expected in content_prompt


def test_stage_content_rule_uses_project_artifact_language():
    prompt = _content_rule("plan")

    for expected in (
        ".loom/project.yml",
        "specs.language",
        "default to English (`en`)",
        "flexible projection aid",
        "not a mandatory checklist or semantic schema",
        "controls the artifact's prose language",
    ):
        assert expected in prompt


def test_artifact_stage_skill_prompt_eval_requires_host_handoff():
    for command in ("spec", "plan", "tasks", "ship"):
        prompt = _content_rule(command)
        for expected in (
            "run the stage command once without `artifact_file`",
            "--json",
            "`status=noop` with `extras.handoff=author_artifact`",
            "normal host-authoring handoff",
            "does not contain that handoff",
            "do not draft or register a downstream artifact",
            "exact repository-relative `extras.artifact_path`",
            "exact `extras.register_command`",
            "Do not reconstruct the artifact path or registration command",
            "user-facing Markdown",
        ):
            assert expected in prompt
        assert "specs/<branch-slug>/" not in prompt


def test_plan_and_tasks_host_projection_limits_review_to_real_delta():
    for command in ("plan", "tasks"):
        prompt = _main_role_rule(command)
        for expected in (
            "previous and new identities",
            "actual changed passages or packets",
            "prior material findings",
            "affected semantic dependencies",
            "Review only finding closure and that delta",
            "run a new full review",
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
        "Preserve explicit `requirement=`, `revision_note=`, or `text=`",
        "`artifact_file` is reserved for the canonical registration command returned by the Kernel handoff",
    ):
        assert expected in prompt


def test_artifact_stage_skill_routes_owner_questions_before_registration():
    for command in ("spec", "plan", "tasks", "ship"):
        prompt = _main_role_rule(command)
        for expected in (
            "loaded role concludes that its own clarification gate is met",
            "use AskUserQuestion before registration",
            "investigable fact or ordinary reversible technical choice",
        ):
            assert expected in prompt


def test_loom_spec_skill_keeps_clarification_with_current_main():
    prompt = _main_role_rule("spec")
    skill = _skill_content("loom-spec", "spec", "description", "requirement=<text>")

    assert "current Main owns this stage's semantic analysis" in prompt
    assert "loaded role concludes that its own clarification gate is met" in prompt
    assert "write the ready clean Markdown artifact" in prompt
    assert "Ask before preflight only when the command or its arguments cannot be interpreted safely" in skill
    assert "use its clarification gate rather than a generic `unclear input` rule" in skill
    assert "If required user input is unclear" not in skill
    assert "accepted governing source" not in skill
    assert "candidate lifecycle or activation rules" not in skill


def test_stage_main_role_prompt_eval_ask_user_question_bad_cases():
    cases = (
        PromptEvalCase(
            name="spec_surfaces_only_correctness_changing_owner_choice",
            surface=_prompt("spec-analyzer.md"),
            badcase="spec agent guesses an unresolved requirement choice or asks the Owner to decide implementation details",
            required_guardrails=(
                "Resolve investigable facts before requesting an Owner choice",
                "An unproven proposed method is not an Owner choice",
                "Request one Owner decision only",
                "accepted input or authoritative evidence independently establishes incompatible current requirement meanings or business rules",
                "choice changes the required result, scope, acceptance meaning",
                "the unresolved choice, credible directions and consequences",
                "the best-supported recommendation",
                "Do not ask the Owner to choose ordinary implementation details or compensate for missing evidence",
                "If an unresolved Owner choice still changes requirement correctness, stop with that clarification",
            ),
        ),
        PromptEvalCase(
            name="plan_rederives_design_after_owner_decision",
            surface=_prompt("plan-architect.md"),
            badcase="plan agent sends ordinary choices to the user or applies an Owner answer to only one technical projection",
            required_guardrails=(
                "Resolve ordinary local, reversible technical choices through an evidence-backed recommendation",
                "An unconfirmed fact with a locatable repository, runtime, or external source is an evidence gap",
                "Request one Owner decision only after investigating every locatable source that can distinguish the direction",
                "accepted semantics and remaining evidence support incompatible directions",
                "a reasonable technical recommendation cannot decide",
                "public or data-contract meaning, irreversible migration",
                "Present the established facts, affected model and mechanism",
                "Re-derive every affected design element after the decision",
            ),
        ),
        PromptEvalCase(
            name="tasks_routes_omitted_design_back_to_plan",
            surface=_prompt("task-planner.md"),
            badcase="task planner turns a material Plan omission into executable tasks",
            required_guardrails=(
                "A missing material design decision cannot be repaired through task wording",
                "A task is ready to emit only when the accepted design supplies",
                "Return to Plan only when correct task construction requires selecting or changing",
                "Do not hide a real design gap in a research/build/verify task",
            ),
        ),
        PromptEvalCase(
            name="ship_separates_owner_decisions_from_workflow_gaps",
            surface=_prompt("release-analyzer.md"),
            badcase="release analyzer guesses risk acceptance or routes routine release execution upstream",
            required_guardrails=(
                "Silence is not risk acceptance",
                "Routine release timing, ordinary approval, or deployment execution is not an implementation gap",
                "The actual choice to merge, deploy, roll out, or accept risk remains outside this analysis",
                "Do not route upstream for a missing ideal tool",
                "risk-acceptance decision",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_review_and_do_agents_prompt_eval_ask_user_question_bad_cases():
    cases = (
        PromptEvalCase(
            name="spec_reviewer_returns_owner_choice_to_analyzer",
            surface=_prompt("spec-reviewer.md"),
            badcase="spec reviewer chooses an Owner direction instead of returning the semantic conflict",
            required_guardrails=(
                "surface an Owner choice",
                "leave the final requirement judgment to `spec-analyzer`",
            ),
        ),
        PromptEvalCase(
            name="builder_returns_owner_decision_without_guessing",
            surface=_prompt("builder.md"),
            badcase="builder asks the user directly or silently expands the task boundary",
            required_guardrails=(
                "Resolve ordinary reversible implementation choices yourself",
                "Stop only when a high-quality implementation would require changing accepted requirement meaning",
                "Do not ask the user directly",
                "do not guess the missing decision",
                "smallest upstream meaning that must change",
            ),
        ),
        PromptEvalCase(
            name="code_reviewer_returns_boundary_conflict_without_deciding_it",
            surface=_prompt("code-reviewer.md"),
            badcase="code reviewer turns a requirement or design decision into local review advice",
            required_guardrails=(
                "report an upstream-boundary finding",
                "Do not edit code",
                "ask the user",
            ),
        ),
        PromptEvalCase(
            name="verifier_does_not_guess_missing_acceptance",
            surface=_prompt("verifier.md"),
            badcase="verifier guesses acceptance or design when proof is missing",
            required_guardrails=(
                "Do not implement fixes, edit code, expand coverage, or ask the user directly",
                "Missing an ideal harness is not itself a product or design decision",
                "If the accepted design or requirement itself is missing",
                "Do not solve any of those by guessing",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_ask_user_question_prompt_eval_non_blocking_counter_cases():
    cases = (
        PromptEvalCase(
            name="builder_keeps_task_local_choices_local",
            surface=_prompt("builder.md"),
            badcase="builder asks the user to choose a local implementation detail inside the task boundary",
            required_guardrails=(
                "Resolve ordinary reversible implementation choices yourself inside the task boundary",
                "Choose local structure by balancing behavior correctness, project fit, performance and resource cost, maintainability, readability, change cost, and verification cost",
            ),
        ),
        PromptEvalCase(
            name="code_reviewer_does_not_manufacture_preferences",
            surface=_prompt("code-reviewer.md"),
            badcase="code reviewer turns normal style preference into a blocking decision",
            required_guardrails=(
                "Equivalent local style, speculative hardening, generic clean-code preference, optional strengthening",
                "There is no finding quota",
                "Return `pass` when no material counterexample survives",
            ),
        ),
        PromptEvalCase(
            name="verifier_missing_harness_is_not_user_decision",
            surface=_prompt("verifier.md"),
            badcase="verifier turns an unavailable preferred harness into a user decision",
            required_guardrails=(
                "If a broad runtime or integration harness cannot start",
                "retain narrower checks that still prove scoped facts",
                "Missing an ideal harness is not itself a product or design decision",
            ),
        ),
        PromptEvalCase(
            name="release_analyzer_does_not_create_extra_approval_system",
            surface=_prompt("release-analyzer.md"),
            badcase="release analyzer turns ordinary release ownership into another approval gate",
            required_guardrails=(
                "Routine release timing, ordinary approval, or deployment execution is not an implementation gap",
                "The actual choice to merge, deploy, roll out, or accept risk remains outside this analysis",
                "You do not make the release owner's actual release decision",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)

def test_builder_prompt_preserves_property_bearing_result_and_lifecycle_cost():
    prompt = _prompt("builder.md")

    for expected in (
        "CodeLoom `builder` role",
        "quality of one task-scoped implementation",
        "frozen Task Packet as the execution boundary",
        "what accepted properties must remain true",
        "which selected mechanism carries each material property",
        "Complete the whole task-scoped result",
        "Fewer lines or objects with a lost behavior",
        "before and after placement, frequency, realistic scale, and cost",
        "work moved from a bounded startup, refresh, or write path into a frequent request path",
        "Do not add speculative infrastructure",
        "Do not claim independent review or full verification",
    ):
        assert expected in prompt

    assert "Kernel" not in prompt
    assert "SQLite" not in prompt


def test_code_reviewer_requires_three_anchor_finding_and_delta_review():
    prompt = _prompt("code-reviewer.md")

    for expected in (
        "attempt-scoped diff from attempt start to that sealed revision",
        "return `blocked` for review-object integrity",
        "smallest relevant candidate-conforming scenario",
        "accepted Task property, design obligation, or demonstrated current-project constraint",
        "concrete input, state, scale, frequency",
        "before/after lifecycle placement, frequency, realistic scale",
        "work previously bounded to startup, refresh, or write is moved into the request path",
        "inspect prior finding closure and the changed hunks",
        "`blocked` only when the review object is unavailable, stale, or invalid",
    ):
        assert expected in prompt

    assert "There is no finding quota" in prompt


def test_loom_do_skill_keeps_host_choreography_and_recovery():
    prompt = _main_role_rule("do")

    for expected in (
        "Do is serial",
        "action=begin",
        "frozen `extras.task_packet`",
        "Do not invoke Builder or Verifier as a subagent",
        "extras.host_internal_flow",
        "exact attempt-scoped diff",
        "action=record-review",
        "seal again and invoke a fresh Code Reviewer",
        "action=retry",
        "action=route",
        "Host-internal",
        "`action=unlock` is user-only recovery",
        "completed the blocked task themselves",
        "`status=implemented` for Build or `status=verified` for Verify",
    ):
        assert expected in prompt

    for forbidden in (
        "before and after lifecycle placement",
        "what accepted properties must remain true",
        "query and traversal count",
    ):
        assert forbidden not in prompt


def test_loom_do_skill_prompt_eval_host_handoff_cases():
    prompt = _main_role_rule("do")

    for expected in (
        "do not run `loom stage do` as a one-shot execution command",
        "extras.attempt_id",
        "extras.lane",
        "extras.main_role",
        "reviewer_handoff",
        "attempt-scoped diff",
        "non-empty `review_summary`",
        "same Build attempt",
        "fresh Code Reviewer",
        "Build completion means the latest sealed implementation passed review",
        "verification_summary",
        "host_recovery.internal_action: resume_complete",
        "run its `command_args` without reconstructing",
        "do not rerun or invalidate unrelated effective tasks",
        "Manual completion does not repair stale registered lineage",
        "status=<implemented|verified|failed|blocked>",
    ):
        assert expected in prompt


def test_verifier_prompt_eval_quality_and_result_semantics():
    verifier = _prompt("verifier.md")

    for expected in (
        "CodeLoom `verifier` role",
        "Verification is behavior judgment, not evidence-field completion",
        "# Verification Method",
        "Choose the strongest useful path that the current project can support",
        "verify the real creation entry",
        "A pre-seeded intermediate state does not prove creation behavior",
        "When performance is material",
        "retain narrower checks that still prove scoped facts",
        "`verified`: every material obligation",
        "`failed`: an actual observation contradicts required behavior",
        "`blocked`: one or more necessary obligations remain not verified",
        "Do not decide workflow routing or attempt state",
        "Do not pad the result with an evidence inventory",
    ):
        assert expected in verifier

    assert "temporary Claude Code child agent" not in verifier

def test_prompt_eval_rejects_old_smallest_implementation_bias():
    surfaces = {
        "builder": _prompt("builder.md"),
        "code-reviewer": _prompt("code-reviewer.md"),
        "loom-do": _main_role_rule("do"),
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


def test_core_agent_prompts_keep_stack_specific_verification_out_of_global_surfaces():
    surfaces = {
        "builder": _prompt("builder.md"),
        "verifier": _prompt("verifier.md"),
        "loom-do": _main_role_rule("do"),
    }
    forbidden = (
        "legacy Spring/MyBatis/XML modules",
        "mapper XML/static SQL inspection",
        "Spring `ApplicationContext` test",
        "Spring Context test",
    )

    for surface_name, surface in surfaces.items():
        for phrase in forbidden:
            assert phrase not in surface, f"{surface_name} still contains stack-specific verification detail: {phrase}"

    assert "focused checks actually run" in surfaces["builder"]
    assert "strongest useful path" in surfaces["verifier"]
    assert "actual checks and observations" in surfaces["loom-do"]

    for surface_name in ("builder", "verifier"):
        assert "temporary Claude Code child agent" not in surfaces[surface_name]

def test_main_roles_carry_semantic_continuity_without_kernel_logic():
    builder = _prompt("builder.md")
    reviewer = _prompt("code-reviewer.md")
    verifier = _prompt("verifier.md")
    release = _prompt("release-analyzer.md")
    task_planner = _prompt("task-planner.md")
    plan_architect = _prompt("plan-architect.md")

    assert "accepted properties must remain true" in builder
    assert "before and after placement, frequency, realistic scale, and cost" in builder
    assert "accepted Task property" in reviewer
    assert "before/after lifecycle placement" in reviewer
    assert "business or technical property" in verifier
    assert "startup, refresh, write, request, and background paths" in verifier
    assert "O(1) access or current-ETag comparison" in verifier
    assert "delivered and proven" in release
    assert "human assertion" in release
    assert "source-derived property" in task_planner
    assert "Mechanism deletion must not silently become property deletion" in plan_architect

    for prompt in (builder, reviewer, verifier, release, task_planner, plan_architect):
        for forbidden in ("Kernel", "SQLite", "runtime_refs", "temporary Claude Code child agent"):
            assert forbidden not in prompt


def test_ship_host_keeps_generic_handoff_and_release_semantics_in_role():
    host_rule = _main_role_rule("ship")
    content_rule = _content_rule("ship")
    release = _prompt("release-analyzer.md")

    for expected in (
        "extras.main_role=release-analyzer",
        "read `references/main-role.md`",
        "current Main owns this stage's semantic analysis",
        "write the ready clean Markdown artifact",
    ):
        assert expected in host_rule

    for expected in ("frozen `extras.input_token`", "<stage>_inputs_changed", "extras.register_command"):
        assert expected in content_rule

    assert "Task completion is not proof" in release
    assert "delivered and proven" in release


def test_plan_reviewer_receives_identified_candidate_draft():
    architect = _prompt("plan-architect.md")
    reviewer = _prompt("plan-reviewer.md")
    host_rule = _main_role_rule("plan")

    for expected in (
        "exact candidate text and supplied identity",
        "State which identity the review inspects",
        "input_missing_or_mismatched",
        "rather than inferring it from an on-disk artifact",
    ):
        assert expected in reviewer

    for expected in (
        "compute its SHA-256",
        "handoff input identity",
        "exact candidate body",
        "accepted upstream properties",
    ):
        assert expected in host_rule

    assert "artifact_file" not in architect
    assert "candidate identity" not in architect


def test_plan_host_delegation_keeps_child_evidence_bounded():
    architect = _prompt("plan-architect.md")
    reviewer = _prompt("plan-reviewer.md")
    host_rule = _main_role_rule("plan")

    for expected in (
        "one unconfirmed fact that can change a named stage judgment",
        "smallest relevant scope",
        "smallest discriminating evidence",
        "source and applicability",
        "must not write artifacts, modify files, ask the user, choose requirements or design",
        "current Main decides applicability and synthesis",
    ):
        assert expected in host_rule

    assert "Request one Owner decision only after investigating" in architect
    assert "Do not manufacture an Owner question for an investigable fact" in reviewer

    for prompt in (architect, reviewer):
        for forbidden in ("temporary Claude Code child agent", "artifact_file", "Kernel", "workflow state"):
            assert forbidden not in prompt


def test_plan_prompts_select_analysis_models_for_material_relationships():
    architect = _prompt("plan-architect.md")
    reviewer = _prompt("plan-reviewer.md")

    for expected in (
        "PlantUML",
        "material object relationship or cardinality",
        "state lifecycle or illegal transition",
        "cross-system synchronous/asynchronous sequence",
        "multi-role workflow",
        "A closed local correction may omit diagrams",
        "A diagram is design evidence, not decoration or a quota",
    ):
        assert expected in architect

    for expected in (
        "minimum complete and proportionate design obligations",
        "smallest reasonable implementation that fully follows the candidate",
        "concrete failure or material cost",
        "Require a concrete surface only when its absence",
    ):
        assert expected in reviewer


def test_tasks_packets_preserve_result_links_and_relation_premises():
    planner = _prompt("task-planner.md")
    reviewer = _prompt("task-reviewer.md")
    for text in ("accepted business or system result", "transferred result premise", "Relation reachability alone", "Before withholding Tasks", "decision-changing claim, inspected scope", "does not replace execution invalidation after a build retry"):
        assert text in planner
    for text in ("changed transferred premise", "layer or file ledger entries", "compact cross-layer task", "Require a candidate-conforming failure"):
        assert text in reviewer
    host = _main_role_rule("tasks") + _content_rule("tasks")
    assert "transferred result premise" not in host
    assert "Before withholding Tasks" not in host

def test_do_roles_preserve_execution_meaning_and_evidence_handoff():
    builder = _prompt("builder.md")
    reviewer = _prompt("code-reviewer.md")
    verifier = _prompt("verifier.md")
    for text in ("Do not re-litigate an accepted Plan choice", "locatable implementation facts from missing execution meaning", "Ordinary reversible details and equivalent local implementations", "the sources inspected"):
        assert text in builder
    for text in ("obligation_source:", "affected_contract:", "missing delta alone is not review-object integrity failure", "trustworthy seal-to-seal delta"):
        assert text in reviewer
    for text in ("behavior:", "entry:", "counterexample:", "proof_limit:", "affected_contract:", "Narrower evidence permits `verified` only when", "identify which prevent packet closure"):
        assert text in verifier
    host = _main_role_rule("do")
    for text in ("prior and new seal identities", "prior verdict and material findings", "Builder dispositions", "from available sealed evidence", "full review of the current sealed attempt-scoped object", "invent missing evidence fields"):
        assert text in host
    assert "obligation_source:" not in host
    assert "proof_limit:" not in host

def test_ship_summarizes_existing_conclusions_without_another_audit():
    release = _prompt("release-analyzer.md")
    for text in (
        "lightweight delivery summary, not another acceptance audit",
        "supplied effective Build and Verify conclusions",
        "Do not recompute attempt validity",
        "Evidence recovery is not a mandatory step",
        "A human assertion needs an explicit recorded source",
        "Do not invent owners, timing, action completion, or risk acceptance",
        "`ready` requires sufficient recorded proof",
        "Do not weaken a required proof obligation",
        "Return an upstream gap instead of a release artifact only when",
        "A small delivery needs only a few paragraphs",
        "Do not rerun verification, review code, change implementation",
    ):
        assert text in release
    for text in (
        "For each material accepted business or technical property, determine",
        "Before concluding blocked, not_proven, or an upstream gap, inspect",
        "A latest attempt does not replace the effective attempt",
    ):
        assert text not in release
    host = _main_role_rule("ship") + _content_rule("ship")
    assert "A human assertion needs" not in host
    assert "`ready` requires sufficient recorded proof" not in host


def test_plan_design_connects_project_path_validation_and_proof():
    plan = _prompt("plan-architect.md")
    for text in (
        "Develop each capability as one connected decision",
        "actual entry, current data, authoritative owner, integration contract",
        "positive replacement path for every still-accepted property",
        "assign each check to the boundary that can enforce its truth",
        "Repeat a check only for a concrete residual failure",
        "expensive work avoided and input-dependent work remaining",
        "Separate an existing shared guarantee from this change's integration",
        "Tasks allocates the implementation and verification work",
        "Existing-environment discovery and reversible local setup are not missing product design",
        "without deleting an obligation",
    ):
        assert text in plan
    reviewer = _prompt("plan-reviewer.md")
    for text in (
        "cheap final response while still doing the expensive upstream work",
        "validate A but publish or consume B",
        "without a residual failure",
        "functioning framework can coexist with a wrongly wired caller",
        "not merely an unspecified fixture or preferred tool",
    ):
        assert text in reviewer


def test_tasks_assign_preparation_and_simulate_usable_handoffs():
    planner = _prompt("task-planner.md")
    for text in (
        "work backward from a usable, provable result",
        "if all producers stop exactly as written",
        "bounded reversible setup and fixtures",
        "must be delivered with the appropriate build result",
        "remain explicit prerequisites",
        "does not invalidate independent work",
        "Do not hide new implementation inside verify",
        "otherwise preserve the limitation and required proof",
        "connect it to the actual input/version consumed",
        "Reissuing the packet and repeating narrower checks does not resolve the same blocker",
        "locating an already-required resource or adding a result reference alone",
    ):
        assert text in planner
    reviewer = _prompt("task-reviewer.md")
    for text in (
        "Simulate all producers stopping exactly as written",
        "without adding unassigned implementation",
        "removing an obligation needs an authorized source",
        "source-text matching instead of behavior",
        "Existing-environment discovery and bounded reversible verify setup need not become build tasks",
    ):
        assert text in reviewer

def test_plan_review_corrections_remain_main_design_decisions():
    plan = _prompt("plan-architect.md")
    reviewer = _prompt("plan-reviewer.md")
    assert "cited obligation and failure scenario apply to the current candidate" in plan
    assert "smallest sufficient correction" in plan
    assert "without dropping an accepted property" in plan
    assert "whole design's invariants and lifecycle cost" in plan
    assert "replacing superseded decisions" in plan
    assert "A proposed mechanism is not an accepted obligation" in reviewer
    assert "not whether Main adopted your proposed solution" in reviewer


def test_tasks_balance_split_value_and_prerequisite_timing():
    planner = _prompt("task-planner.md")
    reviewer = _prompt("task-reviewer.md")
    assert "benefit outweighs handoff, repeated context, and review cost" in planner
    assert "otherwise merge the related work into one bounded result" in planner
    assert "Sharing a repository or release alone is not a reason to merge" in planner
    assert "implementation-start conditions, integration conditions, and final acceptance proof" in planner
    assert "Stronger confidence alone does not justify an earlier dependency" in planner
    assert "If a build's own stop requires real integration, retain that prerequisite" in planner
    assert "never waives required proof, substitutes verify for build review" in planner
    assert "concrete avoidable cost or broken handoff" in reviewer
    assert "Final acceptance evidence is not automatically an implementation-start prerequisite" in reviewer
    assert "never use verify to replace required build review" in reviewer


def test_adopt_does_not_own_repository_scope_discovery():
    adopt = _prompt("adopt-expert.md")
    assert "git.repositories" not in adopt
    from codeloom.app.claude_plugin import bundled_claude_skill_resources
    resources = bundled_claude_skill_resources()
    skill = next(content for path, content in resources.items() if str(path).replace("\\", "/").endswith("loom-adopt/SKILL.md"))
    assert "maintained by `loom init`, not adopt" in skill
    assert "Preserve it unchanged" in skill


def test_stage_ownership_has_local_correction_and_genuine_return_converses():
    pairs = (
        ("spec-analyzer.md", "Technical possibility alone does not establish current scope",
         "Preserve an explicitly accepted obligation", "Missing model, mechanism, integration"),
        ("plan-architect.md", "Repair it here",
         "Return to Spec only when", "Owner-bearing technical choice within Plan"),
        ("task-planner.md", "Repair those defects in Tasks",
         "Return to Plan only when", "decision merely absent from your candidate packet"),
    )
    for name, local, boundary, distinction in pairs:
        prompt = _prompt(name)
        for rule in (local, boundary, distinction, "unaffected", "evidence"):
            assert rule in prompt, (name, rule)


def test_reviewers_consolidate_roots_and_require_residual_failure():
    for name in ("spec-reviewer.md", "plan-reviewer.md", "task-reviewer.md"):
        prompt = _prompt(name)
        for rule in (
            "same obligation, root defect, and failure",
            "Keep independently resolvable failures separate",
            "revised candidate anchor",
            "concrete residual candidate-conforming failure",
            "Not adopting your proposed remedy is not a residual failure",
            "New evidence or a failure introduced by the actual delta remains admissible",
        ):
            assert rule in prompt, (name, rule)


def test_host_review_protocol_defers_semantic_ownership_to_main_roles():
    for stage in ("spec", "plan", "tasks"):
        prompt = _main_role_rule(stage)
        assert "Main owns applicability, adoption, remedy, and readiness" in prompt
        assert "loaded role's decision and upstream-return rules" in prompt
        assert "reviewer recommendation never controls the remedy or route" in prompt
        assert "actual changed passages or packets" in prompt
        assert "Return to Spec only when" not in prompt
        assert "Return to Plan only when" not in prompt