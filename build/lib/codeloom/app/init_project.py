from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from codeloom.app.claude_plugin import install_claude_skills
from codeloom.app.managed_projection import initialize_claude_projection
from codeloom.kernel.snapshots import git_environment

from codeloom.persistence.sqlite import SQLiteStore


def _default_project_yml(
    language: str = "en",
    default_runtime: str = "claude-code",
    enabled_clients: set[str] | None = None,
) -> str:
    enabled_clients = enabled_clients or {default_runtime}
    claude_code_enabled = _yaml_bool("claude-code" in enabled_clients)
    codex_enabled = _yaml_bool("codex" in enabled_clients)
    opencode_enabled = _yaml_bool("opencode" in enabled_clients)
    return f"""project:
  name: codeloom-demo

artifacts:
  root: specs

specs:
  language: {language}

runtime:
  default: {default_runtime}
  clients:
    mock:
      enabled: true
    claude-code:
      enabled: {claude_code_enabled}
      mode: host
    codex:
      enabled: {codex_enabled}
      mode: cli
    opencode:
      enabled: {opencode_enabled}
      mode: sdk

profile:
  languages: ""
  frameworks: ""
  modules: ""

constitution:
  path: .loom/constitution.md
  hash: ""

commands:
  test: ""
  lint: ""
  typecheck: ""
  build: ""

rules:
  files:
    - CLAUDE.md
    - AGENTS.md
"""
DEFAULT_TEMPLATE_NAMES = (
    "spec-template.md",
    "plan-template.md",
    "tasks-template.md",
    "release-template.md",
    "constitution-template.md",
)

DEFAULT_POSITIVE_CASE_NAMES = (
    "java-spring-mybatis.md",
    "python-fastapi.md",
    "react-next.md",
    "go-http.md",
)

DEFAULT_AGENT_NAMES = (
    "code-reviewer.md",
    "adopt-expert.md",
    "spec-reviewer.md",
    "plan-reviewer.md",
    "task-reviewer.md",
)


@dataclass(frozen=True)
class ProjectConfig:
    artifact_root: str = "specs"
    spec_language: str = "en"
    default_runtime: str = "mock"
    constitution_path: str = ".loom/constitution.md"
    constitution_hash: str = ""
    languages: tuple[str, ...] = ()
    frameworks: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    commands: dict[str, str] = field(default_factory=lambda: {"test": "", "lint": "", "typecheck": "", "build": ""})
    git_repositories: tuple[str, ...] | None = None
    git_repositories_error: str = ""

def init_project(cwd: Path, force: bool = False, integrations: set[str] | None = None, language: str = "en", refresh_repositories: bool = False) -> tuple[bool, str]:
    repo_path = cwd.resolve()
    loom_dir = repo_path / ".loom"
    loom_dir.mkdir(parents=True, exist_ok=True)
    selected_integrations = integrations or {"claude-code"}
    default_runtime = "claude-code" if "claude-code" in selected_integrations else "mock"
    project_path = loom_dir / "project.yml"
    previous = project_path.read_bytes().decode("utf-8") if project_path.exists() else ""
    git_section = _git_configuration(previous)
    repositories = None
    if refresh_repositories or not git_section:
        repositories = _discover_git_repositories(repo_path)
        if refresh_repositories and not repositories:
            raise ValueError("repository refresh requires the project directory to be an outer Git root")
    created = not project_path.exists() or force
    content = _default_project_yml(language, default_runtime, selected_integrations) if created else previous
    if created and git_section:
        content = content.rstrip() + "\n\n" + git_section
    if repositories:
        newline = "\r\n" if "\r\n" in content else "\n"
        replacement = newline.join(["git:", "  repositories:",
                                    *[f"    - {json.dumps(path, ensure_ascii=False)}" for path in repositories]]) + newline
        existing = _git_configuration(content)
        content = content.replace(existing, replacement, 1) if existing else content.rstrip("\r\n") + newline * 2 + replacement
    if content != previous:
        project_path.write_bytes(content.encode("utf-8"))
    (loom_dir / "runs").mkdir(parents=True, exist_ok=True)
    _initialize_templates(repo_path, force=force)
    _initialize_constitution(repo_path)
    _initialize_positive_cases(repo_path, force=force)
    SQLiteStore(repo_path).initialize()
    if "claude-code" in selected_integrations:
        written_skills = {Path(path).resolve() for path in install_claude_skills(repo_path, force=force)}
        written_agents = _initialize_claude_agents(repo_path, force=force)
        initialize_claude_projection(repo_path, written_skills | written_agents)
    return created, str(project_path)


def _git_configuration(content: str) -> str:
    lines = content.splitlines(keepends=True)
    for start, line in enumerate(lines):
        if line.startswith("git:"):
            end = start + 1
            while end < len(lines) and (not lines[end].strip() or lines[end].startswith((" ", "\t"))):
                end += 1
            return "".join(lines[start:end])
    return ""


def _discover_git_repositories(project: Path) -> tuple[str, ...]:
    if not (project / ".git").exists():
        return ()
    excluded = {".git", ".loom", ".claude", "node_modules", "vendor", ".venv", "venv",
                "__pycache__", ".tox", ".cache", ".pytest_cache", ".mypy_cache",
                "build", "dist", "target", ".gradle"}
    roots = []
    def inaccessible(error: OSError) -> None:
        raise ValueError(f"repository discovery could not read {error.filename}: {error.strerror}")
    for directory, names, _ in os.walk(project, followlinks=False, onerror=inaccessible):
        root = Path(directory)
        names[:] = sorted(name for name in names if name not in excluded
                          and not (root / name).is_symlink() and (root / name).resolve() == (root / name).absolute())
        marker = root / ".git"
        if not marker.exists():
            continue
        if marker.is_symlink():
            raise ValueError(f"repository discovery does not follow symbolic Git metadata: {marker}")
        try:
            result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                                    env=git_environment(), capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"repository discovery failed at {root}: {exc}") from exc
        if result.returncode or Path(os.fsdecode(result.stdout).strip()).resolve() != root.resolve():
            raise ValueError(f"repository discovery found an invalid Git root: {root}")
        roots.append(root.relative_to(project).as_posix())
    return tuple(sorted(roots, key=lambda path: (len(Path(path).parts), path)))


