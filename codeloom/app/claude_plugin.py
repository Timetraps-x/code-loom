from __future__ import annotations

from pathlib import Path

COMMANDS = {
    "adopt": {
        "description": "Create or revise CodeLoom .loom/constitution.md for this project.",
        "argument_hint": "optional adoption guidance",
    },
    "spec": {
        "description": "Create or revise CodeLoom spec.md for the current git branch.",
        "argument_hint": "requirement=<text> or revision_note=<text>",
    },
    "plan": {
        "description": "Create or revise CodeLoom plan.md for the current git branch.",
        "argument_hint": "constraints=<text> or revision_note=<text>",
    },
    "tasks": {
        "description": "Create or revise CodeLoom tasks.md for the current git branch.",
        "argument_hint": "preference=<text> or revision_note=<text>",
    },
    "do": {
        "description": "Run one CodeLoom build or verify task attempt for the current git branch.",
        "argument_hint": "task_id=T1",
    },
    "ship": {
        "description": "Generate CodeLoom release.md and readiness conclusion for the current git branch.",
        "argument_hint": "optional delivery note",
    },
}

STAGE_MAIN_AGENTS = {
    "spec": "spec-analyzer",
    "plan": "plan-architect",
    "tasks": "task-planner",
    "ship": "release-analyzer",
}

STAGE_REVIEWERS = {
    "spec": "spec-reviewer",
    "plan": "plan-reviewer",
    "tasks": "task-reviewer",
}

STAGE_RESPONSIBILITIES = {
    "spec": "requirement semantics",
    "plan": "system design",
    "tasks": "execution slicing",
    "ship": "delivery readiness",
}

STAGE_PROJECTIONS = {
    "spec": "what must be true in user/business terms",
    "plan": "how the system should represent and implement it safely",
    "tasks": "how the work should be sliced, ordered, and verified",
    "ship": "what has been proven, what remains risky, and how it should be shipped",
}


def bundled_claude_skill_contents() -> dict[str, str]:
    return {
        command: _skill_content(
            f"loom-{command}",
            command,
            metadata["description"],
            metadata["argument_hint"],
        )
        for command, metadata in COMMANDS.items()
    }


def install_claude_skills(repo_path: Path, force: bool = False) -> list[str]:
    skills_dir = repo_path.resolve() / ".claude" / "skills"
    written: list[str] = []

    for command, content in bundled_claude_skill_contents().items():
        written.extend(_write(skills_dir / f"loom-{command}" / "SKILL.md", content, force))

    return written


def _write(path: Path, content: str, force: bool) -> list[str]:
    if path.exists() and not force:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return [path.as_posix()]


def _skill_content(skill_name: str, command: str, description: str, argument_hint: str) -> str:
    if command == "adopt":
        return _adopt_skill_content(skill_name, description, argument_hint)
    argument_rule = _argument_rule(command)
    agent_rule = _agent_rule(command)
    content_rule = _content_rule(command)
    return f"""---
name: {skill_name}
description: {description}
argument-hint: {argument_hint}
user-invocable: true
disable-model-invocation: false
---

Run the CodeLoom `{command}` stage for the current project and current git branch.

User arguments are available as `$ARGUMENTS`. Convert them to `key=value` pairs when possible and pass them through as `--arg key=value`.

Use the shell appropriate for the current platform to execute the stage command at the point required by the rules below:

```text
loom stage {command} --branch <current-git-branch> [--arg key=value ...]
```

Rules:

- Get the current branch from the host git context.
- CodeLoom is a workflow harness over this host, not a replacement for Claude Code, Codex, or OpenCode.
- Do not decide CodeLoom workflow state in the skill body; Kernel owns workflow state and SQLite updates.
- If required user input is unclear, ask before running the command. For `spec`, do not write or register a final artifact while an unanswered Owner decision still changes requirement correctness; ordinary technical design choices route to Plan.
{agent_rule}
{content_rule}
{argument_rule}
- Report the returned KernelResponse status, message, recommended_next, recommended_task_id, artifact_paths, findings, and errors.
"""


