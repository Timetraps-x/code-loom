from __future__ import annotations

from pathlib import Path

from codeloom.app.init_project import init_project


def run(cwd: Path, force: bool = False, integrations: set[str] | None = None) -> tuple[bool, str]:
    return init_project(cwd, force=force, integrations=integrations)
