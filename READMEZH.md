# CodeLoom

CodeLoom 是一个运行在 Claude Code 等 host agent runtime 之上的轻量项目交付 harness。它把一次需求交付组织为 `spec -> plan -> tasks -> do -> ship`，并把每个阶段的产物、执行记录和验证证据留在项目中。

CodeLoom 不替代 host runtime，不重造 agent loop，也不自建重型多 agent 平台；它通过项目规章基线、需求/设计/任务/发布 artifact、任务尝试状态和反馈回归，为模型提供真实项目交付所需的上下文、边界和证据结构，目标是写出更正确、性能更好、更可维护、更贴合项目的代码。

## 工作流

```text
spec   需求语义
plan   系统设计事实
tasks  build / verify 执行边界
do     当前任务执行与证据记录
ship   release.md 交付结论
```

核心原则：

- `spec.md` 描述需求语义和可观察的验收标准。
- `plan.md` 描述设计事实、约束、风险和验证策略，不负责 do 阶段任务拆分。
- `tasks.md` 将 plan 中的设计事实投影为可执行的 build / verify 任务边界，并用 Verification Coverage Map 覆盖当前需求和关键回归面。
- `do` 只执行当前 task，并把推进当前 Loom 生命周期所需的最小辅助 evidence 记录到 SQLite / `.loom/runs/`，包括 attempt changes、runtime logs 和可用的验证摘要。
- `ship` 生成 `release.md`，汇总完成情况、证据和剩余风险。

## 项目布局

初始化后，一个项目会包含：

```text
.loom/project.yml           # 项目配置
.claude/skills/loom-*/      # Claude Code /loom-* project skills
.claude/agents/*.md         # CodeLoom stage / do agents
.loom/templates/            # 项目可定制 artifact 模板
.loom/loom.db               # 本地 SQLite runtime state
.loom/runs/<branch_slug>/   # 当前 lifecycle 的 do attempt 辅助 evidence
specs/<branch_slug>/        # spec.md / plan.md / tasks.md / release.md
```

`.loom/templates/` 是项目模板区，可以按项目直接修改或替换。再次执行 `loom init` 不覆盖已有模板，除非传 `--force`。

`.loom/project.yml`、`.loom/loom.db` 和 `.loom/runs/` 是本地项目配置与运行时状态；`.loom/runs/` 保存推进当前 Loom 生命周期所需的最小辅助 evidence，不是长期审计归档或源码副本；`specs/<branch_slug>/` 是交付类 Markdown artifact。

## specs 交付文档语言

CodeLoom 会把交付文档写入 `specs/<branch_slug>/`。正文语言由 `.loom/project.yml` 配置：

```yaml
specs:
  language: en
```

当前支持 `en` 和 `zh`。默认值是 `en`。

如果希望初始化为中文交付文档：

```powershell
loom init --language=zh
```

默认模板仍提供结构和治理规则；`specs.language` 控制生成 artifact 正文语言。

## 安装

要求：

```text
Python >= 3.11
uv
```

开发环境：

```powershell
uv sync
uv run loom --help
```

从 Git tag 安装：

```powershell
uv tool install codeloom --from git+https://github.com/Timetraps-x/code-loom.git@v0.4.3
loom --help
```

本地开发安装：

```powershell
uv tool install --editable <repo-path>
```

## 快速开始

在目标项目中初始化 Claude Code 集成。`loom init` 默认等价于选择 `loom init --claude-code`：

```powershell
loom init
```

然后按 artifact 阶段和 host-runtime do handoff 推进：

```powershell
loom stage spec --branch <branch> --arg artifact_file=specs/<branch>/spec.md
loom stage plan --branch <branch> --arg artifact_file=specs/<branch>/plan.md
loom stage tasks --branch <branch> --arg artifact_file=specs/<branch>/tasks.md
loom stage do --branch <branch> --arg task_id=T1 --arg action=begin
loom stage do --branch <branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=implemented --arg summary=<summary>
loom stage ship --branch <branch> --arg artifact_file=specs/<branch>/release.md
```

verify task 只有在有验证证据时才能 complete 为 `status=verified`。较长或容易被 shell quoting 破坏的验证摘要，可以用 `--arg verification_summary_file=<path>` 传文件，而不是内联 JSON。

常用辅助命令：

```powershell
loom status --branch <branch>
loom doctor
```

默认输出为 human-readable 摘要；需要机器输出时加 `--json`。

## Claude Code slash commands

`loom init` / `loom init --claude-code` 会安装项目级 slash commands：

```text
/loom-spec
/loom-plan
/loom-tasks
/loom-do T1
/loom-ship
```

这些命令负责生成干净的 Markdown artifact，并通过本地 CodeLoom harness 登记；CodeLoom 维护 artifact 状态、SQLite runtime state 和 do attempt evidence。

## Runtime 行为

当前版本重点支持 Python CLI + Claude Code 集成：

- 普通 `loom init` 会生成 `.loom/project.yml`，并设置 `runtime.default: claude-code`。
- 生成的配置中，`claude-code` 使用 `mode: host`：由当前 Claude Code 会话通过显式 `action=begin` / `action=complete` handoff 执行 task，而不是再启动嵌套的 `claude -p` 进程。
- `mock` runtime 保留给测试和显式 fallback 初始化，不作为正常 do 阶段 runtime。
- build task 成功后记录为 `implemented`；verify task 成功后记录为 `verified`。
- verify task 必须有 evidence；缺少 evidence 的 `verified` claim 会被降级为 `blocked`。
- blocked attempt 可以显式 retry 同一个 task，不需要改 `tasks.md`；有 open blocking finding 时，其他 task 仍会被阻塞。
- do-attempt evidence 包含轻量 `attempt-changes.json`、非空 runtime stdout/stderr logs，以及可选的 `verification_summary` / `verification_summary_file` 内容；默认不持久化 patch 文件或完整 git status 快照。
- do 阶段使用当前 task 作为直接执行边界；只有 task 指向、上下文不清或发现冲突时，才回读 `spec.md` / `plan.md`。

## 验证

```powershell
uv run pytest
uv run python -m compileall codeloom
```
