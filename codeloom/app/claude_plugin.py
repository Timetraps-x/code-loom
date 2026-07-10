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


def install_claude_skills(repo_path: Path, force: bool = False) -> list[str]:
    skills_dir = repo_path.resolve() / ".claude" / "skills"
    written: list[str] = []

    for command, metadata in COMMANDS.items():
        skill_name = f"loom-{command}"
        skill_path = skills_dir / skill_name / "SKILL.md"
        written.extend(
            _write(
                skill_path,
                _skill_content(
                    skill_name,
                    command,
                    metadata["description"],
                    metadata["argument_hint"],
                ),
                force,
            )
        )

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

After any host-agent work required by the rules below, use the shell appropriate for the current platform to execute:

```text
loom stage {command} --branch <current-git-branch> [--arg key=value ...]
```

Rules:

- Get the current branch from the host git context.
- CodeLoom is a workflow harness over this host, not a replacement for Claude Code, Codex, or OpenCode.
- Do not decide CodeLoom workflow state in the skill body; Kernel owns workflow state and SQLite updates.
- For artifact stages, write only the final user-facing Markdown artifact under `specs/<branch-slug>/...`; do not write runtime state or SQLite directly.
- If required user input is unclear, ask before running the command.
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

Create or revise the CodeLoom project constitution for this project.

User arguments are available as `$ARGUMENTS`; use them only as adoption guidance, not as workflow state. If `$ARGUMENTS` contains `update-claude`, use the explicit update-claude mode below.

Rules:

- Use the project Claude Code agent `adopt-expert` from `.claude/agents/adopt-expert.md` when available.
- If `.loom/templates/constitution-template.md` exists, use it as the starting section structure for `.loom/constitution.md`, not as a mandatory checklist.
- Detect the project's real languages/frameworks before reading positive code-shape cases.
- If `.loom/references/positive-cases/` exists, read only cases matching the detected stack; do not load every case just because it exists.
- `adopt-expert` should analyze the project as a whole: repository rules, `CLAUDE.md` files, docs/specs/design/business documents, source code, database design, schema/migration/SQL surfaces, mapper/query conventions, public contracts, stacks, architecture boundaries, verification habits, and assisted-coding risk patterns.
- `adopt-expert` must classify evidence before writing: stable existing conventions, stable positive shapes, repository rules, current branch artifacts, untracked/in-progress code, target-state designs, legacy/non-propagation candidates, and conflicts needing user decision.
- If evidence is broad or conflicting, `adopt-expert` may delegate narrow read-only evidence questions to `scout` or `codebase-scout` when available; scouts return evidence only and must not draft constitution rules or decide what belongs in constitution.
- Before writing, use AskUserQuestion for promotion, authority, or legacy conflicts that would materially change constitution content. Do not ask about facts that can be verified locally or wording that does not change the rule.
- Current branch artifacts, untracked/in-progress code, and target-state designs must not become direct durable constitution rules unless stable repository evidence supports them or the user confirms promotion.
- The output artifact is `.loom/constitution.md`; it is the project constitution / quality baseline next to `.loom/project.yml`.
- Write `.loom/constitution.md` in English by default because it becomes a downstream prompt surface for later LLM stages; use another language only when `$ARGUMENTS` or repository rules explicitly require it.
- Default mode reads `CLAUDE.md` only as input context; do not emit `CLAUDE.md` rewrite suggestions and do not modify any `CLAUDE.md`.
- In explicit `update-claude` mode, `adopt-expert` may include bounded `CLAUDE.md suggestions` for host-runtime context such as commands, verification entry points, safety/no-touch rules, and pointers to constitution.md; do not rewrite `CLAUDE.md` unless the command mode explicitly asks for apply.
- Do not create or edit branch artifacts such as `spec.md`, `plan.md`, `tasks.md`, or `release.md`.
- Do not update SQLite, runtime state, or CodeLoom branch sessions directly.
- Keep the constitution concise and focused on durable project code-quality rules: placement/ownership, business/data/state flow visibility, abstraction/reuse/naming thresholds, stack-local code shape, change risk boundaries, and rule stability.
- Do not generate a project encyclopedia, generic best-practice guide, CodeLoom manual, authority/precedence section, runtime contract, or separate full constitution per language/framework.
- Write the final clean Markdown directly to `.loom/constitution.md`.
- After `.loom/constitution.md` exists, use the shell appropriate for the current platform to execute:

