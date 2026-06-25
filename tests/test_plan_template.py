from __future__ import annotations

from importlib import resources

from codeloom.llm_clients.mock import MockLlmClient


def test_mock_plan_uses_plan_v1_shape():
    plan = MockLlmClient().draft_plan("# Spec\n\n## Requirement\nDo the thing.")

    assert "## 2. Goals and Non-Goals" in plan
    assert "## 3. Current State" in plan
    assert "## 4. Target Design" in plan
    assert "### 4.1 Component Impact" in plan
    assert "## 11. Validation Matrix" in plan
    assert "## 12. Key Decisions" in plan
    assert "## 14. Plan Gaps and Blockers" in plan
    assert "task slicing rationale" not in plan
    assert "task readiness" not in plan


def test_mock_plan_uses_zh_when_configured():
    plan = MockLlmClient().draft_plan("# 规格\n\n## 需求\n做这件事。", language="zh")

    assert "## 2. 目标与非目标" in plan
    assert "## 11. 验证矩阵" in plan


def _template(name: str) -> str:
    return resources.files("codeloom.templates").joinpath(name).read_text(encoding="utf-8")


def test_templates_preserve_coding_goal_anchors():
    spec = _template("spec-template.md")
    plan = _template("plan-template.md")
    tasks = _template("tasks-template.md")
    release = _template("release-template.md")

    for expected in (
        "Observable Success",
        "Observable Failure",
        "Do not write only \"support\", \"optimize\", \"improve\", or \"complete a capability\" without concrete evidence",
    ):
        assert expected in spec

    for expected in (
        "Existing System Path",
        "Boundary Map",
        "null/fallback cases are real external boundaries, legal business states, historical dirty data, or invariant violations",
        "Upstream Entry",
        "Downstream Consumer",
        "Shared Component Regression",
        "State & Failure",
        "Delivery",
    ):
        assert expected in plan

    for expected in (
        "Complexity",
        "Allowed:",
        "Forbidden:",
        "Covered by: Tn",
        "Validates: Tn",
        "## 4. Verification Coverage Map",
        "agent/human context, not Kernel metadata",
        "material impacted regression surfaces",
        "without changing build task granularity",
        "## 5. Execution Order",
        "## 6. Task List",
        "## 7. Task Notes",
        "## 8. Global Notes",
        "Do not expand scope inside the task",
    ):
        assert expected in tasks

    for expected in (
        "Not Verified",
        "Change Inventory",
        "Risks can be accepted only when the user or release owner explicitly accepted them",
        "ready_for_release",
        "blockers",
        "owner_decisions",
    ):
        assert expected in release


def test_tasks_template_declares_kernel_metadata_contract():
    tasks = _template("tasks-template.md")

    for expected in (
        "`/loom:do` parses checklist tasks and their immediate metadata as the runtime source of truth",
        "- [ ] T1: <task title>",
        "  - Lane: build | verify",
        "  - Complexity: trivial | small | non-trivial",
        "Task Notes` are for agents and humans",
        "Task List metadata is the runtime source of truth",
    ):
        assert expected in tasks

def test_agent_templates_define_main_and_subagent_contracts():
    main_agent = _template("agent-template.md")
    subagent = _template("subagent-template.md")

    for expected in (
        "Canonical template for CodeLoom stage-owner agents",
        "description: Use this agent to <create/revise/execute/verify/release> <stage artifact or stage work>.",
        "A subagent result is evidence, not authority",
        "Do not delegate the stage decision, artifact ownership, or readiness conclusion to a subagent",
        "Intent",
        "Boundary",
        "Task",
        "Evidence",
        "Readiness",
    ):
        assert expected in main_agent

    for expected in (
        "Canonical template for CodeLoom bounded specialist agents",
        "You do not own the stage artifact or readiness decision",
        "Do not make final stage readiness decisions",
        "Do not turn missing evidence into a positive claim",
        "- finding:",
        "- evidence:",
        "- uncertainty:",
        "- impact:",
    ):
        assert expected in subagent