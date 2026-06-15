# CodeLoom

CodeLoom 是一个轻量的 AI coding workflow harness。它把一次需求交付组织为 `spec -> plan -> tasks -> do -> ship`，并把每个阶段的产物、执行记录和验证证据留在项目中。

CodeLoom 不替代 Claude Code，也不自建完整 AI coding 平台；它负责阶段边界、产物投影、任务执行记录和交付收敛。

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
- `tasks.md` 将 plan 中的设计事实投影为可执行的 build / verify 任务边界。
- `do` 只执行当前 task，并把 runtime 输出、diff 和验证结果记录到 SQLite / `.loom/runs/`。
- `ship` 生成 `release.md`，汇总完成情况、证据和剩余风险。

## 项目布局

初始化后，一个项目会包含：

```text
.loom/project.yml           # 项目配置
.claude/skills/loom-*/      # Claude Code /loom-* project skills
.claude/agents/*.md         # CodeLoom stage / do agents
.loom/templates/            # 项目可定制 artifact 模板
.loom/loom.db               # 本地 SQLite runtime state
.loom/runs/<branch_slug>/   # do attempt evidence
specs/<branch_slug>/        # spec.md / plan.md / tasks.md / release.md
```

`.loom/templates/` 是项目模板区，可以按项目直接修改或替换。再次执行 `loom init` 不覆盖已有模板，除非传 `--force`。

`.loom/project.yml`、`.loom/loom.db` 和 `.loom/runs/` 是本地项目配置与运行时状态；`specs/<branch_slug>/` 是交付类 Markdown artifact。

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
uv tool install codeloom --from git+https://github.com/Timetraps-x/code-loom.git@v0.2.2
loom --help
```

本地开发安装：

```powershell
uv tool install --editable <repo-path>
```

## 快速开始

在目标项目中初始化 Claude Code 集成：

```powershell
loom init --claude-code
```

然后按阶段推进：

```powershell
loom stage spec --branch <branch>
loom stage plan --branch <branch>
loom stage tasks --branch <branch>
loom stage do --branch <branch> --arg task_id=T1
loom stage ship --branch <branch>
```

常用辅助命令：

```powershell
loom status --branch <branch>
loom doctor
```

默认输出为 human-readable 摘要；需要机器输出时加 `--json`。

## Claude Code slash commands

`loom init --claude-code` 会安装项目级 slash commands：

```text
/loom-spec
/loom-plan
/loom-tasks
/loom-do T1
/loom-ship
```

这些命令负责生成干净的 Markdown artifact 并交给 CodeLoom Kernel 登记；Kernel 负责维护 artifact 状态、SQLite runtime state 和 do attempt evidence。

## Runtime 行为

当前版本重点支持 Python CLI + Claude Code 集成：

- build task 成功后记录为 `implemented`。
- verify task 成功后记录为 `verified`。
- runtime 失败、验证失败或阻塞会记录为 `failed` 并保留 evidence。
- do 阶段使用当前 task 作为直接执行边界；只有 task 指向、上下文不清或发现冲突时，才回读 `spec.md` / `plan.md`。

## 验证

```powershell
uv run pytest
uv run python -m compileall codeloom
```
