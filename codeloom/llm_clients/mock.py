from __future__ import annotations

from codeloom.kernel.llm import LlmClient


class MockLlmClient(LlmClient):
    def draft_spec(self, requirement: str, existing_spec: str | None = None) -> str:
        revision = "\n\n## Revision Note\n" + existing_spec.strip() if existing_spec else ""
        requirement_text = requirement.strip() or "No requirement text provided."
        return f"# Spec\n\n## Requirement\n{requirement_text}{revision}\n"

    def draft_plan(self, spec: str, constraints: str | None = None) -> str:
        constraint_block = f"\n\n## Constraints\n{constraints.strip()}" if constraints else ""
        return (
            "# Plan\n\n"
            "## Source Spec\n"
            f"{spec.strip()}\n\n"
            "## Approach\n"
            "Implement the smallest change that satisfies the current spec.\n\n"
            "## Verification\n"
            "Run configured test, lint, typecheck, and build commands when present."
            f"{constraint_block}\n"
        )

    def draft_tasks(self, spec: str, plan: str, preference: str | None = None) -> str:
        preference_block = f"\n\n## Notes\n{preference.strip()}" if preference else ""
        return (
            "# Tasks\n\n"
            "- [ ] T1: Implement current CodeLoom requirement\n"
            "- [ ] T2: Verify current CodeLoom requirement\n"
            f"{preference_block}\n"
        )

    def draft_ship_summary(self, facts: dict[str, object]) -> str:
        status = facts.get("status", "blocked")
        completed = facts.get("completed_tasks", [])
        findings = facts.get("open_findings", [])
        evidence = facts.get("runtime_refs", [])
        return (
            "# Ship Summary\n\n"
            "## Conclusion\n"
            f"- Status: {status}\n\n"
            "## Scope\n"
            f"- Based on spec.md: {facts.get('spec_hash', '')}\n"
            f"- Based on plan.md: {facts.get('plan_hash', '')}\n"
            f"- Based on tasks.md: {facts.get('tasks_hash', '')}\n\n"
            "## Completed Tasks\n"
            + "\n".join(f"- {task}" for task in completed)
            + "\n\n## Verification Summary\n"
            + str(facts.get("verification_summary", ""))
            + "\n\n## Open Findings\n"
            + ("\n".join(f"- {finding}" for finding in findings) or "- None")
            + "\n\n## Runtime Evidence References\n"
            + ("\n".join(f"- {ref}" for ref in evidence) or "- None")
            + "\n"
        )

    def explain_failure(self, context: str) -> str:
        return f"Mock failure explanation: {context}"
