from __future__ import annotations

from pathlib import Path

from codeloom.app.init_project import init_project
from codeloom.app.request import KernelRequest
from codeloom.app.stages import StageRunner

BRANCH = "master"


def init_repo(path: Path) -> Path:
    init_project(path)
    return path


def run_stage(repo_path: Path, command: str, branch: str = BRANCH, **args: str):
    return StageRunner().run(KernelRequest(repo_path, branch, command, args))


def write_project_config(repo_path: Path, test_command: str = "", runtime: str = "mock") -> None:
    repo_path.joinpath("project.yml").write_text(
        f"""project:
  name: codeloom-test

artifacts:
  root: specs

runtime:
  default: {runtime}
  clients:
    mock:
      enabled: true
    claude-code:
      enabled: true
      mode: cli

commands:
  test: {test_command}
  lint: ""
  typecheck: ""
  build: ""
""",
        encoding="utf-8",
    )