```text
loom adopt --constitution .loom/constitution.md
```

- Report the returned status, message, constitution path, current hash, registered hash, and errors.
"""


def _argument_rule(command: str) -> str:
    if command == "spec":
        return """- For the `spec` stage, never pass bare user text as an unnamed `--arg` and never invent unsupported keys such as `gap`.
- If `$ARGUMENTS` is bare text and no current `spec.md` exists, pass it as `--arg requirement=<text>`.
- If `$ARGUMENTS` is bare text and a current `spec.md` already exists, pass it as `--arg revision_note=<text>` so CodeLoom revises the existing spec.
- Preserve explicit `requirement=`, `revision_note=`, `text=`, or `artifact_file=` keys when the user provides them."""
    if command == "do":
        return "- For the `do` stage, convert a bare task id like `T2` to `--arg task_id=T2`."
    return ""


def _agent_rule(command: str) -> str:
    if command == "do":
        return """- For claude-code host runtime, do not run `loom stage do` as a one-shot execution command.
- First run `loom stage do --branch <current-git-branch> --arg action=begin --arg task_id=<task-id>` and use the returned `extras.attempt_id`, `extras.lane`, `extras.main_agent`, and `extras.task_definition` as the execution boundary.
- For build tasks, use the project Claude Code agent `builder` from `.claude/agents/builder.md` when available; `builder` is the build-lane main agent.
- For verify tasks, use the project Claude Code agent `verifier` from `.claude/agents/verifier.md` when available; `verifier` is the verify-lane main agent.
- `builder` may use `spec.md` or `plan.md` only when the task references a specific section or explicit pointer, when task context is ambiguous, or when implementation reveals a conflict with requirement semantics or design facts.
- When local choices are open, `builder` may choose within the task boundary by considering existing-code consistency, correctness, performance, maintainability, change cost, and verification cost.
- Current requirement semantics and accepted artifact design outrank `.loom/constitution.md` when they conflict; constitution may be stale or lower-quality during legacy cleanup or architecture upgrade work.
- If execution would require changing requirement semantics, public contracts, data model semantics, major UI flow, preserved design constraints, or later task boundaries, complete the attempt as `blocked` instead of expanding the task.
- If `.loom/constitution.md` exists, `builder`, `code-reviewer`, and `verifier` should read only sections relevant to the current task quality, stack guidance, evidence behavior, and any relevant stack profile.
- Treat `.loom/constitution.md` as the project rulebook / quality baseline; it is not workflow state, runtime evidence, approval, requirement authority, or a substitute for current repository facts.
- Constitution guidance must not expand the current task boundary or override current requirement semantics, current user instructions, platform hard constraints, current repository facts, accepted artifact design, or host-native project rules.
- Do not copy constitution text into attempt summaries, review output, or verification handoffs; compress only the relevant constraints.
- When the working tree is already dirty, distinguish the scoped task diff from unrelated pre-existing changes; do not treat unrelated dirty files as implemented, verified, or release-ready for the current task.
- If a task changes a public/API/UI response contract, verify the exact response shape with command, test, browser, manual, or inspection evidence; if only static inheritance/source evidence exists, mark end-to-end contract behavior as not verified.
- Prefer verification evidence that can close in this repository: targeted compile/typecheck, static contract inspection, service-level checks, existing passing tests, or stack-local verification evidence from `.loom/constitution.md`. Do not create or depend on a new broad runtime or integration harness unless current repository evidence shows a comparable harness already starts.
- `builder` and `verifier` may delegate narrow read-only repository fact questions inside the current task boundary to `codebase-scout` from `.claude/agents/codebase-scout.md` when available.
- Use generic `scout` only when artifact/runtime/external evidence is needed and `codebase-scout` is too narrow; both scouts must stay advisory and must not decide task status.
- `builder` should preserve reasonable content density: keep key business/data flow, side effects, transaction boundaries, batch/query behavior, and performance-sensitive paths visible at the useful reading level.
- `builder` and `code-reviewer` should reject cosmetic helper extraction, repeated traversal, N+1 queries, and reusable SQL/query/helper names tied to one-off pages, buttons, tasks, or temporary scenarios.
- For build tasks, `seal-changes` is an internal runtime action that seals the change set from the attempt start tree to the current working-tree content tree; do not present it as a user-facing stage and do not ask the user to run it.
- After `builder` modifies files and before invoking `code-reviewer`, automatically run `loom stage do --branch <current-git-branch> --arg action=seal-changes --arg attempt_id=<attempt-id>`.
- Use the returned `reviewer_handoff` when available; otherwise use `review_scope`, `seal_revision`, `sealed_changes_ref`, and `sealed_diff_command` as the code-reviewer evidence boundary.
- The host owns scoped review evidence. `builder` must not capture Git snapshots, compute scoped diffs, write `.loom/runs` evidence, or update SQLite refs.
- `code-reviewer` must review the host-provided attempt-scoped diff, not a full working tree diff or builder-listed file inventory.
- If `code-reviewer` requests changes and `builder` modifies files again, automatically rerun `action=seal-changes` before rerunning `code-reviewer`; old `seal_revision` values must not be used to complete the attempt.
- If `action=seal-changes` fails, do not invoke `code-reviewer` on full worktree diff and do not ask `builder` to repair runtime evidence; complete as `blocked` or route the runtime blocker to the host/user.
- Complete the attempt by running `loom stage do --branch <current-git-branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=<implemented|verified|failed|blocked> --arg summary=<short-summary>`; build `implemented` completion must automatically include latest sealed changes and review result, for example `--arg review_status=pass --arg seal_revision=<latest-seal-revision>`.
- Build attempts must complete as `implemented`, `failed`, or `blocked`; they must not claim full verification.
- Verify attempts must complete as `verified`, `failed`, or `blocked` with evidence from the verifier; when completing a verify attempt as `verified`, put the verification evidence summary in `summary` or pass `verification_summary_file=<path>`."""
    agent_name = STAGE_MAIN_AGENTS.get(command)
    if not agent_name:
        return ""
    responsibility = STAGE_RESPONSIBILITIES[command]
    projection = STAGE_PROJECTIONS[command]
    return f"""- Use the project Claude Code agent `{agent_name}` from `.claude/agents/{agent_name}.md` as the stage main agent when available.
