from __future__ import annotations

import json

from codeloom.app.init_project import load_project_config
from codeloom.cli.main import main


def test_cli_defaults_to_human_output(tmp_path, capsys):
    exit_code = main(["init", "--cwd", str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("Status: ok")
    assert not output.lstrip().startswith("{")
    assert load_project_config(tmp_path).default_runtime == "claude-code"


def test_cli_json_flag_emits_compact_json(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["stage", "spec", "--cwd", str(tmp_path), "--branch", "master", "--json"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["recommended_next"] == "/loom-plan"

def test_init_accepts_integration_flags(tmp_path, capsys):
    exit_code = main([
        "init",
        "--cwd",
        str(tmp_path),
        "--claude-code",
        "--codex",
        "--opencode",
        "--json",
    ])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["integrations"] == ["claude-code", "codex", "opencode"]

def test_status_reports_branch_summary(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    main(["stage", "spec", "--cwd", str(tmp_path), "--branch", "master"])
    capsys.readouterr()

    exit_code = main(["status", "--cwd", str(tmp_path), "--branch", "master"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Status: ok" in output
    assert "Recommended next: /loom-plan" in output
    assert "Artifacts:" in output


def test_doctor_reports_warning_not_large_json_by_default(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["doctor", "--cwd", str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("Status: warning")
    assert "verification commands" in output
    assert not output.lstrip().startswith("{")


def test_doctor_json_is_available(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["doctor", "--cwd", str(tmp_path), "--json"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["status"] == "warning"
    assert payload["checks"]
