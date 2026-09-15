# Tasks 阶段 LLM 验证记录（当前未执行）

## 目的与当前状态

本记录为 `task-planner`、`task-reviewer`、Tasks Host projection、模板和行为 oracle 预留一次受控真实模型回测。目标不是让模型替代 Kernel，也不是把 Tasks 变成第二个 Plan；目标是观察它们是否能完成以下闭合：

```text
accepted Plan design
→ implementation result chain
→ coherent build slices
→ behavior/risk verify coverage
→ self-contained task packets
→ packet-local Revision judgment
→ downstream-consumer counterexample review
```

**当前状态：已完成一次受限的只读 subagent 回测；尚未完成真实项目端到端回测。** 此前本环境在继续发起类似 `claude --model sonnet -p` 调用时，以“launches an autonomous agent without a named sandbox or approval mechanism”拒绝执行。该权限边界没有被规避；本次通过受控 read-only subagent 获得了一个 case-level 失败信号，也没有把静态测试表述为真实模型行为证据。

本文件记录可重复的验证协议、输入版本、静态证据和该次 subagent 观察，不得据此宣称 Planner 或 Reviewer 已在真实仓库、不同模型或复杂未整理需求中稳定通过。

## 固定输入版本

| Surface | SHA-256 |
| --- | --- |
| `codeloom/agents/task-planner.md` | `d909fc968e8d4040e2dc64f4b51eb6a3140bb9101f1ca736f436bc2e42821cc9` |
| `codeloom/agents/task-reviewer.md` | `5c9dbcb5b1ba12bee0f0b962e7e5e516860ca0131445ab80ed9ce21735cbd865` |
| `codeloom/templates/tasks-template.md` | `2bc93a3d630e2e504c1cea2223b4694e03c2cdf1e7dc9eabdc40ae421541d455` |
| `codeloom/app/claude_plugin.py` Tasks Host projection | `502e7ae4be50b9bc3c25892dc668a17c2359e6ec6d39fb7f551ea3313060dfdc` |

| Case | SHA-256 |
| --- | --- |
| `simple-local-correction.md` | `862c2e8ff1b459b613319e3a7149600a556d481d3cbcbd40d67a13f98a7c9dd2` |
| `cross-layer-capability-slicing.md` | `122a8d63dbf9b4cc2cb572d31679d7c6c7c6974fa06d8c05d721628966a27495` |
| `async-evolution-handoff.md` | `568cf4be12dfb604e3c0a783b7bb05c9a60e37233b9cf43421c9cf024b74dc27` |
| `revision-locality.md` | `4442a46631eef3229a54570539caa47dd124c7fe6318c7c733579d437f15fe14` |
| `malformed-stale-candidate.md` | `c8417caa1385747a27f56113c6b72b1c9b2399260221a41afcdc86cb590411c5` |

## 已完成的静态验证

以下验证只证明源码资源、Host 文案与 oracle 资源彼此对齐：

```text
.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider \
  tests/test_prompt_evals.py \
  tests/test_plan_template.py \
  tests/test_init.py \
  tests/test_task_lanes.py \
  tests/test_retry_supersede.py \
  tests/test_stage_flow.py \
  tests/test_claude_projection.py \
  -k "not packaged_plan_resources_match_source_resources" -q

134 passed, 1 deselected
```

该组测试守护：

- Planner 从 selected Plan design 形成 result chain，按交付结果切分 build、按行为/风险切分 verify，而不按 UI/API/service/DAO 机械拆分；
- 每个 packet 在自身 captured block 内承载 `why / what / where / guard / stop / proof` 所需信息；
- Reviewer 接收 exact candidate text 和 identity，缺失或不匹配时只返回 missing-input，不从磁盘推断候选；
- Reviewer 的方法是 `Baseline → Simulate Consumer → Falsify → Hand back`，并只复审新 identity 的受影响 packet/claim；
- Revision 仅随 execution meaning 局部变化，普通 prose 更新与无关 attempt 不被扩散；
- 五个 Tasks quality case 是 package resources，且不会被 `loom init` 投影为用户 positive cases。

另已执行：

```text
.venv\Scripts\python.exe -B -m compileall -q codeloom
git diff --check
```

二者均未报告 Python 编译或 diff whitespace 错误；`git diff --check` 输出的 CRLF 提示来自工作区既有文件转换提示，不是 whitespace error。

## 待执行的真实模型协议

每个 case 必须使用当前 Prompt 原文、accepted Spec/Plan signals 与 confirmed facts；不得让 Planner 读取另一份候选或把 case 文本本身注册为 `tasks.md`。

```text
accepted Spec + Plan + confirmed facts
→ fresh Planner exact candidate (identity v1)
→ Host supplies the exact candidate text + identity v1
→ fresh Reviewer derives baseline and simulates consumer
→ Planner applies smallest packet-local revision or evidence-backed rejection
→ Host supplies exact revised candidate (identity v2)
→ Reviewer re-reviews only affected packet/claim
→ compare against case oracle
```

每次调用要记录模型、日期、Prompt/case hash、candidate identity、完整 candidate、每项 oracle 的命中/漏检、Revision 前后 packet delta、复审范围及权限/调用结果。没有 exact candidate identity 的 Reviewer 输出不得作为 candidate finding；没有模型调用或没有可观察输出的 case 必须保留为“未执行”。

### Case-Level Pass/Fail Conditions

