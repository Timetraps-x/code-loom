from __future__ import annotations

from codeloom.kernel.llm import LlmClient


class MockLlmClient(LlmClient):
    def draft_spec(self, requirement: str, existing_spec: str | None = None) -> str:
        revision = "\n\n## Revision Note\n" + existing_spec.strip() if existing_spec else ""
        requirement_text = requirement.strip() or "No requirement text provided."
        return f"# Spec\n\n## Requirement\n{requirement_text}{revision}\n"

    def draft_plan(self, spec: str, constraints: str | None = None) -> str:
        constraints_text = constraints.strip() if constraints else "None"
        return (
            "# CodeLoom 技术方案\n\n"
            "based_on_spec_hash: `<mock>`\n\n"
            "## 1. 背景\n\n"
            f"本方案基于当前 spec 生成，作为规格到可执行任务的技术桥接。\n\n{spec.strip()}\n\n"
            "## 2. 目标与非目标\n\n"
            "### 2.1 目标\n\n"
            "- Implement a complete scoped change that satisfies the current spec without unrelated expansion.\n\n"
            "### 2.2 非目标\n\n"
            "- Do not introduce unrelated abstractions or workflow state.\n\n"
            "## 3. 当前状态\n\n"
            "- Mock mode does not inspect repository internals.\n\n"
            "## 4. 目标设计\n\n"
            "### 4.1 总体组件影响\n\n"
            "N/A，原因：mock fallback does not infer component boundaries.\n\n"
            "## 5. 交互与流程设计\n\n"
            "N/A，原因：mock fallback does not infer interaction flows.\n\n"
            "## 6. 数据、状态与一致性设计\n\n"
            "N/A，原因：mock fallback does not infer data or state changes.\n\n"
            "## 7. API / 页面 / 接口契约设计\n\n"
            "N/A，原因：mock fallback does not infer external contracts.\n\n"
            "## 8. 并发、事务与一致性设计\n\n"
            "N/A，原因：mock fallback does not infer consistency risks.\n\n"
            "## 9. 风险控制\n\n"
            "| 风险 | 控制措施 | 验证 |\n"
            "|---|---|---|\n"
            "| 方案过宽 | 在 spec 边界内完整实现，避免无关扩展 | 运行配置的验证命令 |\n\n"
            "## 10. 发布与回滚\n\n"
            "N/A，原因：mock fallback does not infer rollout requirements.\n\n"
            "## 11. 验证矩阵\n\n"
            "| 验收 | 验证方式 | 证据 |\n"
            "|---|---|---|\n"
            "| AC-1 | Run configured test, lint, typecheck, and build commands when present. | Command output |\n\n"
            "## 12. 关键决策\n\n"
            "- Use the current CodeLoom Phase 1 artifact flow for downstream design registration.\n\n"
            "## 13. 替代方案与取舍\n\n"
            "### 13.1 Add a broader architecture layer\n\n"
            "放弃原因：Phase 1 favors narrow changes over speculative abstractions.\n\n"
            "## 14. 计划缺口与阻塞项\n\n"
            "### 14.1 已解决的开放问题\n\n"
            "- None\n\n"
            "### 14.2 阻塞项\n\n"
            "- None\n\n"
            "### 14.3 注意事项\n\n"
            f"- 外部约束：{constraints_text}\n"
        )

    def draft_tasks(self, spec: str, plan: str, preference: str | None = None) -> str:
        preference_block = f"\n\n## Notes\n{preference.strip()}" if preference else ""
        return (
            "# Tasks\n\n"
            "## build\n\n"
            "- [ ] T1: Implement current CodeLoom requirement\n"
            "  - Lane: build\n"
            "  - Covered by: T2\n\n"
            "## verify\n\n"
            "- [ ] T2: Verify current CodeLoom requirement\n"
            "  - Lane: verify\n"
            "  - Validates: T1\n"
            f"{preference_block}\n"
        )

    def draft_ship_summary(self, facts: dict[str, object]) -> str:
        status = facts.get("status", "blocked")
        completed = facts.get("completed_tasks", [])
        findings = facts.get("open_findings", [])
        evidence = facts.get("runtime_refs", [])
        return (
            "# Release Plan\n\n"
            "## 1. Release Conclusion\n"
            f"- Status: {status}\n"
            "- Decision reason: derived from CodeLoom task verification and open findings.\n\n"
            "## 2. Change Summary\n"
            "- Generated from completed tasks and runtime evidence.\n\n"
            "## 3. Completed Tasks\n"
            + ("\n".join(f"- {task}" for task in completed) or "- None")
            + "\n\n## 4. Verification Summary\n"
            + str(facts.get("verification_summary", ""))
            + "\n\n## 5. Open Findings\n"
            + ("\n".join(f"- {finding}" for finding in findings) or "- None")
            + "\n\n## 6. Runtime Evidence References\n"
            + ("\n".join(f"- {ref}" for ref in evidence) or "- None")
            + "\n"
        )

    def explain_failure(self, context: str) -> str:
        return f"Mock failure explanation: {context}"
