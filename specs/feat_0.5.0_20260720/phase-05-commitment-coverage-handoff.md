# Phase 5：复杂承诺覆盖与 Plan 承接

## 目标

让复杂存量需求中的每项重要原始承诺都有可审阅去向，并让 `plan-architect` 按去向处理当前路径、设计改变和证据需求。

```text
原始承诺
→ 当前必要 / 已有正确承接 / 当前实现差距 /
  必须补足的证据 / 合法拆分或后续承接 /
  调研无关 / owner decision
→ Spec 的用户可读判断
→ Plan 的设计、验证或复用处理
```

这不是 Kernel 语义模型、artifact schema 或固定 Markdown 表格。它是 `spec-analyzer` 的临时收敛模型；只在复杂需求中按需投影对下游有意义的结论。

## 已核查事实

- 第一轮改造已要求 `spec-analyzer` 保全原始诉求、比较当前/请求/目标行为、显式表达冲突，并完成 analyzer → reviewer → revision。
- ERP/SIM 真实验证仍暴露：客户补齐、补单、导出等原始承诺可能在 draft 中丢失；当前代码差距与证据不足容易被混为“范围外”或普通风险。
- `plan-architect.md` 已消费 Spec 语义、当前路径、风险、验证和 blocker，但没有明确区分已有正确承接、当前实现差距与证据缺口。
- `stages.py`、SQLite 和 Kernel 只登记 artifact 路径、revision/hash、lineage 与 drift，不读取 Spec 语义；该边界保持不变。

## 涉及文件

```text
codeloom/agents/spec-analyzer.md
codeloom/agents/spec-reviewer.md
codeloom/agents/plan-architect.md
codeloom/templates/spec-template.md
codeloom/app/claude_plugin.py
tests/test_prompt_evals.py
tests/test_spec_artifact_evals.py
codeloom/quality_cases/spec/*.md
```

## 具体改动

### 1. Analyzer 的承诺去向

对复杂需求，Analyzer 先在工作上下文中列出原始重要承诺，再为每项裁决去向：

| 去向 | 含义 | Plan 影响 |
|---|---|---|
| 当前必要 | 缺失则本轮承诺不成立 | 设计必须覆盖 |
| 已有正确承接 | 当前路径已被证据证明可复用 | 说明边界，避免重复实现 |
| 当前实现差距 | 已确认规则与当前可达行为冲突 | 设计必须纠正 |
| 必须补足的证据 | 规则/范围成立，但当前样本、关系或验证不足 | 设计查证或验证，不能推断为实现缺陷 |
| 合法拆分/后续承接 | 有 owner 确认或已有正确承接承载剩余承诺 | 保留承接边界 |
| 调研无关 | 证据表明不影响当前承诺 | 不进入 Plan |
| Owner decision | 证据无法裁决且改变需求正确性 | Analyzer 决定是否 AskUserQuestion |

“当前排除”“第一阶段”或代码存在本身不能替代裁决。临时账本不写入 SQLite、Kernel 或 artifact 的过程区。复杂需求可以按需使用可读标签帮助下游定位承诺，但标签不是 coverage ID、固定 schema 或跨 revision 的语义谱系协议。

### 2. Artifact 的弹性投影

复杂 Spec 可以按需要写出“原始承诺与当前承接”判断，明确本轮必要、已有正确承接、当前实现差距、必须补足的证据和合法后续承接。小闭合修复不强制增加该章节、表格或领域模型。

### 3. Reviewer 的咨询性检查

Reviewer 新增：

- commitment orphaning：重要原始承诺无去向；
- gap laundering：已确认规则与当前可达行为冲突，却被写为已有能力、范围外或模糊风险；
- proof laundering：局部测试、任务完成或有限运行记录被提升为完整承诺已证明。

Reviewer 只指出遗漏承诺、证据和建议去向；Analyzer 保持最终裁决和 AskUserQuestion 责任。

### 4. Plan 的最小消费规则

Plan 不重新裁决业务语义。当 Spec 给出承诺覆盖判断时：

- 将已有正确承接写入现有 current-state/boundary 部分并保留复用边界；
- 将当前实现差距转为目标设计、约束、风险控制与验证；
- 将证据缺口写入现有 validation/gaps/blockers，明确所需查证，不能从缺证据推导设计事实；
- 保留合法拆分/后续承接边界，不能自行恢复或丢弃需求。

不新增 Plan 运行时 primitive、章节契约或 task slicing。

### 5. 评测与真实验证

- 保留确定性 pytest 作为已知坏模式的回归，不将 evaluator 接入 runtime；
- 对 ERP/SIM 加入承诺覆盖、当前差距、证据缺口的 fixture 断言；
- 增加服务期同步、导出字段修复、退款或 UI 工作面等真实 LLM 评测语料；
- 在隔离 worktree 中执行 analyzer → reviewer → revision，并保留最终 `spec.md` 供人工审阅。

## 明确不改

```text
不新增 SQLite 表、coverage ID、Goal/Way/Proof parser、状态机、审批流、round counter。
不修改 StageRunner、artifact registration、CLI 参数或 Kernel semantic gate。
不让 reviewer 决定 requirement truth 或 Plan readiness。
不要求每个 Spec 使用固定承诺矩阵。
不改 ERP/SIM 产品代码或历史需求材料。
```

## 完成标准

- 每个复杂需求的重要原始承诺都能看到有效去向；
- Spec 清楚区分已有承接、当前实现差距与证据缺口；
- Plan 在现有章节中分别复用、纠正或查证，不重新解释业务语义；
- reviewer 只咨询性地发现 orphaning/laundering；
- 真实 artifact 和回归测试不再允许已知 ERP/SIM 失真回归；
- Kernel/SQLite/StageRunner 行为无语义扩张。

## 风险与控制

| 风险 | 控制 |
|---|---|
| 承诺覆盖退化为硬表单 | 仅复杂需求按需投影；不将标题或表格设为运行时契约。 |
| Plan 借分类重定义 Spec | 明确它只能消费分类，并保持 upstream Spec clarification 路由。 |
| 缺证据被当作实现缺陷 | 单列 evidence gap，并要求保留未知和所需证明。 |
| 测试只匹配关键词 | 用 fixture 的 required/forbidden expectation 加真实 LLM artifact 复核。 |

## 依赖与顺序

依赖 Phase 0–4 已有边界和第一轮真实 ERP/SIM 验证。先更新 Analyzer/Reviewer/Host 与 Plan 的语义，再改模板和测试，最后再运行新的隔离真实闭环。
