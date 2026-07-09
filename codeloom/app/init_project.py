from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from codeloom.app.claude_plugin import install_claude_skills
from codeloom.app.constitution import register_constitution

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
    "spec-analyzer.md",
    "plan-architect.md",
    "task-planner.md",
    "builder.md",
    "verifier.md",
    "release-analyzer.md",
    "code-reviewer.md",
    "scout.md",
    "codebase-scout.md",
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
    commands: dict[str, str] = field(default_factory=lambda: {"test": "", "lint": "", "typecheck": "", "build": ""})

def init_project(cwd: Path, force: bool = False, integrations: set[str] | None = None, language: str = "en") -> tuple[bool, str]:
    repo_path = cwd.resolve()
    loom_dir = repo_path / ".loom"
    loom_dir.mkdir(parents=True, exist_ok=True)
    selected_integrations = integrations or {"claude-code"}
    default_runtime = "claude-code" if "claude-code" in selected_integrations else "mock"
    project_path = loom_dir / "project.yml"
    if project_path.exists() and not force:
        created = False
    else:
        project_path.write_text(
            _default_project_yml(language, default_runtime, selected_integrations),
            encoding="utf-8",
        )
        created = True
    (loom_dir / "runs").mkdir(parents=True, exist_ok=True)
    _initialize_templates(repo_path, force=force)
    _initialize_constitution(repo_path)
    _initialize_positive_cases(repo_path, force=force)
    register_constitution(repo_path)
    SQLiteStore(repo_path).initialize()
    if "claude-code" in selected_integrations:
        install_claude_skills(repo_path, force=force)
        _initialize_claude_agents(repo_path, force=force)
    return created, str(project_path)


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

def _initialize_claude_agents(repo_path: Path, force: bool = False) -> None:
    agents_dir = repo_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    bundled_agents = resources.files("codeloom.agents")
    for agent_name in DEFAULT_AGENT_NAMES:
        destination = agents_dir / agent_name
        if destination.exists() and not force:
            continue
        content = bundled_agents.joinpath(agent_name).read_text(encoding="utf-8")
        destination.write_text(content, encoding="utf-8")


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
        elif section == "specs" and stripped.startswith("language:"):
            spec_language = _value(stripped) or "en"
        elif section == "runtime" and stripped.startswith("default:"):
            default_runtime = _value(stripped)
        elif section == "constitution" and stripped.startswith("path:"):
            constitution_path = _value(stripped) or ".loom/constitution.md"
        elif section == "constitution" and stripped.startswith("hash:"):
            constitution_hash = _value(stripped)
        elif section == "commands" and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key in commands:
                commands[key] = _clean(value)
    return ProjectConfig(
        artifact_root=artifact_root,
        spec_language=spec_language,
        default_runtime=default_runtime,
        constitution_path=constitution_path,
        constitution_hash=constitution_hash,
        commands=commands,
    )


def _value(line: str) -> str:
    return _clean(line.split(":", 1)[1])


def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'")
