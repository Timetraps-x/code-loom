from __future__ import annotations

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
