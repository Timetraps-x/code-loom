from __future__ import annotations

from typing import Protocol

from codeloom.spec_evals.models import AgentInvocation, AgentTurn


class SpecEvalExecutor(Protocol):
    name: str

    def invoke(self, invocation: AgentInvocation) -> AgentTurn:
        """Run one isolated evaluator turn without project/runtime access."""
        ...


class FixtureExecutor:
    """Deterministic executor for tests and safe dry runs."""

    name = "fixture"

    def __init__(self, responses: dict[tuple[str, int], str] | None = None) -> None:
        self.responses = responses or {}
        self.invocations: list[AgentInvocation] = []
        self._turns: dict[str, int] = {}

    def invoke(self, invocation: AgentInvocation) -> AgentTurn:
        self.invocations.append(invocation)
        turn_no = self._turns.get(invocation.role, 0) + 1
        self._turns[invocation.role] = turn_no
        content = self.responses.get((invocation.role, turn_no))
        if content is None:
            if invocation.role == "spec-reviewer":
                content = '{"findings": []}'
            elif turn_no > 1:
                content = json_revision(invocation.draft or "")
            else:
                content = invocation.draft or "# Fixture Spec\n\nNo live evaluator response supplied.\n"
        return AgentTurn(role=invocation.role, content=content, executor=self.name, model="fixture")


def json_revision(artifact: str) -> str:
    import json

    return json.dumps(
        {
            "dispositions": [],
            "final_artifact": artifact,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
