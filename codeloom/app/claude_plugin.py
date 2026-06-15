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
    "ship": "delivery confirmation",
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
    task_argument_rule = "- For the `do` stage, convert a bare task id like `T2` to `--arg task_id=T2`." if command == "do" else ""
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

Use the shell appropriate for the current platform to execute:

```text
loom stage {command} --branch <current-git-branch> [--arg key=value ...]
```

Rules:

- Get the current branch from the host git context.
- CodeLoom is a workflow harness over this host, not a replacement for Claude Code, Codex, or OpenCode.
- Do not decide CodeLoom workflow state in the skill body.
- Do not write artifacts or SQLite directly.
- If required user input is unclear, ask before running the command.
{agent_rule}
{content_rule}
{task_argument_rule}
- Report the returned KernelResponse status, message, recommended_next, recommended_task_id, artifact_paths, findings, and errors.
"""


def _agent_rule(command: str) -> str:
    if command == "do":
        return """- For do-stage execution, the current task is the direct execution boundary.
- For build tasks, use the project Claude Code agent `builder` from `.claude/agents/builder.md` when available.
- For verify tasks, use the project Claude Code agent `verifier` from `.claude/agents/verifier.md` when available.
- `builder` may use `spec.md` or `plan.md` only when the task references a specific section or explicit pointer, when task context is ambiguous, or when implementation reveals a conflict with requirement semantics or design facts.
- When local choices are open, `builder` may choose within the task boundary by considering existing-code consistency, correctness, performance, maintainability, change cost, and verification cost.
- If execution would require changing requirement semantics, public contracts, data model semantics, major UI flow, preserved design constraints, or later task boundaries, report blocked instead of expanding the task.
- `builder` may delegate narrow codebase fact gathering or external research to `scout` when available, but `scout` must stay read-only and advisory.
- After file modifications, `builder` must use the project Claude Code agent `code-reviewer` from `.claude/agents/code-reviewer.md` when available before closing the build attempt.
- Build attempts must not claim full verification; Kernel records successful build tasks as implemented and successful verify tasks as verified."""
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
    return f"""- Before drafting, read `.loom/templates/{template_name}` if it exists and use it as the structure for the Markdown artifact.
- If the template is missing, draft a stage-appropriate Markdown artifact without blocking the Kernel.
- Use the current host model to draft the Markdown artifact for this stage.
- The artifact file must contain only user-facing Markdown. Do not include agent output contracts, process notes, execution rules, `result_type`, readiness flags, or SQLite/runtime instructions inside the Markdown.
- Write the artifact directly to `specs/<branch-slug>/{artifact_name}`. Do not create a parallel temporary copy.
- Use the same `<branch-slug>` CodeLoom uses for the current git branch; if unsure, read it from `loom status --branch <current-git-branch> --json`.
- Pass the final artifact file to the Kernel with `--arg artifact_file=specs/<branch-slug>/{artifact_name}` so `loom stage` records artifact state without regenerating duplicate content.{task_format_rule}"""
