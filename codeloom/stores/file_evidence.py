from __future__ import annotations

from pathlib import Path


class FileEvidenceStore:
    def __init__(self, repo_path: Path, branch_slug: str) -> None:
        self.repo_path = repo_path.resolve()
        self.root = self.repo_path / ".loom" / "runs" / branch_slug

    def write_attempt_file(self, task_id: str, attempt_no: int, kind: str, content: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        safe_task_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in task_id)
        filename = f"{safe_task_id}-a{attempt_no:03d}-{kind}"
        path = self.root / filename
        path.write_text(content, encoding="utf-8")
        return path.resolve().relative_to(self.repo_path).as_posix()
