from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from codeloom.app.claude_plugin import COMMANDS
from codeloom.app.init_project import load_project_config
from codeloom.kernel.clients import create_runtime_client
from codeloom.persistence.migrations import CURRENT_SCHEMA_VERSION
from codeloom.persistence.sqlite import SQLiteStore


def run_doctor(cwd: Path) -> dict[str, Any]:
    repo_path = cwd.resolve()
    checks: list[dict[str, str]] = []
    project_path = repo_path / "project.yml"
    _add_check(checks, "project.yml", "ok" if project_path.exists() else "failed", _exists_message(project_path))

    config = load_project_config(repo_path)
    store = SQLiteStore(repo_path)
    if store.db_path.exists():
        try:
            schema_version = store.schema_version()
            status = "ok" if schema_version == CURRENT_SCHEMA_VERSION else "failed"
            _add_check(checks, "sqlite schema", status, f"user_version={schema_version}, expected={CURRENT_SCHEMA_VERSION}")
        except Exception as exc:
            _add_check(checks, "sqlite schema", "failed", f"{type(exc).__name__}: {exc}")
    else:
        _add_check(checks, "sqlite database", "failed", f"missing: {store.db_path}")

    artifact_root = repo_path / config.artifact_root
    parent = artifact_root if artifact_root.exists() else artifact_root.parent
    if parent.exists():
        _add_check(checks, "artifact root", "ok", f"available: {artifact_root}")
    else:
        _add_check(checks, "artifact root", "failed", f"parent missing: {parent}")

    missing_skills = _missing_skill_files(repo_path)
    if missing_skills:
        _add_check(checks, "claude skills", "warning", f"missing {len(missing_skills)} skill files")
    else:
        _add_check(checks, "claude skills", "ok", "all loom skills present")

    try:
        runtime = create_runtime_client(config.default_runtime)
        capabilities = runtime.capabilities()
        if config.default_runtime == "claude-code" and shutil.which("claude") is None:
            _add_check(checks, "runtime", "warning", "claude-code configured but claude CLI was not found")
        else:
            _add_check(checks, "runtime", "ok", f"{config.default_runtime}: {capabilities}")
    except ValueError as exc:
        _add_check(checks, "runtime", "failed", str(exc))

    configured_commands = [name for name, command in config.commands.items() if command.strip()]
    if configured_commands:
        _add_check(checks, "verification commands", "ok", ", ".join(configured_commands))
    else:
        _add_check(checks, "verification commands", "warning", "test/lint/typecheck/build commands are empty")

    return {"status": _overall_status(checks), "checks": checks}


def _add_check(checks: list[dict[str, str]], name: str, status: str, message: str) -> None:
    checks.append({"name": name, "status": status, "message": message})


def _exists_message(path: Path) -> str:
    return f"present: {path}" if path.exists() else f"missing: {path}"


def _missing_skill_files(repo_path: Path) -> list[Path]:
    skills_dir = repo_path / ".claude" / "skills"
    return [skills_dir / f"loom-{command}" / "SKILL.md" for command in COMMANDS if not (skills_dir / f"loom-{command}" / "SKILL.md").exists()]


def _overall_status(checks: list[dict[str, str]]) -> str:
    if any(check["status"] == "failed" for check in checks):
        return "failed"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    return "ok"
