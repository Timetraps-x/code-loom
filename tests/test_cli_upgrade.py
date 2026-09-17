from __future__ import annotations

import json

from codeloom.app.init_project import init_project
from codeloom.cli.main import main
from codeloom.app.managed_projection import MANIFEST_PATH, normalized_digest


def test_cli_upgrade_dry_run_reports_managed_resources(tmp_path, capsys):
    init_project(tmp_path)
    capsys.readouterr()

    exit_code = main(["upgrade", "--cwd", str(tmp_path), "--claude-code", "--dry-run", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert any(resource["path"] == ".claude/skills/loom-plan/references/main-role.md" for resource in payload["resources"])


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


def test_cli_upgrade_reports_and_resolves_modified_retired_owner_agent(tmp_path, capsys):
    init_project(tmp_path)
    agent_path = tmp_path / ".claude" / "agents" / "plan-architect.md"
    agent_path.write_text("managed owner\n", encoding="utf-8")
    manifest_path = tmp_path / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][".claude/agents/plan-architect.md"] = {
        "group": "agents",
        "source": "codeloom.agents/plan-architect.md",
        "installed_sha256": normalized_digest("managed owner\n"),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    agent_path.write_text("custom owner\n", encoding="utf-8")
    capsys.readouterr()

    conflict_exit = main(["upgrade", "--cwd", str(tmp_path), "--claude-code", "--json"])
    conflict = json.loads(capsys.readouterr().out)

    assert conflict_exit == 1
    assert conflict["status"] == "conflict"
    assert next(
        item for item in conflict["resources"] if item["path"] == ".claude/agents/plan-architect.md"
    )["status"] == "migration_conflict"
    assert agent_path.exists()

    resolved_exit = main([
        "upgrade",
        "--cwd",
        str(tmp_path),
        "--claude-code",
        "--resolve",
        ".claude/agents/plan-architect.md=remove",
        "--json",
    ])
    resolved = json.loads(capsys.readouterr().out)

    assert resolved_exit == 0
    assert resolved["status"] == "ok"
    assert not agent_path.exists()