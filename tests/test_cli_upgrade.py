from __future__ import annotations

import json

from codeloom.app.init_project import init_project
from codeloom.cli.main import main


def test_cli_upgrade_dry_run_reports_managed_resources(tmp_path, capsys):
    init_project(tmp_path)
    capsys.readouterr()

    exit_code = main(["upgrade", "--cwd", str(tmp_path), "--claude-code", "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert any(resource["path"] == ".claude/agents/plan-architect.md" for resource in payload["resources"])


def test_cli_upgrade_requires_claude_code_scope(tmp_path):
    try:
        main(["upgrade", "--cwd", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("upgrade without --claude-code must fail")


def test_cli_upgrade_does_not_overwrite_project_configuration(tmp_path, capsys):
    init_project(tmp_path)
    project_path = tmp_path / ".loom" / "project.yml"
    project_path.write_text("project:\n  name: custom\n", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["upgrade", "--cwd", str(tmp_path), "--claude-code", "--json"])
    capsys.readouterr()

    assert exit_code == 0
    assert project_path.read_text(encoding="utf-8") == "project:\n  name: custom\n"
