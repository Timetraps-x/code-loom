# Phase 2：轻量需求决策 Artifact

## 目标

将 `spec.md` 从固定九节、强制 Candidate Goal Slices、Current Release 和 FR/AC 填空，调整为可伸缩的需求决策记录。

模板不是阶段能力；它只承接主 Agent 已经形成的目标、方式和证明判断，并保留给 `plan-architect` 不可丢失的信息。

## 已核查事实

`codeloom/templates/spec-template.md` 当前要求：

```text
Background and Current Problem
Known Facts / Inferences / Owner Decisions
Goal Reframing and Delivery Slicing
Candidate Goal Slices
Current Release Goal
Current-to-Target Behavior
Non-Goals
Users / Actors
Requirements and Business Rules
Proof of Goal
Way Boundaries
Risks and Hard Gates
Open Questions
```

它的 Candidate Goal Slices 表明确要求 journey order 和 `now / later / out`。这会把 Agent 的探索压缩成固定路线图表达，并让最小 current release 变成默认选择。

`claude_plugin.py:_content_rule()` 已要求 host 读取项目中的 `.loom/templates/spec-template.md`，并要求 artifact 是用户可读 Markdown。Kernel 不解析标题、表格、FR 或 AC。

## 涉及文件

后续实现主要修改：

```text
codeloom/templates/spec-template.md
codeloom/agents/spec-analyzer.md
tests/test_prompt_evals.py
tests/test_init.py（仅当初始化模板断言需要调整）
```

只读确认：

```text
codeloom/app/claude_plugin.py
codeloom/app/stages.py
```

## 具体改动

### 1. 将模板降为弹性骨架

建议使用如下推荐结构：

```markdown
# <Requirement Name> Spec

## 当前问题与本轮目标承诺

## 决策依据
### 已证实事实
### 推断与局限
### Owner 决策 / 承诺

## 目标业务 / 系统如何运行

## 方式边界

## 证明方向

## 未决项
```

该结构是可用的投影顺序，不是强制栏目清单。

### 2. 定义每个投影的最小语义

| 投影 | 必须保留的判断 | 不应写入 |
|---|---|---|
| 当前问题与本轮目标承诺 | 当前运行现实、关键断裂、谁在何情境获得何种可观察结果、为何本轮承诺此范围 | 页面/API/表名替代目标，技术方案，未来路线图 |
| 决策依据 | 已证实事实、推断及局限、owner 已确认选择 | Agent 工作日志、无来源的假设、运行态信息 |
| 目标业务/系统如何运行 | 只写影响目标成立的事件、对象、事实来源、角色、责任、状态承诺、工作面、操作、结果和外部后果 | 表结构、DTO、组件、路由、SQL、流程编排细节 |
| 方式边界 | 规则、数据语义、事实主权、权限/责任、既有承接、当前排除、禁止副作用、约束和风险 | 普通工程常识、未确认的技术偏好、可替换实现细节 |
| 证明方向 | 可观察成功、关键失败/反例、相称证据类型和已知限制 | 测试命令、verify task、运行结果、发布判断 |
| 未决项 | 仍会改变目标、范围、语义、验收、公开契约或硬风险的事项 | 可由证据查清的问题、局部实现选择、低影响偏好 |

### 3. 保持语义兼容，不保持强格式兼容

新 artifact 必须仍能表达此前需要的语义：

```text
Background；Known Facts；Inferences；Owner Decisions；Goals；Non-Goals；
Users / Actors；Requirements；Acceptance；Constraints；Risks；Open Questions。
```

但不再强制：

```text
固定标题顺序；
Candidate Goal Slices；
journey order；
Current Release Goal；
now/later/out；
FR/AC ID；
固定表格。
```

主 Agent 可按需求使用自然语言、列表或短表格。只要下游可辨识事实、承诺、边界、证明与未决项，就不应为了模板制造内容。

### 4. 按需求复杂度调整 artifact 密度

小闭合技术修复可以只表达：

```text
当前错误；处理集与排除集；事实来源；正确结果；
禁止副作用；定向证明；无 owner 决策。
```

大业务需求自然展开为：

```text
当前运行现实；目标承诺；业务运行结构；角色/责任/工作面；
既有承接与排除；外部后果；证明方向；需要 owner 决定的分歧。
```

模板不得要求小需求完整领域建模，也不得允许大需求只写一行“支持售后工单”。

### 5. 保留 Artifact Boundary Gate

Spec artifact 必须继续排除：

```text
技术架构设计；任务拆分与执行顺序；测试执行计划；
运行态、session、attempt、SQLite、prompt eval、平台反馈；
Agent 过程、reviewer 讨论、ready/blocked 标记、host 命令。
```

## 明确不改

```text
不新增 Markdown parser、schema validator 或模板标题校验。
不让 Kernel 检查标题、FR/AC、Goal/Method/Proof 或段落完整度。
不增加 database 字段或 artifact metadata。
不把 Spec 改成 Plan、Tasks、验证报告或 release.md。
不让模板取代 spec-analyzer 的探索、判断和 AskUserQuestion。
```

## 完成标准

- 模板能支持自然语言的轻量 Spec，不要求 FR/AC 表格或固定九节。
- 模板不再要求 journey-order、smallest current-release slice、Candidate Goal Slices 或 now/later/out。
- 任何下游必须信息仍能被清楚投影：当前问题、本轮承诺、证据、运行模型、方式边界、证明方向、未决项。
- 小技术修复不会被模板迫使生成领域模型；大业务需求不会被模板允许退化成页面/接口清单。
- `stages.py` 不因模板结构变化而改动，且仍能注册最终 Markdown artifact。

## 风险

| 风险 | 控制方式 |
|---|---|
| 模板太松导致 Plan 无法理解范围 | 保留决策依据、目标承诺、方式边界、证明方向、未决项五类不可丢失语义。 |
| 新术语变成另一套硬模板 | 允许按问题使用标题子集、自然语言与短表，不将标题作为 Kernel 契约。 |
| Agent 只写抽象目标 | Phase 1 要求目标必须落在角色、情境、可观察结果和必要运行条件。 |
| 方式边界侵入技术设计 | 明确只写语义、规则、事实、权限、范围、副作用和风险。 |
| 历史项目模板被覆盖 | Phase 4 制定显式、人工审阅迁移方式。 |

## 依赖与顺序

依赖 [Phase 0](phase-00-scope-and-invariants.md) 与 [Phase 1](phase-01-analyzer-workflow.md)。必须在 Analyzer 的收敛方法确定后才修改模板；否则新模板会再次反向约束 Agent 思考。

## 未决项

- 后续实施需检查 `.loom/templates/spec-template.md` 的初始化和升级传播机制，确认用户自定义模板不会被 bundle 覆盖。
- 若现有 mock LLM 或 parser 有隐含 FR/AC 格式依赖，应仅在实际发现后补最小兼容调整，不提前扩展 Kernel。
