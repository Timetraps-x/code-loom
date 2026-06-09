from __future__ import annotations

import subprocess
from pathlib import Path

from codeloom.kernel.artifacts import TaskDefinition
from codeloom.kernel.runtime import RuntimeResult


class ClaudeCodeRuntimeClient:
    name = "claude-code"

    def prepare(self, repo_path: Path, task: TaskDefinition) -> None:
        return None

    def execute(self, repo_path: Path, task: TaskDefinition) -> RuntimeResult:
        prompt = _task_prompt(task)
        try:
            completed = subprocess.run(
                ["claude", "-p", prompt],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError:
            return RuntimeResult(False, "Claude Code runtime failed: claude CLI not found", "", "", "claude CLI not found")
        except subprocess.TimeoutExpired as exc:
            return RuntimeResult(False, "Claude Code runtime failed: timed out", _collect_git_diff(repo_path), exc.stdout or "", exc.stderr or "")

        diff = _collect_git_diff(repo_path)
        success = completed.returncode == 0
        summary = f"Claude Code runtime completed {task.task_id}" if success else f"Claude Code runtime failed {task.task_id}"
        return RuntimeResult(success, summary, diff, completed.stdout, completed.stderr)

    def collect_result(self, result: RuntimeResult) -> RuntimeResult:
        return result

    def collect_diff(self, result: RuntimeResult) -> str:
        return result.diff

    def abort(self, runtime_context: object | None = None) -> bool:
        return False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "sync": True, "diff": True, "abort": False, "command": "claude -p"}


def _task_prompt(task: TaskDefinition) -> str:
    return (
        "You are executing a CodeLoom task inside the current repository.\n"
        "Implement only this task and run relevant local checks when appropriate.\n"
        "Do not commit, push, force reset, or discard unrelated user changes.\n\n"
        f"Task id: {task.task_id}\n"
        f"Task title: {task.title}\n"
        f"Raw task line: {task.raw}\n"
    )


def _collect_git_diff(repo_path: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "diff", "--"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return ""
    return completed.stdout if completed.returncode == 0 else ""
