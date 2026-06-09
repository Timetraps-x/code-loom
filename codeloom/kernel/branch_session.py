from __future__ import annotations

from pathlib import Path

from codeloom.kernel.artifacts import branch_slug
from codeloom.persistence.sqlite import SQLiteStore


def load_branch_session(store: SQLiteStore, repo_path: Path, branch_name: str, artifact_root: str) -> dict[str, object]:
    return store.get_or_create_branch_session(branch_name, branch_slug(branch_name), artifact_root)
