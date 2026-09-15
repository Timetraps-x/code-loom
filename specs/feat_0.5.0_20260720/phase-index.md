# Spec 阶段能力化改造

## 目标

本轮只输出可实施的改造 Phase 文档，不直接修改 `codeloom/agents/`、模板、Python 或测试。

改造目标是将 Spec 从“按固定模板生成文档”调整为由 `spec-analyzer` 主导的、基于证据的需求决策收敛能力：

```text
目标：本轮要改变什么现实结果、建立什么业务承诺。
方式：用什么方法理解和收敛；哪些规则、事实、范围和副作用不能擅改。
证明：什么可观察结果足以说明目标成立；哪些局部产物不能冒充完成。
```

## 已核查边界

| 主体 | 负责 | 不负责 |
|---|---|---|
| `spec-analyzer` | 业务/需求理解、证据探索、目标承诺、方式边界、证明方向、有限 `AskUserQuestion`、artifact 综合与修订 | runtime 状态、hash、lineage、workflow 状态 |
| `spec-reviewer` | 咨询性发现、证据、不确定性、影响与建议 | 写 artifact、直接提问、决定 ready/blocked |
| Claude Code host | 投影 Agent 能力，调用 Agent、写最终 Markdown、传入 `artifact_file` | 判断需求语义是否完整 |
| Kernel / SQLite | artifact 精确路径、revision/hash、lineage、drift、推荐 | 解析目标/方式/证明、判断业务语义、管理澄清轮次或审批 |

现有实现中：

- `codeloom/app/claude_plugin.py:_agent_rule()` 已投影 stage main agent、reviewer、`AskUserQuestion` 和 `artifact_file` handoff。
- `codeloom/app/stages.py:StageRunner._host_artifact_required_response()` 只要求 host-authored artifact；`_artifact_content()` 只验证精确路径；`_sync_one_artifact()` 只登记 revision/hash/lineage 与 drift。
- `tests/test_stage_flow.py`、`tests/test_cli_status_doctor.py` 已覆盖 artifact_file、精确路径、无 fallback 与 drift；这些机械契约保持不变。

## Phase 顺序

```text
Phase 0：范围和不可变边界
  → Phase 1：spec-analyzer 的多轮证据收敛能力
  → Phase 2：轻量需求决策 artifact
  → Phase 3：reviewer、host 投影与 AskUserQuestion 协作
  → Phase 4：prompt eval、兼容性回归与 rollout
  → Phase 5：复杂承诺覆盖与 Plan 承接
```

`phase-00-scope-and-invariants.md` 必须先完成。先定义 Agent 应如何思考，再让模板承接其判断；不能反过来由模板固定思路。

## 文档清单

| Phase | 文档 | 后续主要实现面 |
|---|---|---|
| 0 | [范围与不可变边界](phase-00-scope-and-invariants.md) | 无代码修改；定义边界 |
| 1 | [Analyzer 多轮收敛](phase-01-analyzer-workflow.md) | `codeloom/agents/spec-analyzer.md` |
| 2 | [轻量需求决策 artifact](phase-02-decision-artifact.md) | `codeloom/templates/spec-template.md`、analyzer output contract |
| 3 | [Reviewer、host 与澄清](phase-03-reviewer-host-projection.md) | `spec-reviewer.md`、`codeloom/app/claude_plugin.py` |
| 4 | [评估、兼容与 rollout](phase-04-evals-compatibility-rollout.md) | `tests/test_prompt_evals.py`、现有 host/runtime 回归 |
| 5 | [复杂承诺覆盖与 Plan 承接](phase-05-commitment-coverage-handoff.md) | Spec/Plan agents、模板与行为型评测 |

## 明确不在本轮引入

```text
Goal / Method / Proof SQLite 表或 ID 生命周期
Goal graph / trace graph
Spec approval state 或澄清轮次持久化
Kernel 语义解析、完整性 gate、固定 AskUserQuestion gate
新阶段、新 Agent、新 CLI 参数或平行运行时
对 Plan / Tasks / Do / Ship 的重新设计
```

`spec-goal-method.md` 是此前讨论形成的候选输入，其中的 `journey order`、`smallest current-release slice`、`now/later/out` 不能直接成为新模型规则。

## 文档级验收

- 每个 Phase 都明确：目标、已核查事实、涉及文件、具体改动、明确不改、完成标准、风险、依赖/顺序、未决项。
- 每项 Kernel 描述仅限于 artifact 注册、hash/lineage、drift 与推荐，不能赋予业务判断职责。
- 后续实施无需修改 `stages.py`、`persistence/sqlite.py` 或 `persistence/migrations.py`。
