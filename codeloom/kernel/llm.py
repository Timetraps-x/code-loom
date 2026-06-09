from __future__ import annotations

from typing import Protocol


class LlmClient(Protocol):
    def draft_spec(self, requirement: str, existing_spec: str | None = None) -> str:
        ...

    def draft_plan(self, spec: str, constraints: str | None = None) -> str:
        ...

    def draft_tasks(self, spec: str, plan: str, preference: str | None = None) -> str:
        ...

    def draft_ship_summary(self, facts: dict[str, object]) -> str:
        ...

    def explain_failure(self, context: str) -> str:
        ...