def _adopt_skill_content(skill_name: str, description: str, argument_hint: str) -> str:
    return f"""---
name: {skill_name}
description: {description}
argument-hint: {argument_hint}
user-invocable: true
disable-model-invocation: false
---

Adopt stable project engineering guidance and the mechanical project profile discovered from the repository.

User arguments are available as `$ARGUMENTS`; use them as adoption guidance. `update-claude` requests a separate suggestion result and never authorizes editing `CLAUDE.md` unless the user also explicitly requests apply.

Rules:

- Read `.loom/project.yml` first. Use its configured `constitution.path`, existing `profile` values, and existing `commands`; do not assume `.loom/constitution.md` when another path is configured.
- Use the project Claude Code agent `adopt-expert` from `.claude/agents/adopt-expert.md` when available. Give it the adoption guidance and whether `update-claude` mode is active.
- Give the Agent `.loom/templates/constitution-template.md` as an optional section aid and only positive cases matching the repository's actual stacks. Positive cases are interpretation examples, not project evidence.
- Let `adopt-expert` own repository investigation, promotion judgment, constitution synthesis, and profile recommendations. Child-agent delegation is optional; absence of a delegation channel is not itself a blocker.
- If the Agent reports one material promotion, authority, or legacy conflict that repository evidence cannot decide, use AskUserQuestion for the highest-information Owner decision, then ask the Agent to resynthesize the affected result. Do not ask about locally verifiable facts or harmless omissions.
- Write only the returned constitution candidate to the exact configured constitution path. It must not retain the seed marker, template guidance, empty sections, project profile, commands, or `CLAUDE.md` suggestions.
- Treat the returned project profile independently. Update only evidence-backed `profile.languages`, `profile.frameworks`, `profile.modules`, and `commands.test|lint|typecheck|build` values in `.loom/project.yml`; preserve explicit existing values when the Agent has no evidence, and ask before replacing a materially conflicting explicit value.
- In default mode, do not emit or apply `CLAUDE.md` suggestions. In `update-claude` mode, display the Agent's bounded suggestions separately; never append them to the constitution and never edit `CLAUDE.md` without an explicit apply request.
- Do not create or edit branch artifacts such as `spec.md`, `plan.md`, `tasks.md`, or `release.md`.
- After writing the constitution and any profile patch, use the shell appropriate for the platform to execute `loom adopt --constitution <exact-configured-path>`.
- Report status, message, constitution path, seeded, current hash, registered hash, usable, profile changes, any separate `CLAUDE.md` suggestions, and errors.
"""


def _argument_rule(command: str) -> str:
    if command == "spec":
        return """- For the `spec` stage, never pass bare user text as an unnamed `--arg` and never invent unsupported keys such as `gap`.
- If `$ARGUMENTS` is bare text and no current `spec.md` exists, pass it as `--arg requirement=<text>`.
- If `$ARGUMENTS` is bare text and a current `spec.md` already exists, pass it as `--arg revision_note=<text>` so CodeLoom revises the existing spec.
- Preserve explicit `requirement=`, `revision_note=`, or `text=` keys when the user provides them. `artifact_file` is reserved for the canonical registration command returned by the Kernel handoff."""
    if command == "do":
        return "- For the `do` stage, convert a bare task id like `T2` to `--arg task_id=T2`."
    return ""


