# ERP/SIM 历史补单

```json spec-eval
{
  "id": "erp-sim-history-supplement",
  "title": "ERP/SIM 历史补单",
  "schema_version": 1,
  "language": "zh",
  "entry_request": "评估并收敛一项同时涉及 ERP 客户补齐、SIM 候选识别、历史销售出库、重跑和导出的复合需求。",
  "evidence_packet": [
    "历史诉求包含客户补齐、SIM 补单、来源分类和导出。",
    "当前 Job 可能继续执行并创建本地业务对象。",
    "历史决策、代码和测试的重试语义可能冲突。",
    "ERP 关系和导出完整性仍存在证据不足。"
  ],
  "review_focus": ["commitment_orphaning", "gap_laundering", "proof_laundering", "owner_routing"],
  "quality_dimensions": ["commitment_coverage", "evidence_classification", "reachable_side_effects", "proof_strength"],
  "rubric_id": "erp_sim_complex_coverage"
}
```

## 输入风险

历史需求同时包含 ERP 客户补齐、SIM 候选识别、ERP 来源分类、自动补销售出库、重跑幂等和 SIM 导出。当前 Job 可能继续执行并创建本地业务对象；历史决策、代码和测试的重试语义可能冲突。

## 必须裁决

- 客户补齐、SIM 补单、导出分别不能静默消失。
- 已有追踪、当前自动执行差距、ERP 关系证据不足和导出验证不足必须区分。
- 无可补来源、未审核、来源冲突的状态和副作用必须有事实依据或 owner 路由。

## 禁止结论

- 将完整需求缩为资格分类。
- 将当前 Job 存在当作“不落库”边界已满足。
- 将有限 ERP 样本、局部测试或历史任务完成写成所有来源已被证明。

## 场景与链路信号

- 背景应说明历史数据为什么影响客户、SIM 业务使用者或后续运营，而不只罗列 Job 和表。
- 相关链路至少覆盖候选识别、ERP 来源判断、自动写入或阻断、状态/原因留痕、重跑或人工后续处理，以及导出或查询结果。
- 应从候选识别重放到来源判断、当前 Job 的自动写入或阻断、状态留痕、重跑或人工承接以及导出结果，并明确每个节点的当前事实、目标结果和禁止副作用。
- 隐含承诺包括：不因不确定事实误创建出库、失败/阻断结果可理解和可追溯、批量处理不能以局部成功掩盖遗漏。

## 审阅标准

最终 artifact 应让 Plan 明确：哪些路径复用、哪些当前行为必须纠正、哪些关系需要补样本或真实流程证明。
