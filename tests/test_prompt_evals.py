from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from codeloom.app.claude_plugin import _adopt_skill_content, _agent_rule, _argument_rule, _content_rule
from codeloom.prompt_evals.supplement import missing_prompt_eval_case_drafts, write_missing_prompt_eval_cases


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


def test_adopt_agent_prompt_keeps_semantics_strong_without_delegation_gate():
    prompt = _agent_prompt("adopt-expert.md")

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
    do_prompt = _agent_rule("do")

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
    analyzer = _agent_prompt("spec-analyzer.md")

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
        "Do not produce technical architecture",
    ):
        assert expected in analyzer


def test_spec_reviewer_prompt_uses_minimal_counterexamples():
    reviewer = _agent_prompt("spec-reviewer.md")

    for expected in (
        "bounded advisory reviewer supporting `spec-analyzer`",
        "# Scope and Proportionality",
        "For a closed correction",
        "For a complex demand",
        "# Counterexample Method",
        "**Bind**",
        "**Falsify**",
        "**Hand back**",
        "smallest evidence-backed counterexample",
        "## Commitment loss",
        "## Evidence overreach",
        "Missing evidence alone is not a finding",
        "challenge a claimed evidence gap when relevant evidence already resolves the fact",
        "the draft uses uncertainty to avoid a material judgment",
        "## Causal-chain incompleteness",
        "## Unauthorized convergence",
        "supporting evidence and uncertainty",
        "the impact on the requirement",
        "the smallest useful recommendation",
        "Do not rewrite the Spec",
    ):
        assert expected in reviewer


def test_spec_agent_prompts_exclude_process_and_cross_layer_language():
    surface = "\n".join((_agent_prompt("spec-analyzer.md"), _agent_prompt("spec-reviewer.md")))

    for forbidden in (
        "Internal Requirement-Convergence Sequence",
        "Raw promise inventory",
        "Claim-to-evidence selection",
        "Convergence read-back",
        "# Commitment Coverage",
        "ledger",
        "lineage",
        "compatibility",
        "legacy",
        "FR/AC",
        "host-callable",
        "temporary Claude Code child agent",
        "plan-architect",
        "Host",
        "Kernel",
        "SQLite",
        "artifact_file",
        "AskUserQuestion",
        "blocks Spec convergence",
    ):
        assert forbidden not in surface


