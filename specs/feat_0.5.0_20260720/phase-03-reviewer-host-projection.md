# Phase 3：Reviewer、Host Projection 与 AskUserQuestion 协作

## 目标

让 `spec-reviewer`、`spec-analyzer` 与 Claude Code host 使用同一套轻量需求决策边界：主 Agent 探索、判断和提问；reviewer 提供咨询性证据；host 投影能力并注册最终 artifact；Kernel 保持机械运行职责。

## 已核查事实

- `codeloom/agents/spec-reviewer.md` 目前已规定不改写 Spec、不决定 planning readiness、不直接问用户；但其 Downstream Consumer Check 仍检查 journey-order goal slices、current-release slice 与 later/out。
- `codeloom/app/claude_plugin.py:_agent_rule()` 已让 artifact stage 使用主 Agent、reviewer、AskUserQuestion，并要求 host 最终写 artifact 后传入 `artifact_file`。
- `codeloom/app/claude_plugin.py:_content_rule()` 已要求 artifact 是用户可读 Markdown，来自项目模板，且排除运行态和内部控制内容。
- `codeloom/app/stages.py:_host_artifact_required_response()`、`_artifact_content()`、`_run_spec()`、`_sync_one_artifact()` 已形成 host authored artifact、精确路径、revision/hash/lineage 的机械边界。

## 涉及文件

后续实现主要修改：

```text
codeloom/agents/spec-reviewer.md
codeloom/app/claude_plugin.py
codeloom/agents/spec-analyzer.md（协作语义同步）
tests/test_prompt_evals.py
```

只读并保持不变：

```text
codeloom/app/stages.py
tests/test_stage_flow.py
tests/test_cli_status_doctor.py
tests/test_host_handoff.py
```

## 具体改动

### 1. Reviewer 从栏目审查改为判断质量审查

删除或替换对以下内容的固定要求：

```text
journey order；
small independently useful slices；
current-release slice；
later/out slices；
固定标题/表格存在。
```

Reviewer 只应发现以下高价值缺陷：

| 维度 | 缺陷定义 |
|---|---|
| 目标降级 | 用户/业务结果被页面、接口、表、模块或最小 CRUD 代替。 |
| 现实误判 | 当前实现、历史补救、字段存在、推断被误当成正确规则或事实。 |
| 运行遗漏 | 缺关键角色/责任、对象/事实来源、状态后果、必要工作面、外部后果或关键例外，且遗漏会改变本轮判断。 |
| 越权收敛 | 多种可信承诺/规则方向存在，主 Agent 未查证或未 AskUserQuestion 就自行选择。 |
| 方式漂移 | 规则、数据语义、权限、处理/排除集、非目标、禁止副作用或风险接受被弱化成技术建议。 |
| 证明漂移 | 截图、HTTP 200、编译、mock 或局部测试被写成业务目标已成立。 |
| 过度 Spec 化 | 表、API、SQL、事务、任务拆分、验证执行或 UI 组件被提前锁死。 |

Reviewer 保持当前输出结构：

```markdown
## Findings
- finding:
  severity:
  evidence:
  uncertainty:
  impact:
  recommendation:

## Questions the main agent may need to ask
- question:
  why it matters:
  blocks planning:
  evidence:
```

Reviewer handoff 应使主 Agent 能读到 finding 的 affected judgment、evidence、uncertainty、impact 与 recommendation；必要时可另列主 Agent 可能需要路由的问题及其 why it matters、是否阻止 Spec 收敛和证据。该表达服务于咨询性交接，不是固定 Markdown 标题、Kernel parser 或 runtime gate。

### 2. Host 投影 Spec 专属能力

在 `claude_plugin.py:_agent_rule("spec")` 的通用规则上增加 Spec 专属段落：

```text
先以证据理解当前现实和关键断裂；
大需求先比较业务承诺与必要跨度，不按 journey 自动选最小步骤；
区分目标、候选方法、已确认规范和证明方向；
仅在 owner-bearing uncertainty 不能由证据消除时使用 AskUserQuestion；
用户回答后重新检查目标、方式、证明是否改变；
未收敛时继续 Agent 探索/澄清，不写最终 artifact；
收敛后只写最终用户可读 spec.md，再通过 artifact_file 注册。
```

