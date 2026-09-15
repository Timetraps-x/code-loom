from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

DEFAULT_CONSTITUTION_PATH = ".loom/constitution.md"
CONSTITUTION_SEED_MARKER = "CODELOOM_CONSTITUTION_SEED"


def register_constitution(cwd: Path, constitution: str = DEFAULT_CONSTITUTION_PATH) -> dict[str, Any]:
    repo_path = cwd.resolve()
    relative_path = _validated_constitution_path(repo_path, constitution)
    path = repo_path / relative_path
    if not path.exists():
        return {
            "status": "failed",
            "message": "constitution file is missing",
            "constitution": _status(relative_path, False, None, "", False),
            "errors": [f"missing: {relative_path.as_posix()}"],
        }

    content_hash = _hash_file(path)
    seeded = _is_seeded(path)
    project_path = repo_path / ".loom" / "project.yml"
    if not project_path.exists():
        return {
            "status": "failed",
            "message": "project is not initialized",
            "constitution": _status(relative_path, True, content_hash, "", seeded),
            "errors": [f"missing: {project_path}"],
        }
    if seeded:
        return {
            "status": "failed",
            "message": "constitution scaffold must be replaced before registration",
            "constitution": _status(relative_path, True, content_hash, "", True),
            "errors": ["constitution_not_adopted"],
        }

    _update_project_yml(project_path, relative_path.as_posix(), content_hash)
    return {
        "status": "ok",
        "message": "constitution registered",
        "constitution": _status(relative_path, True, content_hash, content_hash, False),
        "errors": [],
    }


def constitution_status(
    repo_path: Path,
    configured_path: str = DEFAULT_CONSTITUTION_PATH,
    registered_hash: str = "",
) -> dict[str, Any]:
    relative_path = _validated_constitution_path(repo_path.resolve(), configured_path or DEFAULT_CONSTITUTION_PATH)
    path = repo_path.resolve() / relative_path
    exists = path.exists()
    current_hash = _hash_file(path) if exists else None
    seeded = _is_seeded(path) if exists else False
    return _status(relative_path, exists, current_hash, registered_hash, seeded)


def _status(
    relative_path: Path,
    exists: bool,
    current_hash: str | None,
    registered_hash: str,
    seeded: bool,
) -> dict[str, Any]:
    registered = bool(registered_hash)
    matches_registered = bool(current_hash and registered and current_hash == registered_hash)
    return {
        "path": relative_path.as_posix(),
        "exists": exists,
        "seeded": seeded,
        "registered": registered,
        "current_hash": current_hash,
        "registered_hash": registered_hash or "",
        "matches_registered": matches_registered,
        "usable": bool(exists and not seeded and matches_registered),
    }


def _validated_constitution_path(repo_path: Path, configured_path: str) -> Path:
    raw_path = Path(configured_path)
    resolved = raw_path if raw_path.is_absolute() else repo_path / raw_path
    resolved = resolved.resolve()
    if not resolved.is_relative_to(repo_path):
        raise ValueError("constitution path must stay inside the project")
    relative_path = resolved.relative_to(repo_path)
    if not relative_path.parts or relative_path.parts[0] != ".loom":
        raise ValueError("constitution path must stay under .loom")
    return relative_path


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _is_seeded(path: Path) -> bool:
    try:
        return CONSTITUTION_SEED_MARKER in path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False


def _update_project_yml(project_path: Path, constitution_path: str, constitution_hash: str) -> None:
    lines = project_path.read_text(encoding="utf-8").splitlines()
    section = ["constitution:", f"  path: {constitution_path}", f"  hash: {constitution_hash}"]

    start = _top_level_section_start(lines, "constitution")
    if start is None:
        insert_at = _top_level_section_start(lines, "rules")
        if insert_at is None:
            lines.extend(["", *section])
        else:
            lines[insert_at:insert_at] = [*section, ""]
    else:
        end = start + 1
        while end < len(lines) and (lines[end].startswith(" ") or not lines[end].strip()):
            end += 1
        lines[start:end] = section + ([""] if end < len(lines) else [])

    project_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _top_level_section_start(lines: list[str], section: str) -> int | None:
    marker = f"{section}:"
    for index, line in enumerate(lines):
        if line == marker:
            return index
    return None