def test_spec_host_projection_prompt_eval_preserves_agent_kernel_boundary():
    prompt = _agent_rule("spec")

    for expected in (
        "`spec-analyzer` as the owner of requirement semantics",
        "Kernel only registers the final artifact",
        "Ground the current business or system reality in evidence before drafting",
        "do not default to journey order, the earliest step, a smallest CRUD slice, current/later/out, or a candidate implementation",
        "Use `spec-reviewer` only for advisory review",
        "Ask one highest-information decision",
        "If such an Owner decision remains unresolved, do not write or register a final `spec.md`",
        "Goal, Way, and Proof are Agent reasoning responsibilities",
        "artifact_file",
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
        "Open questions, only when material",
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


def test_plan_and_tasks_prompt_eval_stage_projection_cases():
    plan = _agent_prompt("plan-architect.md")
    plan_reviewer = _agent_prompt("plan-reviewer.md")
    task_planner = _agent_prompt("task-planner.md")
    task_reviewer = _agent_prompt("task-reviewer.md")

    for expected in (
        "both the target business implementation model and its concrete landing in the current project",
        "# Inputs and Evidence",
        "what the evidence proves, what it does not prove, and why it applies",
        "Group promises that must be established by one coherent capability",
        "smallest wrong or prohibited result the design must make unreachable",
        "# Form the Business Implementation Design",
        "authoritative, derived, attached, and external snapshot facts",
        "Unify work surfaces only when they share a business fact",
        "trigger and actor",
        "accountable command or owner",
        "bounded retry or attempt budget",
        "single authority",
        "claim, redelivery, actual invocation, and crash-after-claim",
        "automatic, scheduled, manual/support, admin, callback, and reconciliation paths",
        "bind each read surface to the same authoritative fact",
        "local acceptance or submission from an external unknown or terminal outcome",
        "# Land the Design in the Current Project",
        "reuse, extend, correct, replace, add, or preserve a real difference",
        "A technical surface is material when omitting it",
        "**UI and work surfaces:**",
        "**Commands, queries, APIs, RPCs, and Jobs:**",
        "**Data, schema, and read models:**",
        "**SQL, DAO, mapper, and query paths:**",
        "**Transactions, concurrency, idempotency, and integration:**",
        "Keep all participating surfaces semantically aligned",
        "Use the smallest useful PlantUML diagram",
        "material object relationship or cardinality",
        "state lifecycle or illegal transition",
        "cross-system synchronous/asynchronous sequence",
        "multi-role workflow",
        "A closed local correction may omit diagrams",
        "Produce a readable, self-evidencing `plan.md`",
    ):
        assert expected in plan

    for expected in (
        "bounded, adversarial reviewer supporting `plan-architect`",
        "Use the exact candidate text and its supplied identity",
        "# Independent Minimum Baseline",
        "Do not use the candidate's headings, terminology, selected abstractions, or omissions to define this baseline",
        "The absence of a preferred heading, table, label, class, endpoint, field, index, diagram, or technical surface is not a defect by itself",
        "# Counterexample Method",
        "**Baseline**",
        "**Falsify**",
        "**Hand back**",
        "smallest reasonable implementation that fully follows the candidate",
        "## Commitment-to-model break",
        "## Mechanism break",
        "vary which event each reasonable consumer counts—claim, redelivery, invocation, or crash-after-claim",
        "automatic, scheduled, manual/support, admin, callback, and reconciliation entry",
        "same authoritative fact rather than allowing local submission to appear as external success",
        "## Project-landing or cross-layer break",
        "## Evidence or authority break",
        "A candidate is underdetermined when a reasonable implementer must still choose",
        "Do not output a coverage matrix, missing-field checklist, replacement Plan",
        "If no material counterexample survives",
    ):
        assert expected in plan_reviewer

    assert "tools:" not in plan
    assert "tools:" not in plan_reviewer

    surface = "\n".join((plan, plan_reviewer))
    for forbidden in (
        "# Stage Ownership",
        "temporary Claude Code child agent",
        "artifact_file",
        "Kernel",
        "workflow state",
        "Tasks and Do",
        "Causal Design Coverage",
        "supersession/withdrawal",
        "Plan disposition",
    ):
        assert forbidden not in surface

    for expected in (
        "execution slicing recorded in `tasks.md`",
        "accepted Spec results and Plan design",
        "# Form the Implementation Result Chain",
        "current-to-target implementation results",
        "shared prerequisite and protected invariant",
        "# Slice Build Work",
        "Do not split mechanically by UI, API, service, mapper, schema, file, class, function, or technical layer",
        "transaction, state transition, public contract, permission gate, migration invariant, or external-effect protocol",
        "# Design Verify Coverage",
        "One verify task may cover several naturally related build tasks",
        "start proof at the real behavior entry that creates it",
        "prohibited repeated or terminal re-entry",
        "Verification proves behavior established by accepted design and implementation",
        "selected mechanism, state or write owner, public/data/external contract",
        "return the smallest Plan design gap instead of creating research or `verify` work",
        "# Compile Self-Contained Task Packets",
        "why   — accepted result and selected design",
        "where — current responsibility and target landing when material",
        "Inside the same captured block",
        "A Task List item containing only `Lane`, `Complexity`, and `Revision` is invalid",
        "Put every execution-critical fact directly beneath its own checklist line",
        "A Plan reference supplies traceability, not missing execution context",
        "exact authoritative state or fact, legal transition, losing-concurrency result, external-effect guard, stop condition, and proof obligation",
        "generic instruction to “follow the Plan” cannot be the only source",
        "# Revise and Write",
        "Revision protects execution meaning, not Markdown wording",
        "preserve the ID, update the title only if needed, and increment only the affected packet's Revision",
        "never bump every task merely because an upstream artifact changed",
        "smallest evidence-backed design gap",
    ):
        assert expected in task_planner

    for expected in (
        "bounded, adversarial reviewer supporting `task-planner`",
        "Use the exact candidate text and supplied candidate identity",
        "identity is missing or mismatched",
        "# Independent Consumer Baseline",
        "# Simulate the Consumer",
        "# Falsify",
        "# Hand Back",
        "reasonable implementation, code-review, or verification consumer",
        "first isolate the packet at its checklist line",
        "A metadata-only Task List item is not saved by a table, delivery map, or later `Task Notes` section",
        "Later reader notes, delivery maps, or global prose cannot repair",
        "smallest reasonable execution that fully follows the candidate",
        "disguise evidence needed to select or finish Plan design as a `verify` task",
        "generic Plan reference the only source of an authoritative fact, transition, concurrency outcome, external-effect guard, stop, or proof obligation",
        "proving only a pre-seeded intermediate state while omitting the real creation entry or prohibited repeated/terminal re-entry",
        "split one transaction, state transition, public contract, permission gate, or invariant",
        "turn grouped verification into an unrelated mega-batch",
        "duplicate IDs, dangling build/verify relations",
        "non-semantic bump, or an unrelated packet change",
        "not a defect by itself",
        "inspected scope, the affected packet, and the smallest recovery path",
        "say so without treating the result as approval",
    ):
        assert expected in task_reviewer

    for prompt in (task_planner, task_reviewer):
        for forbidden in (
            "Kernel",
            "Host",
            "workflow state",
            "artifact_file",
            "temporary Claude Code child agent",
            "Plan validation matrix",
            "deferred",
            "mapping-gap",
            "formal disposition",
        ):
            assert forbidden not in prompt


def test_loom_tasks_skill_prompt_eval_assignment_cases():
    prompt = _content_rule("tasks")

    cases = (
        PromptEvalCase(
            name="tasks_blocks_owner_or_missing_facts",
            surface=prompt,
            badcase="tasks stage turns missing facts into research Tn items",
            required_guardrails=(
                "Only a fact necessary to define safe slicing",
                "lanes other than `build` or `verify`",
                "never encode it as build/verify tasks or Do fact gathering",
            ),
        ),
        PromptEvalCase(
            name="tasks_forms_results_without_kernel_graph",
            surface=prompt,
            badcase="tasks stage turns Plan headings into a dependency graph scheduler",
            required_guardrails=(
                "trace selected Spec commitments to their Plan abstract/concrete design records",
                "implementation path of stage-level results",
                "Planner's recommended order",
                "Host and Kernel must not parse or gate on that prose",
                "not a Kernel graph or scheduling contract",
            ),
        ),
        PromptEvalCase(
            name="tasks_requires_inline_packet_context",
            surface=prompt,
            badcase="tasks stores design references only in a later Task Notes section",
            required_guardrails=(
                "Each task block must contain the execution-critical context",
                "Do not put required context only in later Task Notes",
                "relevant commitment/design trace",
                "proof handoff",
                "Task-local context is opaque to Kernel",
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
                "keep non-blocking constraints, risk notes, and validation notes in task context",
            ),
        ),
        PromptEvalCase(
            name="tasks_requires_natural_grouped_verification",
            surface=prompt,
            badcase="verify task becomes unrelated mega-batch",
            required_guardrails=(
                "multiple naturally related build tasks",
                "covered tasks, risks, required counterexamples/regression surfaces, and expected evidence",
            ),
        ),
        PromptEvalCase(
            name="tasks_maintains_local_revision_metadata",
            surface=prompt,
            badcase="tasks stage rewrites one task packet then globally bumps all revisions",
            required_guardrails=(
                "Planner and Reviewer compare task packets",
                "material proof surface",
                "implementation-before/after relation",
                "Do not bump `Revision`",
                "never automatically bump all tasks after upstream drift",
            ),
        ),
        PromptEvalCase(
            name="tasks_requires_settled_design_and_unique_identity",
            surface=prompt,
            badcase="tasks stage turns an omitted material Plan design into duplicate executable Tn items",
            required_guardrails=(
                "accepted Plan design supplies the material result, concrete landing, clear boundary, protected invariant, and proof direction",
                "Route a missing material design decision or evidence-backed design blocker upstream",
                "Every `Tn` ID must be unique",
                "Do not reuse or duplicate an ID",
            ),
        ),
        PromptEvalCase(
            name="tasks_requires_revision_baseline_and_stable_titles",
            surface=prompt,
            badcase="tasks stage title-polishes a task or guesses its Revision without comparing prior evidence",
            required_guardrails=(
                "available prior `tasks.md`, ID/title/Revision values, and attempt baseline",
                "concrete Revision claim with inspected scope and a smallest recovery route",
                "Do not change an existing task title",
                "material execution-contract change retains the ID",
            ),
        ),
        PromptEvalCase(
            name="tasks_recovers_available_evidence_before_scoping_gap",
            surface=prompt,
            badcase="tasks stage blocks on optional documentation instead of recovering accepted and named-source evidence",
            required_guardrails=(
                "Recover accepted artifact, existing task/attempt, and named-source evidence",
                "Ideal/optional documentation, a preferred harness, and ordinary local details are not blockers",
                "proceed with the supported task slice",
                "Do not emit research/scout/discovery tasks",
            ),
        ),
        PromptEvalCase(
            name="tasks_scopes_necessary_evidence_gap_without_blocking_unaffected_work",
            surface=prompt,
            badcase="tasks stage emits a generic blocked result when only one necessary slicing claim remains unassessable",
            required_guardrails=(
                "Only a fact necessary to define safe slicing",
                "bounded `insufficient evidence` result after available evidence recovery",
                "concrete Revision claim with inspected scope and a smallest recovery route",
                "do not make it a gate for unaffected tasks",
            ),
        ),
        PromptEvalCase(
            name="tasks_preserves_packet_local_revision_after_reviewer_counterevidence",
            surface=prompt,
            badcase="reviewer uncertainty causes Planner to rewrite unrelated task packets or block registration",
            required_guardrails=(
                "change only directly affected task packets",
                "Preserve unrelated IDs, titles, Revisions, attempts, and task-local context",
                "Reviewer counterevidence is advisory, never a readiness gate",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)

def test_tasks_reviewer_projection_uses_exact_candidate_identity():
    tasks_prompt = _agent_rule("tasks")
    content_prompt = _content_rule("tasks")
    tasks_reviewer_rule = "For `tasks`, advisory review must receive exact candidate text and candidate identity"

    for expected in (
        tasks_reviewer_rule,
        "The reviewer reports the inspected identity",
        "missing or mismatched identity permits only a missing-input response",
        "Re-review only a new exact candidate identity and affected packet/claim",
        "reviewer silence, uncertainty, or non-material strengthening is not a readiness gate",
    ):
        assert expected in tasks_prompt
    for expected in (
        "The artifact file must contain only user-facing Markdown",
        "exact repository-relative `extras.artifact_path`",
        "exact `extras.register_command`",
        "Do not reconstruct the artifact path or registration command",
    ):
        assert expected in content_prompt
    for command in ("spec", "plan", "ship"):
        assert tasks_reviewer_rule not in _agent_rule(command)


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


def test_plan_and_tasks_host_projection_uses_recovery_first_continuation_routes():
    plan_prompt = _agent_rule("plan")
    tasks_prompt = _agent_rule("tasks")

    for expected in (
        "Prefer completing evidence recovery and candidate revision in the current invocation",
        "Re-review only materially changed mechanisms and dependencies",
        "--arg action=route --arg target_stage=<spec|plan>",
        "use `spec` only for a missing requirement meaning",
        "`plan` for unresolved evidence or design owned by Plan",
        "continuation route, not a blocking finding",
    ):
        assert expected in plan_prompt

    for expected in (
        "Prefer completing evidence recovery and packet revision in the current invocation",
        "Verification proves established behavior",
        "--arg action=route --arg target_stage=<plan|tasks>",
        "use `plan` only when material design or design evidence is unresolved",
        "Never encode that recovery as a research/build/verify task or blocking finding",
    ):
        assert expected in tasks_prompt


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


def test_artifact_stage_skill_prompt_eval_routes_owner_questions_before_kernel():
    for command in ("spec", "plan", "tasks", "ship"):
        prompt = _agent_rule(command)

        for expected in (
            "owner-bearing uncertainty",
            "use AskUserQuestion before running the Kernel stage",
            "do not guess business semantics, risk acceptance, or long-term technical direction",
        ):
            assert expected in prompt


def test_loom_spec_skill_prompt_eval_runs_host_clarification_to_convergence():
    prompt = _agent_rule("spec")

    for expected in (
        "Use AskUserQuestion only after evidence leaves one owner-bearing requirement decision",
        "Ask one highest-information decision",
        "If such an Owner decision remains unresolved, do not write or register a final `spec.md`",
    ):
        assert expected in prompt


def test_stage_main_agent_prompt_eval_ask_user_question_bad_cases():
    cases = (
        PromptEvalCase(
            name="spec_surfaces_only_correctness_changing_owner_choice",
            surface=_agent_prompt("spec-analyzer.md"),
            badcase="spec agent guesses an unresolved requirement choice or asks the Owner to decide implementation details",
            required_guardrails=(
                "Resolve investigable facts before requesting an Owner choice",
                "An unproven proposed method is not an Owner choice",
                "Request one Owner decision only",
                "accepted input or evidence affirmatively supports incompatible requirement meanings or business rules",
                "choice changes the required result, scope, acceptance meaning",
                "the unresolved choice, credible directions and consequences",
                "the best-supported recommendation",
                "Do not ask the Owner to choose ordinary implementation details or compensate for missing evidence",
                "If an unresolved Owner choice still changes requirement correctness, stop with that clarification",
            ),
        ),
        PromptEvalCase(
            name="plan_rederives_design_after_owner_decision",
            surface=_agent_prompt("plan-architect.md"),
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
            surface=_agent_prompt("task-planner.md"),
            badcase="task planner turns a material Plan omission into executable tasks",
            required_guardrails=(
                "A missing material design decision cannot be repaired through task wording",
                "A task is ready to emit only when the accepted design supplies",
                "stop the final artifact and return the smallest evidence-backed design gap",
                "Do not disguise it as research, build, or verify work",
            ),
        ),
        PromptEvalCase(
            name="ship_separates_owner_decisions_from_workflow_gaps",
            surface=_agent_prompt("release-analyzer.md"),
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
            surface=_agent_prompt("spec-reviewer.md"),
            badcase="spec reviewer chooses an Owner direction instead of returning the semantic conflict",
            required_guardrails=(
                "surface an Owner choice",
                "leave the final requirement judgment to `spec-analyzer`",
            ),
        ),
        PromptEvalCase(
            name="builder_returns_owner_decision_without_guessing",
            surface=_agent_prompt("builder.md"),
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
            surface=_agent_prompt("code-reviewer.md"),
            badcase="code reviewer turns a requirement or design decision into local review advice",
            required_guardrails=(
                "report an upstream-boundary finding",
                "Do not edit code",
                "ask the user",
            ),
        ),
        PromptEvalCase(
            name="verifier_does_not_guess_missing_acceptance",
            surface=_agent_prompt("verifier.md"),
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
            surface=_agent_prompt("builder.md"),
            badcase="builder asks the user to choose a local implementation detail inside the task boundary",
            required_guardrails=(
                "Resolve ordinary reversible implementation choices yourself inside the task boundary",
                "Choose local structure by balancing behavior correctness, project fit, performance and resource cost, maintainability, readability, change cost, and verification cost",
            ),
        ),
        PromptEvalCase(
            name="code_reviewer_does_not_manufacture_preferences",
            surface=_agent_prompt("code-reviewer.md"),
            badcase="code reviewer turns normal style preference into a blocking decision",
            required_guardrails=(
                "Equivalent local style, speculative hardening, generic clean-code preference, optional strengthening",
                "There is no finding quota",
                "Return `pass` when no material counterexample survives",
            ),
        ),
        PromptEvalCase(
            name="verifier_missing_harness_is_not_user_decision",
            surface=_agent_prompt("verifier.md"),
            badcase="verifier turns an unavailable preferred harness into a user decision",
            required_guardrails=(
                "If a broad runtime or integration harness cannot start",
                "retain narrower checks that still prove scoped facts",
                "Missing an ideal harness is not itself a product or design decision",
            ),
        ),
        PromptEvalCase(
            name="release_analyzer_does_not_create_extra_approval_system",
            surface=_agent_prompt("release-analyzer.md"),
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

def test_builder_prompt_eval_good_cases():
    prompt = _agent_prompt("builder.md")

    for expected in (
        "build-lane implementation agent",
        "quality of one task-scoped implementation",
        "complete, correct, performant, maintainable, readable, secure, reliable, and testable code",
        "High quality is not a universal checklist",
        "frozen Task Packet as the execution boundary",
        "Inspect current code, callers, consumers, tests, state/data flow, and nearby conventions",
        "Resolve ordinary reversible implementation choices yourself",
        "Complete the whole task-scoped result",
        "Keep important business, data, state, transaction, query, and external-call flow visible",
        "When the path is material, examine boundedness, query and traversal count",
        "# When the Task Cannot Close",
        "Do not claim independent review or full verification",
        "Do not produce a compliance checklist or an evidence-field inventory",
    ):
        assert expected in prompt


def test_builder_prompt_eval_bad_cases():
    prompt = _agent_prompt("builder.md")
    cases = (
        PromptEvalCase(
            name="do_not_bypass_task_packet_boundary",
            surface=prompt,
            badcase="builder reinterprets upstream prose into a broader execution scope",
            required_guardrails=(
                "frozen Task Packet as the execution boundary",
                "Preserve later tasks and unrelated working-tree changes",
                "Do not turn a local implementation into an unrequested cross-project cleanup",
            ),
        ),
        PromptEvalCase(
            name="do_not_optimize_for_tiny_patch",
            surface=prompt,
            badcase="builder leaves the task-scoped behavior incomplete to minimize changed lines",
            required_guardrails=(
                "Complete the whole task-scoped result",
                "Do not reduce a required action, state/data effect, side effect, permission outcome, feedback path, or supported entry",
            ),
        ),
        PromptEvalCase(
            name="material_performance_requires_visible_judgment",
            surface=prompt,
            badcase="builder chooses looped queries without examining realistic cost",
            required_guardrails=(
                "When the path is material, examine boundedness, query and traversal count",
                "batch opportunities, external-call count, transaction scope, concurrency, idempotency",
                "avoids avoidable N+1 work, repeated traversal, duplicate external effects, unbounded work",
            ),
        ),
        PromptEvalCase(
            name="major_semantic_change_returns_upstream",
            surface=prompt,
            badcase="builder guesses a new contract or design mechanism during implementation",
            required_guardrails=(
                "Stop only when a high-quality implementation would require changing accepted requirement meaning",
                "public/data/external contract",
                "material design mechanism",
                "why no task-local implementation is safe",
                "Report this conflict to the host",
                "do not perform workflow routing or modify upstream artifacts",
            ),
        ),
        PromptEvalCase(
            name="stale_guidance_does_not_expand_build_scope",
            surface=prompt,
            badcase="builder copies stale convention or generic guidance into extra architecture",
            required_guardrails=(
                "Current requirement meaning and accepted design outrank stale conventions or generic guidance",
                "Reuse an existing capability when its semantics fit",
                "Do not add speculative infrastructure",
            ),
        ),
        PromptEvalCase(
            name="builder_places_named_facts_by_semantic_owner",
            surface=prompt,
            badcase="builder places stable domain facts under a convenient implementation class",
            required_guardrails=(
                "Place named facts and responsibilities with their semantic owner",
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
            badcase="implementation expands beyond the frozen Task result or silently changes accepted design",
            required_guardrails=(
                "the patch expands beyond the Task, implements later work, or silently changes accepted design",
                "where this task stops",
            ),
        ),
        PromptEvalCase(
            name="review_requires_concrete_failure",
            surface=prompt,
            badcase="reviewer emits a generic quality label without a failure or cost",
            required_guardrails=(
                "# Counterexample Method",
                "concrete input, state, scale, concurrency, failure, consumer, or maintenance scenario",
                "the wrong result or material cost",
                "the smallest useful correction",
            ),
        ),
        PromptEvalCase(
            name="review_rejects_generic_style_findings",
            surface=prompt,
            badcase="reviewer blocks equivalent local style or speculative hardening",
            required_guardrails=(
                "Equivalent local style, speculative hardening, generic clean-code preference, optional strengthening",
                "not findings",
                "There is no finding quota",
            ),
        ),
        PromptEvalCase(
            name="review_uses_attempt_scoped_diff_only",
            surface=prompt,
            badcase="reviewer treats full working-tree state or a Builder file list as the task change",
            required_guardrails=(
                "attempt-scoped diff from attempt start to that sealed revision",
                "Do not infer current-task changes from the full working tree, `git status`, a Builder file list",
            ),
        ),
        PromptEvalCase(
            name="review_blocks_invalid_review_object",
            surface=prompt,
            badcase="reviewer passes despite unavailable or mismatched scoped changes",
            required_guardrails=(
                "If the attempt-scoped diff is unavailable or does not match the supplied revision",
                "return `blocked` for review-object integrity",
                "blocked` only when the review object is unavailable, stale, or invalid",
                "decide workflow routing",
                "instead of reviewing another object",
            ),
        ),
        PromptEvalCase(
            name="review_falsifies_material_performance_cost",
            surface=prompt,
            badcase="reviewer misses looped queries or reports performance without a growth mechanism",
            required_guardrails=(
                "realistic input size causes N+1 queries, repeated traversal, duplicate I/O, unbounded work",
                "Use only lenses that can change the correctness or quality conclusion for this task",
            ),
        ),
        PromptEvalCase(
            name="review_checks_semantic_ownership_only_when_concrete",
            surface=prompt,
            badcase="reviewer misses duplicated stable facts or complains about ownership without consequence",
            required_guardrails=(
                "stable fact is placed under a temporary or incorrect owner",
                "making a concrete rule change inconsistent or duplicated",
            ),
        ),
    )

    for case in cases:
        _assert_guardrails(case)


def test_loom_do_skill_prompt_eval_bad_cases():
    prompt = _agent_rule("do")
    cases = (
        PromptEvalCase(
            name="skill_routes_lanes_to_quality_owners",
            surface=prompt,
            badcase="host treats every task as generic implementation plus verification",
            required_guardrails=(
                "Use the project `builder` Agent for `build` tasks",
                "project `verifier` Agent for `verify` tasks",
            ),
        ),
        PromptEvalCase(
            name="skill_keeps_local_choices_with_builder",
            surface=prompt,
            badcase="host asks the user about a reversible task-local implementation choice",
            required_guardrails=(
                "Local reversible choices remain with Builder",
                "Do not ask about task-local implementation choices",
            ),
        ),
        PromptEvalCase(
            name="skill_keeps_review_orchestration_out_of_builder",
            surface=prompt,
            badcase="builder invokes review or constructs runtime evidence itself",
            required_guardrails=(
                "Builder does not invoke Code Reviewer or manage runtime actions",
                "follow `extras.host_internal_flow`",
                "seal that exact attempt before review",
            ),
        ),
        PromptEvalCase(
            name="skill_never_falls_back_to_full_worktree_review",
            surface=prompt,
            badcase="host reviews full working-tree state when exact sealed review input is unavailable",
            required_guardrails=(
                "exact attempt-scoped diff",
                "`reviewer_handoff` returned from `seal-changes`",
                "never substitute a full-worktree diff, Builder file list, or stale seal",
            ),
        ),
        PromptEvalCase(
            name="skill_requires_fresh_review_after_changes",
            surface=prompt,
            badcase="host reuses an earlier pass after Builder changes the implementation",
            required_guardrails=(
                "On `changes_requested`",
                "seal again and invoke a fresh Code Reviewer for the new seal",
                "a prior review never approves a later seal revision",
            ),
        ),
        PromptEvalCase(
            name="skill_auto_recovers_internal_actions",
            surface=prompt,
            badcase="host exposes a retryable seal or completion action to the user",
            required_guardrails=(
                "Host-internal",
                "`host_recovery.user_visible` is false",
                "perform it automatically",
            ),
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
        "extras.lane",
        "extras.main_agent",
        "frozen `extras.task_packet`",
        "extras.host_internal_flow",
        "Builder owns complete, correct, performant, maintainable, readable, secure, reliable, and testable implementation",
        "Builder does not invoke Code Reviewer",
        "reviewer_handoff",
        "attempt-scoped diff",
        "action=record-review",
        "non-empty `review_summary`",
        "same Builder attempt",
        "fresh Code Reviewer",
        "complete the build attempt as `implemented`",
        "Build completion means the latest sealed implementation passed review",
        "Complete it as `verified` only when every material obligation is proved strongly enough",
        "verification_summary",
        "Do is serial",
        "`extras.skipped: true`",
        "`status: completing` with a persisted `completion_candidate_ref`",
        "run the supplied `host_recovery.command_args` without reconstructing",
        "`effect: local_implementation` with a valid Build `retry_task_id`",
        "call `action=retry` for that Build",
        "call `action=route`",
        "do not rerun or invalidate unrelated effective tasks",
        "status=<implemented|verified|failed|blocked>",
    ):
        assert expected in prompt


def test_verifier_prompt_eval_quality_and_result_semantics():
    verifier = _agent_prompt("verifier.md")

    for expected in (
        "verify-lane agent",
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


def test_core_agent_prompts_keep_stack_specific_verification_out_of_global_surfaces():
    surfaces = {
        "builder": _agent_prompt("builder.md"),
        "verifier": _agent_prompt("verifier.md"),
        "loom-do": _agent_rule("do"),
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

    assert "Run proportional local checks" in surfaces["builder"]
    assert "Do not create a broad harness" in surfaces["builder"]
    assert "selecting checks" in surfaces["verifier"]
    assert "broad runtime or integration harness" in surfaces["verifier"]
    assert "proportional checks" in surfaces["loom-do"]
    assert "preferred broad harness" in surfaces["loom-do"]

    for surface_name in ("builder", "verifier"):
        assert "temporary Claude Code child agent" not in surfaces[surface_name]

def test_coding_goal_prompt_guardrails_cover_bad_cases():
    builder = _agent_prompt("builder.md")
    reviewer = _agent_prompt("code-reviewer.md")
    verifier = _agent_prompt("verifier.md")
    release = _agent_prompt("release-analyzer.md")
    task_planner = _agent_prompt("task-planner.md")
    plan_architect = _agent_prompt("plan-architect.md")

    for expected in (
        "quality of one task-scoped implementation",
        "High quality is not a universal checklist",
        "behavior correctness, project fit, performance and resource cost, maintainability, readability",
        "Keep important business, data, state, transaction, query, and external-call flow visible",
        "query and traversal count",
        "Introduce a helper or abstraction only when it provides real reuse",
        "Place named facts and responsibilities with their semantic owner",
        "focused tests when they are the natural protection",
        "no known task-scoped correctness or material quality defect",
        "Do not claim independent review or full verification",
    ):
        assert expected in builder

    for expected in (
        "bounded, adversarial reviewer",
        "# Independent Baseline",
        "# Counterexample Method",
        "smallest relevant candidate-conforming scenario",
        "N+1 queries, repeated traversal, duplicate I/O, unbounded work",
        "There is no finding quota",
        "failure_scenario",
        "the wrong result or material cost",
        "Do not add a category merely to classify a finding",
    ):
        assert expected in reviewer

    for expected in (
        "Verification is behavior judgment, not evidence-field completion",
        "Do not broaden to the whole Plan or unrelated build tasks",
        "Choose the strongest useful path that the current project can support",
        "A pre-seeded intermediate state does not prove creation behavior",
        "retain narrower checks that still prove scoped facts",
        "`verified`: every material obligation",
        "`failed`: an actual observation contradicts required behavior",
        "`blocked`: one or more necessary obligations remain not verified",
        "conclusion: verified | failed | not_verified | not_applicable",
    ):
        assert expected in verifier

    for prompt in (builder, reviewer, verifier):
        for forbidden in ("Kernel", "SQLite", "runtime_refs", "temporary Claude Code child agent"):
            assert forbidden not in prompt


    for expected in (
        "Frozen Ship Packet as the current execution baseline",
        "what was delivered, what is actually proven",
        "Task completion is not proof",
        "Read only the smallest relevant part of `spec.md`, `plan.md`, or `tasks.md`",
        "Do not convert successful execution, completed tasks, compilation, static inspection",
        "Include SQL/data changes, configuration or switches, permissions, UI/menu changes",
        "A simple change does not acquire these concerns because a template names them",
        "Silence is not risk acceptance",
        "Release readiness: ready | blocked",
        "Goal result confidence: proven | partially_proven | not_proven",
        "effect: tasks",
        "Do not rerun verification, review code, change implementation",
        "You do not make the release owner's actual release decision",
    ):
        assert expected in release

    for forbidden in ("Kernel", "SQLite", "AskUserQuestion", "artifact registration", "Host"):
        assert forbidden not in release

    for expected in (
        "execution slicing recorded in `tasks.md`",
        "accepted Spec results and Plan design",
        "current-to-target implementation results",
        "coherent deliverable outcome",
        "A `build` task establishes one bounded implementation result",
        "A `verify` task proves a behavior, risk boundary, contract",
        "One verify task may cover several naturally related build tasks",
        "Inside the same captured block",
        "accepted result and selected design",
        "current responsibility and target landing when material",
        "Revision protects execution meaning, not Markdown wording",
        "Do not place execution-critical information only in later notes or maps",
        "never bump every task merely because an upstream artifact changed",
    ):
        assert expected in task_planner

    for expected in (
        "target business implementation model and its concrete landing",
        "required result, its primary scenarios",
        "smallest wrong or prohibited result",
        "authoritative, derived, attached, and external snapshot facts",
        "trigger and actor",
        "atomic local fact/state change",
        "current path and semantic owner",
        "reuse, extend, correct, replace, add, or preserve a real difference",
        "protected fact, invariant, or counterexample",
        "A technical surface is material when omitting it",
        "Keep all participating surfaces semantically aligned",
        "Verification design",
        "Produce a readable, self-evidencing `plan.md`",
    ):
        assert expected in plan_architect


def test_ship_host_uses_frozen_packet_and_internal_freshness_recovery():
    host_rule = _agent_rule("ship")

    for expected in (
        "ship_prerequisites_incomplete",
        "exact frozen `extras.ship_packet` and `extras.ship_input_hash`",
        "Task completion alone is not proof",
        "effect: spec | plan | tasks",
        "exact registration command carrying the original `ship_input_hash`",
        "Treat `ship_inputs_changed` as Host-internal freshness recovery",
        "Do not ask the user to repair workflow state",
        "does not require inventing another approval gate",
    ):
        assert expected in host_rule


def test_plan_reviewer_receives_identified_candidate_draft():
    architect = _agent_prompt("plan-architect.md")
    reviewer = _agent_prompt("plan-reviewer.md")
    host_rule = _agent_rule("plan")

    for expected in (
        "provided `plan.md` candidate",
        "Use the exact candidate text and its supplied identity",
        "If candidate text is absent, state the missing input and stop",
        "rather than inferring it from an on-disk artifact",
    ):
        assert expected in reviewer

    for expected in (
        "exact candidate",
        "draft identity",
        "readable commitment/design traceability",
        "only current-state evidence, not candidate review",
        "The Architect delivers an exact candidate",
    ):
        assert expected in host_rule

    assert "artifact_file" not in architect
    assert "draft identity" not in architect


def test_plan_host_delegation_keeps_child_evidence_bounded():
    architect = _agent_prompt("plan-architect.md")
    reviewer = _agent_prompt("plan-reviewer.md")
    host_rule = _agent_rule("plan")

    for expected in (
        "When an unconfirmed fact can change this stage's judgment, formulate one bounded question",
        "For `plan`, investigate only current models, callers, consumers, data/state writes",
        "The child agent returns only `question`, `observed facts`, `constraints or counterevidence`, `unknowns`, and `decision relevance`",
        "It must not write artifacts, modify files, ask the user, choose requirements or design, assign tasks, decide readiness, or decide workflow state",
        "`plan-architect` decides applicability and synthesizes the artifact",
        "A fact with a locatable repository, runtime, or external source is an evidence gap",
        "do not use an Owner question to acquire it",
        "Route an Owner question only after that investigation leaves incompatible directions",
        "Review the exact candidate through `plan-reviewer`",
        "Re-review only materially changed mechanisms and dependencies",
    ):
        assert expected in host_rule

    for expected in (
        "An unconfirmed fact with a locatable repository, runtime, or external source is an evidence gap",
        "Do not use an Owner decision to obtain a fact that can be investigated",
        "If that fact prevents a correct design, stop with the specific evidence needed",
        "Request one Owner decision only after investigating every locatable source that can distinguish the direction",
    ):
        assert expected in architect

    for prompt in (architect, reviewer):
        for forbidden in (
            "temporary Claude Code child agent",
            "artifact_file",
            "Kernel",
            "workflow state",
        ):
            assert forbidden not in prompt


def test_plan_prompts_select_analysis_models_for_material_relationships():
    architect = _agent_prompt("plan-architect.md")
    reviewer = _agent_prompt("plan-reviewer.md")

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
        "independently derived minimum design obligation",
        "smallest reasonable implementation that fully follows the candidate",
        "concrete failure scenario",
        "Require a concrete surface only when its absence",
    ):
        assert expected in reviewer