def _agent_rule(command: str) -> str:
    if command == "do":
        return """- For claude-code host runtime, do not run `loom stage do` as a one-shot execution command.
- Do is serial: never run two task Agents or attempts concurrently. Start only the Kernel-recommended task, or submit the requested `task_id` to the same eligibility check; an explicit id never bypasses `Depends on`, `Validates`, or an active attempt.
- Start with `loom stage do --branch <current-git-branch> --arg action=begin [--arg task_id=<task-id>] --json`. Treat the returned `extras.attempt_id`, `extras.lane`, `extras.main_agent`, frozen `extras.task_packet`, skip result, prerequisite blocker, and host-recovery data as authoritative.
- When begin returns `extras.skipped: true`, do not rerun that task. Continue from the returned recommendation. When it returns an existing attempt, recover that attempt's pending Host action; never invoke its task Agent a second time merely because begin was repeated. When it returns `status: completing` with a persisted `completion_candidate_ref`, run the supplied `host_recovery.command_args` without reconstructing or resubmitting the original completion fields.
- Give the frozen Task Packet to the selected Agent as the execution boundary. Let the Agent inspect the task-local code, callers, consumers, tests, state/data path, and nearby conventions needed for a high-quality judgment; do not require an evidence inventory.
- Read task-relevant `CLAUDE.md` guidance. Read the exact `extras.constitution.path` only when `extras.constitution.usable` is true, and only for task-relevant quality or stack guidance; otherwise continue from the frozen packet, current repository facts, and `extras.project_profile` without treating Adopt as a prerequisite. Read a specifically referenced Spec or Plan passage only when the packet is materially ambiguous or repository facts reveal a concrete conflict. Current requirement meaning and accepted design outrank stale guidance.
- Use the project `builder` Agent for `build` tasks and the project `verifier` Agent for `verify` tasks.
- Builder owns complete, correct, performant, maintainable, readable, secure, reliable, and testable implementation inside the Task boundary wherever those qualities are material. Local reversible choices remain with Builder; requirement, accepted-contract, design-mechanism, or Task-boundary conflicts are returned explicitly rather than guessed.
- Builder does not invoke Code Reviewer or manage runtime actions. After Builder returns an implemented result, follow `extras.host_internal_flow` and seal that exact attempt before review.
- Give Code Reviewer the frozen Task Packet, current `seal_revision`, and exact attempt-scoped diff identified by the `reviewer_handoff` returned from `seal-changes`; never substitute a full-worktree diff, Builder file list, or stale seal.
- Record each Reviewer verdict for that seal with `action=record-review`, the exact revision, and a non-empty `review_summary`.
- On `changes_requested`, return only material findings to the same Builder attempt. After a material revision, seal again and invoke a fresh Code Reviewer for the new seal; a prior review never approves a later seal revision. If Builder and Reviewer make no material progress on the same findings, stop repeating the loop and route the concrete unresolved boundary instead of manufacturing another seal.
- On review `pass`, complete the build attempt as `implemented`. Build completion means the latest sealed implementation passed review; it never means the behavior is fully verified.
- For a `verify` task, run Verifier on the frozen packet and the effective Build attempts named by its inputs. Verifier must use proportional checks and preserve narrower valid conclusions when a preferred broad harness is unavailable. Complete it as `verified` only when every material obligation is proved strongly enough, passing concise actual checks and observations through `verification_summary` or `verification_summary_file`.
- Complete Verify as `failed` when an observation contradicts required behavior, and as `blocked` when a necessary obligation remains not verified and cannot close in the current task.
- If Verifier returns `effect: local_implementation` with a valid Build `retry_task_id`, first complete the Verify attempt as `failed`, then call `action=retry` for that Build with `cause_attempt_id=<verify-attempt-id>` and the non-empty defect summary. Run only the Build attempt Kernel returns; its changed effective result mechanically invalidates real dependents and validators while independent effective tasks remain reusable.
- When Builder, Reviewer, or Verifier identifies a genuine `tasks`, `plan`, or `spec` boundary, terminally close the source attempt as appropriate and call `action=route` with its `attempt_id`, exact `target_stage`, and concise `reason`. Do not turn task-local implementation choices or unavailable preferred tooling into an upstream route.
- A Do continuation is scoped to its root task and affected relation closure. Follow the upstream recommendation for affected work, but do not rerun or invalidate unrelated effective tasks; an independent task may still proceed later through normal serial eligibility.
- Treat begin recovery, seal, record-review, stale reseal, repeated completion, and targeted retry as Host-internal. When `host_recovery.user_visible` is false, perform it automatically when possible rather than exposing it as a user step.
- Ask the user only for a remaining owner-bearing requirement, public/data contract, irreversible direction, or risk-acceptance decision. Do not ask about task-local implementation choices, missing ideal tooling, or recoverable internal actions.
- Submit an initial completion with `loom stage do --branch <current-git-branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=<implemented|verified|failed|blocked> --arg summary=<short-summary>`, adding the required verification summary for `verified`. A persisted `completing` recovery uses its supplied command instead.
"""

    agent_name = STAGE_MAIN_AGENTS.get(command)
    if not agent_name:
        return ""
    responsibility = STAGE_RESPONSIBILITIES[command]
    projection = STAGE_PROJECTIONS[command]
    return f"""- Use the project Claude Code agent `{agent_name}` from `.claude/agents/{agent_name}.md` as the stage main agent when available.
- Treat `{agent_name}` as the owner of this stage's {responsibility} analysis and artifact synthesis; Kernel remains responsible for registering artifact state.
- Shared iteration vocabulary may orient the analysis, but this stage must project it through `{projection}` rather than using a generic large rubric.
{_spec_agent_rule() if command == "spec" else _plan_agent_rule() if command == "plan" else _tasks_agent_rule() if command == "tasks" else _ship_agent_rule() if command == "ship" else ""}{_evidence_delegation_rule(command)}
{_reviewer_rule(command, agent_name)}
- If `{agent_name}` identifies owner-bearing uncertainty, use AskUserQuestion before running the Kernel stage; do not guess business semantics, risk acceptance, or long-term technical direction.
- If unblocked, write the ready clean Markdown artifact to the canonical `extras.artifact_path` returned by the Kernel handoff, then register it with `extras.register_command`."""


