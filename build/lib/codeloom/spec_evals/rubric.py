from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from codeloom.spec_evals.models import RubricResult, SpecEvalCase


@dataclass(frozen=True)
class CoverageSignal:
    label: str
    accepted_phrases: tuple[str, ...]


@dataclass(frozen=True)
class ComplexCoverageExpectation:
    required_commitments: tuple[CoverageSignal, ...]
    required_current_gaps: tuple[CoverageSignal, ...]
    required_evidence_gaps: tuple[CoverageSignal, ...]
    forbidden_claims: tuple[str, ...]


ERP_SIM_COVERAGE = ComplexCoverageExpectation(
    required_commitments=(
        CoverageSignal("ERP 客户补齐", ("ERP 客户补齐", "客户补齐")),
        CoverageSignal("SIM 历史补销售出库", ("SIM 历史补销售出库", "SIM 历史销售出库补单")),
        CoverageSignal("SIM 列表导出", ("SIM 列表导出", "SIM 导出列表")),
    ),
    required_current_gaps=(
        CoverageSignal("固定频率重试", ("固定频率重试", "定时重试")),
        CoverageSignal("同一客户与同一设备出库时间", ("同一客户与同一设备出库时间", "客户与设备的出库时间归集", "客户和设备的出库时间归集")),
    ),
    required_evidence_gaps=(
        CoverageSignal("委外领料", ("委外领料",)),
        CoverageSignal("详情分录、ICCID、`wlbm`", ("详情分录、ICCID、`wlbm`", "详情分录、ICCID 和 wlbm")),
    ),
    forbidden_claims=("当前代码已验证 ERP 分录、ICCID 与料号对应",),
)


def evaluate_complex_coverage(
    artifact: str,
    expectation: ComplexCoverageExpectation = ERP_SIM_COVERAGE,
) -> RubricResult:
    failures = _coverage(expectation.required_commitments, artifact, "missing-commitment")
    failures.extend(_coverage(expectation.required_current_gaps, artifact, "missing-current-gap"))
    failures.extend(_coverage(expectation.required_evidence_gaps, artifact, "missing-evidence-gap"))
    failures.extend(
        f"forbidden-overclaim:{claim}"
        for claim in expectation.forbidden_claims
        if claim in artifact
    )
    return RubricResult("erp_sim_complex_coverage", tuple(failures))


@dataclass(frozen=True)
class RequirementUnderstandingExpectation:
    required_background: tuple[CoverageSignal, ...]
    required_scenarios: tuple[CoverageSignal, ...]
    required_chain: tuple[CoverageSignal, ...]
    required_implicit_commitments: tuple[CoverageSignal, ...]
    forbidden_claims: tuple[str, ...]


def evaluate_requirement_understanding(
    artifact: str,
    expectation: RequirementUnderstandingExpectation,
) -> RubricResult:
    failures = _coverage(expectation.required_background, artifact, "missing-background")
    failures.extend(_coverage(expectation.required_scenarios, artifact, "missing-scenario"))
    failures.extend(_coverage(expectation.required_chain, artifact, "missing-chain"))
    failures.extend(_coverage(expectation.required_implicit_commitments, artifact, "missing-implicit-commitment"))
    failures.extend(
        f"forbidden-overreach:{claim}"
        for claim in expectation.forbidden_claims
        if claim in artifact
    )
    return RubricResult("requirement_understanding", tuple(failures))


def evaluate_erp_sim_spec_artifact(artifact: str) -> RubricResult:
    failures: list[str] = []

    if "资格分类" in artifact and not any(
        signal in artifact
        for signal in ("既有承接", "owner 已确认拆分", "Owner decision", "后续承接")
    ):
        failures.append("scope-orphaning")

    if "不自动创建本地业务对象" in artifact and not any(
        signal in artifact
        for signal in ("当前 Job", "prepare", "execute", "自动执行路径", "关闭或改造")
    ):
        failures.append("runtime-contradiction")

    if "本地前置不足必须留痕" in artifact and "本地前置不足不进入追踪表" in artifact:
        failures.append("tracking-policy-contradiction")

    if "当前代码已验证 ERP 分录、ICCID 与料号对应" in artifact:
        failures.append("evidence-strength-overclaim")

    if (
        "ERP 无来源不自动重试" in artifact
        and "当前代码、历史决策与测试的状态策略冲突" not in artifact
        and "Owner decision" not in artifact
    ):
        failures.append("state-policy-divergence")

    return RubricResult("erp_sim_spec_artifact", tuple(failures))


def evaluate_artifact(case: SpecEvalCase, artifact: str) -> RubricResult:
    evaluator = RUBRICS.get(case.rubric_id)
    if evaluator is None:
        return RubricResult(case.rubric_id, (), (f"No deterministic rubric for {case.rubric_id}.",))
    return evaluator(artifact)


