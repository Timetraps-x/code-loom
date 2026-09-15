from __future__ import annotations

import time
from typing import Any

from codeloom.spec_evals.models import AgentInvocation, AgentTurn


class AnthropicSpecEvalExecutor:
    name = "anthropic"

    def __init__(self, model: str, max_tokens: int = 4096) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("install the spec-eval-llm extra to use the Anthropic executor") from exc
        self.model = model
        self.max_tokens = max_tokens
        self.client = Anthropic()

    def invoke(self, invocation: AgentInvocation) -> AgentTurn:
        started = time.perf_counter()
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": invocation.prompt}],
        )
        content = "\n".join(text for text in (_text_block(block) for block in message.content) if text)
        usage = getattr(message, "usage", None)
        return AgentTurn(
            role=invocation.role,
            content=content,
            executor=self.name,
            model=str(getattr(message, "model", self.model)),
            request_id=str(getattr(message, "id", "")) or None,
            input_tokens=_usage_value(usage, "input_tokens"),
            output_tokens=_usage_value(usage, "output_tokens"),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )


def _text_block(block: Any) -> str:
    if isinstance(block, dict):
        return str(block.get("text") or "")
    return str(getattr(block, "text", "") or "")


def _usage_value(usage: Any, name: str) -> int | None:
    value = getattr(usage, name, None)
    return int(value) if value is not None else None
