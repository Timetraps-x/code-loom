# Spec Real-LLM Quality Cases

这些语料用于平台维护时的显式、隔离真实 LLM 评测，不是用户项目运行时输入或阶段门禁。

每个案例保留原始诉求和证据、Analyzer draft、Reviewer findings、Analyzer revision 与最终 `spec.md`。运行报告记录模型、上下文版本、耗时、token 和初稿/终稿的已知 rubric failures，便于区分一次成功与可重复表现。确定性 rubric 只捕获已知坏模式，不能替代人工语义判断。

## 评测重点

### Analyzer

审阅最终 artifact 是否：

- 从混合、局部或带方案倾向的输入中恢复了真实用户或系统结果；
- 保全全部材料性显式承诺和有证据支持的隐含承诺；
- 区分事实、有限推断、当前行为、实现冲突、证据不足与 Owner 选择；
- 只使用会改变需求判断的背景、场景和因果链；
- 区分局部表现与完整业务结果，表达事实主权、状态、责任、外部后果和反馈；
- 让复杂需求保持完整，让小型修复保持闭合；
- 形成连贯、用户可读的需求决定，而不是分析台账或技术方案；
- 只在证据无法裁决且选择会改变需求正确性时保留一个 Owner 决定。

### Reviewer

Reviewer 只应报告有证据支持、能够改变需求正确性的最小反例：

- **Commitment loss**：材料目标、规则、范围或禁止后果被遗漏、缩小或用局部功能替代；
- **Evidence overreach**：草案结论超过代码、测试、样本、记录或推断能够证明的范围；
- **Causal-chain incompleteness**：遗漏关键事实、状态、责任、副作用、结果或反馈，使错误结果仍可能发生或局部成功冒充完整结果；
- **Unauthorized convergence**：多个可信 Owner 方向仍会产生不同结果，草案却未经授权选边。

缺少偏好的标题、表格、标签、领域全景、理想证据或非材料信息不能单独构成 finding。缺少证据只有在草案依赖该事实作出材料结论时才构成 evidence overreach。

Reviewer 的价值通过初稿与修订稿比较判断：finding 应给 Analyzer 带来承诺保全、证据边界、因果完整性或 Owner 判断上的净增益，而不是增加形式要求或代替 Analyzer 裁决。

## 现有案例侧重

| 案例 | 主要观察 |
|---|---|
| `erp-sim-history-supplement` | 多承诺保全、有限样本、当前 Job 副作用和完整业务链。 |
| `export-field-correction` | 小修复比例性、事实来源、影响范围和定向证明。 |
| `refund-or-ui-work-surface` | 动作、状态、外部事实、失败/重复、反馈与完整结果的区别。 |
| `owner-rule-conflict` | 重试与冻结方向的证据冲突及 Owner 选择。 |
| `non-template-complex-artifact` | 语义质量不依赖固定标题、表格或标签。 |
| `sim-service-term-sync` | 明确边界的小需求不被扩张，不因无关资料缺失而制造问题。 |

## 评测元数据

每个案例包含一个 `json spec-eval` fenced block，至少提供：

- `id`、`title`、`schema_version`、`language`；
- 不可变的 `entry_request` 和 `evidence_packet`；
- `review_focus`、`quality_dimensions`、`rubric_id`。

该 block 是维护者评测输入，不是最终 Spec 的格式要求。其余 Markdown 作为案例说明提供给评测 Agent。

## 隔离运行与产物

使用 `python -m codeloom.spec_evals` 时必须显式指定 `--output-dir`。默认 fixture executor 不联网；真实 provider 需要显式指定 executor、model 和 live 模式。

评测包不调用用户项目的阶段运行、状态存储或 artifact 路径。一次 run 在指定目录下生成唯一目录，包含报告、draft、findings、dispositions 和 final Spec，不记录 credential，也不覆盖已有 run。

离线案例不拥有真实仓库工具或真实 Owner 对话，因此不能证明 Agent 的仓库取证、交互闭环或跨需求稳定性。真实项目能力需要单独的受控运行证据。
