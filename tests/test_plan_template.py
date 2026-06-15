from __future__ import annotations

from codeloom.llm_clients.mock import MockLlmClient


def test_mock_plan_uses_plan_v1_shape():
    plan = MockLlmClient().draft_plan("# Spec\n\n## Requirement\nDo the thing.")

    assert "## 2. 目标与非目标" in plan
    assert "## 3. 当前状态" in plan
    assert "## 4. 目标设计" in plan
    assert "### 4.1 总体组件影响" in plan
    assert "## 11. 验证矩阵" in plan
    assert "## 12. 关键决策" in plan
    assert "## 14. 计划缺口与阻塞项" in plan
    assert "任务拆分依据" not in plan
    assert "任务就绪" not in plan
