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
        "A statement is material when omitting or reinterpreting it changes",
        "Seek discriminating evidence",
        "Identify each source, its supported conclusion, applicable conditions, and material conflicts",
        "Compare the current reality with the required reality",
        "false completion",
        "Every material promise receives an evidence-backed judgment",
        "Own the resolution of gaps through targeted investigation, supported inference, or Owner clarification",
        "Identifying a gap or asking a question is an intermediate action",
        "Close investigable fact questions before deciding that a gap remains",
        "Derive requirement consequences from established facts and applicable accepted rules",
        "use the result without requesting redundant confirmation",
        "An inference can explain an accepted requirement but cannot choose an undecided business policy",
        "Retain an evidence gap only after targeted investigation",
        "the required result remains decidable without it",
        "seek the smallest resolving evidence or factual answer from an available source",
        "advance independent work, and resume that judgment when the input arrives",
        "Uncertainty about current reality does not replace the judgment on an accepted promise",
        "Goal, Way, and Proof as reasoning lenses, not required headings",
        "Use targeted investigation and supported inference to settle facts and implied consequences",
        "Request the smallest useful Owner clarification",
        "a material requirement choice remains unresolved",
        "currently authoritative requirements remain incompatible after applying their precedence",
        "when evidence explicitly identifies an undecided policy, focus the question on that policy",
        "Produce a coherent, user-facing `spec.md`",
        "Before the first review, compare the candidate with the original demand and applicable corrections",
        "the relations needed for the accepted overall result must survive their synthesis",
        "Carry settled commitments through clarification and revision so resolving one gap advances the same deliverable",
        "Only an Owner or another accepted governing source",
        "none creates requirement authority by itself",
        "leave mechanism selection to Plan",
        "steady-state requests not perform a full-table query",
        "Leave design choices within the settled requirement to Plan",
        "proportionate, readable coverage",
        "same authority and disposition may be synthesized",
        "Do not produce technical architecture",
    ):
        assert expected in analyzer


def test_spec_analyzer_prompt_connects_context_discovery_to_evidence():
    analyzer = _prompt("spec-analyzer.md")
    for expected in (
        "# Recover the Needed Business Chain",
        "# Investigate Decision-Changing Context",
        "keeping independently variable meanings distinct",
        "smallest useful condition change and replay the affected chain",
        "retain interacting conditions when the real situation requires them",
        "Treat a candidate situation as a hypothesis to investigate",
        "Distinguish observed facts, supported inferences, current behavior, and Owner choices",
        "Let evidence revise the chain and its branches",
        "Reuse evidence while its source, conditions, and protected meaning remain applicable",
        "Interpret each new input against the current demand",
        "discussion history is not accepted scope",
        "each part could satisfy its own wording while the accepted overall result still fails",
        "Do not infer atomic completion, execution order, or a shared lifecycle",
        "legitimate behavior required by the accepted demand can still complete",
        "Ground a refusal, required field, fallback, or silent skip in a governing requirement",
        "stop propagation where no semantic effect is supported",
        "Merge the effective decision into the Spec body",
        "replace superseded meanings, and check the whole requirement for contradictions",
        "Plan can select a design from the current Spec and necessary evidence references",
        "leave mechanism selection within the settled boundary to Plan",
    ):
        assert expected in analyzer


def test_spec_analyzer_prompt_bounds_scenario_expansion():
    analyzer = _prompt("spec-analyzer.md")
    for expected in (
        "Keep a closed correction focused on its actual result and direct risk",
        "not a fixed sequence of required nodes",
        "When delivery or visibility is itself the agreed result",
        "only when an accepted obligation or reachable consequence makes it necessary",
        "If the required meaning, behavior, and proof stay the same, discard the extra branch",
        "Choose the number and form of comparisons according to the demand",
        "Retain scenarios and causal links when an accepted obligation or evidenced direct risk connects them to the current result",
        "Finish once these delivery conditions are satisfied",
    ):
        assert expected in analyzer