def _spec_agent_rule() -> str:
    return """- For `spec`, use `spec-analyzer` as the owner of requirement semantics; Kernel only registers the final artifact.
- Ground the current business or system reality in evidence before drafting, and do not default to journey order, the earliest step, a smallest CRUD slice, current/later/out, or a candidate implementation.
- Use `spec-reviewer` only for advisory review. The main agent owns evidence synthesis, whether clarification is needed, and every final requirement judgment.
- Use AskUserQuestion only after evidence leaves one owner-bearing requirement decision whose answer changes correctness. Ask one highest-information decision, absorb the answer, and revisit the affected requirement judgment before continuing.
- If such an Owner decision remains unresolved, do not write or register a final `spec.md`; keep the host conversation in clarification rather than guessing.
- After convergence, write only the clean user-readable artifact and register it through `artifact_file`. Goal, Way, and Proof are Agent reasoning responsibilities, not required Markdown headings or Kernel state.
"""

def _plan_agent_rule() -> str:
    return """- For `plan`, `plan-architect` owns system design that makes accepted `spec.md` commitments implementable in the current project. Accepted Spec supplies required and prohibited business results; project context supplies constraints, reuse evidence, and cost signals rather than target business truth.
- Design through commitment and minimal counterexample → targeted project evidence → selected implementation route → abstract model with shared/separate facts and variation axes → business mechanism with truth, invariants, ownership, state, and collaboration → necessary current-project projection → normal, blocked, and applicable recovery/duplicate scenario evidence. Do not map requirements or business nouns directly to a technology inventory.
- The final `plan.md` is complete only when a reader can trace each material commitment to a selected model, enforceable mechanism, necessary projection, and observable outcome—and trace each material table, API, UI, Job, state, or integration back to the truth or invariant it protects. Heading presence or technical vocabulary is not closure.
- Seek a common model only when lifecycle, responsibility, authority, or invariant is genuinely shared; represent real differences as explicit variation axes, policies, or attached facts. Split only when authority, lifecycle, permission, query/migration boundary, or non-coexisting facts require it. Avoid both one model per business noun and universal nullable records with scattered conditionals.
- Project data/schema/read paths, commands/APIs/Jobs, work surfaces/authorization, integration, transactions/concurrency/idempotency, migration/compatibility, performance, observability, and PlantUML only when the selected mechanism needs them to prevent a counterexample, support implementation, or avoid re-deciding a material semantic in Tasks/Do. Use actual project evidence where known; unknown material facts remain qualified recommendations, assumptions, evidence gaps, Owner routes, or blocked boundaries—not `N/A` or hidden deferral.
- Resolve local reversible choices as Architect recommendations. Use AskUserQuestion only when evidence and a reasonable recommendation cannot safely decide an independent external semantic, public/data-contract, irreversible, long-term, compliance, or risk-acceptance fork. Absorb each answer as new Plan input and re-derive the affected model, mechanism, projection, and scenarios; do not use fixed rounds.
- A project fact that changes the model, mechanism, material projection, or Owner route needs a compact inspectable evidence anchor. A fact with a locatable repository, runtime, or external source is an evidence gap: investigate or delegate it and state the specific evidence needed; do not use an Owner question to acquire it. Route an Owner question only after that investigation leaves incompatible directions that evidence and a reasonable recommendation cannot decide.
- The Architect delivers an exact candidate with readable commitment/design traceability; the host writes `artifact_file`; Kernel registers artifact revision and workflow state. Every material accepted commitment or readable scope must be traceable to a selected model, enforceable mechanism, necessary projection, evidence qualification, and scenario result. An unresolved material Owner decision is a clarification request, not a ready candidate.
- Review the exact candidate through `plan-reviewer`. Reconcile material counterexamples through causal revision, evidence-backed rejection, further evidence, or Owner/Spec routing; missing or mismatched identity permits only current-state evidence, not candidate review. Re-review only materially changed mechanisms and dependencies.
- Prefer completing evidence recovery and candidate revision in the current invocation. If no final Plan can be written, call `loom stage plan --branch <current-git-branch> --arg action=route --arg target_stage=<spec|plan> --arg reason=<compact-reason>`: use `spec` only for a missing requirement meaning and `plan` for unresolved evidence or design owned by Plan. This records a continuation route, not a blocking finding.
- Plan records accepted design and its scenario evidence, not task allocation, patches, commands, operational runbooks, release conclusions, or Kernel workflow details.
"""
def _tasks_agent_rule() -> str:
    return """- For `tasks`, `task-planner` owns the semantic translation from accepted Spec results and Plan design into an implementation result chain, coherent `build` slices, behavior/risk `verify` coverage, self-contained task packets, and packet-local Revision judgment.
- Before writing tasks, recover the selected Plan results, concrete landings, protected facts/invariants, current-to-target implementation results, shared prerequisites, independent results, integration windows, and natural verification windows. Do not project this reasoning as a fixed schema or a runtime graph.
- Slice `build` by coherent delivery result, inseparable contract/state/transaction/permission/migration/external-effect boundary, failure isolation, local stop, rollback boundary, and natural proof destination—not technical layer, file, class, or function. Slice `verify` by behavior, risk, contract, or regression surface; grouped verification may cover several builds without merging their results, stopping points, or ownership boundaries.
- Emit a task only when accepted Plan design already supplies the material result, boundary, credible current-project landing, protected invariant, and proof direction required for safe slicing. Verification proves established behavior; it must not investigate a fact whose answer changes the Plan mechanism, contract, external-effect safety, or build slicing.
- Put Task List items in Planner's recommended execution order. Dependencies, critical path, parallel tracks, integration windows, and coverage remain agent/human planning context only: Host and Kernel must not parse them as a dependency graph, runnable gate, or scheduler.
- Place every fact needed by a task consumer inside its captured checklist block after `Lane`, `Complexity`, and `Revision`: accepted design/result, material landing, authoritative state or fact, transition/concurrency/external-effect guard, local stop, and proof handoff when relevant. A generic Plan reference is traceability, not a substitute for this contract; later maps or Task Notes must not be its sole source.
- For a Tasks revision, compare the affected prior packet and attempt baseline before changing the smallest affected packets. Preserve unrelated IDs, titles, Revisions, attempts, and context. Revise a verify packet only when its covered behavior or proof obligation changes. Missing ideal/optional context is not a blocker; a necessary claim that remains unassessable after bounded inspection names the inspected scope and smallest recovery route. Reviewer output is advisory counterevidence, not a readiness gate.
- Prefer completing evidence recovery and packet revision in the current invocation. If no final Tasks artifact can be written, call `loom stage tasks --branch <current-git-branch> --arg action=route --arg target_stage=<plan|tasks> --arg reason=<compact-reason>`: use `plan` only when material design or design evidence is unresolved, and `tasks` for a bounded Tasks-owned continuation. Never encode that recovery as a research/build/verify task or blocking finding.
"""



