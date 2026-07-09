from __future__ import annotations

from codeloom.kernel.llm import LlmClient


class MockLlmClient(LlmClient):
    def draft_spec(self, requirement: str, existing_spec: str | None = None, language: str = "en") -> str:
        revision = "\n\n## Revision Note\n" + existing_spec.strip() if existing_spec else ""
        requirement_text = requirement.strip() or "No requirement text provided."
        if language == "zh":
            return f"# 规格\n\n## 需求\n{requirement_text}{revision}\n"
        return f"# Spec\n\n## Requirement\n{requirement_text}{revision}\n"

    def draft_plan(self, spec: str, constraints: str | None = None, language: str = "en") -> str:
        constraints_text = constraints.strip() if constraints else "None"
        if language == "zh":
            return self._draft_zh_plan(spec, constraints_text)
        return self._draft_en_plan(spec, constraints_text)

    def draft_tasks(self, spec: str, plan: str, preference: str | None = None, language: str = "en") -> str:
        if language == "zh":
            preference_block = f"\n\n## 备注\n{preference.strip()}" if preference else ""
            return (
                "# 任务\n\n"
                "## build\n\n"
                "- [ ] T1: 实现当前 CodeLoom 需求\n"
                "  - Lane: build\n"
                "  - Covered by: T2\n\n"
                "## verify\n\n"
                "- [ ] T2: 验证当前 CodeLoom 需求\n"
                "  - Lane: verify\n"
                "  - Validates: T1\n"
                f"{preference_block}\n"
            )
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

    def draft_ship_summary(self, facts: dict[str, object], language: str = "en") -> str:
        status = facts.get("status", "blocked")
        completed = facts.get("completed_tasks", [])
        findings = facts.get("open_findings", [])
        blockers = facts.get("readiness_blockers", [])
        evidence = facts.get("runtime_refs", [])
        verification_summary = str(facts.get("verification_summary", ""))
        if language == "zh":
            return (
                "# 发布计划\n\n"
                "## 1. 发布结论\n"
                f"- 状态：{status}\n"
                "- 判断依据：来自 CodeLoom 任务验证、阻塞项和运行证据。\n\n"
                "## 2. 变更摘要\n"
                "- 根据已完成任务和运行证据生成。\n\n"
                "## 3. 已完成任务\n"
                + ("\n".join(f"- {task}" for task in completed) or "- 无")
                + "\n\n## 4. 验证摘要\n"
                + verification_summary
                + "\n\n### 4.1 未验证 / 阻塞项\n"
                + ("\n".join(f"- {blocker}" for blocker in blockers) or "- 无")
                + "\n\n## 5. 开放问题\n"
                + ("\n".join(f"- {finding}" for finding in findings) or "- 无")
                + "\n\n## 6.1 变更清单 / 运行证据引用\n"
                + ("\n".join(f"- {ref}" for ref in evidence) or "- 无")
                + "\n"
            )
        return (
            "# Release Plan\n\n"
            "## 1. Release Conclusion\n"
            f"- Status: {status}\n"
            "- Decision reason: derived from CodeLoom task verification, readiness blockers, and runtime evidence.\n\n"
            "## 2. Change Summary\n"
            "- Generated from completed tasks and runtime evidence.\n\n"
            "## 3. Completed Tasks\n"
            + ("\n".join(f"- {task}" for task in completed) or "- None")
            + "\n\n## 4. Verification Summary\n"
            + verification_summary
            + "\n\n### 4.1 Not Verified / Readiness Blockers\n"
            + ("\n".join(f"- {blocker}" for blocker in blockers) or "- None")
            + "\n\n## 5. Open Findings\n"
            + ("\n".join(f"- {finding}" for finding in findings) or "- None")
            + "\n\n## 6.1 Change Inventory / Runtime Evidence References\n"
            + ("\n".join(f"- {ref}" for ref in evidence) or "- None")
            + "\n"
        )

    def explain_failure(self, context: str) -> str:
        return f"Mock failure explanation: {context}"

    def _draft_en_plan(self, spec: str, constraints_text: str) -> str:
        return (
            "# CodeLoom Technical Plan\n\n"
            "based_on_spec_hash: `<mock>`\n\n"
            "## 1. Background\n\n"
            f"This plan is generated from the current spec as the bridge from requirements to executable tasks.\n\n{spec.strip()}\n\n"
            "## 2. Goals and Non-Goals\n\n"
            "### 2.1 Goals\n\n"
            "- Implement a complete scoped change that satisfies the current spec without unrelated expansion.\n\n"
            "### 2.2 Non-Goals\n\n"
            "- Do not introduce unrelated abstractions or workflow state.\n\n"
            "## 3. Current State\n\n"
            "- Mock mode does not inspect repository internals.\n\n"
            "## 4. Target Design\n\n"
            "### 4.1 Component Impact\n\n"
            "N/A because mock fallback does not infer component boundaries.\n\n"
            "## 5. Interaction and Flow Design\n\n"
            "N/A because mock fallback does not infer interaction flows.\n\n"
            "## 6. Data, State, and Consistency Design\n\n"
            "N/A because mock fallback does not infer data or state changes.\n\n"
            "## 7. API / Page / Interface Contract Design\n\n"
            "N/A because mock fallback does not infer external contracts.\n\n"
            "## 8. Concurrency, Transactions, and Consistency Design\n\n"
            "N/A because mock fallback does not infer consistency risks.\n\n"
            "## 9. Risk Controls\n\n"
            "| Risk | Control | Verification |\n"
            "|---|---|---|\n"
            "| Plan too broad | Stay inside the spec boundary and avoid unrelated expansion. | Run configured verification commands. |\n\n"
            "## 10. Release and Rollback\n\n"
            "N/A because mock fallback does not infer rollout requirements.\n\n"
            "## 11. Validation Matrix\n\n"
            "| Acceptance | Verification Method | Evidence |\n"
            "|---|---|---|\n"
            "| AC-1 | Run configured test, lint, typecheck, and build commands when present. | Command output |\n\n"
            "## 12. Key Decisions\n\n"
            "- Use the current CodeLoom Phase 1 artifact flow for downstream design registration.\n\n"
            "## 13. Alternatives and Tradeoffs\n\n"
            "### 13.1 Add a broader architecture layer\n\n"
            "Rejected because Phase 1 favors narrow changes over speculative abstractions.\n\n"
            "## 14. Plan Gaps and Blockers\n\n"
            "### 14.1 Resolved Open Questions\n\n"
            "- None\n\n"
            "### 14.2 Blockers\n\n"
            "- None\n\n"
            "### 14.3 Notes\n\n"
            f"- External constraints: {constraints_text}\n"
        )

    def _draft_zh_plan(self, spec: str, constraints_text: str) -> str:
        return (
            "# CodeLoom 技术方案\n\n"
            "based_on_spec_hash: `<mock>`\n\n"
            "## 1. 背景\n\n"
            f"本方案基于当前 spec 生成，作为需求到可执行任务的技术桥接。\n\n{spec.strip()}\n\n"
            "## 2. 目标与非目标\n\n"
            "### 2.1 目标\n\n"
            "- 在当前 spec 边界内完整实现需求，不做无关扩展。\n\n"
            "### 2.2 非目标\n\n"
            "- 不引入无关抽象或工作流状态。\n\n"
            "## 3. 当前状态\n\n"
            "- Mock 模式不会检查仓库内部实现。\n\n"
            "## 4. 目标设计\n\n"
            "### 4.1 组件影响\n\n"
            "N/A，原因：mock fallback 不推断组件边界。\n\n"
            "## 5. 交互与流程设计\n\n"
            "N/A，原因：mock fallback 不推断交互流程。\n\n"
            "## 6. 数据、状态与一致性设计\n\n"
            "N/A，原因：mock fallback 不推断数据或状态变化。\n\n"
            "## 7. API / 页面 / 接口契约设计\n\n"
            "N/A，原因：mock fallback 不推断外部契约。\n\n"
            "## 8. 并发、事务与一致性设计\n\n"
            "N/A，原因：mock fallback 不推断一致性风险。\n\n"
            "## 9. 风险控制\n\n"
            "| 风险 | 控制措施 | 验证 |\n"
            "|---|---|---|\n"
            "| 方案过宽 | 保持在 spec 边界内，避免无关扩展。 | 运行已配置的验证命令。 |\n\n"
            "## 10. 发布与回滚\n\n"
            "N/A，原因：mock fallback 不推断发布要求。\n\n"
            "## 11. 验证矩阵\n\n"
            "| 验收项 | 验证方式 | 证据 |\n"
            "|---|---|---|\n"
            "| AC-1 | 存在配置时运行 test、lint、typecheck 和 build 命令。 | 命令输出 |\n\n"
            "## 12. 关键决策\n\n"
            "- 使用当前 CodeLoom Phase 1 artifact flow 注册后续设计。\n\n"
            "## 13. 替代方案与取舍\n\n"
            "### 13.1 增加更宽的平台架构层\n\n"
            "放弃原因：Phase 1 更偏向窄范围变更，而不是推测性抽象。\n\n"
            "## 14. 计划缺口与阻塞项\n\n"
            "### 14.1 已解决的开放问题\n\n"
            "- 无\n\n"
            "### 14.2 阻塞项\n\n"
            "- 无\n\n"
            "### 14.3 注意事项\n\n"
            f"- 外部约束：{constraints_text}\n"
        )
