from __future__ import annotations

from codeloom.kernel.clients import create_runtime_client


def test_claude_code_runtime_client_registered():
    client = create_runtime_client("claude-code")

    assert client.name == "claude-code"
    assert client.capabilities()["command"] == "claude -p"
