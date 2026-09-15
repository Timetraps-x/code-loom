# SIM 服务期同步

```json spec-eval
{
  "id": "sim-service-term-sync",
  "title": "SIM 服务期同步",
  "schema_version": 1,
  "language": "zh",
  "entry_request": "只修正满足既有本地筛选且已关联订单的 SIM 服务期同步。",
  "evidence_packet": [
    "已关联订单是既有前置。",
    "允许的结果是同步服务期，不是补造订单。",
    "ERP 查询、订单创建和未授权字段更新都属于禁止副作用。",
    "Proof 只观察允许的同步结果及禁止副作用未发生。"
  ],
  "review_focus": ["scope_minimality", "side_effect_boundary", "proof_strength"],
  "quality_dimensions": ["scope_boundary", "fact_ownership", "reachable_side_effects", "proof_strength"],
  "rubric_id": "sim_sync_boundary"
}
```

## 输入风险

需求只修正满足既有本地筛选且已关联订单的 SIM 服务期同步。AI 容易为了“完整”而补订单、查询 ERP、扩大候选集、更新未授权字段或引入额外副作用。

## 必须裁决

- 明确处理集、排除集和本地事实来源。
- 已有关联订单是既有前置，不得补造。
- 禁止 ERP 查询、订单创建和未授权字段更新。
- Proof 只观察允许的同步结果及禁止副作用未发生。

## 禁止结论

- 将通用性、安全性或缺数据作为新增补单、兜底和外部查询理由。
- 因小修复而虚构完整领域流程、多个目标候选或 owner 决策。

## 场景与链路信号

- 背景只需说明已关联订单的 SIM 服务期为何需要同步，不应扩展为订单或 ERP 领域治理。
- 相关链路保持闭合且最小：符合本地筛选的 SIM → 既有关联订单事实 → 允许字段同步 → 可观察结果；禁止副作用也是该链路的一部分。
- 不得因缺少外部数据、性能想象或通用工程惯例挖掘出额外目标、Owner 问题或质量约束。

## 审阅标准

artifact 应轻量且可直接让 Plan 定位当前路径、字段边界与定向证明。
