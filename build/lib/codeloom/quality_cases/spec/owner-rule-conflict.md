# Owner 规则冲突

```json spec-eval
{
  "id": "owner-rule-conflict",
  "title": "Owner 规则冲突",
  "schema_version": 1,
  "language": "zh",
  "entry_request": "在重复提交的重试与冻结规则冲突时，保留证据、路由唯一 Owner 决策并明确 Proof 边界。",
  "evidence_packet": [
    "当前请求、历史说明和局部测试分别支持重试与冻结两个方向。",
    "规则选择会改变用户责任、资金或外部副作用与失败恢复语义。",
    "Reviewer 可以指出冲突，但不能替 Owner 选择业务规则或直接提问。",
    "只有影响需求正确性的未决冲突才需要一次最高信息量 Owner clarification。"
  ],
  "review_focus": ["owner_routing", "state_semantics", "external_side_effects", "proof_strength"],
  "quality_dimensions": ["owner_decision", "state_semantics", "reachable_side_effects", "proof_strength"],
  "rubric_id": "owner_rule_conflict"
}
```

## 输入风险

同一业务规则存在两个可信方向：一种要求重复提交在外部失败后允许用户重试；另一种要求首次提交后必须冻结，等待人工核对。当前请求、历史说明和局部测试分别支持不同方向，且选择会改变用户责任、资金/外部副作用与失败恢复语义。

## 必须裁决

- Analyzer 必须保留两个方向及各自证据，不能根据当前代码或局部测试静默选择；
- 必须说明该选择如何改变 Goal、Way、重复提交边界和 Proof direction；
- 证据不能决定时，Analyzer 只向 Owner 路由一个最高信息量问题；
- Reviewer 只能指出冲突、反例和需要 Owner 决定的原因，不能选择规则或直接提问。

## 禁止结论

- 将当前实现的冻结或重试行为写成已确认业务规则；
- 将冲突隐藏为普通技术风险、后续优化或无依据的默认值；
- 将重试按钮、HTTP 返回或局部测试通过写成外部结果已正确。

## 场景与澄清信号

- 背景是用户、人工核对方和外部系统对重复提交后的责任边界不同，而非单纯的重试实现选择。
- 最小链路覆盖首次提交、外部失败、重复请求、人工交接、最终外部结果和用户可见反馈；应重放两个可信方向在当前行为、目标结果、责任边界和禁止副作用上的差异。
- 只有“继续自动重试”与“冻结等待人工”这两个可信方向无法由证据裁决且改变正确性，才应路由一次最高信息量 Owner clarification；不得把其他局部实现细节附带成问卷。

## 审阅标准

最终 artifact 应让 Plan 知道：哪项 Owner 决定仍未确定、它约束哪些可达副作用和状态语义、以及后续需要观察什么 outcome。