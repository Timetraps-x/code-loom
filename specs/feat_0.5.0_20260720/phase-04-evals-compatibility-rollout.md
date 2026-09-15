# Phase 4：Prompt Eval、兼容性回归与 Rollout

## 目标

用真实 AI coding 失败模式验证 Spec 阶段能力是否真的改变，同时保持现有 host-authored artifact、hash/lineage 与 drift 机械契约无回归。

评估重点不是“新模板标题是否存在”，而是 Agent 是否做出了正确的探索、收敛、边界和澄清判断。

## 已核查事实

- `tests/test_prompt_evals.py` 当前使用 prompt 文本 guardrail 断言，已覆盖 `spec-analyzer` 的事实/推断/owner decision、bounded clarification 与 planning handoff，也覆盖 reviewer 不直接提问和 host handoff。
- `tests/test_stage_flow.py` 覆盖 claude-code 各 artifact 必须有 `artifact_file`、精确 `specs/<branch>/...` 路径、无 fallback artifact，以及 artifact drift resolution。
- `tests/test_cli_status_doctor.py` 覆盖 host handoff 的 blocked response 和 extras。
- `codeloom/app/stages.py` 不读取 Spec Markdown 的章节或业务内容；模板变化不会要求 schema migration。

## 涉及文件

后续实现主要修改：

```text
tests/test_prompt_evals.py
codeloom/prompt_evals/cases.py（按当前 case 机制确认后再改）
codeloom/prompt_evals/surfaces.py（按当前 surface 机制确认后再改）
```

必须保持并运行：

```text
tests/test_stage_flow.py
tests/test_cli_status_doctor.py
tests/test_host_handoff.py（若当前仓库存在该文件）
tests/test_init.py（若修改 bundle/template 初始化断言）
```

## 具体改动

### 1. 以行为判例增强 Prompt Eval

新增或改写判例，使 Agent prompt 必须表达以下判断能力。

| 判例 | 输入风险 | 期望能力 |
|---|---|---|
| 新增售后域 | 大需求被自动缩成“创建工单”或表单/API | 先查当前运行、角色责任、事实来源、工作面、履约承诺和既有承接；只有真实承诺分歧才提问。 |
| SIM 服务期同步 | AI 因“更通用/安全”补订单、查 ERP、扩大处理集、默认 batch、兜底或更新额外字段 | 明确处理/排除集、事实主权、禁止副作用和相称证明。 |
| 订单导出字段错误 | 小闭合修复被迫做领域建模、目标候选或 AskUserQuestion | 直接收敛正确字段、处理范围、正确结果和定向证明。 |
| 售后退款 | “同意退款”被混同为“退款已完成” | 区分处理结论、财务事实主权、外部副作用、失败状态和证明边界。 |
| UI 工作面 | 截图、页面渲染或 HTTP 200 被当成业务完成 | 要求角色完成动作、正确状态/数据或副作用、反馈和关键失败路径的证明方向。 |
| Owner 决策 | reviewer 直接提问/决定 ready，或 Agent 对低影响实现细节提问 | reviewer 只路由；主 Agent 仅在 owner-bearing ambiguity 中形成带推荐的决策包。 |

Guardrail 断言应尽量针对行为边界，避免只绑定一个标题、一个表格或具体文案。

### 2. 调整旧的 journey-slicing 断言

移除或替换依赖以下旧模型的测试断言：

```text
journey order
smallest current-release slice
later/out slices
Current Release Goal
Candidate Goal Slices
```

替换为：

```text
不按技术层拆分；
不自动选择最早或最小 CRUD；
通过证据裁决当前必要、既有承接、当前排除、调研无关与 owner 决策；
多个可信承诺方向且证据无法决定时，形成 bounded AskUserQuestion；
小需求不因形式被过度探索。
```

### 3. 保持 host/runtime 兼容性测试

以下现有测试语义不得弱化：

