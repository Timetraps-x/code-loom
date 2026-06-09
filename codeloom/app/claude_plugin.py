from __future__ import annotations

import json
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
        "description": "Run one CodeLoom task attempt and verification for the current git branch.",
        "argument_hint": "task_id=T1",
    },
    "ship": {
        "description": "Generate CodeLoom ship.md and readiness conclusion for the current git branch.",
        "argument_hint": "optional delivery note",
    },
}


def install_claude_plugin(repo_path: Path, force: bool = False) -> list[str]:
    root = repo_path.resolve() / ".claude" / "skills" / "loom"
    plugin_dir = root / ".claude-plugin"
    skills_dir = root / "skills"
    written: list[str] = []

    plugin_json = plugin_dir / "plugin.json"
    written.extend(_write(plugin_json, json.dumps({"name": "loom"}, indent=2) + "\n", force))

    for command, metadata in COMMANDS.items():
        skill_path = skills_dir / command / "SKILL.md"
        written.extend(_write(skill_path, _skill_content(command, metadata["description"], metadata["argument_hint"]), force))

    return written


def _write(path: Path, content: str, force: bool) -> list[str]:
    if path.exists() and not force:
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return [path.as_posix()]


def _skill_content(command: str, description: str, argument_hint: str) -> str:
    task_argument_rule = "- For the `do` stage, convert a bare task id like `T2` to `--arg task_id=T2`." if command == "do" else ""
    content_rule = _content_rule(command)
    return f"""---
description: {description}
argument-hint: {argument_hint}
disable-model-invocation: true
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
{content_rule}
{task_argument_rule}
- Report the returned KernelResponse status, message, recommended_next, recommended_task_id, artifact_paths, findings, and errors.
"""


def _content_rule(command: str) -> str:
    if command not in {"spec", "plan", "tasks", "ship"}:
        return ""
    task_format_rule = ""
    if command == "tasks":
        task_format_rule = "\n- The candidate must contain parseable task lines exactly like `- [ ] T1: <task title>`. Do not use only section headings for tasks."
    return f"""- Use the current host model to draft the Markdown candidate for this stage.
- Write that candidate to a temporary UTF-8 file, not to the final artifact path.
- Pass the temporary file to the Kernel with `--arg content_file=<temp-path>` so `loom stage` writes artifacts and SQLite state.{task_format_rule}"""
