from __future__ import annotations

import json
from pathlib import Path

import pytest

from codeloom.spec_evals.__main__ import main


def test_cli_fixture_requires_output_dir(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2
    assert "--output-dir" in capsys.readouterr().err


def test_cli_fixture_writes_only_explicit_output_dir(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    assert main(["--case", "sim-service-term-sync", "--output-dir", "eval-output"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["runs"][0]["failed"] == 1
    assert list((tmp_path / "eval-output").iterdir())
    assert not (tmp_path / ".loom").exists()
    assert not (tmp_path / "specs").exists()
    assert not list(tmp_path.glob("*.db"))


def test_cli_rejects_live_fixture_and_missing_live_model(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--live", "--output-dir", "out"])
    assert exc_info.value.code == 2
    assert "--live is only valid" in capsys.readouterr().err

    with pytest.raises(SystemExit) as exc_info:
        main(["--executor", "anthropic", "--output-dir", "out"])
    assert exc_info.value.code == 2
    assert "--live is required" in capsys.readouterr().err


def test_cli_repeat_creates_distinct_runs(tmp_path: Path, capsys):
    assert main(["--repeat", "2", "--output-dir", str(tmp_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert len(payload["runs"]) == 2
    assert payload["runs"][0]["run_id"] != payload["runs"][1]["run_id"]
    assert len(list(tmp_path.iterdir())) == 2
