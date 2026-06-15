from __future__ import annotations

import subprocess

from codeloom.kernel.artifacts import TaskDefinition
from codeloom.kernel.clients import create_runtime_client
from codeloom.runtime_clients.claude_code import ClaudeCodeRuntimeClient


def test_claude_code_runtime_client_registered():
    client = create_runtime_client("claude-code")

    assert client.name == "claude-code"
    assert client.capabilities()["command"] == "claude -p --permission-mode acceptEdits"


def test_claude_code_runtime_treats_fail_output_as_failed(tmp_path, monkeypatch):
    commands = []

    def fake_run(command, cwd=None, capture_output=False, text=False, timeout=None):
        commands.append(command)
        if command[:3] == ["git", "status", "--short"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "FAIL — verification did not pass\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    task = TaskDefinition("T2", "Verify marker", "- [ ] T2: Verify marker", "fp", "verify")
    result = ClaudeCodeRuntimeClient().execute(tmp_path, task)

    assert not result.success
    assert result.summary == "Claude Code runtime failed T2"
    assert any(command[-2:] == ["--permission-mode", "acceptEdits"] for command in commands)


def test_claude_code_runtime_treats_markdown_fail_as_failed(tmp_path, monkeypatch):
    def fake_run(command, cwd=None, capture_output=False, text=False, timeout=None):
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "T2 验证结果：**FAIL**\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    task = TaskDefinition("T2", "Verify marker", "- [ ] T2: Verify marker", "fp", "verify")
    result = ClaudeCodeRuntimeClient().execute(tmp_path, task)

    assert not result.success

def test_claude_code_runtime_allows_pass_output_with_historical_blocked_text(tmp_path, monkeypatch):
    def fake_run(command, cwd=None, capture_output=False, text=False, timeout=None):
        if command[:3] == ["git", "status", "--short"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "PASS — prior blocked attempt was ignored as historical evidence\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    task = TaskDefinition("T2", "Verify marker", "- [ ] T2: Verify marker", "fp", "verify")
    result = ClaudeCodeRuntimeClient().execute(tmp_path, task)

    assert result.success


def test_claude_code_runtime_treats_permission_request_as_failed(tmp_path, monkeypatch):
    def fake_run(command, cwd=None, capture_output=False, text=False, timeout=None):
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "已阻塞：需要你批准写入文件后我才能继续\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    task = TaskDefinition("T1", "Build marker", "- [ ] T1: Build marker", "fp", "build")
    result = ClaudeCodeRuntimeClient().execute(tmp_path, task)

    assert not result.success
    assert result.summary == "Claude Code runtime failed T1"


def test_claude_code_runtime_collects_attempt_scoped_untracked_diff(tmp_path, monkeypatch):
    calls = {"status": 0}
    marker = tmp_path / "codeloom-chain-smoke.md"

    def fake_run(command, cwd=None, capture_output=False, text=False, timeout=None):
        if command[:3] == ["git", "status", "--short"]:
            calls["status"] += 1
            if calls["status"] == 1:
                return subprocess.CompletedProcess(command, 0, " M .idea/jarRepositories.xml\n", "")
            return subprocess.CompletedProcess(command, 0, " M .idea/jarRepositories.xml\n?? codeloom-chain-smoke.md\n", "")
        if command[:2] == ["git", "diff"]:
            return subprocess.CompletedProcess(command, 0, "diff --git a/.idea/jarRepositories.xml b/.idea/jarRepositories.xml\n", "")
        marker.write_text("This is a spec-plan-tasks-do-ship smoke test.\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "done\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    task = TaskDefinition("T1", "Build marker", "- [ ] T1: Build marker", "fp", "build")
    result = ClaudeCodeRuntimeClient().execute(tmp_path, task)

    assert result.success
    assert "codeloom-chain-smoke.md" in result.diff
    assert ".idea/jarRepositories.xml" not in result.diff