同时保留已有通用规则：

- `spec-analyzer` 是 stage owner；
- `spec-reviewer` 是 advisory；
- artifact 不写 runtime/session/prompt eval/control 内容；
- host 写 `specs/<branch-slug>/spec.md`；
- Kernel 仅通过 `artifact_file` 注册。

不得新增：

```text
--arg goal=...
--arg method=...
--arg proof=...
--arg round=...
AskUserQuestion 状态写入 SQLite
```

### 3. AskUserQuestion 的准确归属

`AskUserQuestion` 落在主 Agent，而不是 reviewer 或 Kernel：

```text
spec-analyzer
→ 查证
→ 形成不同业务承诺/规则方向
→ 判断证据无法裁决且 owner 选择会改变需求正确性
→ 提供决策包并 AskUserQuestion
→ 吸收答案
→ 修订需求决策
```

提问必须是已调研的决策包：

```text
已证实事实；
唯一无法由证据裁决的分歧；
候选方向及各自的目标、范围、依赖、风险/不可逆后果；
推荐及理由；
owner 要确认的一个业务决定。
```

不将代码检索、命名偏好、表/API/SQL/组件选择或低影响实现细节升级为用户问题。

### 4. 保持 Kernel 机械边界

以下行为必须原样保留：

| 现有机制 | 保持原因 |
|---|---|
| `_host_artifact_required_response()` | 只确保 claude-code host 先写最终 artifact，不裁决内容。 |
| `_artifact_content()` 精确路径验证 | 防止错误 artifact 注册，不阅读业务语义。 |
| `_sync_one_artifact()` revision/hash/lineage | 让下游判断 artifact 版本与 drift，不替代需求证据。 |
| `_drift_response()` / `_derive_recommendation()` | 只基于 artifact 是否存在和 lineage，不做 Spec 完整性判断。 |

## 明确不改

```text
不修改 stages.py、SQLite schema 或 artifact revision 模型。
不让 reviewer 调用 AskUserQuestion。
不让 Kernel 检查是否存在 Owner Decision、是否有 Goal/Method/Proof、是否经历多轮或是否“规划就绪”。
不将 reviewer finding 自动映射为 Kernel blocked 状态。
不将 host skill 写成第二个需求分析器或固定流程引擎。
```

## 完成标准

- reviewer 能发现目标降级、现实误判、运行遗漏、越权收敛、方式/证明漂移和过度 Spec 化，而不要求固定切片表。
- `spec-analyzer` 是唯一可提问的 Spec 角色；reviewer 只返回问题建议。
- `_agent_rule("spec")` 明确先证据探索、后承诺收敛；不再投影 journey-first 的最小步骤选择。
- artifact_file 缺失、错误路径、revision/hash/lineage 和 drift 的现有行为不变。
- 无任何新 CLI 参数、SQLite 状态或 Kernel semantic gate。

## 风险

| 风险 | 控制方式 |
|---|---|
| reviewer 重写需求或代替 owner 选择 | 保留 advisory output contract 与 main Agent synthesis responsibility。 |
| host 与 Agent prompt 不一致 | 在 prompt eval 同时断言 agent/reviewer/host 的关键 guardrail。 |
| AskUserQuestion 过度触发 | 只允许 owner-bearing、证据无法裁决且会改变需求正确性的分歧。 |
| 为“等待澄清”增加 runtime status | 未收敛时只是不写最终 artifact；Kernel 无需知道原因。 |
| host 模板规则又变成硬模板 | `_content_rule()` 继续说模板控制结构，但 Phase 2 将模板改为弹性骨架。 |

## 依赖与顺序

依赖 [Phase 0](phase-00-scope-and-invariants.md)、[Phase 1](phase-01-analyzer-workflow.md) 和 [Phase 2](phase-02-decision-artifact.md)。Analyzer 的行为与 artifact 投影先稳定，再让 reviewer/host 对齐。

## 未决项

- 后续实现时需读取当前 `STAGE_PROJECTIONS` 的 Spec projection 文案，避免与新规则重复或冲突。
- 是否需要为 `spec` 单独抽取一个小型 projection helper，应在实现阶段以最小改动为准；不为了文案复用引入抽象层。
