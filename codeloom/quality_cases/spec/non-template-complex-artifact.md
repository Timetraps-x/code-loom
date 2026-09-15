# 无固定标题的复杂 Spec

```json spec-eval
{
  "id": "non-template-complex-artifact",
  "title": "无固定标题的复杂 Spec",
  "schema_version": 1,
  "language": "zh",
  "entry_request": "在不依赖固定标题、表格或字段顺序的前提下，评估复杂历史数据修复需求的完整语义与证明边界。",
  "evidence_packet": [
    "历史数据修复同时涉及客户、销售出库记录和导出字段。",
    "现有自动任务仍可能重试并创建本地对象，部分关系只有有限样本。",
    "合格 artifact 可以用连续文本、列表或表格表达完整需求语义。",
    "页面、接口成功或局部测试不能证明完整业务目标已满足。"
  ],
  "review_focus": ["artifact_freedom", "commitment_orphaning", "evidence_classification", "proof_strength"],
  "quality_dimensions": ["artifact_freedom", "commitment_coverage", "evidence_classification", "proof_strength"],
  "rubric_id": "non_template_complex"
}
```

本案例只验证 artifact 语义，不规定章节标题、表格或字段顺序。

某历史数据修复同时要求补齐客户、补齐销售出库记录并纠正导出字段。现有自动任务仍可能重试并创建本地对象；客户与设备出库时间的归集与目标冲突。委外领料及详情分录、ICCID 和料号关系只有有限样本，尚不能判断当前实现缺陷。

一个合格 artifact 可以用连续文本、列表或表格表达：为什么历史数据问题会影响相关业务角色；候选、来源判断、自动处理/阻断、状态追溯和导出结果构成的最小链路；三项业务承诺是否属于本轮；自动重试和归集为何是 current implementation gap；委外领料及字段关系为何是 evidence gap；禁止自动创建时当前可达 Job 如何被纳入 Way boundary；以及用户、系统或外部环境未来应观察的成功和失败结果。可理解的失败/阻断反馈、避免错误创建和可追溯的批量结果属于有证据支持的隐含承诺，但不得扩张为通用 UX 或工程清单。

不得因未使用 `Current Problem`、`Proof Direction` 或 `Original Promises and Coverage` 等推荐标题而降低质量判断；也不得将样例、页面、接口成功或局部测试拔高为完整业务目标已证明。