def test_spec_reviewer_requires_identified_candidate_and_material_challenge():
    reviewer = _prompt("spec-reviewer.md")

    for expected in (
        "exact delegated candidate text and supplied candidate identity",
        "candidate anchor",
        "accepted obligation or confirmed fact with a source that actually establishes that authority",
        "check that the cited source and location contain the attributed content",
        "from its content and context, not file names or retrieval order",
        "Reuse verified sources while those conditions remain applicable",
        "A locatable passage is sufficient without line numbers or a verbatim quotation",
        "candidate-conforming failure",
        "Report a missing fact when the draft relies on it to make a material requirement judgment",
        "scoped_evidence_limit",
        "re-review only prior material finding closure",
        "no_material_challenge",
        "cannot establish requirement authority by themselves",
        "authority or provenance is unclear",
        "Do not treat omission of a candidate lifecycle",
        "Classify proposed mechanisms as design inputs and missing investigable facts as evidence work",
        "Return an observation or scoped evidence limit when provenance remains unclear",
        "required legitimate behavior that an added condition rejects or silently skips",
        "each part could satisfy the draft while the accepted overall result fails",
        "An explicitly undecided policy is sufficient to establish that choice",
        "otherwise identify which accepted sources and consequential meanings leave it open",
        "unchanged text can need review when new evidence overturns a prior basis",
        "Unrelated new material does not expand the scope",
        "findings for `spec-analyzer` to synthesize into the final requirement judgment",
    ):
        assert expected in reviewer


def test_spec_role_prompts_keep_workflow_mechanics_out_of_semantic_roles():
    surface = "\n".join((_prompt("spec-analyzer.md"), _prompt("spec-reviewer.md")))

    for forbidden in ("Kernel", "SQLite", "artifact_file", "AskUserQuestion", "temporary Claude Code child agent"):
        assert forbidden not in surface