def _ship_agent_rule() -> str:
    return """- For `ship`, run preflight only after Do has completed every current Build and Verify task. If Kernel returns `ship_prerequisites_incomplete`, do not draft `release.md`; follow the exact recommended Do task.
- Give `release-analyzer` the exact frozen `extras.ship_packet` and `extras.ship_input_hash`. Do not ask it to reconstruct attempts, verification, findings, or runtime refs from SQLite.
- Release Analyzer determines what was delivered, what is actually proven, material release impacts, risks, manual actions, owner decisions, rollback/monitoring needs, and the evidence-bounded readiness conclusion. Task completion alone is not proof of the intended result.
- If Release Analyzer returns a genuine upstream `effect: spec | plan | tasks`, call `loom stage ship --branch <current-git-branch> --arg action=route --arg target_stage=<effect> --arg reason=<compact-reason>` before writing a release artifact. Do not route routine deployment execution, release timing, ordinary approval, or risk acceptance upstream.
- Otherwise write only the clean `release.md` and execute the exact registration command carrying the original `ship_input_hash`.
- Treat `ship_inputs_changed` as Host-internal freshness recovery: discard the stale candidate, use the returned new packet and command, and rerun Release Analyzer. Do not ask the user to repair workflow state.
- Ask the user only when the release conclusion depends on an unresolved owner decision such as explicit risk acceptance or an irreversible external action. A normal release-owner decision to deploy remains outside Ship analysis and does not require inventing another approval gate.
"""


def _evidence_delegation_rule(command: str) -> str:
    scopes = {
        "spec": "business behavior, terms, states, data meaning, actors, dependencies, compatibility facts, and external domain rules that can change requirement meaning or acceptance",
        "plan": "current models, callers, consumers, data/state writes, contracts, work surfaces, migrations, tests, performance paths, and external technical or domain facts that can change the abstract model or concrete projection",
        "tasks": "accepted Spec commitments and Plan landing points, dependencies, constraints, and proof paths; existing tasks and attempt baselines for a revision; and named repository/artifact sources needed to recover a bounded execution fact. Unresolved requirement or design questions return upstream rather than becoming research tasks",
        "ship": "named artifact, runtime, attempt, verification, repository, or external release-constraint facts that can change an evidence-backed readiness claim",
    }
    scope = scopes.get(command)
    if scope is None:
        return ""
    return f"""- When an unconfirmed fact can change this stage's judgment, formulate one bounded question and delegate it to a temporary Claude Code child agent rather than loading broad exploration or research into the main session.
- For `{command}`, investigate only {scope}.
- The child agent returns only `question`, `observed facts`, `constraints or counterevidence`, `unknowns`, and `decision relevance` with locatable sources. It must not write artifacts, modify files, ask the user, choose requirements or design, assign tasks, decide readiness, or decide workflow state. `{STAGE_MAIN_AGENTS[command]}` decides applicability and synthesizes the artifact; a validation assumption cannot replace a fact that should have been investigated."""



