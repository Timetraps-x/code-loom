from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from codeloom.app.claude_plugin import install_claude_skills

from codeloom.persistence.sqlite import SQLiteStore


DEFAULT_PROJECT_YML = """project:
  name: codeloom-demo

artifacts:
  root: specs

runtime:
  default: mock
  clients:
    mock:
      enabled: true
    claude-code:
      enabled: false
      mode: cli
    codex:
      enabled: false
      mode: cli
    opencode:
      enabled: false
      mode: sdk

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


@dataclass(frozen=True)
class ProjectConfig:
    artifact_root: str = "specs"
    default_runtime: str = "mock"
    commands: dict[str, str] = field(default_factory=lambda: {"test": "", "lint": "", "typecheck": "", "build": ""})


def init_project(cwd: Path, force: bool = False, integrations: set[str] | None = None) -> tuple[bool, str]:
    repo_path = cwd.resolve()
    project_path = repo_path / "project.yml"
    if project_path.exists() and not force:
        created = False
    else:
        project_path.write_text(DEFAULT_PROJECT_YML, encoding="utf-8")
        created = True
    (repo_path / ".loom" / "runs").mkdir(parents=True, exist_ok=True)
    SQLiteStore(repo_path).initialize()
    selected_integrations = integrations or {"claude-code"}
    if "claude-code" in selected_integrations:
        install_claude_skills(repo_path, force=force)
    return created, str(project_path)


def load_project_config(cwd: Path) -> ProjectConfig:
    project_path = cwd.resolve() / "project.yml"
    if not project_path.exists():
        return ProjectConfig()
    artifact_root = "specs"
    default_runtime = "mock"
    commands = {"test": "", "lint": "", "typecheck": "", "build": ""}
    section: str | None = None
    for raw_line in project_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw_line.startswith(" ") and stripped.endswith(":"):
            section = stripped[:-1]
            continue
        if section == "artifacts" and stripped.startswith("root:"):
            artifact_root = _value(stripped)
        elif section == "runtime" and stripped.startswith("default:"):
            default_runtime = _value(stripped)
        elif section == "commands" and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key in commands:
                commands[key] = _clean(value)
    return ProjectConfig(artifact_root=artifact_root, default_runtime=default_runtime, commands=commands)


def _value(line: str) -> str:
    return _clean(line.split(":", 1)[1])


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'")