def _yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _initialize_templates(repo_path: Path, force: bool = False) -> None:
    templates_dir = repo_path / ".loom" / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    bundled_templates = resources.files("codeloom.templates")
    for template_name in DEFAULT_TEMPLATE_NAMES:
        destination = templates_dir / template_name
        if destination.exists() and not force:
            continue
        content = bundled_templates.joinpath(template_name).read_text(encoding="utf-8")
        destination.write_text(content, encoding="utf-8")


def _initialize_constitution(repo_path: Path) -> None:
    constitution_path = repo_path / ".loom" / "constitution.md"
    if constitution_path.exists():
        return
    content = resources.files("codeloom.templates").joinpath("constitution-template.md").read_text(encoding="utf-8")
    constitution_path.write_text(content, encoding="utf-8")

def _initialize_positive_cases(repo_path: Path, force: bool = False) -> None:
    cases_dir = repo_path / ".loom" / "references" / "positive-cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    bundled_cases = resources.files("codeloom.quality_cases.positive")
    for case_name in DEFAULT_POSITIVE_CASE_NAMES:
        destination = cases_dir / case_name
        if destination.exists() and not force:
            continue
        content = bundled_cases.joinpath(case_name).read_text(encoding="utf-8")
        destination.write_text(content, encoding="utf-8")

def _initialize_claude_agents(repo_path: Path, force: bool = False) -> set[Path]:
    agents_dir = repo_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    bundled_agents = resources.files("codeloom.agents")
    written: set[Path] = set()
    for agent_name in DEFAULT_AGENT_NAMES:
        destination = agents_dir / agent_name
        if destination.exists() and not force:
            continue
        content = bundled_agents.joinpath(agent_name).read_text(encoding="utf-8")
        destination.write_text(content, encoding="utf-8")
        written.add(destination.resolve())
    return written


def load_project_config(cwd: Path) -> ProjectConfig:
    project_path = cwd.resolve() / ".loom" / "project.yml"
    if not project_path.exists():
        return ProjectConfig()
    artifact_root = "specs"
    spec_language = "en"
    default_runtime = "mock"
    commands = {"test": "", "lint": "", "typecheck": "", "build": ""}
    constitution_path = ".loom/constitution.md"
    constitution_hash = ""
    profile = {"languages": (), "frameworks": (), "modules": ()}
    repositories: list[str] | None = None
    repositories_error = ""
    repository_list = False
    git_section_seen = False
    section: str | None = None
    for raw_line in project_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw_line.startswith(" "):
            section = stripped[:-1] if stripped.endswith(":") else None
            repository_list = False
            if stripped.startswith("git:") and stripped != "git:":
                repositories_error = "git configuration must use an indented repositories block list"
            if stripped == "git:":
                if git_section_seen:
                    repositories_error = "duplicate git configuration"
                git_section_seen = True
            continue
        if section == "git":
            if stripped.startswith("repositories:"):
                if repositories is not None or _value(stripped):
                    repositories_error = "git.repositories must be a single block list"
                repositories = []
                repository_list = True
            elif repository_list and raw_line.startswith("    - "):
                value = stripped[2:].strip()
                try:
                    if value.startswith('"'):
                        value = json.loads(value)
                    elif value.startswith("'"):
                        if not value.endswith("'"):
                            raise ValueError("unclosed repository path quote")
                        value = value[1:-1].replace("''", "'")
                    repositories.append(value)
                except ValueError:
                    repositories_error = "invalid quoted git.repositories path"
            else:
                repositories_error = "invalid git.repositories entry; use project-relative paths in a block list"
        elif section == "artifacts" and stripped.startswith("root:"):
            artifact_root = _value(stripped)
        elif section == "specs" and stripped.startswith("language:"):
            spec_language = _value(stripped) or "en"
        elif section == "runtime" and stripped.startswith("default:"):
            default_runtime = _value(stripped)
        elif section == "profile" and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key in profile:
                profile[key] = _csv_values(value)
        elif section == "constitution" and stripped.startswith("path:"):
            constitution_path = _value(stripped) or ".loom/constitution.md"
        elif section == "constitution" and stripped.startswith("hash:"):
            constitution_hash = _value(stripped)
        elif section == "commands" and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key in commands:
                commands[key] = _clean(value)
    if git_section_seen and repositories is None:
        repositories_error = "git.repositories block list is missing"
    return ProjectConfig(
        artifact_root=artifact_root,
        spec_language=spec_language,
        default_runtime=default_runtime,
        constitution_path=constitution_path,
        constitution_hash=constitution_hash,
        languages=profile["languages"],
        frameworks=profile["frameworks"],
        modules=profile["modules"],
        commands=commands,
        git_repositories=tuple(repositories) if repositories is not None else None,
        git_repositories_error=repositories_error,
    )


def _value(line: str) -> str:
    return _clean(line.split(":", 1)[1])


def _csv_values(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in _clean(value).split(",") if item.strip())


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'")