def test_spec_host_projection_preserves_main_ownership_and_exact_review_handoff():
    prompt = _main_role_rule("spec")
    assert "extras.input_token" not in prompt
    assert "extras.input_snapshot" not in prompt
    skill = _skill_content("loom-spec", "spec", "description", "request=<text>")
    assert "the current Main investigates it directly or delegates" in skill
    assert "delegation is optional" in skill
    assert "investigate it through the stage owner's temporary child-agent boundary" not in skill

    for expected in (
        "extras.main_role=spec-analyzer",
        "read `references/main-role.md`",
        "Do not invoke `spec-analyzer` as a Claude Code Agent",
        "current Main owns this stage's semantic analysis",
        "one bounded question",
        "compute its SHA-256",
        "use that candidate hash to identify the exact text under review",
        "Reassess prior findings where a changed premise affects their applicability",
        "the current demand and accepted business and technical properties",
        "actual text delta (which may be empty)",
        "material input changes",
        "Repeat review only when material text changes or changes to the demand",
        "leave an affected judgment that needs review",
        "Supply the exact candidate body",
        "current Main owns applicability, adoption, remedy, and readiness",
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
        "complete, proportionate first design",
        "accepted obligation from a confirmed fact and a candidate mechanism",
        "Read-only consumption, derived status",
        "adequacy and necessity from its first draft",
        "Repeat a check or query when a concrete residual failure or changed fact requires a fresh judgment",
        "positive path that still carries it",
        "input actually published and used",
        "Account separately for O(1) reference access and input-sized parsing, transfer, or HTTP 200 serialization",
        "not a mechanism blacklist",
    ):
        assert expected in plan

    for expected in (
        "exact candidate body or hash-checked copy and review identity",
        "Build the independent baseline from the current accepted demand",
        "trace each obligation to its authority",
        "candidate-conforming failure or unsupported material cost",
        "Carry every accepted property, correctness guarantee, and cost boundary through a proposed simplification",
        "Trace reused evidence to the consumed version",
        "Main owns design, user questions, remedies, and readiness",
        "finding closure, the real delta",
        "treat existing-environment discovery and reversible fixture preparation as execution work",
    ):
        assert expected in plan_reviewer

    assert "use its clarification gate rather than a generic `unclear input` rule" in plan_skill
    assert "If required user input is unclear" not in plan_skill
    assert "accepted property or hard constraint from a confirmed fact" not in plan_skill

    for expected in (
        "accepted business and technical properties, selected mechanisms",
        "source-derived property",
        "Carry the accepted business or system result and its required properties, selected Plan decision, and this packet's local outcome in the captured block",
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
        "Review only finding closure and that affected scope",
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
        "Declare `Depends on` for every task (`None` when independent)",
        "Explicit relations govern eligibility and input-result reuse",
        "Legacy artifacts without any relation declarations still use previous-item dependencies",
        "Task-local semantic context remains opaque to Kernel",
        "the current Main investigates it directly or delegates",
        "delegation is optional",
    ):
        assert expected in host

    for forbidden in (
        "investigate it through the stage owner's temporary child-agent boundary",
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
        "Review finding closure and the affected scope",
        "prior task packets, declared dependency/coverage relations, and relevant attempt evidence",
        "current Main owns applicability, adoption, remedy, and readiness",
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


def test_plan_and_tasks_host_projection_limits_review_to_affected_scope():
    for command in ("plan", "tasks"):
        prompt = _main_role_rule(command)
        for expected in (
            "previous and new identities",
            "affected semantic dependencies",
            "run a new full review",
        ):
            assert expected in prompt
        for expected in (
            "when Main judges another review useful",
            "actual text delta (which may be empty)",
            "material evidence or decision changes",
            "prior findings, Main dispositions",
            "Review finding closure and the affected scope",
            "Reassess prior findings where a changed premise affects their applicability, including with unchanged candidate text",
            "Repeat review only when material text changes or changes to applicable decisions or evidence leave an affected judgment that needs review",
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
    assert "Wait for the user's answer before treating the choice as settled" in prompt
    assert "silence, tool failure, or a recommendation is not an answer" in prompt
    assert "update the candidate before review or registration" in prompt
    assert "Independent settled work may continue" in prompt
    assert "Ask the concrete resolving question rather than only returning a blocker summary" in prompt
    assert "Once resolved, continue the existing authoring, review, and registration flow" in prompt
    assert "do not register a complete Spec while a material requirement choice remains unresolved" in prompt
    for command in ("plan", "tasks", "ship"):
        assert "Wait for the user's answer before treating the choice as settled" not in _main_role_rule(command)


def test_stage_main_role_prompt_eval_ask_user_question_bad_cases():
    cases = (
        PromptEvalCase(
            name="spec_surfaces_only_correctness_changing_owner_choice",
            surface=_prompt("spec-analyzer.md"),
            badcase="spec agent guesses an unresolved requirement choice or asks the Owner to decide implementation details",
            required_guardrails=(
                "Close investigable fact questions before deciding that a gap remains",
                "Use targeted investigation and supported inference to settle facts and implied consequences",
                "Request the smallest useful Owner clarification",
                "a material requirement choice remains unresolved",
                "currently authoritative requirements remain incompatible after applying their precedence",
                "The choice must change the required user or system result, scope, acceptance meaning",
                "Present the facts, exact undecided meaning, concrete alternatives and consequences",
                "what each alternative would let the affected actor do and what result would follow",
                "record the selection from the Owner's answer",
                "Ask the concrete resolving question",
                "Apply an answer only to the meaning and scope it resolves",
                "merge it and supported consequences into the current Spec, preserve independent settled commitments, and continue",
                "For a partial reply, use the resolved part, investigate remaining facts, and ask only the remaining Owner choice",
                "Do not reopen a settled choice without new evidence or an explicit change",
                "Leave design choices within the settled requirement to Plan",
                "Resolve any remaining requirement choice through the clarification rule above",
                "Finish once these delivery conditions are satisfied",
            ),
        ),
        PromptEvalCase(
            name="plan_rederives_design_after_owner_decision",
            surface=_prompt("plan-architect.md"),
            badcase="plan agent sends ordinary choices to the user or applies an Owner answer to only one technical projection",
            required_guardrails=(
                "Investigate locatable facts before asking the user",
                "Use `AskUserQuestion` to confirm an unresolved key design decision",
                "consequential technical directions, core models, responsibility boundaries, and cross-module contracts",
                "A reversible or low-risk choice can still require that decision",
                "Present the recommendation and obtain the user's selection before building the dependent detailed design",
                "Carry forward prior acceptance or explicit delegation while its premises remain applicable",
                "Do not ask the user to research code or choose complexity",
                "Ordinary equivalent engineering details",
                "Apply the answer before proceeding with the dependent design",
                "A partial reply settles only what it actually answers",
                "develop its consequences yourself and incorporate them into the selected design",
                "Do not reopen a settled choice without new evidence or an explicit change",
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
                "Use recorded owners, timing, completed actions, and explicit risk-acceptance decisions",
                "Leave routine release timing, approval, and deployment execution with the release owner",
                "The release owner decides whether to merge, deploy, roll out, or accept a known risk",
                "An existing Verify obligation with an unavailable observation belongs in the summary with its effect on readiness",
                "Keep ordinary release actions, timing, approval, and risk acceptance in the summary with their actual impact",
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
                "findings for `spec-analyzer` to synthesize into the final requirement judgment",
            ),
        ),
        PromptEvalCase(
            name="builder_returns_owner_decision_without_guessing",
            surface=_prompt("builder.md"),
            badcase="builder guesses an unresolved owner decision or silently expands the task boundary",
            required_guardrails=(
                "Resolve ordinary reversible implementation choices yourself",
                "Stop only when a high-quality implementation would require changing accepted requirement meaning",
                "The current Main handles necessary user clarification through that flow, applies the answer",
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
                "Do not implement fixes or edit product code",
                "Surface unresolved task meaning through the current Skill flow for Main to clarify and apply",
                "do not guess acceptance criteria",
                "Investigate locatable repository and runtime facts directly and choose an available proof path",
                "If the accepted design or requirement itself is missing",
                "identify the exact missing boundary and the input needed to resolve it",
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
                "retain narrower checks that establish scoped facts",
                "seek an available path for the remaining required behavior",
            ),
        ),
        PromptEvalCase(
            name="release_analyzer_does_not_create_extra_approval_system",
            surface=_prompt("release-analyzer.md"),
            badcase="release analyzer turns ordinary release ownership into another approval gate",
            required_guardrails=(
                "Leave routine release timing, approval, and deployment execution with the release owner",
                "The release owner decides whether to merge, deploy, roll out, or accept a known risk",
                "Normally write the delivery summary, including known gaps and the smallest follow-up",
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
        "The separate Verifier takes its full obligations from its own Tasks packet",
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
        "complete the build attempt as `implemented`, recording that the latest sealed implementation passed review",
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
        "Run or inspect real checks and base each conclusion on the observed result and its applicable scope",
        "# Verification Method",
        "Choose the strongest useful path that the current project can support",
        "verify the real creation entry",
        "Use pre-seeded intermediate state for the later behavior it exercises and cover creation through its own entry",
        "When performance is material",
        "retain narrower checks that establish scoped facts",
        "`verified`: every material obligation",
        "`failed`: an actual observation contradicts required behavior",
        "`blocked`: one or more necessary obligations remain not verified",
        "Do not decide workflow routing or attempt state",
        "State the result, decisive observations, and any unresolved required behavior with its next action",
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
    assert "sufficient recorded proof that every material accepted result is delivered" in release
    assert "human assertion" in release
    assert "source-derived property" in task_planner
    assert "does not authorize deleting an accepted business or technical property" in plan_architect

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

    assert "Base behavior claims on the recorded Verify observations and conclusions" in release
    assert "sufficient recorded proof that every material accepted result is delivered" in release


def test_plan_reviewer_receives_identified_candidate_draft():
    architect = _prompt("plan-architect.md")
    reviewer = _prompt("plan-reviewer.md")
    host_rule = _main_role_rule("plan")

    for expected in (
        "exact candidate body or hash-checked copy and review identity",
        "State which identity you inspect",
        "input_missing_or_mismatched",
        "rather than inferring another candidate from disk",
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

    content_rule = _content_rule("plan")
    assert "current Main investigates it directly or delegates a bounded factual question" in content_rule
    assert "A short check in a known source can be done directly; delegation is optional" in content_rule
    assert "investigate it through the stage owner's temporary child-agent boundary" not in content_rule
    assert "Investigate locatable facts before asking the user" in architect
    assert "Leave equivalent implementation details and investigable facts with Main" in reviewer
    assert "consequential technical directions, core models, responsibility boundaries, cross-module contracts" in reviewer
    assert "Preserve existing authorization" in reviewer

    for prompt in (architect, reviewer):
        for forbidden in ("temporary Claude Code child agent", "artifact_file", "Kernel", "workflow state"):
            assert forbidden not in prompt


def test_plan_prompts_select_analysis_models_for_material_relationships():
    architect = _prompt("plan-architect.md")
    reviewer = _prompt("plan-reviewer.md")

    for expected in (
        "Use PlantUML",
        "relationship, cardinality, state transition, cross-system sequence",
        "multi-role workflow",
        "closed local correction may omit them",
        "design evidence, not decoration or a quota",
    ):
        assert expected in architect

    for expected in (
        "Build the independent baseline from the current accepted demand",
        "smallest reasonable implementation that fully follows the candidate",
        "candidate-conforming failure or unsupported material cost",
        "Require a missing design detail when it enables such a failure or cost",
    ):
        assert expected in reviewer


def test_tasks_packets_preserve_result_links_and_relation_premises():
    planner = _prompt("task-planner.md")
    reviewer = _prompt("task-reviewer.md")
    for text in (
        "accepted business or system result", "transferred result premise", "Relation reachability alone",
        "Before withholding Tasks", "affected claim, inspected scope", "derive supported consequences",
        "If a source fails, seek an available alternative", "use `AskUserQuestion` for that specific fact",
        "Wait for the answer, apply what it establishes", "Identifying a gap or asking is an intermediate action",
        "while advancing independent supported work", "Known execution prerequisites may remain explicit",
        "does not replace execution invalidation after a build retry", "recorded input attempt IDs",
        "without changing the consumer's definition", "Keep these runtime mechanics in the review context",
        "`#` or `###` does not end the captured block",
    ):
        assert text in planner
    for text in (
        "changed transferred premise", "layer or file ledger entries", "Accept compact cross-layer work",
        "candidate-conforming downstream failure", "recorded input attempt IDs", "task-definition change",
        "Re-execution against that new result remains required", "A changed proof obligation or consumed contract still does",
        "rather than demand a bump to compensate for unknown mechanics", "parser retains the intervening raw text",
    ):
        assert text in reviewer
    template = resources.files("codeloom.templates").joinpath("tasks-template.md").read_text(encoding="utf-8")
    for text in (
        "With the explicit relations below", "`#` or `###` does not end the captured block",
        "allowed repeated operation needs no invented rejection rule",
        "fresh proof with an unchanged verify Revision",
    ):
        assert text in template
    host = _main_role_rule("tasks") + _content_rule("tasks")
    assert "transferred result premise" not in host
    assert "Before withholding Tasks" not in host

def test_do_roles_preserve_execution_meaning_and_evidence_handoff():
    builder = _prompt("builder.md")
    reviewer = _prompt("code-reviewer.md")
    verifier = _prompt("verifier.md")
    for text in (
        "Do not re-litigate an accepted Plan choice",
        "locatable implementation facts from missing execution meaning",
        "Ordinary reversible details and equivalent local implementations",
        "the sources inspected",
        "Reuse conditions already established on this call path and authoritative data already read",
        "check their design basis against the actual code",
        "Treat the proposed correction as a suggestion",
    ):
        assert text in builder
    for text in (
        "obligation_source:", "affected_contract:",
        "If the current sealed object is valid but the delta cannot be established, perform a full review", "trustworthy seal-to-seal delta",
        "recover the accepted design from the Task Packet and relevant Plan passages",
        "design requirement, actual code behavior, material discrepancy",
        "Preserve equivalent local choices the design leaves open",
    ):
        assert text in reviewer
    for text in (
        "behavior:", "entry:", "counterexample:", "proof_limit:", "affected_contract:",
        "Use `verified` when the combined evidence sufficiently covers every material packet obligation", "identify which prevent packet closure",
        "frozen Verify Packet from your own Tasks task",
        "Use Builder notes and review results to locate evidence, then make your own judgment against the packet's obligations",
        "Keep checks and bounded experiments within the packet's required behavior and covered build results",
    ):
        assert text in verifier
    host = _main_role_rule("do")
    for text in (
        "prior and new seal identities", "prior verdict and material findings", "Builder dispositions",
        "from available sealed evidence", "full review of the current sealed attempt-scoped object",
        "invent missing evidence fields", "own frozen Tasks packet",
        "Apply the answer and continue within the accepted task",
    ):
        assert text in host
    assert "obligation_source:" not in host
    assert "proof_limit:" not in host

def test_ship_summarizes_existing_conclusions_without_another_audit():
    release = _prompt("release-analyzer.md")
    for text in (
        "baseline for a lightweight delivery summary",
        "The Host supplies effective attempt identity and validity",
        "read the relevant passages of the current accepted Spec, Plan, or Tasks",
        "without those passages, Build summaries, or human completion notes",
        "stop once the result, its supporting observations, and consequential gaps are clear",
        "Consult a referenced record when a missing observation, contradiction, or ambiguity could change a material claim",
        "Combine contributions from multiple Build and Verify tasks into the outcome they jointly deliver",
        "including the relevant environment or operating range",
        "explain the practical effect and the smallest action needed to resolve it",
        "A behavior can be `proven` while release readiness is `blocked`",
        "An existing Verify obligation with an unavailable observation belongs in the summary",
        "missing implementation or proof coverage in the task definitions",
        "Attribute a human assertion to its explicit recorded source",
        "Use recorded owners, timing, completed actions, and explicit risk-acceptance decisions",
        "`ready` requires sufficient recorded proof",
        "When a required check is unavailable, retain its obligation",
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
        "representative current entry, data flow, semantic owner, integration boundary",
        "positive path that still carries it",
        "where facts are acquired, which business judgments and effects use them",
        "Reuse acquired data and established guarantees within the conditions that make them valid",
        "place each judgment at the boundary that owns its truth",
        "Repeat a check or query when a concrete residual failure or changed fact requires a fresh judgment",
        "before and after work at startup, refresh, write, request, or background time",
        "Prove this change's integration using evidenced shared-platform guarantees within their applicable scope",
        "Tasks allocates the work",
        "Leave existing-environment discovery and reversible setup to execution",
        "Select a feasible proof path that satisfies the obligation with proportional infrastructure",
    ):
        assert text in plan
    reviewer = _prompt("plan-reviewer.md")
    for text in (
        "Include input-sized upstream work and serialization alongside the final comparison",
        "Trace reused evidence to the consumed version",
        "identify a residual failure before requesting repeated validation",
        "Check how the selected technology or component connects to that path",
        "treat existing-environment discovery and reversible fixture preparation as execution work",
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
        "Keep existing-environment discovery and bounded reversible setup with verify",
    ):
        assert text in reviewer

def test_plan_review_corrections_remain_main_design_decisions():
    plan = _prompt("plan-architect.md")
    reviewer = _prompt("plan-reviewer.md")
    assert "check its source, scenario, and applicability" in plan
    assert "smallest sufficient correction" in plan
    assert "does not authorize deleting an accepted business or technical property" in plan
    assert "update dependent interfaces, states, diagrams, and proof together" in plan
    assert "Replace superseded decisions instead of accumulating exceptions" in plan
    assert "leaving the remedy with Main" in reviewer
    assert "Close a challenge when any valid correction satisfies the accepted obligation" in reviewer


def test_tasks_balance_split_value_and_prerequisite_timing():
    planner = _prompt("task-planner.md")
    reviewer = _prompt("task-reviewer.md")
    assert "benefit outweighs handoff, repeated context, and review cost" in planner
    assert "merge unless a concrete isolation benefit justifies that handoff" in planner
    assert "independently usable result, a safe local stop, or useful isolation" in planner
    assert "implementation-start conditions, integration conditions, and final acceptance proof" in planner
    assert "Stronger confidence alone does not justify an earlier dependency" in planner
    assert "If a build's own stop requires real integration, retain that prerequisite" in planner
    assert "never waives required proof, substitutes verify for build review" in planner
    assert "concrete avoidable cost or broken handoff" in reviewer
    assert "identify what the consumer actually needs to begin or reach its stated stop" in reviewer
    assert "Preserve necessary integration conditions, final proof, and independent build review" in reviewer


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
        ("spec-analyzer.md", "A hypothetical future operation does not authorize new",
         "do not silently defer it to simplify the work", "Missing model, mechanism, integration"),
        ("plan-architect.md", "Repair design defects within Plan",
         "Return to Spec only when", "A choice inside the accepted requirement is Plan work"),
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
        rules = (
            "same obligation, root defect, and failure",
            "Keep independently resolvable failures separate",
        )
        if name == "plan-reviewer.md":
            rules += (
                "concrete residual failure at the current anchor",
                "Close a challenge when any valid correction satisfies the accepted obligation",
                "New evidence or a failure introduced by the actual delta remains admissible",
                "evidence that changes a judgment without changing candidate text",
                "directly affected dependencies",
            )
        elif name == "task-reviewer.md":
            rules += (
                "current candidate anchor",
                "concrete residual candidate-conforming failure",
                "satisfies the accepted obligation through any valid remedy",
                "actual text delta (which may be empty)",
                "Reassess prior findings where a changed premise affects their applicability, including with unchanged text",
                "Review only finding closure and that affected scope",
            )
        else:
            rules += (
                "revised candidate anchor",
                "concrete residual candidate-conforming failure",
                "satisfies the accepted obligation through any valid remedy",
                "New evidence or a failure introduced by the actual delta remains admissible",
            )
        for rule in rules:
            assert rule in prompt, (name, rule)


def test_host_review_protocol_defers_semantic_ownership_to_main_roles():
    for stage in ("spec", "plan", "tasks"):
        prompt = _main_role_rule(stage)
        assert "Main owns applicability, adoption, remedy, and readiness" in prompt
        assert "loaded role's decision and upstream-return rules" in prompt
        assert "Evaluate findings against the accepted obligations and applicable evidence, select the correction" in prompt
        assert "actual text delta (which may be empty)" in prompt
        if stage == "spec":
            assert "material input changes" in prompt
        else:
            assert "material evidence or decision changes" in prompt
        assert "Return to Spec only when" not in prompt
        assert "Return to Plan only when" not in prompt


def test_plan_method_forms_a_first_design_before_review_repair():
    plan = _prompt("plan-architect.md")
    assert plan.index("# Understand the Work") < plan.index("# Form Viable Routes")
    assert plan.index("# Form Viable Routes") < plan.index("# Make the Selected Route Implementable")
    assert plan.index("# Make the Selected Route Implementable") < plan.index("# Check the First Design")
    for text in (
        "preventing unsupported responsibilities in the first draft is the goal",
        "In an existing project, ground design in a representative current entry",
        "In a new project without implementation examples, start from the accepted behavior",
        "Missing historical code is not a reason to stop",
        "relevant first-party guidance, mature external implementations, or documented practice",
        "explain their applicable mechanisms, assumptions, and costs",
        "Combine internal and external evidence to develop feasible routes",
        "Reuse applicable evidence for a bounded correction",
        "If a source or tool fails, seek available evidence or another viable investigation path",
        "Use established premises to resolve supported consequences and continue",
        "then apply the result and finish the affected design",
        "Investigate enough to make the choice understandable, not until every source is exhausted",
        "If only one key route is feasible",
        "Tasks can consume the selected design directly",
        "make their use and local differences clear at the consumers",
        "Derive transaction or coordination boundaries from the facts that must remain consistent",
        "Present the recommendation and obtain the user's selection before building the dependent detailed design",
        "Complexity is derived after the direction is chosen",
        "A user-confirmed mechanism is a real constraint",
        "Preserve unaffected wording, decisions, and assets",
        "If the answer would change or contradict accepted Spec",
        "the reviewer is not responsible for turning an oversized or incomplete first draft",
    ):
        assert text in plan
    host = _main_role_rule("plan")
    assert "use AskUserQuestion before registration" in host
    assert "generic operation lifecycle" not in host
