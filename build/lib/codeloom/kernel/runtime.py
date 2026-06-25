from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from codeloom.kernel.artifacts import TaskDefinition


@dataclass(frozen=True)
class RuntimeResult:
    success: bool
    summary: str
    diff: str
    stdout: str
    stderr: str


class RuntimeClient(Protocol):
    name: str

    def prepare(self, repo_path: Path, task: TaskDefinition) -> object | None:
        ...

    def execute(self, repo_path: Path, task: TaskDefinition) -> RuntimeResult:
        ...

    def collect_result(self, result: RuntimeResult) -> RuntimeResult:
        ...

    def collect_diff(self, result: RuntimeResult) -> str:
        ...

    def abort(self, runtime_context: object | None = None) -> bool:
        ...

    def capabilities(self) -> dict[str, object]:
        ...