- Treat `{agent_name}` as the owner of this stage's {responsibility} analysis and artifact synthesis; Kernel remains responsible for registering artifact state.
- Shared iteration vocabulary may orient the analysis, but this stage must project it through `{projection}` rather than using a generic large rubric.
- If project facts or external consensus are insufficient, `{agent_name}` may delegate a narrow fact-gathering or research question to the project Claude Code agent `scout` from `.claude/agents/scout.md` when available.
- Treat `scout` as advisory: it gathers observed facts, external references, relevant differences, implications, and open questions; it must not write artifacts, ask the user, or decide workflow state.
{_reviewer_rule(command, agent_name)}
- If `{agent_name}` identifies owner-bearing uncertainty, use AskUserQuestion before running the Kernel stage; do not guess business semantics, risk acceptance, or long-term technical direction.
- If unblocked, write the ready clean Markdown artifact to the stage's final `specs/<branch-slug>/...` path, then ask the Kernel to register it through `artifact_file`."""


def _reviewer_rule(command: str, agent_name: str) -> str:
    reviewer_name = STAGE_REVIEWERS.get(command)
    if not reviewer_name:
        return "- No separate reviewer agent is required for this stage; the stage main agent should self-check delivery risks."
    return f"""- After `{agent_name}` drafts or outlines the artifact, use the project Claude Code agent `{reviewer_name}` from `.claude/agents/{reviewer_name}.md` for advisory review when available.
- Treat `{reviewer_name}` as advisory only: it identifies gaps, risks, unclear questions, and suggested revisions; it must not write artifacts, ask the user, decide pass/fail, or decide workflow state.
- `{agent_name}` must absorb or explicitly reject reviewer feedback before writing the final clean artifact."""


