from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Literal

from codeloom import __version__
from codeloom.app.claude_plugin import bundled_claude_skill_contents

ProjectionGroup = Literal["agents", "skills"]
ProjectionStatus = Literal[
    "created",
    "updated",
    "adopted",
    "unchanged",
    "conflict",
    "missing",
    "unmanaged",
    "retired",
    "invalid_manifest",
]

MANIFEST_SCHEMA = 1
MANIFEST_PATH = PurePosixPath(".loom/managed/claude-code.json")


@dataclass(frozen=True)
class ProjectionResource:
    path: PurePosixPath
    group: ProjectionGroup
    source: str
    content: str

    @property
    def digest(self) -> str:
        return normalized_digest(self.content)


@dataclass(frozen=True)
class ProjectionResult:
    path: str
    group: ProjectionGroup
    status: ProjectionStatus
    message: str


def normalized_digest(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def bundled_claude_resources() -> tuple[ProjectionResource, ...]:
    bundled_agents = resources.files("codeloom.agents")
    agents = tuple(
        ProjectionResource(
            path=PurePosixPath(".claude") / "agents" / agent_name,
            group="agents",
            source=f"codeloom.agents/{agent_name}",
            content=bundled_agents.joinpath(agent_name).read_text(encoding="utf-8"),
        )
        for agent_name in sorted(item.name for item in bundled_agents.iterdir() if item.name.endswith(".md"))
    )
    skills = tuple(
        ProjectionResource(
            path=PurePosixPath(".claude") / "skills" / f"loom-{command}" / "SKILL.md",
            group="skills",
            source=f"generated:claude_plugin:loom-{command}",
            content=content,
        )
        for command, content in bundled_claude_skill_contents().items()
    )
    return agents + skills


def initialize_claude_projection(repo_path: Path, written_paths: set[Path]) -> None:
    resources_by_path = {resource.path: resource for resource in bundled_claude_resources()}
    manifest_path = repo_path.resolve() / MANIFEST_PATH
    existing = _load_manifest(manifest_path)
    files = existing.get("files", {}) if existing else {}

    for path, resource in resources_by_path.items():
        destination = _destination(repo_path, path)
        if destination in written_paths or not destination.exists():
            files[path.as_posix()] = _manifest_entry(resource, resource.digest)

    if files:
        _write_manifest(manifest_path, files, resources_by_path)


def upgrade_claude_projection(
    repo_path: Path,
    *,
    group: str = "all",
    dry_run: bool = False,
    resolve_bundle_paths: set[str] | None = None,
) -> dict[str, object]:
    selected_groups = _parse_groups(group)
    resources_by_path = {resource.path: resource for resource in bundled_claude_resources()}
    selected_resources = {
        path: resource for path, resource in resources_by_path.items() if resource.group in selected_groups
    }
    resolutions = _parse_resolutions(resolve_bundle_paths or set(), selected_resources)
    manifest_path = repo_path.resolve() / MANIFEST_PATH
    manifest = _load_manifest(manifest_path)
    if manifest_path.exists() and manifest is None:
        return _payload(
            dry_run,
            [
                ProjectionResult(
                    path=MANIFEST_PATH.as_posix(),
                    group="agents",
                    status="invalid_manifest",
                    message="managed projection manifest is unreadable or unsupported",
                )
            ],
        )

    files = manifest.get("files", {}) if manifest else {}
    legacy = _legacy_hashes()
    results: list[ProjectionResult] = []
    next_files = dict(files)

    for path, resource in selected_resources.items():
        destination = _destination(repo_path, path)
        entry = files.get(path.as_posix())
        result, installed_digest = _classify_resource(destination, resource, entry, legacy, path in resolutions)
        results.append(result)
        if result.status in {"created", "updated", "adopted"}:
            next_files[path.as_posix()] = _manifest_entry(resource, installed_digest)
            if not dry_run and result.status != "adopted":
                _atomic_write(destination, resource.content)
        elif result.status == "unchanged" and entry:
            next_files[path.as_posix()] = _manifest_entry(resource, resource.digest)

    for raw_path, entry in files.items():
        path = _safe_manifest_path(raw_path)
        if path is None or path in resources_by_path or entry.get("group") not in selected_groups:
            continue
        results.append(
            ProjectionResult(
                path=raw_path,
                group=entry["group"],
                status="retired",
                message="resource is no longer bundled and was preserved",
            )
        )

    if not dry_run and any(result.status in {"created", "updated", "adopted", "unchanged"} for result in results):
        _write_manifest(manifest_path, next_files, resources_by_path)

    return _payload(dry_run, results)


def projection_status(repo_path: Path) -> list[ProjectionResult]:
    payload = upgrade_claude_projection(repo_path, dry_run=True)
    return [
        ProjectionResult(
            path=item["path"],
            group=item["group"],
            status=item["status"],
            message=item["message"],
        )
        for item in payload["resources"]
    ]


def _classify_resource(
    destination: Path,
    resource: ProjectionResource,
    entry: object,
    legacy: dict[str, set[str]],
    resolve_bundle: bool,
) -> tuple[ProjectionResult, str]:
    if resolve_bundle:
        return ProjectionResult(resource.path.as_posix(), resource.group, "created" if not destination.exists() else "updated", "explicitly resolved with bundled content"), resource.digest
    if not destination.exists():
        if isinstance(entry, dict):
            return ProjectionResult(resource.path.as_posix(), resource.group, "missing", "managed resource is missing; use --resolve <path>=bundle to restore it"), ""
        return ProjectionResult(resource.path.as_posix(), resource.group, "created", "new bundled resource"), resource.digest

    current_digest = normalized_digest(destination.read_text(encoding="utf-8"))
    if isinstance(entry, dict):
        installed = entry.get("installed_sha256")
        if current_digest == resource.digest:
            status = "unchanged" if installed == resource.digest else "adopted"
            return ProjectionResult(resource.path.as_posix(), resource.group, status, "already matches bundled content"), resource.digest
        if current_digest == installed:
            return ProjectionResult(resource.path.as_posix(), resource.group, "updated", "unchanged managed resource can be upgraded"), resource.digest
        return ProjectionResult(resource.path.as_posix(), resource.group, "conflict", "managed resource has local changes"), ""

    if current_digest == resource.digest:
        return ProjectionResult(resource.path.as_posix(), resource.group, "adopted", "existing resource already matches bundled content"), resource.digest
    if current_digest in legacy.get(resource.path.as_posix(), set()):
        return ProjectionResult(resource.path.as_posix(), resource.group, "updated", "recognized legacy CodeLoom projection"), resource.digest
    return ProjectionResult(resource.path.as_posix(), resource.group, "unmanaged", "existing resource is not a recognized CodeLoom projection"), ""


def _payload(dry_run: bool, results: list[ProjectionResult]) -> dict[str, object]:
    resources = [
        {"path": result.path, "group": result.group, "status": result.status, "message": result.message}
        for result in sorted(results, key=lambda result: result.path)
    ]
    has_conflicts = any(result["status"] in {"conflict", "missing", "invalid_manifest"} for result in resources)
    return {
        "status": "conflict" if has_conflicts else "ok",
        "dry_run": dry_run,
        "bundle_version": __version__,
        "bundle_digest": _bundle_digest(bundled_claude_resources()),
        "resources": resources,
    }


def _parse_groups(group: str) -> set[ProjectionGroup]:
    if group == "all":
        return {"agents", "skills"}
    if group in {"agents", "skills"}:
        return {group}
    raise ValueError("group must be one of: all, agents, skills")


def _parse_resolutions(values: set[str], resources: dict[PurePosixPath, ProjectionResource]) -> set[PurePosixPath]:
    resolved: set[PurePosixPath] = set()
    for value in values:
        path, separator, target = value.partition("=")
        candidate = _safe_manifest_path(path)
        if separator != "=" or target != "bundle" or candidate is None or candidate not in resources:
            raise ValueError("--resolve must use a bundled relative path in the form <path>=bundle")
        resolved.add(candidate)
    return resolved


def _safe_manifest_path(value: object) -> PurePosixPath | None:
    if not isinstance(value, str):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return None
    return path


def _destination(repo_path: Path, path: PurePosixPath) -> Path:
    root = repo_path.resolve()
    destination = root.joinpath(*path.parts)
    resolved_parent = destination.parent.resolve()
    if root != resolved_parent and root not in resolved_parent.parents:
        raise ValueError("projection path escapes repository")
    if destination.is_symlink():
        raise ValueError("projection resource cannot be a symbolic link")
    return destination


def _manifest_entry(resource: ProjectionResource, installed_digest: str) -> dict[str, str]:
    return {
        "group": resource.group,
        "source": resource.source,
        "installed_sha256": installed_digest,
        "bundle_sha256": resource.digest,
        "bundle_version": __version__,
    }


def _bundle_digest(resources: tuple[ProjectionResource, ...]) -> str:
    value = "\n".join(f"{resource.path}:{resource.digest}" for resource in sorted(resources, key=lambda item: item.path.as_posix()))
    return normalized_digest(value)


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("schema") != MANIFEST_SCHEMA or data.get("integration") != "claude-code":
        return None
    files = data.get("files")
    if not isinstance(files, dict) or any(not isinstance(entry, dict) for entry in files.values()):
        return None
    return data


def _write_manifest(path: Path, files: dict[str, object], resources_by_path: dict[PurePosixPath, ProjectionResource]) -> None:
    payload = {
        "schema": MANIFEST_SCHEMA,
        "integration": "claude-code",
        "bundle": {"package_version": __version__, "bundle_digest": _bundle_digest(tuple(resources_by_path.values()))},
        "files": files,
    }
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _legacy_hashes() -> dict[str, set[str]]:
    try:
        data = json.loads(resources.files("codeloom.projections").joinpath("legacy_claude_code.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {path: set(hashes) for path, hashes in data.get("files", {}).items() if isinstance(hashes, list)}