def _reviewer_rule(command: str, agent_name: str) -> str:
    reviewer_name = STAGE_REVIEWERS.get(command)
    if not reviewer_name:
        return "- No separate reviewer agent is required for this stage; the stage main agent should self-check delivery risks."

    spec_reviewer_rule = (
        f"""- For `spec`, after `{agent_name}` drafts or outlines the artifact, use `{reviewer_name}` for advisory review. For a closed small correction, review only its current commitment, included/excluded boundary, authoritative facts, allowed/prohibited consequences, observable result, and unsupported expansion. For a complex demand, also review commitment coverage, source conflict, evidence gaps, reachable side effects, target-relevant scenarios, complete-chain links, and owner-bearing ambiguity.
- For `spec`, the reviewer returns evidence, uncertainty, impact, recommendation, and any question the main agent may need to route. It does not ask the user or decide readiness. The main agent reconciles material findings and revisits affected commitments, boundaries, conflicts, and Proof direction."""
        if command == "spec"
        else ""
    )
    tasks_reviewer_rule = (
        "\n- For `tasks`, advisory review must receive exact candidate text and candidate identity, plus the accepted design evidence needed for its scope. The reviewer reports the inspected identity; missing or mismatched identity permits only a missing-input response and current facts, not candidate findings. For a Revision claim, provide only the affected prior packet and attempt baseline."
        "\n- The reviewer independently recovers the minimum downstream consumer obligation, simulates Builder, Code Reviewer, or Verifier reading only the captured packet, and constructs the smallest candidate-conforming failure. It checks design re-decision, unsafe split/merge of an invariant or boundary, packet-external execution context, unsupported verify coverage, grouped-verify overreach, duplicate IDs, Revision locality, and unrelated-packet preservation. Missing ideal/optional input is non-blocking; `insufficient evidence` applies only to a necessary scoped claim after bounded inspection and names the inspected scope and recovery route."
        "\n- Planner reconciles material counterexamples through the smallest packet revision, evidence-backed rejection, evidence recovery, or upstream design routing. Re-review only a new exact candidate identity and affected packet/claim; reviewer silence, uncertainty, or non-material strengthening is not a readiness gate."
        if command == "tasks"
        else ""
    )
    plan_reviewer_rule = (
        "\n- For `plan`, advisory review must receive exact candidate text and draft identity, report the inspected identity, and return only current-state evidence when either is missing or mismatched. The reviewer treats on-disk `plan.md` as baseline evidence unless it is explicitly the same candidate. It tries to construct the smallest reasonable implementation that follows the candidate yet makes an accepted commitment unreachable, permits a prohibited result, loses material historical truth, bypasses a gate, recovers unsafely, or pushes a material semantic to Tasks/Do. It attacks commitment→model, model→mechanism, mechanism→projection, projection→outcome, and scenario evidence; it requires a concrete data/API/UI/integration/migration/concurrency/proof projection only when its absence enables that counterexample. It must not review headings or a universal field checklist. A material `implementation-design-gap` includes exact candidate passage, protected commitment/invariant, smallest counterexample, break location, evidence/uncertainty, and smallest Architect handling path. It also checks false merge/split, unsupported project facts, undispositioned commitments, unsupported `covered` claims, and artifact-boundary leakage. Equivalent local forms, naming, layout, or untouched technical surfaces are non-blocking strengthening. Review is a diagnostic delta, not a replacement candidate or readiness decision."
        if command == "plan"
        else ""
    )
    return f"""{spec_reviewer_rule}
- After `{agent_name}` drafts or outlines the artifact, use the project Claude Code agent `{reviewer_name}` from `.claude/agents/{reviewer_name}.md` for advisory review when available.
- Treat `{reviewer_name}` as advisory only: it returns evidence-backed counterexamples, uncertainty, impact, and the smallest handling path. It must not write artifacts, ask the user, decide requirement meaning, approve/reject the stage, or decide workflow state.
- Review whether a material factual conclusion lacks a locatable project or external basis, or whether an unresolved upstream requirement/design issue was pushed into a later stage. Return the missing evidence and affected record; do not replace the stage main agent with broad research or a competing artifact.
- Before writing the final clean artifact, `{agent_name}` must reconcile every material reviewer finding through revision, evidence-backed rejection, owner routing, handoff to Plan, or an explanation that it cannot affect requirement correctness. For `plan`, non-blocking strengthening may be adopted, retained as a constraint, or rejected with reason; it must not become an Owner decision or replace the selected design narrative.{plan_reviewer_rule}{tasks_reviewer_rule}
"""


