# Tasks

based_on_plan_hash: `<plan-hash>`

> Runtime note:
> `/loom:do` 当前以 checklist 行作为任务来源。
> 请保留 `- [ ] Tn: <task title>` 格式；不要只写 `### Tn`、不要用表格替代 checklist、不要使用中文冒号。

## 1. 执行边界概览

说明任务如何从 `plan.md` 的设计事实投影为执行边界。优先按风险边界、交付边界、依赖顺序和自然验证窗口组织；不要按文件、类、函数或技术层机械拆分。不要复制 plan 的解释过程、替代方案讨论或大段背景；但必须提炼 do 执行所需的设计事实、约束、不变式、契约、风险和验证要求。

## 2. Execution Lanes

Executable task lanes stay deliberately small. They describe what `/loom:do` should execute, not every kind of thinking that may happen around execution.

| Lane | 用途 | 常见 agent |
|---|---|---|
| build | 实现或修改交付物，可能包含代码、SQL、配置、页面、文档 | builder |
| verify | 测试、验收、证据汇总、风险复核，可覆盖多个 build task | verifier |

不要创建 `scout`、`research`、`discovery`、`planning`、`release`、`ship` 等可执行 `Tn` 任务。阻止安全切片的缺失事实必须在生成 `tasks.md` 前澄清或返回 blocked；只有不影响切片安全性的已知约束、风险提醒、验证注意事项，才可写入具体 build/verify task 的上下文。release 相关信息放到非执行的 `Ship inputs`。

## 3. Delivery Map

| Task | Lane | Plan 来源 | 验收来源 | 执行边界 |
|---|---|---|---|---|
| T1 | build | §<plan section> | AC-<id> | <本任务负责的交付或风险边界> |
| T2 | verify | §<plan section> | AC-<id> | <本任务验证的行为、风险或回归面> |

## 4. 执行顺序

如果不涉及依赖，写 `按 Task List 顺序执行`。

| 顺序 | Tasks | 说明 |
|---|---|---|
| 1 | T1 | <前置任务或风险最高任务> |
| 2 | T2 | <后续验证或 release 准备> |

## 5. Task List

- [ ] T1: <任务标题，写结果，不写流水账>
- [ ] T2: <任务标题，写结果，不写流水账>

## 6. Task Notes

### T1: <任务标题>

- Lane: build / verify
- From plan: §<章节>（只引用来源章节，不复制大段 plan 原文；执行所需设计事实写入 Boundary / Done / Notes）
- Acceptance: AC-<id> / N/A
- Depends on: None / Tn
- Scope:
  - `<path-or-module-or-area>`
- Suggested validation:
  - `<command-or-manual-check>`
- Covered by: Tn

#### Boundary

本节描述执行边界，不描述逐行实现步骤。

允许做：

- <本任务允许处理的行为、模块、交付物或配置范围>

禁止做：

- <本任务不得改变的需求语义、公开契约、数据模型语义、主要 UI 流程、后续任务边界或无关重构>

#### Done

- <完成后可观察到的结果>
- <最低验证或证据>

#### Evidence

- <命令输出、截图、SQL 结果、diff、说明或 N/A>

#### Notes

- <仅记录会影响执行判断的设计事实、约束、不变式、契约、风险提醒、验证要求或非阻塞实现提示>
- 不要复制 plan 的解释过程；必须保留 builder / code-reviewer / verifier 不读完整 plan 也能执行和审查的上下文。
- 不要枚举普通局部编码选择；builder 应按现有代码风格和任务边界自行判断。

---

### T2: <任务标题>

- Lane: build / verify
- From plan: §<章节>（只引用来源章节，不复制大段 plan 原文；执行所需设计事实写入 Boundary / Done / Notes）
- Acceptance: AC-<id> / N/A
- Depends on: None / Tn
- Scope:
  - `<path-or-module-or-area>`
- Suggested validation:
  - `<command-or-manual-check>`
- Validates: Tn / N/A

#### Boundary

本节描述执行边界，不描述逐行实现步骤。

允许做：

- ...

禁止做：

- ...

#### Done

- ...

#### Evidence

- ...

#### Notes

- <仅记录会影响执行判断的设计事实、约束、不变式、契约、风险提醒、验证要求或非阻塞实现提示>

## 7. 全局注意事项

- `plan.md` 仍是设计真相源，tasks.md 只做执行切片；不要复制 plan 原文，但必须提炼 do 执行所需的设计事实、约束、不变式、契约、风险和验证要求。
- checklist 行是 runtime 硬接口；其他字段是执行上下文，不作为强 schema。
- 可执行 `Tn` 任务只使用 `build` 或 `verify` lane。
- build task 要说明边界、依赖、停止点和验证覆盖；每个 build task 必须有明确的 `Covered by: Tn` 或 grouped verify task，但不要求每个 build task 单独做完整功能验收。
- verify task 可以按行为、风险或回归面覆盖多个 build task；verify-only 场景可以没有 build task，但 verify task 必须指向 plan section、acceptance criteria 或 expected evidence。
- 如果执行中发现 plan 不成立，应回到 `/loom:plan` 或 `/loom:tasks`；如果影响需求语义，应回到 `/loom:spec`。不要在 task 内擅自扩大范围。