def _coverage(signals: tuple[CoverageSignal, ...], artifact: str, prefix: str) -> list[str]:
    return [
        f"{prefix}:{signal.label}"
        for signal in signals
        if not any(phrase in artifact for phrase in signal.accepted_phrases)
    ]


def _generic(
    rubric_id: str,
    required: tuple[CoverageSignal, ...],
    forbidden: tuple[str, ...],
    manual_review: tuple[str, ...],
) -> Callable[[str], RubricResult]:
    def evaluate(artifact: str) -> RubricResult:
        failures = _coverage(required, artifact, "missing")
        failures.extend(f"forbidden:{claim}" for claim in forbidden if claim in artifact)
        return RubricResult(rubric_id, tuple(failures), manual_review)

    return evaluate


def _erp_sim(artifact: str) -> RubricResult:
    failures = _coverage(
        (
            CoverageSignal("客户补齐", ("ERP 客户补齐", "客户补齐")),
            CoverageSignal("SIM 补销售出库", ("SIM 历史补销售出库", "SIM 历史销售出库补单")),
            CoverageSignal("SIM 导出", ("SIM 列表导出", "SIM 导出列表")),
            CoverageSignal("重试差距", ("固定频率重试", "定时重试")),
            CoverageSignal("时间归集差距", ("同一客户与同一设备出库时间", "客户与设备的出库时间归集", "客户和设备的出库时间归集")),
            CoverageSignal("委外领料证据缺口", ("委外领料",)),
            CoverageSignal("详情关系证据缺口", ("详情分录、ICCID、`wlbm`", "详情分录、ICCID 和 wlbm")),
        ),
        artifact,
        "missing",
    )
    failures.extend(
        f"forbidden-overclaim:{claim}"
        for claim in ("当前代码已验证 ERP 分录、ICCID 与料号对应", "当前代码已完整证明所有来源")
        if claim in artifact
    )
    return RubricResult("erp_sim_complex_coverage", tuple(failures), ("人工确认每项原始承诺的最终去向和 Plan 可消费性。",))


RUBRICS: dict[str, Callable[[str], RubricResult]] = {
    "erp_sim_complex_coverage": _erp_sim,
    "sim_sync_boundary": _generic(
        "sim_sync_boundary",
        (
            CoverageSignal("处理集", ("处理集", "符合本地筛选")),
            CoverageSignal("既有关联订单", ("已关联订单", "关联订单")),
            CoverageSignal("禁止 ERP 查询", ("禁止 ERP 查询", "不查询 ERP", "排除 ERP")),
            CoverageSignal("禁止创建订单", ("订单创建", "不得补造", "不创建订单")),
            CoverageSignal("同步结果证明", ("Proof", "证明", "可观察结果")),
        ),
        ("引入额外补单", "虚构完整领域流程"),
        ("人工确认处理集和禁止副作用是否足够支持 Plan。",),
    ),
    "export_field_correction": _generic(
        "export_field_correction",
        (
            CoverageSignal("字段事实来源", ("事实来源", "正确字段")),
            CoverageSignal("导出范围", ("导出范围", "受影响范围")),
            CoverageSignal("定向证明", ("定向证据", "证明方向", "回归边界")),
        ),
        ("完整领域模型", "无关数据迁移", "整域性能治理"),
        ("人工确认是否保持为小闭合修复而非领域重构。",),
    ),
    "refund_ui_proof": _generic(
        "refund_ui_proof",
        (
            CoverageSignal("授权动作", ("权限", "授权用户", "触发决定")),
            CoverageSignal("外部事实", ("外部系统", "到账", "外部成功")),
            CoverageSignal("失败和重复", ("失败", "重复提交")),
            CoverageSignal("反馈追溯", ("反馈", "追溯")),
        ),
        ("HTTP 200 即退款完成", "页面出现即退款完成", "按钮可点即完成"),
        ("人工确认状态语义与外部事实主权是否完整。",),
    ),
    "owner_rule_conflict": _generic(
        "owner_rule_conflict",
        (
            CoverageSignal("两个可信方向", ("重试", "冻结")),
            CoverageSignal("冲突证据", ("冲突", "证据不能决定")),
            CoverageSignal("Owner 问题", ("Owner", "owner", "澄清")),
            CoverageSignal("副作用边界", ("外部副作用", "责任边界")),
        ),
        ("默认选择重试", "默认冻结"),
        ("人工确认问题是否确实只有一个最高信息量 Owner 决策。",),
    ),
    "non_template_complex": _generic(
        "non_template_complex",
        (
            CoverageSignal("背景和角色", ("背景", "业务角色", "受影响")),
            CoverageSignal("完整链路", ("链路", "触发", "结果与反馈")),
            CoverageSignal("实现差距", ("实现差距", "当前行为")),
            CoverageSignal("证据缺口", ("证据缺口", "尚不能判断")),
        ),
        ("必须使用固定标题", "固定 schema", "完整工程清单"),
        ("人工确认语义是否独立于标题、表格或字段顺序。",),
    ),
}