def _content_rule(command: str) -> str:
    if command not in {"spec", "plan", "tasks", "ship"}:
        return ""
    task_format_rule = ""
    template_name = "release-template.md" if command == "ship" else f"{command}-template.md"
    if command == "tasks":
        task_format_rule = (
            "\n- Executable tasks must be build or verify tasks only; do not create `Tn` items for lanes other than `build` or `verify`."
            "\n- Every executable task line must include immediate metadata: `Lane`, `Complexity`, and `Revision`. New tasks start at `Revision: 1`."
            "\n- When updating an existing `tasks.md`, first compare the existing parseable Task List metadata and task meanings against the new draft; preserve a task's `Revision` unless its execution boundary, done criteria, verification coverage, lane, or dependency semantics changed; if those changed while keeping the same task id, increment `Revision` by 1."
            "\n- Do not bump `Revision` for wording, formatting, evidence prose, or non-semantic Task Notes updates."
            "\n- Build tasks need boundaries, dependencies, local completion boundaries, and verification coverage, but they do not each need independent functional verification."
            "\n- Every build task must have a clear verification owner or grouped verify task."
            "\n- Verify tasks may cover multiple naturally related build tasks and must name the covered tasks, risks, and expected evidence."
            "\n- Do not copy large plan sections into tasks or micromanage function names, local variables, or line-level edits."
            "\n- Extract enough execution context from plan design facts that builder, code-reviewer, and verifier can execute or review the current task without rereading the whole plan."
            "\n- Missing facts that block safe slicing must be clarified before generating `tasks.md` or returned as blocked; only non-blocking known constraints, risk notes, and validation notes belong in task context."
            "\n- For each build/verify task, include Task Notes for `Context need`, `Codebase facts to confirm`, and `Quality constraints` when those facts affect execution or verification judgment."
            "\n- These task-local context fields are execution context only; do not treat them as task metadata and do not place them between the checklist task line and immediate Lane / Complexity / Revision metadata."
            "\n- When the request includes platform validation, independent artifact review, or eval/prompt tuning beside a product change, keep business build tasks bounded to the product change and place only do-stage verification needs in verify task evidence;"
            " leave unrelated follow-up outside `tasks.md`."
            "\n- The artifact must contain parseable task lines exactly like `- [ ] T1: <task title>`. Do not use only section headings for tasks."
        )
    artifact_name = "release.md" if command == "ship" else f"{command}.md"
    return f"""- Before drafting, read `.loom/project.yml` and use `specs.language` as the artifact content language for `specs/<branch-slug>/{artifact_name}`; default to English (`en`) when it is missing or unclear.
- Before drafting, read `.loom/templates/{template_name}` if it exists and use it as the structure and governance for the Markdown artifact.
- The template controls structure, but `.loom/project.yml` `specs.language` controls the artifact's prose language.
- If `.loom/constitution.md` exists, read only sections relevant to this stage's output quality, stack guidance, and evidence behavior.
- Treat `.loom/constitution.md` as the project rulebook / quality baseline; it is not workflow state, runtime evidence, approval, requirement authority, or a substitute for current repository facts.
- Current requirement semantics and accepted artifact design outrank `.loom/constitution.md` when they conflict; constitution may be stale or lower-quality during legacy cleanup or architecture upgrade work.
- Constitution guidance must not expand the current branch artifact boundary or override current requirement semantics, current user instructions, platform hard constraints, current repository facts, accepted artifact design, or host-native project rules.
- Do not copy constitution text into the artifact; compress only relevant constraints into the stage analysis.
- Separate product or business delivery scope from platform validation scope; artifact review, real-flow validation, and prompt/eval tuning notes must not authorize extra product changes or appear as product artifact content unless the current requirement explicitly changes CodeLoom.
- Before writing the artifact, apply the stage main agent's Artifact Boundary Gate: write only artifact-owned content, and keep branch/session state, workflow mechanics, platform feedback routing, prompt/eval tuning, and runtime control details out of the Markdown.
- Artifact factual claims must be backed by current source, repository evidence, runtime evidence, or recorded attempt evidence; mark unsupported claims as assumptions, risks, or not verified.
- If the template is missing, draft a stage-appropriate Markdown artifact without blocking the Kernel.
- Use the current host model and the stage main agent to draft the Markdown artifact for this stage before running the Kernel registration command.
- The artifact file must contain only user-facing Markdown. Do not include agent output contracts, process notes, execution rules, `result_type`, readiness flags, branch/session facts, platform feedback routing, prompt/eval tuning notes, or SQLite/runtime instructions inside the Markdown.
- Write the artifact directly to `specs/<branch-slug>/{artifact_name}`. Do not create a parallel temporary copy.
- Use the same `<branch-slug>` CodeLoom uses for the current git branch; if unsure, read it from `loom status --branch <current-git-branch> --json`.
- Pass the final artifact file to the Kernel with `--arg artifact_file=specs/<branch-slug>/{artifact_name}`; do not run the Kernel artifact stage without `artifact_file` in `claude-code` host mode.{task_format_rule}"""
