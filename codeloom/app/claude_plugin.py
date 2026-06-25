from __future__ import annotations

from pathlib import Path

COMMANDS = {
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
- If execution would require changing requirement semantics, public contracts, data model semantics, major UI flow, preserved design constraints, or later task boundaries, complete the attempt as `blocked` instead of expanding the task.
- `builder` and `verifier` may delegate narrow read-only repository fact questions inside the current task boundary to `codebase-scout` from `.claude/agents/codebase-scout.md` when available.
- Use generic `scout` only when artifact/runtime/external evidence is needed and `codebase-scout` is too narrow; both scouts must stay advisory and must not decide task status.
- `builder` should preserve reasonable content density: keep key business/data flow, side effects, transaction boundaries, batch/query behavior, and performance-sensitive paths visible at the useful reading level.
- `builder` and `code-reviewer` should reject cosmetic helper extraction, repeated traversal, N+1 queries, and reusable SQL/query/helper names tied to one-off pages, buttons, tasks, or temporary scenarios.
- After file modifications, `builder` must use the project Claude Code agent `code-reviewer` from `.claude/agents/code-reviewer.md` when available before closing the build attempt.
- Complete the attempt by running `loom stage do --branch <current-git-branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=<implemented|verified|failed|blocked> --arg summary=<short-summary>`.
- Build attempts must complete as `implemented`, `failed`, or `blocked`; they must not claim full verification.
- Verify attempts must complete as `verified`, `failed`, or `blocked` with evidence from the verifier."""
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
        task_format_rule = "\n- Executable tasks must be build or verify tasks only; do not create scout, research, discovery, adjustment, planning, release, ship, rollback-summary, or shippability-judgment `Tn` items.\n- Build tasks need boundaries, dependencies, local completion boundaries, and verification coverage, but they do not each need independent functional verification.\n- Every build task must have a clear verification owner or grouped verify task.\n- Verify tasks may cover multiple naturally related build tasks and must name the covered tasks, risks, and expected evidence.\n- Do not copy large plan sections into tasks or micromanage function names, local variables, or line-level edits.\n- Extract enough execution context from plan design facts that builder, code-reviewer, and verifier can execute or review the current task without rereading the whole plan.\n- Missing facts that block safe slicing must be clarified before generating `tasks.md` or returned as blocked; only non-blocking known constraints, risk notes, and validation notes belong in task context.\n- Optional `## Ship inputs` content is non-executable and must not contain `- [ ] Tn:` checklist lines.\n- The artifact must contain parseable task lines exactly like `- [ ] T1: <task title>`. Do not use only section headings for tasks."
    artifact_name = "release.md" if command == "ship" else f"{command}.md"
    return f"""- Before drafting, read `.loom/project.yml` and use `specs.language` as the artifact content language for `specs/<branch-slug>/{artifact_name}`; default to English (`en`) when it is missing or unclear.
- Before drafting, read `.loom/templates/{template_name}` if it exists and use it as the structure and governance for the Markdown artifact.
- The template controls structure, but `.loom/project.yml` `specs.language` controls the artifact's prose language.
- If the template is missing, draft a stage-appropriate Markdown artifact without blocking the Kernel.
- Use the current host model and the stage main agent to draft the Markdown artifact for this stage before running the Kernel registration command.
- The artifact file must contain only user-facing Markdown. Do not include agent output contracts, process notes, execution rules, `result_type`, readiness flags, or SQLite/runtime instructions inside the Markdown.
- Write the artifact directly to `specs/<branch-slug>/{artifact_name}`. Do not create a parallel temporary copy.
- Use the same `<branch-slug>` CodeLoom uses for the current git branch; if unsure, read it from `loom status --branch <current-git-branch> --json`.
- Pass the final artifact file to the Kernel with `--arg artifact_file=specs/<branch-slug>/{artifact_name}`; do not run the Kernel artifact stage without `artifact_file` in `claude-code` host mode.{task_format_rule}"""
