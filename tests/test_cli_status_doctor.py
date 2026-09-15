from __future__ import annotations

import json

import pytest

from codeloom.app.init_project import load_project_config
from codeloom.cli.main import main


def _write_spec_artifact(repo):
    spec_path = repo / "specs" / "master" / "spec.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("# Spec\n\n## Requirement\nCLI spec\n", encoding="utf-8")


def test_cli_version_flags(capsys):
    with pytest.raises(SystemExit) as long_exit:
        main(["--version"])
    assert long_exit.value.code == 0
    assert capsys.readouterr().out.strip() == "codeloom 0.5.1"

    with pytest.raises(SystemExit) as short_exit:
        main(["-v"])
    assert short_exit.value.code == 0
    assert capsys.readouterr().out.strip() == "codeloom 0.5.1"

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

    assert exit_code == 0
    assert payload["status"] == "noop"
    assert payload["errors"] == []
    assert payload["recommended_next"] == "/loom-spec"
    assert payload["extras"]["handoff"] == "author_artifact"
    assert payload["extras"]["main_agent"] == "spec-analyzer"
    assert payload["extras"]["artifact_path"] == "specs/master/spec.md"
    assert payload["extras"]["register_command"] == "loom stage spec --branch master --arg artifact_file=specs/master/spec.md"

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
    assert "Constitution: seeded/unadopted" in output


def test_status_reports_project_profile(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    project_path = tmp_path / ".loom" / "project.yml"
    project_path.write_text(
        project_path.read_text(encoding="utf-8")
        .replace('languages: ""', 'languages: "Python, TypeScript"')
        .replace('frameworks: ""', 'frameworks: "FastAPI, React"')
        .replace('modules: ""', 'modules: "api, web"'),
        encoding="utf-8",
    )
    capsys.readouterr()

    exit_code = main(["status", "--cwd", str(tmp_path), "--branch", "master"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Project profile: Python, TypeScript, FastAPI, React, api, web" in output


def test_status_reports_continuation_route_without_open_finding(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    _write_spec_artifact(tmp_path)
    main([
        "stage",
        "spec",
        "--cwd",
        str(tmp_path),
        "--branch",
        "master",
        "--arg",
        "artifact_file=specs/master/spec.md",
    ])
    route_exit = main([
        "stage",
        "plan",
        "--cwd",
        str(tmp_path),
        "--branch",
        "master",
        "--arg",
        "action=route",
        "--arg",
        "target_stage=spec",
        "--arg",
        "reason=requirement meaning needs revision",
    ])
    capsys.readouterr()

    status_exit = main(["status", "--cwd", str(tmp_path), "--branch", "master"])
    output = capsys.readouterr().out

    assert route_exit == 0
    assert status_exit == 0
    assert "Recommended next: /loom-spec" in output
    assert "Continuation: plan -> spec: requirement meaning needs revision" in output
    assert "Open findings: 0" in output


def test_doctor_reports_warning_not_large_json_by_default(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    capsys.readouterr()

    exit_code = main(["doctor", "--cwd", str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("Status: warning")
    assert "verification commands" in output
    assert "constitution: seeded/unadopted" in output
    assert not output.lstrip().startswith("{")


def test_doctor_distinguishes_registered_and_changed_constitution(tmp_path, capsys):
    main(["init", "--cwd", str(tmp_path)])
    constitution_path = tmp_path / ".loom" / "constitution.md"
    constitution_path.write_text("# Project Constitution\n\n- Services own transitions.\n", encoding="utf-8")
    assert main(["adopt", "--cwd", str(tmp_path), "--json"]) == 0
    capsys.readouterr()

    assert main(["doctor", "--cwd", str(tmp_path)]) == 0
    registered_output = capsys.readouterr().out
    assert "constitution: registered" in registered_output

    constitution_path.write_text("# Project Constitution\n\n- Revised service ownership.\n", encoding="utf-8")
    assert main(["doctor", "--cwd", str(tmp_path)]) == 0
    changed_output = capsys.readouterr().out
    assert "constitution: hash mismatch" in changed_output


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
