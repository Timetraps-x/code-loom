from __future__ import annotations

import json

from codeloom.app.init_project import load_project_config
from codeloom.cli.main import main


def _write_spec_artifact(repo):
    spec_path = repo / "specs" / "master" / "spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("# Spec\n\n## Requirement\nCLI spec\n", encoding="utf-8")

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

    _write_spec_artifact(tmp_path)
    exit_code = main([
        "stage",
        "spec",
        "--cwd",
        str(tmp_path),
        "--branch",
        "master",
        "--arg",
        "artifact_file=specs/master/spec.md",
        "--json",
    ])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["recommended_next"] == "/loom-plan"


def test_cli_stage_spec_without_artifact_file_reports_host_handoff(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["stage", "spec", "--cwd", str(tmp_path), "--branch", "master", "--json"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 1
    assert payload["status"] == "blocked"
    assert payload["errors"] == ["host_artifact_required"]
    assert payload["recommended_next"] == "/loom-spec"
    assert payload["extras"]["main_agent"] == "spec-analyzer"
    assert payload["extras"]["artifact_path"] == "specs/master/spec.md"

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
    _write_spec_artifact(tmp_path)
    main(["stage", "spec", "--cwd", str(tmp_path), "--branch", "master", "--arg", "artifact_file=specs/master/spec.md"])
    capsys.readouterr()

    exit_code = main(["status", "--cwd", str(tmp_path), "--branch", "master"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Status: ok" in output
    assert "Recommended next: /loom-plan" in output
    assert "Artifacts:" in output
    assert "Constitution: present matched" in output


def test_doctor_reports_warning_not_large_json_by_default(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["doctor", "--cwd", str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("Status: warning")
    assert "verification commands" in output
    assert "constitution" in output
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
    assert any(check["name"] == "constitution" for check in payload["checks"])
