from __future__ import annotations

import hashlib
from pathlib import Path


class MarkdownArtifactStore:
    FILENAMES = {
        "spec": "spec.md",
        "plan": "plan.md",
        "tasks": "tasks.md",
        "ship": "release.md",
    }

    def __init__(self, repo_path: Path, artifact_root: str, branch_slug: str) -> None:
        self.repo_path = repo_path.resolve()
        self.root = self.repo_path / artifact_root / branch_slug

    def path_for(self, kind: str) -> Path:
        filename = self.FILENAMES[kind]
        return self.root / filename

    def read(self, kind: str) -> str | None:
        path = self.path_for(kind)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, kind: str, content: str) -> tuple[Path, str]:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(kind)
        path.write_text(content, encoding="utf-8")
        return path, self.content_hash(content)

    def hash_existing(self, kind: str) -> str | None:
        content = self.read(kind)
        if content is None:
            return None
        return self.content_hash(content)

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.repo_path).as_posix()

    @staticmethod
    def content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
