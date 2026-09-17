from __future__ import annotations

import os
import tempfile
from pathlib import Path


class FileEvidenceStore:
    def __init__(self, repo_path: Path, branch_slug: str) -> None:
        self.repo_path = repo_path.resolve()
        self.root = self.repo_path / ".loom" / "runs" / branch_slug

    def attempt_file_ref(self, task_id: str, attempt_no: int, kind: str) -> str:
        safe_task_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in task_id)
        path = self.root / f"{safe_task_id}-a{attempt_no:03d}-{kind}"
        return path.resolve().relative_to(self.repo_path).as_posix()

    def write_attempt_file(self, task_id: str, attempt_no: int, kind: str, content: str) -> str:
        ref = self.attempt_file_ref(task_id, attempt_no, kind)
        path = self.repo_path / ref
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(dir=self.root, prefix=".evidence-", suffix=".tmp", text=True)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return ref