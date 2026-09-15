# Phase 0：范围与不可变边界

## 目标

建立 Spec 阶段改造的事实基线和权责边界，防止后续把 Agent 能力改造实现成 Kernel 语义门禁、SQLite 业务模型或强制流程。

## 已核查事实

- `codeloom/agents/spec-analyzer.md` 是 Spec 需求语义的 stage owner；当前已有事实、推断、owner decision、目标、规则、验收和开放问题，但 workflow 仍是一轮式，并强制 broad demand 使用 journey-order 的 smallest current-release slice。
- `codeloom/agents/spec-reviewer.md` 已限定为只读 advisory reviewer；其输出是 findings 和 main agent 可能需要问的问题。
- `codeloom/app/claude_plugin.py:_agent_rule()` 已向 Claude Code host 投影 stage owner、reviewer、AskUserQuestion 与 artifact 注册规则；`_content_rule()` 要求最终内容是用户可读 Markdown。
- `codeloom/app/stages.py:StageRunner._host_artifact_required_response()` 在 claude-code runtime 下只要求 host 先写最终 artifact；`_artifact_content()` 只校验指定路径；`_sync_artifact_state()` / `_sync_one_artifact()` 只维护 hash、revision、lineage 和 drift。
- `artifact_revisions` 已能通过 spec hash 向 plan、tasks、ship 传递 artifact lineage；它不承载需求语义。
- `tests/test_stage_flow.py`、`tests/test_cli_status_doctor.py` 与 `tests/test_prompt_evals.py` 已验证 host handoff 和 Agent/reviewer 文字边界。

## 涉及文件

后续实现需要参考：

```text
codeloom/agents/spec-analyzer.md
codeloom/agents/spec-reviewer.md
codeloom/templates/spec-template.md
codeloom/app/claude_plugin.py
codeloom/app/stages.py
tests/test_prompt_evals.py
tests/test_stage_flow.py
tests/test_cli_status_doctor.py
```

本 Phase 不修改上述文件。

## 具体改动

后续 Phase 必须遵守以下职责：

| 主体 | 权责 |
|---|---|
| `spec-analyzer` | 通过多轮证据探索理解业务/技术现实，判断目标承诺、方式边界、证明方向与 owner 决策；负责调用 `AskUserQuestion`、吸收答案、综合 reviewer 发现并写最终 Spec。 |
| `spec-reviewer` | 发现需求判断缺口，提供证据、不确定性、影响和建议；只将问题路由回主 Agent。 |
| Claude Code host | 使用 main Agent/reviewer，提供工具上下文，承载 AskUserQuestion，写最终 `spec.md`，调用 Kernel 注册 artifact。 |
| Kernel / SQLite | 验证 artifact_file 位置，保存 artifact revision/hash/lineage、drift finding 和下一步推荐；不读取业务内容作语义裁决。 |

Spec 的多轮是主 Agent 内部的工作循环：新增证据、冲突、owner 回答或 reviewer 发现改变了目标/方式/证明时，Agent 再探索和修订。它不是 Runtime 的 round 状态，也不要求用户每轮确认。

## 明确不改

```text
不修改 codeloom/app/stages.py 的 artifact_file、revision/hash、lineage、drift 或 recommendation 行为。
不修改 persistence/sqlite.py 或 persistence/migrations.py。
不新增 Goal / Method / Proof 表、Goal ID、Goal graph、trace graph 或语义状态机。
不新增 Spec approval state、澄清轮次持久化、固定 AskUserQuestion gate。
不新增 stage、Agent、CLI 参数或 nested runtime。
不让 Kernel 判断“Spec 是否业务完整”“是否问过用户”“是否达到第几轮”。
```

## 完成标准

- 后续每项提示、模板和测试改造都能归属到 Agent、reviewer 或 host，不需要为语义正确性修改 Kernel。
- 主 Agent 与 Kernel 的边界可用一句话描述：Agent 负责需求判断，Kernel 负责 artifact 运行事实。
- `spec-goal-method.md` 仅作为旧候选输入，不被当作新模型的权威定义。

## 风险

| 风险 | 控制方式 |
|---|---|
| 将“目标—方式—证明”误实现为 runtime 字段或硬契约 | 只放入 Agent reasoning、artifact 表达和 prompt eval。 |
| 为追踪多轮澄清增加 session 状态机 | 多轮仅由 host/main Agent 的当前对话与 artifact revision 自然承接。 |
| 将 artifact hash 当作业务证据 | hash 只证明 artifact 版本与下游 lineage，不证明需求语义正确。 |
| reviewer 成为第二需求 owner | 保持 advisory output；主 Agent 决定吸收、拒绝或询问。 |

## 依赖与顺序

本 Phase 是后续所有 Phase 的前置条件。Phase 1、2、3、4 的任何方案若触及本页“明确不改”的部分，应回到本页重新评估，而不是直接扩展 runtime。

## 未决项

- 后续实际实施时，是否需将现有已初始化项目中的 `.claude/agents/` 和 `.loom/templates/` 更新为新 bundle，须在 Phase 4 按项目自定义覆盖风险制定迁移策略。
- 本轮不判断 `spec-goal-method.md` 中每一条历史观点的对错；只禁止它绕过新的 Phase 设计直接成为实现要求。
