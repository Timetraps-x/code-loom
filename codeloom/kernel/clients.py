from __future__ import annotations

from codeloom.kernel.llm import LlmClient
from codeloom.kernel.runtime import RuntimeClient
from codeloom.llm_clients.mock import MockLlmClient
from codeloom.runtime_clients.claude_code import ClaudeCodeRuntimeClient
from codeloom.runtime_clients.mock import MockRuntimeClient


def create_llm_client(name: str = "mock") -> LlmClient:
    if name == "mock":
        return MockLlmClient()
    raise ValueError(f"unsupported LLM client: {name}")


def create_runtime_client(name: str = "mock") -> RuntimeClient:
    if name == "mock":
        return MockRuntimeClient()
    if name == "claude-code":
        return ClaudeCodeRuntimeClient()
    raise ValueError(f"unsupported runtime client: {name}")
