from __future__ import annotations

from importlib import resources
from pathlib import Path, PurePosixPath

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

STAGE_MAIN_ROLES = {
    "spec": "spec-analyzer",
    "plan": "plan-architect",
    "tasks": "task-planner",
    "ship": "release-analyzer",
}

SKILL_ROLE_FILES = {
    "spec": {"references/main-role.md": "spec-analyzer.md"},
    "plan": {"references/main-role.md": "plan-architect.md"},
    "tasks": {"references/main-role.md": "task-planner.md"},
    "do": {
        "references/builder-role.md": "builder.md",
        "references/verifier-role.md": "verifier.md",
    },
    "ship": {"references/main-role.md": "release-analyzer.md"},
}

STAGE_REVIEWERS = {
    "spec": "spec-reviewer",
    "plan": "plan-reviewer",
    "tasks": "task-reviewer",
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


def bundled_claude_skill_resources() -> dict[PurePosixPath, str]:
    skill_contents = bundled_claude_skill_contents()
    role_files = resources.files("codeloom.roles")
    bundled = {
        PurePosixPath(f"loom-{command}") / "SKILL.md": content
        for command, content in skill_contents.items()
    }
    for command, files in SKILL_ROLE_FILES.items():
        for relative_path, role_file in files.items():
            bundled[PurePosixPath(f"loom-{command}") / relative_path] = role_files.joinpath(role_file).read_text(
                encoding="utf-8"
            )
    return bundled


def install_claude_skills(repo_path: Path, force: bool = False) -> list[str]:
    root = repo_path.resolve()
    skills_dir = root / ".claude" / "skills"
    written: list[str] = []

    for relative_path, content in bundled_claude_skill_resources().items():
        written.extend(_write(skills_dir.joinpath(*relative_path.parts), content, force, root))

    return written


def _write(path: Path, content: str, force: bool, root: Path) -> list[str]:
    if path.is_symlink():
        raise ValueError("Claude Code Skill resource cannot be a symbolic link")
    current = root
    for part in path.parent.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Claude Code Skill resource parent cannot be a symbolic link")
    resolved_parent = path.parent.resolve()
    if root != resolved_parent and root not in resolved_parent.parents:
        raise ValueError("Claude Code Skill resource path escapes repository")
    if path.exists():
        if not path.is_file():
            raise ValueError("Claude Code Skill resource must be a regular file")
        if not force:
            return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return [path.as_posix()]


def _skill_content(skill_name: str, command: str, description: str, argument_hint: str) -> str:
    if command == "adopt":
        return _adopt_skill_content(skill_name, description, argument_hint)
    argument_rule = _argument_rule(command)
    main_role_rule = _main_role_rule(command)
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
- Ask before preflight only when the command or its arguments cannot be interpreted safely. Artifact semantics, evidence gaps, and technical direction belong to the loaded Main Role: run preflight, load that role, investigate available evidence, and use its clarification gate rather than a generic `unclear input` rule.
{main_role_rule}
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

User arguments are available as `$ARGUMENTS`; pass them as adoption guidance, including whether `update-claude` mode is active.

Rules:

- Read `.loom/project.yml` first. Use its configured `constitution.path` for writing and registration, and retain the current `profile` values and `commands` as context.
- Use the project Claude Code agent `adopt-expert` from `.claude/agents/adopt-expert.md` when available; otherwise read that role and carry out its work directly. Supply the adoption guidance, configured path, current profile/commands, and mode. Let it own repository investigation, promotion judgment, constitution synthesis, and profile recommendations.
- Make `.loom/templates/constitution-template.md` available as an optional section aid. Let the Agent select positive cases matching the repository's actual stacks as investigation aids.
- If a material promotion, authority, or legacy conflict remains after investigation, use AskUserQuestion to present the viable options, the Agent's recommendation and reasons, and the affected rule or profile field. Obtain the highest-information Owner decision, then resynthesize the affected result and continue using that decision.
- Write only the returned constitution candidate to the exact configured constitution path. Check that its Markdown contains project rules and has cleared the seed marker, template guidance, and empty sections; verify that profile values, commands, and suggestions stay in their separate outputs.
- Treat the returned project profile independently. Update only evidence-backed `profile.languages`, `profile.frameworks`, `profile.modules`, and `commands.test|lint|typecheck|build` values in `.loom/project.yml`; preserve explicit existing values when the Agent has no evidence, and ask before replacing a materially conflicting explicit value.
- Preserve `git.repositories` unchanged; `loom init` owns repository scope configuration.
- Keep `CLAUDE.md` suggestions inactive in default mode. In `update-claude` mode, display the returned suggestions separately from the constitution. Editing `CLAUDE.md` requires an explicit apply request from the user.
- Leave branch artifacts such as `spec.md`, `plan.md`, `tasks.md`, and `release.md` unchanged.
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


def _main_role_rule(command: str) -> str:
    if command == "do":
        return """- For claude-code host runtime, do not run `loom stage do` as a one-shot execution command.
- Do is serial: never run two task attempts concurrently. Start only the Kernel-recommended task, or submit the requested `task_id` to the same eligibility check; an explicit id never bypasses `Depends on`, `Validates`, or an active attempt.
- Start with `loom stage do --branch <current-git-branch> --arg action=begin [--arg task_id=<task-id>] --json`. Treat the returned `extras.attempt_id`, `extras.lane`, `extras.main_role`, frozen `extras.task_packet`, skip result, prerequisite blocker, and host-recovery data as authoritative.
- When begin returns `extras.skipped: true`, do not rerun that task. Continue from the returned recommendation. When it returns an existing attempt, recover that attempt's pending Host action from its frozen `extras.task_packet` and supplied sealed evidence; never reconstruct it from the current `tasks.md`. Small execution records and conclusions live in SQLite and are supplied by the Host handoff, not standalone JSON files. Use the returned inline `sealed_changes` with the sealed diff command for review. When `status: completing` supplies `host_recovery.internal_action: resume_complete`, run its `command_args` without reconstructing or resubmitting the original completion fields.
- Treat `task_packet_integrity_error` as a blocked recovery with preserved evidence. Report its exact `extras.unlock_command`; do not replace the packet from current Tasks and do not invoke unlock automatically.
- Execute the frozen Task Packet directly in the current Main. For `extras.main_role=builder`, first read `references/builder-role.md`; for `extras.main_role=verifier`, first read `references/verifier-role.md`. Reject any other `main_role`. Do not invoke Builder or Verifier as a subagent.
- Let the current Main inspect the task-local code and evidence required by the loaded role. Read task-relevant `CLAUDE.md` guidance. Read the exact `extras.constitution.path` only when `extras.constitution.usable` is true and only for task-relevant quality or stack guidance; otherwise continue from the frozen packet, current repository facts, and `extras.project_profile` without treating Adopt as a prerequisite. Read relevant Spec or Plan passages when needed to understand or check the task's accepted design, resolve material ambiguity, or investigate a concrete conflict. Current requirement meaning and accepted design outrank stale guidance.
- The current Main applies the Builder role's method for handling findings; it does not replace the independent Code Reviewer or manage review state. After the `builder` role produces an implemented result, follow `extras.host_internal_flow` and seal that exact attempt before invoking Code Reviewer.
- Give Code Reviewer the frozen Task Packet, current `seal_revision`, and exact attempt-scoped diff identified by the `reviewer_handoff` returned from `seal-changes` to compare the actual code with the task's accepted design; never substitute a full-worktree diff, a self-reported file list, or a stale seal.
- Record each Reviewer verdict for that seal with `action=record-review`, the exact revision, and a non-empty `review_summary`. When new evidence or restored review access changes a judgment with unchanged code, invoke a fresh Code Reviewer for the same seal, supplying the changed evidence and prior finding dispositions. Append that re-review using `supersedes_review_id=<prior-review-record-id>` from the review being reconsidered; the Host preserves its history. If that identity is stale, recover the latest recorded review and reassess the affected judgment before submitting again.
- On `changes_requested`, the current Main handles only material findings in the same Build attempt using the Builder role's guidance. After a material revision, seal again and invoke a fresh Code Reviewer for the new seal; a prior review never approves a later seal revision. If no material progress occurs on the same findings, investigate the concrete obstacle before repeating the loop. Route only a genuine upstream meaning gap under the routing rule below; otherwise continue a supported task-local repair, or close the attempt as failed or blocked with the unresolved obstacle when it cannot proceed.
- For re-review, supply the frozen Packet, prior and new seal identities, prior verdict and review_summary, material findings, Builder dispositions, changed evidence, and actual changed hunks or a trustworthy seal-to-seal delta from available sealed evidence. Cover finding closure, obligations affected by code or evidence changes, and necessary review left unfinished; reuse completed review only while its code and premises still apply. If a trustworthy delta or prior review coverage is unavailable, request a full review of the current sealed attempt-scoped object; do not reconstruct a delta from the working tree or self-reported changes, invent missing evidence fields, or reuse the prior verdict.
- On review `pass`, complete the build attempt as `implemented`, recording that the latest sealed implementation passed review.
- In the `verifier` role, take the full verification context and obligations from its own frozen Tasks packet, and independently check the effective Build attempts named by its inputs. Use Builder summaries and review findings to locate relevant changes, then judge each packet obligation through actual checks. Complete it as `verified` only with concise actual checks and observations in `verification_summary` or `verification_summary_file`.
- Otherwise use the loaded role's `failed` or `blocked` conclusion without inventing stronger evidence.
- If Verify returns `effect: local_implementation` with a valid Build `retry_task_id`, first complete the Verify attempt as `failed`, then call `action=retry` for that Build with `cause_attempt_id=<verify-attempt-id>` and the non-empty defect summary. Run only the Build attempt Kernel returns; its changed effective result mechanically invalidates real dependents and validators while independent effective tasks remain reusable.
- When the current Main or Code Reviewer identifies a genuine `tasks`, `plan`, or `spec` boundary, terminally close the source attempt as appropriate and call `action=route` with its `attempt_id`, exact `target_stage`, and concise `reason`. Do not turn task-local implementation choices or unavailable preferred tooling into an upstream route.
- A Do continuation is scoped to its root task and affected relation closure. Follow the upstream recommendation for affected work, but do not rerun or invalidate unrelated effective tasks; an independent task may still proceed later through normal serial eligibility.
- Treat begin recovery, seal, record-review, stale reseal, repeated completion, and targeted retry as Host-internal. When `host_recovery.user_visible` is false, perform it automatically when possible rather than exposing it as a user step.
- `action=unlock` is user-only recovery and must never run automatically. Without `status`, it only releases the mechanical block, leaves the attempt non-successful, and preserves packet, completion candidate, seal, review, finding, verification, and runtime evidence.
- When the user explicitly states that they completed the blocked task themselves and asks to unblock its dependents, submit `action=unlock` with the exact `attempt_id`, `status=implemented` for Build or `status=verified` for Verify, and a concise `summary`. This records the user's manual completion assertion, preserves existing evidence, and may satisfy downstream dependency eligibility.
- After either unlock form, submit later Do work normally. Manual completion does not repair stale registered lineage, change task identity, or bypass any other dependency.
- Resolve locatable facts and supported inferences first. Ask the user only for a remaining owner-bearing requirement, public/data contract, irreversible direction, or risk-acceptance decision. Apply the answer and continue within the accepted task; if it changes upstream meaning, use the existing route. Do not ask about task-local implementation choices, missing ideal tooling, or recoverable internal actions.
- Submit an initial completion with `loom stage do --branch <current-git-branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=<implemented|verified|failed|blocked> --arg summary=<short-summary>`, adding the required verification summary for `verified`. A persisted `completing` recovery uses its supplied command instead.
"""

    role_name = STAGE_MAIN_ROLES.get(command)
    if not role_name:
        return ""
    clarification_rule = "- When the loaded role concludes that its own clarification gate is met, use AskUserQuestion before registration. Otherwise continue under that role's evidence and decision rules; an investigable fact or ordinary reversible technical choice is not owner-bearing merely because it is unclear."
    if command == "spec":
        clarification_rule += " Ask the concrete resolving question rather than only returning a blocker summary. Wait for the user's answer before treating the choice as settled; silence, tool failure, or a recommendation is not an answer. On resumption, apply the reply under the loaded role, use evidence or supported inference to resolve remaining gaps, and update the candidate before review or registration. Once resolved, continue the existing authoring, review, and registration flow. Independent settled work may continue; do not register a complete Spec while a material requirement choice remains unresolved."
    return f"""- Treat `extras.main_role={role_name}` as the current Main's role for this stage; Kernel remains responsible for registering artifact state.
- Before stage-owned analysis or synthesis, read `references/main-role.md` and apply it in the current Main conversation. Do not invoke `{role_name}` as a Claude Code Agent or delegate stage ownership to a subagent.
- The current Main owns this stage's semantic analysis, evidence applicability, user clarification, artifact candidate, reviewer-finding disposition, and final artifact synthesis.
{_evidence_delegation_rule(command)}
{_reviewer_rule(command, role_name)}
{clarification_rule}
- If unblocked, write the ready clean Markdown artifact to the canonical `extras.artifact_path` returned by the Kernel handoff, then register it with `extras.register_command`."""




def _evidence_delegation_rule(command: str) -> str:
    if command not in STAGE_MAIN_ROLES:
        return ""
    return f"""- When the loaded `{STAGE_MAIN_ROLES[command]}` role identifies one unconfirmed fact that can change a named stage judgment, it may delegate that one bounded question to a temporary Claude Code child agent.
- Give the child agent the exact question, smallest relevant scope, explicit exclusions, and requested fact/evidence output. Stop when the smallest discriminating evidence is found; do not delegate a subsystem inventory.
- The child agent returns observed facts, source and applicability, counterevidence, remaining unknowns, and decision relevance. It must not write artifacts, modify files, ask the user, choose requirements or design, assign tasks, decide readiness, or decide workflow state. The current Main decides applicability and synthesis."""



def _reviewer_rule(command: str, role_name: str) -> str:
    reviewer_name = STAGE_REVIEWERS.get(command)
    if not reviewer_name:
        return "- No separate reviewer agent is required for this stage; the current Main performs the self-check required by the loaded role."
    candidate_identity = "form a review identity from the handoff input identity (`extras.input_token` when present, otherwise `extras.input_snapshot`) plus that candidate hash."
    review_context = "relevant accepted upstream properties"
    if command == "plan":
        review_context = "the original accepted Spec body or its accessible verified path, its registration identity from `extras.input_snapshot.upstream.spec`, and relevant accepted upstream properties"
    if command == "tasks":
        review_context += ", and, for affected revisions, prior task packets, declared dependency/coverage relations, and relevant attempt evidence"
    rereview_handoff = "after a material revision, supply the previous and new identities, actual changed passages or packets, prior material findings, their Main Role dispositions, and affected semantic dependencies. Review finding closure and that delta. If a trustworthy delta is unavailable, run a new full review of the bounded object."
    repeat_boundary = "Repeat review only when material candidate progress leaves a judgment that needs review."
    if command == "spec":
        candidate_identity = "use that candidate hash to identify the exact text under review."
        review_context = "the current demand and accepted business and technical properties"
        rereview_handoff = "when Main judges another review useful after material text, demand, applicable decision, or evidence changes, supply the previous and new identities, actual text delta (which may be empty), material input changes, prior findings, Main dispositions, and affected judgments. Review finding closure and the affected scope. Reassess prior findings where a changed premise affects their applicability, including with unchanged candidate text. If a trustworthy change scope is unavailable, run a new full review of the bounded object."
        repeat_boundary = "Repeat review only when material text changes or changes to the demand, applicable decisions, or evidence leave an affected judgment that needs review."
    elif command in {"plan", "tasks"}:
        rereview_handoff = "when Main judges another review useful after material text, applicable decision, or evidence changes, supply the previous and new identities, actual text delta (which may be empty), material evidence or decision changes, prior findings, Main dispositions, and affected semantic dependencies. Review finding closure and the affected scope. Reassess prior findings where a changed premise affects their applicability, including with unchanged candidate text. If a trustworthy change scope is unavailable, run a new full review of the bounded object."
        repeat_boundary = "Repeat review only when material text changes or changes to applicable decisions or evidence leave an affected judgment that needs review."
    return f"""- **Candidate handoff:** after the current Main drafts the exact candidate, compute its SHA-256 and {candidate_identity}
- Invoke `{reviewer_name}` from `.claude/agents/{reviewer_name}.md` for advisory review. Supply the exact candidate body or hash-checked canonical working copy, the review identity, {review_context}, confirmed project facts and anchors, applicable Owner corrections or decisions, and a bounded review scope.
- If candidate text or identity is absent or mismatched, accept only `input_missing_or_mismatched`; do not let the reviewer infer another candidate from disk.
- **Main disposition:** the current Main owns applicability, adoption, remedy, and readiness under the loaded role's decision and upstream-return rules. Evaluate findings against the accepted obligations and applicable evidence, and decide whether to adopt, adapt or decline each finding. Apply adopted corrections, retain a concise basis for material dispositions, and carry settled dispositions forward while their premises apply. A supported decision to decline a finding completes its disposition. Preserve material findings and dispositions for any re-review.
- **Re-review handoff:** {rereview_handoff}
- **Closure:** {repeat_boundary} Main resolves remaining questions under the loaded role and delivers once its completion conditions are satisfied."""


def _content_rule(command: str) -> str:
    if command not in {"spec", "plan", "tasks", "ship"}:
        return ""
    template_name = {
        "spec": "spec-template.md",
        "plan": "plan-template.md",
        "tasks": "tasks-template.md",
        "ship": "release-template.md",
    }[command]
    task_format_rule = ""
    semantic_reference_rule = ""
    investigation_rule = "investigate it through the stage owner's temporary child-agent boundary."
    if command in {"spec", "plan", "tasks"}:
        investigation_rule = "the current Main investigates it directly or delegates a bounded factual question under the evidence-delegation rule. A short check in a known source can be done directly; delegation is optional."
    if command == "spec":
        semantic_reference_rule = (
            "\n- For a complex Spec, use a readable commitment label only when it improves human navigation. Labels are optional and must not create a fixed ID, schema, or cross-revision lineage requirement."
        )
    elif command == "plan":
        semantic_reference_rule = (
            "\n- Read the complete accepted `spec.md` beside the canonical Plan path in `extras.artifact_path`. This uses the configured artifact directory and branch slug already resolved by Kernel. Verify its UTF-8 text SHA-256 against `extras.input_snapshot.upstream.spec.content_hash`, using universal newline normalization as the Markdown store does. If the source is missing or differs, refresh preflight and reconcile the authoritative input before dependent design work."
            "\n- Carry the verified Spec source and registration identity, applicable user decisions and current project evidence into Plan review. Supply the decision text and its scope, including a replacement decision when one changes; summaries guide access to the original basis. Retain sound existing design when resuming and apply changed premises to the affected route and consumers."
            "\n- Keep `based_on_spec_hash` as actual whole-artifact provenance when available; semantic traceability remains readable Artifact content owned by the Plan role, not a parsed mapping contract."
        )
    if command == "tasks":
        task_format_rule = (
            "\n- Executable task lines must be parseable as `- [ ] T1: <task title>`, use only `build` or `verify` lanes, and include immediate `Lane`, `Complexity`, and `Revision` metadata. Every `Tn` must be unique."
            "\n- Declare `Depends on` for every task (`None` when independent), `Covered by` for builds, and `Validates` for verifies; keep references consistent. Explicit relations govern eligibility and input-result reuse. Legacy artifacts without any relation declarations still use previous-item dependencies. Task-local semantic context remains opaque to Kernel and must not become a generic graph, scheduler, or extra runtime metadata."
        )
    return f"""- Before drafting, run the stage command once without `artifact_file`, preserve applicable user stage arguments, and request JSON:

```text
loom stage {command} --branch <current-git-branch> [--arg key=value ...] --json
```

- Treat `status=noop` with `extras.handoff=author_artifact` as the normal host-authoring handoff, not a failure or a completed stage. Use its exact `extras.artifact_path`, `extras.register_command`, `extras.main_role`, and `extras.reviewer_agent` values for this invocation. For Plan, Tasks, and Ship, the command contains the frozen `extras.input_token`; never reconstruct or omit it.
- If registration returns `<stage>_inputs_changed`, discard the stale candidate as a workflow input, accept the refreshed handoff, and rerun the same Main Role against `extras.input_snapshot`. Do not silently register, patch the token, or ask the user to resolve this host-internal retry.
- If the preflight response does not contain that handoff—for example, because a prerequisite is missing or a continuation route redirects the stage—do not draft or register a downstream artifact. Report the returned response and follow its single `recommended_next`.
- Before drafting, read `.loom/project.yml` and use `specs.language` as the prose language of the artifact at `extras.artifact_path`; default to English (`en`) when it is missing or unclear.
- Before drafting, read `.loom/templates/{template_name}` if it exists and use it as a flexible projection aid for the Markdown artifact, not a mandatory checklist or semantic schema.
- The template may suggest organization, but `.loom/project.yml` `specs.language` controls the artifact's prose language. Omit irrelevant sections and prefer the current Main's role judgment over heading completion.
- Use `extras.project_profile` as the mechanical language/framework/module/command context supplied by the project configuration.
- Read the exact `extras.constitution.path` only when `extras.constitution.usable` is true, and only sections relevant to this stage's output quality, stack guidance, and evidence behavior. When it is false, continue from repository facts, `CLAUDE.md`, current requirements, accepted artifacts, and the project profile; do not turn Adopt into a prerequisite.
- Treat a usable constitution as the project rulebook / quality baseline; it is not workflow state, runtime evidence, approval, requirement authority, or a substitute for current repository facts.
- Current requirement semantics and accepted artifact design outrank constitution guidance when they conflict; even a registered baseline can be lower-quality for legacy cleanup or architecture upgrade work.
- Constitution guidance must not expand the current branch artifact boundary or override current requirement semantics, current user instructions, platform hard constraints, current repository facts, accepted artifact design, or host-native project rules.
- Do not copy constitution text into the artifact; compress only relevant constraints into the stage analysis.
- Separate product or business delivery scope from platform validation scope; artifact review, real-flow validation, and prompt/eval tuning notes must not authorize extra product changes or appear as product artifact content unless the current requirement explicitly changes CodeLoom.
- Before writing the artifact, apply the current Main Role's Artifact Boundary Gate: write only artifact-owned content, and keep branch/session state, workflow mechanics, platform feedback routing, prompt/eval tuning, and runtime control details out of the Markdown.
- Artifact factual claims must be backed by current source, repository evidence, runtime evidence, or recorded attempt evidence. When a material project or external fact should be investigated, do not relabel its absence as a validation assumption; {investigation_rule} Mark only residual unsupported claims as risks or not verified.
- If the template is missing, draft a stage-appropriate Markdown artifact without blocking the Kernel.
- Use the current Main in the `extras.main_role` named by the handoff to draft the Markdown artifact after preflight and before registration; never start that role as a subagent.
- The artifact file must contain only user-facing Markdown. Do not include agent output contracts, process notes, execution rules, `result_type`, internal workflow/control metadata, branch/session facts, platform feedback routing, prompt/eval tuning notes, or SQLite/runtime instructions inside the Markdown.
- Write the artifact directly to the exact repository-relative `extras.artifact_path`; create only its parent directory when absent, and do not create a parallel temporary copy.
- After Main has completed material finding dispositions, applied necessary revisions, and judged the exact artifact ready under the loaded role's completion conditions, execute the exact `extras.register_command` returned by the same handoff. Do not reconstruct the artifact path or registration command from branch names, default directories, or template names.{task_format_rule}{semantic_reference_rule}"""
