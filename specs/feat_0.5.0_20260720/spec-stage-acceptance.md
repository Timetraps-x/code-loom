# Spec 阶段达标验收

## 本轮目标

确认 Spec 能将人类不完整需求收敛为 Plan 无需重新猜测的 AI-Coding 需求，同时保持 Agent 语义判断、Host 执行协作、Kernel 机械登记的边界。

## 已落实的设计边界

| 目标 | 实现证据 | 状态 |
|---|---|---|
| 需求发现与收敛 | `spec-analyzer.md` 保留背景、目标相关场景、最小完整链路、显式/隐含承诺与证据分类 | 已落实 |
| 目标、方式、证明 | Analyzer 以 Goal / Way / Proof 组织判断，但不把它们变成模板或 Kernel schema | 已落实 |
| 复杂需求承诺覆盖 | 每项材料性承诺有当前必要、已有承接、实现差距、证据缺口、合法承接、无关或 Owner decision 去向 | 已落实 |
| 可选承诺标签 | `C:` 或自然语言标签仅用于复杂需求的可读定位；不要求 ID、谱系或跨 revision 追踪 | 已落实 |
| Reviewer 协作 | Reviewer 返回 evidence、uncertainty、impact、recommendation 与主 Agent 可路由的问题；不直接问用户或决定 readiness | 已落实 |
| Owner 澄清 | 改变 requirement correctness 的未决 Owner decision 不写入或注册 final Spec；普通技术设计问题交给 Plan | 已落实 |
| 弹性 artifact | 模板是用户可读的决策投影，不是固定栏目或 parser schema | 已落实 |
| Kernel 边界 | 未修改 `StageRunner`、SQLite、migration、artifact registration、hash/revision/drift 机制 | 已保持 |

## 自动化验证

已通过：

```text
.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider \
  tests/test_spec_evals.py \
  tests/test_spec_artifact_evals.py \
  tests/test_prompt_evals.py \
  tests/test_claude_projection.py

51 passed

.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider \
  tests/test_plan_template.py -k "not packaged_plan_resources_match_source_resources" \
  tests/test_task_lanes.py \
  tests/test_stage_flow.py \
  tests/test_cli_status_doctor.py

86 passed, 1 deselected
```

离线 `spec_evals` 现在保留初稿与复审后的 rubric 结果，并生成 `comparison.json`，使维护者能看到 reviewer/revision 消除、引入和保留的已知坏模式。该检测仍是确定性回归，不是完整语义 judge。

`tests/test_plan_template.py::test_packaged_plan_resources_match_source_resources` 本轮未纳入通过集：它要求 `build/lib/codeloom/` 与源码逐字同步，但当前 `.venv` 不含 `pip` 或 `setuptools`，仓库又没有 `setup.py`，无法通过现有构建工具重建镜像。该限制不影响源码回归结果，但在可用构建环境中同步 package mirror 前，不应将本轮标记为可发布。

## 尚未能自动证明的能力

离线 evaluator 只接收冻结的 case evidence，并刻意不访问用户仓库、SQLite 或 Claude Code 工具循环。因此它不能证明：

- 从原始、局部的人类描述自主发现完整需求；
- 真实仓库取证是否正确、充分且可定位；
- `AskUserQuestion` 是否只问一个最高信息量 Owner decision，并正确吸收真实回答；
- Reviewer 在真实需求上是否稳定产生净增益；
- Plan 是否只凭最终 Spec 即可正确消费承诺去向与边界。

## 达标所需的 host-native 验证

在隔离的真实项目或受控副本中执行以下三类验证，并把 raw demand、读取证据、初稿、reviewer finding、澄清问题/答案、修订 Spec、Plan 消费结果和人工判定一并追加到本文件：

1. 复杂需求：验证承诺覆盖、当前实现差距、证据缺口和可达副作用的区分。
2. 小闭合修复：验证不会被强制领域化、标签化或无依据扩大范围。
3. Owner 冲突：验证只有唯一最高信息量问题进入 `AskUserQuestion`，回答后重推导 Goal、Way 与 Proof；未回答时不注册 final artifact。

在上述 host-native 证据完成前，本轮结论是：**Spec 的方法、协作边界和确定性回归已达标；真实需求发现与澄清能力仍待真实项目验证，不能宣称整体目标已完全证明。**
