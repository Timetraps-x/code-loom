from __future__ import annotations

import re

from codeloom.kernel.llm import LlmClient


class MockLlmClient(LlmClient):
    def draft_spec(self, requirement: str, existing_spec: str | None = None, language: str = "en") -> str:
        requirement_text = requirement.strip() or "No requirement text provided."
        existing_references = self._commitment_references(existing_spec or "")
        reference = existing_references[0] if existing_references else ""
        if language == "zh":
            return self._draft_zh_spec(requirement_text, existing_spec, existing_references, reference)
        return self._draft_en_spec(requirement_text, existing_spec, existing_references, reference)

    def draft_plan(
        self,
        spec: str,
        constraints: str | None = None,
        language: str = "en",
        spec_hash: str | None = None,
    ) -> str:
        constraints_text = constraints.strip() if constraints else "None"
        references = self._commitment_references(spec)
        if language == "zh":
            return self._draft_zh_plan(spec, constraints_text, references, spec_hash)
        return self._draft_en_plan(spec, constraints_text, references, spec_hash)

    def draft_tasks(self, spec: str, plan: str, preference: str | None = None, language: str = "en") -> str:
        references = self._commitment_references(spec)
        commitment = references[0] if references else "accepted requirement"
        design = self._design_reference(commitment) if references else "selected Plan design"
        if language == "zh":
            preference_block = f"\n\n## 可选读者备注\n{preference.strip()}" if preference else ""
            return (
                "# 任务\n\n"
                "## 实施路径\n\n"
                "Mock only carries readable Spec semantics and any optional labels; it does not inspect the repository and therefore does not claim concrete landing points, dependencies, or parallel tracks.\n\n"
                "## 任务清单\n\n"
                "- [ ] T1: 建立当前 CodeLoom 需求的实施结果\n"
                "  - Lane: build\n"
                "  - Complexity: small\n"
                "  - Revision: 1\n"
                "  - Depends on: None\n"
                "  - Covered by: T2\n"
                f"  - Context: `{commitment}` through `{design}`; Mock 需要后续项目证据确定真实实施落点。\n"
                "  - Boundaries: 仅落实已接受结果；不在 Mock 中发明仓库契约或设计。\n"
                "  - Handoff: 记录针对已接受结果的实现证据。\n\n"
                "- [ ] T2: 证明当前 CodeLoom 需求的结果\n"
                "  - Lane: verify\n"
                "  - Complexity: small\n"
                "  - Revision: 1\n"
                "  - Depends on: T1\n"
                "  - Validates: T1\n"
                f"  - Context: `{commitment}` through `{design}`; 验证 T1 承接的结果。\n"
                "  - Boundaries: 只报告现有证据能支持的证明强度和限制。\n"
                "  - Handoff: 记录自动化、静态或真实流程证据及限制。\n"
                f"{preference_block}\n"
            )
        preference_block = f"\n\n## Optional Reader Notes\n{preference.strip()}" if preference else ""
        return (
            "# Tasks\n\n"
            "## Implementation Path\n\n"
            "Mock carries readable Spec semantics and any optional labels; it does not inspect the repository and therefore does not claim concrete landing points, dependencies, or parallel tracks.\n\n"
            "## Task List\n\n"
            "- [ ] T1: Implement current CodeLoom requirement\n"
            "  - Lane: build\n"
            "  - Complexity: small\n"
            "  - Revision: 1\n"
            "  - Depends on: None\n"
            "  - Covered by: T2\n"
            f"  - Context: `{commitment}` through `{design}`; Mock requires project evidence to identify a real implementation landing point.\n"
            "  - Boundaries: Implement only the accepted result; do not invent repository contracts or design in Mock mode.\n"
            "  - Handoff: Record implementation evidence for the accepted result.\n\n"
            "- [ ] T2: Verify current CodeLoom requirement\n"
            "  - Lane: verify\n"
            "  - Complexity: small\n"
            "  - Revision: 1\n"
            "  - Depends on: T1\n"
            "  - Validates: T1\n"
            f"  - Context: `{commitment}` through `{design}`; validates the result carried by T1.\n"
            "  - Boundaries: Report only the proof strength and limitations supported by available evidence.\n"
            "  - Handoff: Record automated, static, or real-flow evidence and limitations.\n"
            f"{preference_block}\n"
        )

    def draft_ship_summary(self, facts: dict[str, object], language: str = "en") -> str:
        status = str(facts.get("status", "blocked"))
        confidence = "proven" if status == "ready" else "partially_proven"
        completed = list(facts.get("completed_tasks", []))
        blockers = list(facts.get("readiness_blockers", []))
        evidence = list(facts.get("runtime_refs", []))
        verification_summary = str(facts.get("verification_summary", ""))
        header = (
            f"based_on_spec_hash: `{facts.get('spec_hash', '')}`\n"
            f"based_on_plan_hash: `{facts.get('plan_hash', '')}`\n"
            f"based_on_tasks_hash: `{facts.get('tasks_hash', '')}`\n"
            f"based_on_execution_hash: `{facts.get('ship_input_hash', '')}`\n"
        )
        evidence_lines = [
            f"- {item.get('task_id')} attempt {item.get('attempt_no')} {item.get('kind')}: {item.get('path')}"
            for item in evidence
            if isinstance(item, dict)
        ]
        if language == "zh":
            return (
                "# 发布\n\n"
                + header
                + "\n## 1. 交付结论\n\n"
                + f"- 发布就绪：{status}\n"
                + f"- 目标结果可信度：{confidence}\n"
                + "- 结论：基于当前有效任务、验证记录和运行证据。\n\n"
                + "## 2. 已交付结果与边界\n\n"
                + ("\n".join(f"- {task}" for task in completed) or "- 无")
                + "\n\n## 3. 证明与限制\n\n"
                + verification_summary
                + "\n\n"
                + ("\n".join(f"- 限制：{blocker}" for blocker in blockers) or "- 限制：无")
                + "\n\n## 4. 发布影响操作\n\n- N/A：Mock未发现额外发布操作。\n\n"
                + "## 5. 风险、人工操作与Owner决定\n\n"
                + ("\n".join(f"- {blocker}" for blocker in blockers) or "- 无")
                + "\n\n## 7. 证据引用\n\n"
                + ("\n".join(evidence_lines) or "- 无")
                + "\n"
            )
        return (
            "# Release\n\n"
            + header
            + "\n## 1. Delivery Conclusion\n\n"
            + f"- Release readiness: {status}\n"
            + f"- Goal result confidence: {confidence}\n"
            + "- Conclusion: based on current effective tasks, verification records, and runtime evidence.\n\n"
            + "## 2. Delivered Outcomes and Boundaries\n\n"
            + ("\n".join(f"- {task}" for task in completed) or "- None")
            + "\n\n## 3. Proof and Limitations\n\n"
            + verification_summary
            + "\n\n"
            + ("\n".join(f"- Limitation: {blocker}" for blocker in blockers) or "- Limitation: None")
            + "\n\n## 4. Release-impact Actions\n\n- N/A: Mock found no additional release action.\n\n"
            + "## 5. Risks, Manual Actions, and Owner Decisions\n\n"
            + ("\n".join(f"- {blocker}" for blocker in blockers) or "- None")
            + "\n\n## 7. Evidence References\n\n"
            + ("\n".join(evidence_lines) or "- None")
            + "\n"
        )

    def explain_failure(self, context: str) -> str:
        return f"Mock failure explanation: {context}"

    def _draft_en_spec(
        self, requirement_text: str, existing_spec: str | None, existing_references: list[str], reference: str
    ) -> str:
        anchor = f" Optional anchor: `{reference}`." if reference else ""
        prior = "\n\n## Existing Context\n" + existing_spec.strip() if existing_spec else ""
        return (
            "# Spec\n\n"
            "## Branch Commitment\n"
            f"- {requirement_text}{anchor}\n"
            "- Proof direction: future evidence establishes the observable result of this commitment."
            + prior
        )

    def _draft_zh_spec(
        self, requirement_text: str, existing_spec: str | None, existing_references: list[str], reference: str
    ) -> str:
        anchor = f" 可选定位标签：`{reference}`。" if reference else ""
        prior = "\n\n## 既有上下文\n" + existing_spec.strip() if existing_spec else ""
        return (
            "# 规格\n\n"
            "## 本轮承诺\n"
            f"- {requirement_text}{anchor}\n"
            "- 证明方向：未来证据证明该承诺的可观察结果。"
            + prior
        )

    @staticmethod
    def _commitment_references(content: str) -> list[str]:
        return list(dict.fromkeys(re.findall(r"C:[^\s`，。；：,.;:()\[\]{}<>]+", content)))

    @staticmethod
    def _next_commitment_reference(requirement: str, existing_references: list[str]) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", requirement.lower()).strip("-")[:48] or "requirement"
        candidate = f"C:{slug}"
        suffix = 2
        while candidate in existing_references:
            candidate = f"C:{slug}-{suffix}"
            suffix += 1
        return candidate

    @staticmethod
    def _retained_commitments(content: str, references: list[str], language: str = "en") -> list[str]:
        retained: list[str] = []
        for reference in references:
            line = next((line.strip() for line in content.splitlines() if reference in line), reference)
            if language == "zh":
                retained.append(f"- 保留承诺 `{reference}`：{line}")
            else:
                retained.append(f"- Retained commitment `{reference}`: {line}")
        return retained

    @staticmethod
    def _legacy_summary(content: str) -> str:
        for line in content.splitlines():
            summary = line.strip().lstrip("- ").strip()
            if summary and not summary.startswith("#"):
                return summary
        return "Legacy artifact contains no extractable commitment text."

    @staticmethod
    def _plan_header(spec_hash: str | None) -> str:
        if spec_hash:
            return f"based_on_spec_hash: `{spec_hash}`"
        return "based_on_spec_hash: unavailable (not supplied by caller)"

    @staticmethod
    def _design_reference(reference: str) -> str:
        return f"D:design-{reference.removeprefix('C:')}"

    def _draft_en_plan(
        self, spec: str, constraints_text: str, references: list[str], spec_hash: str | None
    ) -> str:
        header = self._plan_header(spec_hash)
        if not references:
            trace = (
                "- Accepted requirement: readable Spec semantics are present without an optional label.\n"
                "  - Design boundary: Mock cannot select an abstract model, mechanism, or current-project landing without repository evidence.\n"
            )
        else:
            entries = []
            for reference in references:
                design_reference = self._design_reference(reference)
                entries.append(
                    f"- `{reference}` through `{design_reference}`: current repository evidence is unavailable in mock mode.\n"
                    "  - Design direction: establish the required and prohibited results, then select the facts, states, owners, invariants, mechanism, and current-to-target landing.\n"
                    "  - Evidence boundary: project-specific UI, API, data, query, integration, evolution, and proof decisions remain unresolved rather than invented.\n"
                )
            trace = "\n".join(entries)
        return (
            "# CodeLoom Plan\n\n"
            f"{header}\n\n"
            "## 1. Design Basis and Route\n\n"
            f"This mock preserves accepted requirements without inspecting repository internals.\n\n{spec.strip()}\n\n"
            "- Current project evidence: unavailable in mock mode; do not infer existing coverage or a target route.\n"
            f"- External constraints: {constraints_text}\n\n"
            "## 2. Business Implementation Design\n\n"
            + trace
            + "\n- Mechanism boundary: a real design must connect trigger and authoritative fact to judgment/state, accountable owner, local change, external collaboration, failure/recovery meaning, and observable result.\n"
            + "- Landing boundary: Mock cannot decide whether a real project path should be reused, extended, corrected, replaced, added, or kept distinct.\n"
            + "- Material-surface boundary: a real Plan designs concrete UI, contract, data/query, code responsibility, consistency, integration, evolution, observability, diagram, and verification surfaces only when they protect an identified truth or counterexample.\n"
            + "- Scenario boundary: a table, endpoint, diagram, or HTTP success is not proof that an accepted result occurs or a prohibited result is unreachable.\n\n"
            + "## 3. Shared Cross-Block Decisions\n\n"
            + "- None can be established without concrete mechanisms and project evidence.\n\n"
            + "## 4. Evidence and Implementation Freedom\n\n"
            + "- Required evidence: inspect the relevant semantic owners, callers, consumers, facts, state paths, contracts, and verification surfaces before finalizing design.\n"
            + "- Local freedom: implementation details remain open only when they cannot change requirement meaning, the selected model, protected truth, consistency, evolution, or proof.\n"
        )

    def _draft_zh_plan(
        self, spec: str, constraints_text: str, references: list[str], spec_hash: str | None
    ) -> str:
        header = self._plan_header(spec_hash)
        if not references:
            trace = (
                "- 已接受需求：Spec 使用可读语义但没有可选标签。\n"
                "  - 设计边界：没有仓库证据时，Mock 不能选择抽象模型、机制或当前项目落点。\n"
            )
        else:
            entries = []
            for reference in references:
                design_reference = self._design_reference(reference)
                entries.append(
                    f"- `{reference}` 通过 `{design_reference}`：Mock 模式没有当前仓库证据。\n"
                    "  - 设计方向：先建立必要与禁止结果，再选择事实、状态、Owner、不变量、机制和当前到目标的承接。\n"
                    "  - 证据边界：项目特定的 UI、API、数据、查询、集成、演进和证明设计保持未决，不能编造。\n"
                )
            trace = "\n".join(entries)
        return (
            "# CodeLoom 方案\n\n"
            f"{header}\n\n"
            "## 1. 设计依据与路线\n\n"
            f"该 Mock 保留已接受需求，但不检查仓库内部实现。\n\n{spec.strip()}\n\n"
            "- 当前项目证据：Mock 模式不可获得；不得推断既有正确承接或目标路线。\n"
            f"- 外部约束：{constraints_text}\n\n"
            "## 2. 业务实现设计\n\n"
            + trace
            + "\n- 机制边界：真实设计必须把触发与权威事实连接到判断/状态、责任 Owner、本地变更、外部协作、失败/恢复含义和可观察结果。\n"
            + "- 落点边界：Mock 不能判断真实项目路径应复用、扩展、修正、替换、新增或保留差异。\n"
            + "- 材料技术面边界：真实 Plan 只在具体 UI、契约、数据/查询、代码责任、一致性、集成、演进、可观测性、图和验证设计保护已识别真相或反例时加入它们。\n"
            + "- 场景边界：表、接口、图或 HTTP 成功不能证明已接受结果真正发生，或禁止结果不可达。\n\n"
            + "## 3. 跨设计块共享决定\n\n"
            + "- 没有具体机制和项目证据时，无法建立共享设计决定。\n\n"
            + "## 4. 证据与实施自由\n\n"
            + "- 所需证据：最终设计前检查相关语义 Owner、调用者、消费者、事实、状态路径、契约和验证面。\n"
            + "- 局部自由：只有不会改变需求含义、选定模型、受保护真相、一致性、演进或证明时，实施细节才保持开放。\n"
        )