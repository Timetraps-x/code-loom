from __future__ import annotations

import json

from codeloom.app.init_project import init_project, load_project_config
from codeloom.cli.main import main
from tests.test_stage_flow import _init_git_repo


def repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _init_git_repo(path)
    return path


def test_init_discovers_nested_roots_without_head_or_business_labels(tmp_path):
    root = repo(tmp_path / "project")
    repo(root / "services/app")
    repo(root / "services/app/components/lib")
    repo(root / "client space")
    (root / ".gitignore").write_text("services/\nclient space/\n", encoding="utf-8")
    for excluded in ("node_modules", ".venv", "vendor", "build", ".loom"):
        repo(root / excluded / "unrelated")
    init_project(root)
    assert load_project_config(root).git_repositories == (".", "client space", "services/app", "services/app/components/lib")


def test_init_fills_missing_scope_preserving_existing_configuration(tmp_path):
    root = repo(tmp_path / "project")
    repo(root / "child")
    (root / ".loom").mkdir()
    original = b'# owner configuration\r\nprofile:\r\n  languages: "custom"\r\ncommands:\r\n  test: "custom test"\r\n'
    config = root / ".loom/project.yml"
    config.write_bytes(original)
    created, _ = init_project(root)
    assert not created
    assert config.read_bytes().startswith(original)
    assert load_project_config(root).git_repositories == (".", "child")
    assert load_project_config(root).commands["test"] == "custom test"


def test_existing_scope_is_preserved_until_explicit_refresh(tmp_path, capsys):
    root = repo(tmp_path / "project")
    init_project(root)
    path = root / ".loom/project.yml"
    original = path.read_bytes()
    repo(root / "child")
    init_project(root)
    assert path.read_bytes() == original
    assert load_project_config(root).git_repositories == (".",)
    assert main(["init", "--cwd", str(root), "--refresh-repositories", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["repositories_refreshed"] is True
    assert load_project_config(root).git_repositories == (".", "child")
    before_git = original.split(b"git:\n", 1)[0]
    assert path.read_bytes().startswith(before_git)


def test_force_preserves_explicit_repository_scope(tmp_path):
    root = repo(tmp_path / "project")
    init_project(root)
    repo(root / "child")
    init_project(root, force=True)
    assert load_project_config(root).git_repositories == (".",)


def test_init_non_git_directory_does_not_invent_scope(tmp_path, capsys):
    init_project(tmp_path)
    path = tmp_path / ".loom/project.yml"
    previous = path.read_bytes()
    assert load_project_config(tmp_path).git_repositories is None
    assert main(["init", "--cwd", str(tmp_path), "--refresh-repositories", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    assert path.read_bytes() == previous


def test_discovery_error_does_not_overwrite_existing_scope(tmp_path, capsys):
    root = repo(tmp_path / "project")
    init_project(root)
    config = root / ".loom/project.yml"
    previous = config.read_bytes()
    broken = root / "broken"
    broken.mkdir()
    (broken / ".git").write_text("gitdir: missing\n", encoding="utf-8")
    assert main(["init", "--cwd", str(root), "--refresh-repositories", "--json"]) == 1
    assert "invalid Git root" in json.loads(capsys.readouterr().out)["message"]
    assert config.read_bytes() == previous
