from __future__ import annotations

from pathlib import Path

from codeloom.kernel.artifacts import TaskDefinition
from codeloom.kernel.runtime import RuntimeResult


class MockRuntimeClient:
    name = "mock"

    def prepare(self, repo_path: Path, task: TaskDefinition) -> None:
        return None

    def execute(self, repo_path: Path, task: TaskDefinition) -> RuntimeResult:
        diff = (
            f"diff --git a/mock/{task.task_id}.txt b/mock/{task.task_id}.txt\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            f"+++ b/mock/{task.task_id}.txt\n"
            "@@ -0,0 +1 @@\n"
            f"+{task.title}\n"
        )
        return RuntimeResult(
            success=True,
            summary=f"Mock runtime completed {task.task_id}: {task.title}",
            diff=diff,
            stdout=f"mock runtime executed {task.task_id}\n",
            stderr="",
        )

    def collect_result(self, result: RuntimeResult) -> RuntimeResult:
        return result

    def collect_diff(self, result: RuntimeResult) -> str:
        return result.diff

    def abort(self, runtime_context: object | None = None) -> bool:
        return False

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "sync": True, "diff": True, "abort": False}