| Case | Planner pass condition | Reviewer pass condition |
| --- | --- | --- |
| Simple local correction | 一个紧凑 build + verify 或等价结果切片；不制造 DB、DTO、迁移、Job 或 research work。 | 能指出全局替换/DTO 扩展的越界后果；不因无 schema、diagram 或理想 harness 误报。 |
| Cross-layer capability slicing | 保持 server authorization、history、conditional terminal transition 与 customer projection 的不可分割边界；不按 UI/API/service/DAO 分层。 | 只消费 packet 即可构造 direct API bypass、并发 terminal decision、history 或 projection 失败。 |
| Async evolution handoff | 围绕 dispatch identity/outbox、callback state safety、compatibility projection 与风险 verify 切片。 | 发现重复 dispatch、延迟 callback 覆盖、历史 correlation 与 legacy `submitted=true` 的具体 failure；不要求新 queue/coordinator。 |
| Revision locality | 保留 T1/T2 identity；仅在 callback event identity 改变覆盖义务时 bump 受影响 packet。 | 找到遗漏 material bump 与错误 global bump/title churn；不因 T2 prose-only change 误报。 |
| Malformed or stale candidate | 不适用：该 case 直接使用 seeded candidate。 | identity `v1` 不匹配 `v2` 时停止；匹配时发现 duplicate ID、packet-external guard 和缺失 verify proof。 |

## 2026-09-11 Subagent 回测：packet 边界失败信号

### 运行边界

本次使用一个只读 Sonnet subagent，要求其先读取当前 Planner、Reviewer、Tasks template、Tasks Host rule，以及 cross-layer、malformed/stale、revision-locality 三个 oracle；随后在 response 内执行 Planner candidate、Reviewer、identity gate 与 Revision 模拟。没有写入、注册或修改任何 CodeLoom artifact。

该 subagent 的工作目录与 quality case 的可见位置不一致：Prompt/Template 由其隔离 worktree 读取，quality case 由仓库根目录读取。这个布局差异不影响本次 packet 文本判定，但意味着它不是完整 host runtime 的端到端验证。

### 输入与可观察结果

- candidate identity：`tasks-backtest-cross-layer-v1`；
- cross-layer Planner 的业务切片方向正确：将 server-owned action transition、role/current-state guard、immutable history、conditional terminal update 与 customer projection 保持为一个 coherent build result，另配一个按 direct API bypass、concurrency、history 和 projection 风险组织的 verify；
- stale `tasks-candidate-refund-v1` 对 `tasks-candidate-refund-v2` 正确停止候选审查；matching identity 时，正确指出 duplicate `T1`、build packet 缺失 server/history/conditional-update guard，以及 verify packet 缺失 packet-local proof；
- Revision 判断正确保留 T1/T2 identity，T1 的 callback event identity 变化提升 Revision，T2 prose-only Context 保持 Revision，T3 仅在其 proof coverage 扩展时提升。

### 失败：Planner 与同次 Reviewer 都忽略了 packet 截止边界

生成的 `tasks-backtest-cross-layer-v1` 在 `## Task List` 中为 T1/T2 只写了 `Lane`、`Complexity` 和 `Revision`。所有 result、landing、guard、stop、covered relation 与 proof 内容被放进后续 `## Task Notes`、Delivery Map 和全局表格。

这不满足当前 packet contract：每个 checklist line 的 captured block 在下一个 task 或新的 top-level section 前结束，后续 notes 不会成为 T1/T2 的执行上下文。因而 Builder/Reviewer/Verifier 只消费 packet 时，无法得知要保持的 authorization/history/conditional-update/customer-projection result，也无法得知 verify 的 covered proof obligations。

同一 subagent 随后作为 Reviewer 却把这些 later notes 当作 packet 内容并返回“no material counterexample survives”。因此本次 Reviewer 回测**失败**：它没有按照自身 Prompt 的“only that task block / later notes cannot repair”规则构造最小反例。该结果不能被解释为 candidate 通过。

### 定向修正与有限复测

基于该失败，Planner、Reviewer 与 Tasks template 已补强同一条语义：

- metadata-only Task List item 无效；
- packet 从 checklist line 开始，到下一个 task 或新的 top-level section 前结束；
- table、delivery map 和 later `Task Notes` 即使重复同一 ID，也不能补足 packet；
- Reviewer 在模拟 consumer 前必须先隔离这个 packet boundary。

对应 source assertions 已加入 Prompt/template/init 测试，并通过定向源测试。随后 fresh Planner 产生了 `tasks-backtest-cross-layer-v2`：其 T1/T2 都在自身 checklist block 内直接包含 result、landing、guard、stop 与 proof handoff，不依赖 later notes。另一个 fresh Reviewer 只审查该 exact candidate identity 后，正确给出三个 material counterexample：support submission 未被 prove、already-terminal approve/reject 未被 prove、以及 packet 用泛化的 Plan 引用代替精确 state/write/transaction/concurrency contract。

该有限复测证明 metadata-only packet 问题可被 Prompt 收紧并在新候选中避免，也证明 Reviewer 能对看似完整的结果切片提出 verification/self-contained counterexample。它没有完成 Planner 根据这三项 finding 的 revision/re-review，也不证明当前 Prompt 在独立 remote worktree 中可被完整读取；后续仍须使用新的 Prompt hash 和可见的 quality cases 做完整闭环。

## 边界

这些 quality case 是维护者调优资产，不是生产 Tasks evaluator 平台。它们不新增 Kernel 语义解析、dependency graph、scheduler、SQLite state、migration、CLI 或 Do-stage 路由。即使后续完成有限真实模型调用，也只能支持 case-level 行为结论，不能证明跨项目稳定性或所有复杂需求的无歧义消费能力。
