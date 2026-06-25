from __future__ import annotations

from codeloom.kernel.artifacts import TaskDefinition
from codeloom.kernel.clients import create_runtime_client
from codeloom.runtime_clients.claude_code import ClaudeCodeRuntimeClient


def test_claude_code_runtime_client_registered_as_host_runtime():
    client = create_runtime_client("claude-code")

    assert client.name == "claude-code"
    assert client.capabilities()["mode"] == "host"
    assert client.capabilities()["sync"] is False


def test_claude_code_runtime_does_not_launch_nested_cli(tmp_path, monkeypatch):
    def fail_run(*args, **kwargs):
        raise AssertionError("claude-code host runtime must not launch subprocesses")

    monkeypatch.setattr("subprocess.run", fail_run)

    task = TaskDefinition("T1", "Build marker", "- [ ] T1: Build marker", "fp", "build")
    result = ClaudeCodeRuntimeClient().execute(tmp_path, task)

    assert not result.success
    assert result.summary == "Claude Code host runtime requires begin/complete handoff"
    assert result.stderr == "host runtime does not execute via nested claude CLI"
