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
        before_status = _git_status(repo_path)
        try:
            completed = subprocess.run(
                ["claude", "-p", prompt, "--permission-mode", "acceptEdits"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError:
            return RuntimeResult(False, "Claude Code runtime failed: claude CLI not found", "", "", "claude CLI not found")
        except subprocess.TimeoutExpired as exc:
            return RuntimeResult(False, "Claude Code runtime failed: timed out", _collect_git_diff(repo_path, before_status), exc.stdout or "", exc.stderr or "")

        diff = _collect_git_diff(repo_path, before_status)
        output = f"{completed.stdout}\n{completed.stderr}"
        success = completed.returncode == 0 and not _has_runtime_failure_signal(output)
        summary = f"Claude Code runtime completed {task.task_id}" if success else f"Claude Code runtime failed {task.task_id}"
        return RuntimeResult(success, summary, diff, completed.stdout, completed.stderr)

    def collect_result(self, result: RuntimeResult) -> RuntimeResult:
        return result

    def collect_diff(self, result: RuntimeResult) -> str:
        return result.diff

    def abort(self, runtime_context: object | None = None) -> bool:
        return False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "sync": True, "diff": True, "abort": False, "command": "claude -p --permission-mode acceptEdits"}


def _task_prompt(task: TaskDefinition) -> str:
    if task.lane == "verify":
        lane_instruction = "Verify the current verify task, its covered build tasks, and expected evidence from the task notes. Do not broaden verification to the whole plan unless the verify task explicitly requires it. Report pass, fail, or blocked with evidence. Do not implement fixes unless the task explicitly requires it.\n"
    else:
        lane_instruction = "Execute this build task within the current task boundary. Use spec.md or plan.md only when the task references a specific section or explicit pointer, when task context is ambiguous, or when implementation reveals a conflict with requirement semantics or design facts. When local choices are open, choose within the task boundary by considering existing-code consistency, correctness, performance, maintainability, change cost, and verification cost. If execution would require changing requirement semantics, public contracts, data model semantics, major UI flow, preserved design constraints, or later task boundaries, stop as blocked. Use code-reviewer before closing the build attempt when files change. Do not claim full verification.\n"
    return (
        "You are executing a CodeLoom task inside the current repository.\n"
        f"Task lane: {task.lane}\n"
        f"{lane_instruction}"
        "Do not commit, push, force reset, discard unrelated user changes, invoke /loom commands, or run loom stage commands from inside this task.\n\n"
        f"Task id: {task.task_id}\n"
        f"Task title: {task.title}\n"
        f"Task definition:\n{task.raw}\n"
    )


def _has_runtime_failure_signal(output: str) -> bool:
    normalized = output.strip().lower()
    if not normalized:
        return False
    failure_prefixes = ("fail", "failed", "blocked", "error")
    failure_terms = (
        "需要你批准",
        "permission denied",
        "not approved",
        "未通过",
        "已阻塞",
        "cannot continue",
        "**fail**",
        "未执行",
    )
    return normalized.startswith(failure_prefixes) or any(term in normalized for term in failure_terms)


def _collect_git_diff(repo_path: Path, before_status: set[str] | None = None) -> str:
    if before_status is None:
        tracked = _git_diff(repo_path)
        return tracked

    after_status = _git_status(repo_path)
    new_status = sorted(after_status - before_status)
    if not new_status:
        return ""

    chunks: list[str] = []
    for line in new_status:
        path = _status_path(line)
        if not path:
            continue
        if line.startswith("?? "):
            chunks.append(f"Untracked file: {path}\n")
            content = _read_text_file(repo_path / path)
            if content is not None:
                chunks.append(f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(content.splitlines())} @@\n{_added_lines(content)}")
            continue
        patch = _git_diff(repo_path, path)
        if patch:
            chunks.append(patch)
        else:
            chunks.append(f"Changed file: {path}\n")
    return "\n".join(chunk.rstrip() for chunk in chunks if chunk).strip()


def _git_status(repo_path: Path) -> set[str]:
    try:
        completed = subprocess.run(["git", "status", "--short"], cwd=repo_path, capture_output=True, text=True)
    except FileNotFoundError:
        return set()
    if completed.returncode != 0:
        return set()
    return {line for line in completed.stdout.splitlines() if line.strip()}


def _git_diff(repo_path: Path, path: str | None = None) -> str:
    command = ["git", "diff", "--"]
    if path is not None:
        command.append(path)
    try:
        completed = subprocess.run(command, cwd=repo_path, capture_output=True, text=True)
    except FileNotFoundError:
        return ""
    return completed.stdout if completed.returncode == 0 else ""


def _status_path(line: str) -> str:
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1].strip()
    return path


def _read_text_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _added_lines(content: str) -> str:
    return "\n".join(f"+{line}" for line in content.splitlines()) + ("\n" if content else "")
