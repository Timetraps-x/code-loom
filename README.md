# CodeLoom

CodeLoom 是一个依托 Claude Code / Codex / OpenCode 的 AI coding workflow harness。它组织 `spec -> plan -> tasks -> do -> ship`，不自建 AI coding 平台。

## 当前状态

Phase 1 已跑通最小闭环：

```text
loom init
/loom:spec
/loom:plan
/loom:tasks
/loom:do
/loom:ship
```

核心产物：

```text
project.yml                 # 项目配置
.claude/skills/loom/        # Claude Code /loom:* skills
specs/<branch_slug>/        # spec.md / plan.md / tasks.md / ship.md
.loom/loom.db               # SQLite runtime memory
.loom/runs/<branch_slug>/   # attempt evidence
```

`.loom/` 是本地运行时状态，不提交；`specs/<branch_slug>/` 是交付类 artifact。

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

用户级安装：

```powershell
uv tool install codeloom --from git+https://github.com/Timetraps-x/code-loom.git@v0.1.0
loom --help
```

本地开发安装：

```powershell
uv tool install --editable <repo-path>
```

## 使用

初始化目标项目：

```powershell
loom init
```

CLI：

```powershell
loom stage spec --branch <branch>
loom stage plan --branch <branch>
loom stage tasks --branch <branch>
loom stage do --branch <branch> --arg task_id=T1
loom stage ship --branch <branch>
loom status --branch <branch>
loom doctor
```

Claude Code slash commands：

```text
/loom:spec
/loom:plan
/loom:tasks
/loom:do T1
/loom:ship
```

默认输出为 human 摘要；需要机器输出时加 `--json`。

## 验证

```powershell
uv run pytest
uv run python -m compileall codeloom
```