```text
claude-code 未提供 artifact_file 时必须返回 host-authored handoff；
artifact_file 必须是当前 branch 对应的精确 artifact 路径；
不能生成 fallback artifact；
artifact revision/hash/lineage 与 drift resolution 保持；
main_agent/reviewer_agent extras 保持可用；
最终 artifact 只含用户可读 Markdown。
```

这些验证的是宿主与 Kernel 的机械契约，不是 Spec 语义 gate。

### 4. Rollout 与已有项目迁移

发布说明需区分 bundle 与已初始化项目：

- 新项目会从更新后的 bundled agents/templates 获得新能力。
- 已有项目内的 `.claude/agents/`、`.loom/templates/` 可能被用户自定义；不能被 `init` 强制覆盖。
- 提供显式、人工审阅式迁移说明：对比 bundled `spec-analyzer.md`、`spec-reviewer.md`、`spec-template.md` 后，仅迁移新能力/边界文本，保留项目规则和模板定制。
- 不把 prompt eval 或升级检查变成运行时阻塞；它们是平台维护验证。

### 5. 后续实际实施验证命令

修改实现后按依赖顺序执行：

```text
uv run pytest tests/test_prompt_evals.py tests/test_stage_flow.py tests/test_cli_status_doctor.py
uv run pytest
```

如果修改初始化 bundle，再补：

```text
uv run pytest tests/test_init.py
```

无需运行 `tests/test_sqlite_migrations.py`，除非实际范围违反本 Phase 的“不改 SQLite”边界；出现这种情况应先回到 Phase 0 重新决策。

## 明确不改

```text
不新增 Kernel semantic test 或 runtime gate。
不新增 SQLite migration、Spec 表或 artifact metadata。
不将 prompt eval 失败映射为用户项目运行时 blocked。
不以替换模板标题作为测试通过标准。
不为测试目的重构 stages.py 或 artifact parser。
不在本轮扩展 Plan / Tasks / Do / Ship 的功能范围。
```

## 完成标准

- Prompt eval 能区分目标漂移、方式漂移、证明漂移、现实误判、越权收敛和轻量性失败。
- 新增售后域、SIM 同步和订单导出修复三类判例的期望行为都可明确表达。
- reviewer 不直接问用户或决定 readiness 的规则仍被测试。
- host handoff、精确 artifact 路径、hash/lineage、drift 和无 fallback artifact 的回归测试继续通过。
- 新模板可以省略 FR/AC 或固定标题而不触发 Kernel 行为变化。
- 文档/测试中没有把 Spec 语义检查升级为 SQLite 或 `StageRunner` 职责。

## 风险

| 风险 | 控制方式 |
|---|---|
| 只做字符串替换，真实能力未改变 | 以具体失败模式建立 guardrail；后续可加入人工/模型判例评估。 |
| 测试过度绑定新术语 | 断言行为边界和禁止行为，不强制某个 Markdown 标题。 |
| 改 Agent 后 host projection 仍保留旧规则 | 同时断言 `_agent_rule("spec")`、analyzer 与 reviewer 关键语义。 |
| 影响已有项目自定义模板 | 采用显式、人工审阅迁移，不自动覆盖。 |
| 为追求覆盖引入大规模 runtime 测试 | 保持现有 host/runtime 回归；不新建语义执行引擎。 |

## 依赖与顺序

依赖 [Phase 0](phase-00-scope-and-invariants.md)、[Phase 1](phase-01-analyzer-workflow.md)、[Phase 2](phase-02-decision-artifact.md) 和 [Phase 3](phase-03-reviewer-host-projection.md)。

必须在 Agent、artifact、reviewer/host 语义稳定后执行。测试应验证已设计的能力，不应反向决定业务模型。

## 未决项

- 需要在实际实施前读取 `codeloom/prompt_evals/cases.py` 和 `surfaces.py`，确定其是否已适合承载行为判例；若不适合，先在 `tests/test_prompt_evals.py` 做最小补充，避免额外 eval 框架。
- 需要确认 `tests/test_host_handoff.py` 是否存在；若不存在，以实际已有 host handoff 测试文件为准，不创建重复覆盖。