def _content_rule(command: str) -> str:
    if command not in {"spec", "plan", "tasks", "ship"}:
        return ""
    task_format_rule = ""
    semantic_reference_rule = ""
    if command == "spec":
        semantic_reference_rule = (
            "\n- For a complex Spec, use a readable commitment label only when it helps downstream navigation. Labels are optional and must not create an ID, schema, or cross-revision lineage requirement."
        )
    elif command == "plan":
        semantic_reference_rule = (
            "\n- Keep `based_on_spec_hash` as actual whole-artifact provenance when available, and make every material Spec commitment or readable scope traceable to a selected model, enforceable mechanism, necessary project projection, evidence qualification, and scenario result—not a requirements mapping or a technical-surface inventory."
            "\n- For `plan`, treat `commitment → model → mechanism → current-project projection → observable outcome` as the delivery contract. The template is flexible: omit untouched technical surfaces and combine headings when clarity improves, but do not leave a material semantic for Tasks/Do to decide. A table, API, UI, Job, or desired result is insufficient until it states the truth, invariant, or mechanism it protects; a current-project projection is required only where its absence permits a concrete counterexample or blocks implementation."
        )
    task_format_rule = ""
    template_name = "release-template.md" if command == "ship" else f"{command}-template.md"
    if command == "tasks":
        task_format_rule = (
            "\n- Executable tasks must be build or verify tasks only; do not create `Tn` items for lanes other than `build` or `verify`."
            "\n- Every executable task line must include immediate metadata: `Lane`, `Complexity`, and `Revision`. New tasks start at `Revision: 1`."
            "\n- Before slicing, trace selected Spec commitments to their Plan abstract/concrete design records and form an implementation path of stage-level results, shared prerequisites, critical path, parallel tracks, integration windows, and verification windows. These are Planner semantics, not a Kernel graph or scheduling contract."
            "\n- Put Task List items in Planner's recommended order. Describe dependencies, parallelism, integration, coverage, and critical path only as agent/human context; Host and Kernel must not parse or gate on that prose."
            "\n- Each task block must contain the execution-critical context that `/loom:do` needs: relevant commitment/design trace, target result, direction or confirmed landing fact when needed, guards/out-of-scope/stop, and proof handoff. Do not put required context only in later Task Notes, Delivery Maps, or Execution Order."
            "\n- When updating an existing `tasks.md`, Planner and Reviewer compare task packets and preserve a task's `Revision` unless commitment/design trace, execution boundary, done criteria, verification coverage, lane, material proof surface, invariant/contract/risk, or implementation-before/after relation changed. New tasks start at `Revision: 1`."
            "\n- Do not bump `Revision` for wording, formatting, links, evidence prose, or non-semantic inline/later context updates; never automatically bump all tasks after upstream drift."
            "\n- Build tasks need boundaries, local completion boundaries, and verification coverage, but they do not each need independent functional verification."
            "\n- Every build task must have a clear verification owner or grouped verify task."
            "\n- Verify tasks may cover multiple naturally related build tasks and must name the covered tasks, risks, required counterexamples/regression surfaces, and expected evidence."
            "\n- Do not copy large plan sections into tasks or micromanage function names, local variables, or line-level edits."
            "\n- Extract enough execution context from plan design facts that builder, code-reviewer, and verifier can execute or review the current task without rereading the whole plan."
            "\n- Only a fact necessary to define safe slicing may require clarification or a bounded `insufficient evidence` result after available evidence recovery; keep non-blocking constraints, risk notes, and validation notes in task context."
            "\n- Task-local context is opaque to Kernel after the immediate metadata. It must not become dependency parsing, a runnable gate, a task graph, or extra runtime metadata."
            "\n- When the request includes platform validation, independent artifact review, or eval/prompt tuning beside a product change, keep business build tasks bounded to the product change and place only do-stage verification needs in verify task evidence;"
            " leave unrelated follow-up outside `tasks.md`."
            "\n- Before creating a parseable task, confirm that accepted Plan design supplies the material result, concrete landing, clear boundary, protected invariant, and proof direction required for safe slicing. Route a missing material design decision or evidence-backed design blocker upstream; never encode it as build/verify tasks or Do fact gathering."
            "\n- Every `Tn` ID must be unique within the artifact and retain its identity across revisions. Do not reuse or duplicate an ID because of reordering or title polish."
            "\n- For a revision, compare available prior `tasks.md`, ID/title/Revision values, and attempt baseline before judging a task packet. If a necessary baseline remains unavailable after bounded inspection, report `insufficient evidence` only for that concrete Revision claim with inspected scope and a smallest recovery route; do not make it a gate for unaffected tasks."
            "\n- Do not change an existing task title for wording, formatting, links, evidence prose, or non-semantic context edits; preserve its Revision too. A material execution-contract change retains the ID, updates the title only when needed, and increments Revision."
            "\n- Recover accepted artifact, existing task/attempt, and named-source evidence before blocking or escalating. Ideal/optional documentation, a preferred harness, and ordinary local details are not blockers; proceed with the supported task slice and record a bounded limitation only when useful."
            "\n- Report `insufficient evidence` only for a concrete necessary claim that remains unassessable after bounded inspection; state its inspected scope and smallest recovery route. Do not emit research/scout/discovery tasks."
            "\n- For a revision, change only directly affected task packets and verify packets whose coverage obligation changes. Preserve unrelated IDs, titles, Revisions, attempts, and task-local context; Reviewer counterevidence is advisory, never a readiness gate."
            "\n- The artifact must contain parseable task lines exactly like `- [ ] T1: <task title>`. Do not use only section headings for tasks."
        )
    return f"""- Before drafting, run the stage command once without `artifact_file`, preserve applicable user stage arguments, and request JSON:

```text
loom stage {command} --branch <current-git-branch> [--arg key=value ...] --json
```

- Treat `status=noop` with `extras.handoff=author_artifact` as the normal host-authoring handoff, not a failure or a completed stage. Use its exact `extras.artifact_path`, `extras.register_command`, `extras.main_agent`, and `extras.reviewer_agent` values for this invocation.
- If the preflight response does not contain that handoff—for example, because a prerequisite is missing or a continuation route redirects the stage—do not draft or register a downstream artifact. Report the returned response and follow its single `recommended_next`.
- Before drafting, read `.loom/project.yml` and use `specs.language` as the prose language of the artifact at `extras.artifact_path`; default to English (`en`) when it is missing or unclear.
- Before drafting, read `.loom/templates/{template_name}` if it exists and use it as a flexible projection aid for the Markdown artifact, not a mandatory checklist or semantic schema.
- The template may suggest organization, but `.loom/project.yml` `specs.language` controls the artifact's prose language. Omit irrelevant sections and prefer the stage main agent's semantic judgment over heading completion.
- Use `extras.project_profile` as the mechanical language/framework/module/command context supplied by the project configuration.
- Read the exact `extras.constitution.path` only when `extras.constitution.usable` is true, and only sections relevant to this stage's output quality, stack guidance, and evidence behavior. When it is false, continue from repository facts, `CLAUDE.md`, current requirements, accepted artifacts, and the project profile; do not turn Adopt into a prerequisite.
- Treat a usable constitution as the project rulebook / quality baseline; it is not workflow state, runtime evidence, approval, requirement authority, or a substitute for current repository facts.
- Current requirement semantics and accepted artifact design outrank constitution guidance when they conflict; even a registered baseline can be lower-quality for legacy cleanup or architecture upgrade work.
- Constitution guidance must not expand the current branch artifact boundary or override current requirement semantics, current user instructions, platform hard constraints, current repository facts, accepted artifact design, or host-native project rules.
- Do not copy constitution text into the artifact; compress only relevant constraints into the stage analysis.
- Separate product or business delivery scope from platform validation scope; artifact review, real-flow validation, and prompt/eval tuning notes must not authorize extra product changes or appear as product artifact content unless the current requirement explicitly changes CodeLoom.
- Before writing the artifact, apply the stage main agent's Artifact Boundary Gate: write only artifact-owned content, and keep branch/session state, workflow mechanics, platform feedback routing, prompt/eval tuning, and runtime control details out of the Markdown.
- Artifact factual claims must be backed by current source, repository evidence, runtime evidence, or recorded attempt evidence. When a material project or external fact should be investigated, do not relabel its absence as a validation assumption; investigate it through the stage owner's temporary child-agent boundary. Mark only residual unsupported claims as risks or not verified.
- If the template is missing, draft a stage-appropriate Markdown artifact without blocking the Kernel.
- Use the current host model and the stage main agent named by the handoff to draft the Markdown artifact after preflight and before registration.
- The artifact file must contain only user-facing Markdown. Do not include agent output contracts, process notes, execution rules, `result_type`, internal workflow/control metadata, branch/session facts, platform feedback routing, prompt/eval tuning notes, or SQLite/runtime instructions inside the Markdown.
- Write the artifact directly to the exact repository-relative `extras.artifact_path`; create only its parent directory when absent, and do not create a parallel temporary copy.
- After the exact artifact is ready and reviewer findings are reconciled, execute the exact `extras.register_command` returned by the same handoff. Do not reconstruct the artifact path or registration command from branch names, default directories, or template names.{task_format_rule}{semantic_reference_rule}"""
