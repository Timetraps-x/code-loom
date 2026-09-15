from __future__ import annotations

from codeloom.spec_evals.rubric import (
    ComplexCoverageExpectation,
    CoverageSignal,
    ERP_SIM_COVERAGE,
    RequirementUnderstandingExpectation,
    evaluate_complex_coverage,
    evaluate_erp_sim_spec_artifact,
    evaluate_requirement_understanding,
)


def test_rejects_scope_orphaning_without_continuation():
    artifact = "本轮只做资格分类，创建本地销售出库属于当前排除。"

    assert evaluate_erp_sim_spec_artifact(artifact).failures == ("scope-orphaning",)


def test_rejects_unaddressed_automatic_execution_side_effect():
    artifact = "本轮不自动创建本地业务对象，只进行来源分类。"

    assert evaluate_erp_sim_spec_artifact(artifact).failures == ("runtime-contradiction",)


def test_rejects_inconsistent_tracking_policy():
    artifact = "本地前置不足必须留痕；本地前置不足不进入追踪表。"

    assert evaluate_erp_sim_spec_artifact(artifact).failures == ("tracking-policy-contradiction",)


def test_rejects_unproven_erp_relation_as_existing_capability():
    artifact = "当前代码已验证 ERP 分录、ICCID 与料号对应。"

    assert evaluate_erp_sim_spec_artifact(artifact).failures == ("evidence-strength-overclaim",)


def test_rejects_silently_selected_retry_policy():
    artifact = "ERP 无来源不自动重试。"

    assert evaluate_erp_sim_spec_artifact(artifact).failures == ("state-policy-divergence",)


def test_accepts_explicit_scope_runtime_tracking_evidence_and_conflict_handling():
    artifact = """
本轮建立资格分类，同时明确后续承接：既有承接仅覆盖已存在销售出库保护；创建本地销售出库仍是 Owner decision，不能静默排除。
当前 Job 会按 retry、prepare、execute 自动执行；在承诺不自动创建本地业务对象前，必须关闭或改造该自动执行路径。
本地前置不足不进入追踪表；进入追踪表的记录才按 ERP 分类后阻断或推进。
ERP 分录、ICCID 与料号对应是目标约束，当前代码尚未完整验证。
ERP 无来源不自动重试；当前代码、历史决策与测试的状态策略冲突已记录，并由 Owner decision 收敛。
"""

    assert evaluate_erp_sim_spec_artifact(artifact).passed


def test_rejects_dropped_commitment_current_gap_and_evidence_gap():
    artifact = "ERP 客户补齐与 SIM 历史补销售出库。"

    assert evaluate_complex_coverage(artifact).failures == (
        "missing-commitment:SIM 列表导出",
        "missing-current-gap:固定频率重试",
        "missing-current-gap:同一客户与同一设备出库时间",
        "missing-evidence-gap:委外领料",
        "missing-evidence-gap:详情分录、ICCID、`wlbm`",
    )


def test_accepts_complex_commitment_coverage_without_overclaim():
    artifact = """
ERP 客户补齐、SIM 历史补销售出库与 SIM 列表导出均为本轮必要承诺。
当前实现差距：固定频率重试尚未满足；同一客户与同一设备出库时间的归集尚未满足。
证据缺口：委外领料缺少验证；详情分录、ICCID、`wlbm` 关系尚未完整证明。
"""

    assert evaluate_complex_coverage(artifact).passed


def test_accepts_coverage_without_template_headings_or_exact_phrasing():
    artifact = """
客户补齐、SIM 历史销售出库补单和 SIM 导出列表共同构成本轮结果。
定时重试与客户和设备的出库时间归集仍与目标冲突。
委外领料及详情分录、ICCID 和 wlbm 的关系仍需查证。
"""

    assert evaluate_complex_coverage(artifact).passed


def test_rejects_requirement_artifact_without_background_scenario_chain_or_implicit_commitment():
    expectation = RequirementUnderstandingExpectation(
        required_background=(CoverageSignal("受影响业务人员", ("仓库人员",)),),
        required_scenarios=(CoverageSignal("重复提交", ("重复提交",)),),
        required_chain=(CoverageSignal("反馈与追溯", ("处理记录",)),),
        required_implicit_commitments=(CoverageSignal("可理解反馈", ("可理解的失败原因",)),),
        forbidden_claims=("重构整个订单域",),
    )
    artifact = "系统新增一个同步接口。"

    assert evaluate_requirement_understanding(artifact, expectation).failures == (
        "missing-background:受影响业务人员",
        "missing-scenario:重复提交",
        "missing-chain:反馈与追溯",
        "missing-implicit-commitment:可理解反馈",
    )


def test_accepts_requirement_understanding_without_fixed_headings():
    expectation = RequirementUnderstandingExpectation(
        required_background=(CoverageSignal("受影响业务人员", ("仓库人员",)),),
        required_scenarios=(CoverageSignal("重复提交", ("重复提交",)),),
        required_chain=(CoverageSignal("反馈与追溯", ("处理记录",)),),
        required_implicit_commitments=(CoverageSignal("可理解反馈", ("可理解的失败原因",)),),
        forbidden_claims=("重构整个订单域",),
    )
    artifact = """
仓库人员需要获知外部同步未完成的原因，避免重复手工登记。
同一请求重复提交时不应重复创建记录；权限不足也必须得到可理解的失败原因。
请求先核对来源状态，再更新本地记录，并向仓库人员显示结果和处理记录以供追溯。
"""

    assert evaluate_requirement_understanding(artifact, expectation).passed


def test_rejects_unsupported_quality_scope_expansion():
    expectation = RequirementUnderstandingExpectation(
        required_background=(),
        required_scenarios=(),
        required_chain=(),
        required_implicit_commitments=(),
        forbidden_claims=("重构整个订单域",),
    )

    assert evaluate_requirement_understanding("需要重构整个订单域以提升性能。", expectation).failures == (
        "forbidden-overreach:重构整个订单域",
    )