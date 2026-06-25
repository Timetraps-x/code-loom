from __future__ import annotations

from pathlib import Path

from codeloom.kernel.artifacts import TaskDefinition
from codeloom.kernel.runtime import RuntimeResult


class ClaudeCodeRuntimeClient:
    name = "claude-code"

    def prepare(self, repo_path: Path, task: TaskDefinition) -> None:
        return None

    def execute(self, repo_path: Path, task: TaskDefinition) -> RuntimeResult:
        return RuntimeResult(
            False,
            "Claude Code host runtime requires begin/complete handoff",
            "",
            "",
            "host runtime does not execute via nested claude CLI",
        )

    def collect_result(self, result: RuntimeResult) -> RuntimeResult:
        return result

    def collect_diff(self, result: RuntimeResult) -> str:
        return result.diff

    def abort(self, runtime_context: object | None = None) -> bool:
        return False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "sync": False, "diff": True, "abort": False, "mode": "host"}
