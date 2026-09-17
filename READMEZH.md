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
- `do` 只执行当前 task。冻结输入、封存变更清单、审查/验证结论和完成恢复状态保存在 SQLite；`.loom/runs/` 仅保存非空日志以及值得直接查看的文件证据。
- `ship` 在当前全部 Build 和 Verify 任务都已有有效结果后执行，生成 `release.md`，说明交付了什么、证明了什么以及当前是否具备发布条件。

## 项目布局

初始化后，一个项目会包含：

```text
.loom/project.yml           # 项目配置
.claude/skills/loom-*/      # Claude Code /loom-* project skills
.claude/agents/*.md         # CodeLoom stage / do agents
.loom/templates/            # 项目可定制 artifact 模板
.loom/loom.db               # 本地 SQLite runtime state
.loom/runs/<branch_slug>/   # 非空日志及文件证据
specs/<branch_slug>/        # spec.md / plan.md / tasks.md / release.md
```

`.loom/templates/` 是项目模板区，可以按项目直接修改或替换。再次执行 `loom init` 不覆盖已有模板，除非传 `--force`。`loom upgrade --claude-code` 只更新受管理的 `.claude/agents/` 与 `.claude/skills/` projection；只有明确需要刷新 bundled project templates 时才使用 `loom init --force`。

`.loom/project.yml`、`.loom/loom.db` 和 `.loom/runs/` 是本地项目配置与运行时数据。小型执行记录存 SQLite，不再为每个内部步骤生成 JSON 文件；`.loom/runs/` 用于可直接查看或体积较大的证据，不是长期审计归档或源码副本；`specs/<branch_slug>/` 是交付类 Markdown artifact。

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
uv tool install codeloom --from git+https://github.com/Timetraps-x/code-loom.git@v0.5.2
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
# Artifact stage 先不带 artifact_file 请求 handoff。
loom stage spec --branch <branch>
loom stage plan --branch <branch>
loom stage tasks --branch <branch>
loom stage do --branch <branch> --arg task_id=T1 --arg action=begin
loom stage do --branch <branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=implemented --arg summary=<summary>
loom stage ship --branch <branch>
# 写入 artifact 后，执行 handoff 原样返回的 register_command。
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
- Artifact Markdown 文件只是工作副本；只有当前 handoff 返回的完整 `register_command` 才会创建权威 revision。Plan、Tasks、Ship 的命令包含冻结输入 token。
- 新 Do attempt 必须基于 current registered Spec → Plan → Tasks；已有 attempt 从 Frozen Task Packet 恢复，不用当前 `tasks.md` 重建上下文。
- `action=unlock` 只由用户显式触发。不带 `status` 时仅释放错误机械阻塞、保留证据，并让 attempt 保持非成功。
- 如果用户明确说明任务已由自己手工完成，可携带准确 `attempt_id`、`status=implemented|verified` 和摘要执行 `action=unlock`；该操作登记用户的手工完成声明并可解除下游依赖，但后续 Do 仍检查当前 lineage、任务身份和其余依赖。
- build task 成功后记录为 `implemented`；verify task 成功后记录为 `verified`。
- verify task 必须有 evidence；缺少 evidence 的 `verified` claim 会被降级为 `blocked`。
- blocked attempt 可以显式 retry 同一个 task，不需要改 `tasks.md`；有 open blocking finding 时，其他 task 仍会被阻塞。
- 新 Do attempt 不再生成 Task Packet、attempt-changes、review、completion-candidate、verification-summary 五类 JSON 文件。这些记录存入 SQLite，由正常 Host handoff 提供。非空 stdout/stderr 仍保存为文件；verification-summary 输入文件只读取，不复制进 `.loom/runs/`。旧文件型 attempt 保留兼容读取，升级不删除其证据；无日志的执行无需生成 Do 文件，也不新增完整 patch 归档。

### 嵌套 Git 仓库项目

`loom init` 识别项目内 Git 仓库根并写入 `.loom/project.yml`；adopt 不再维护仓库范围，Do 只按配置捕获。普通 init 在缺少仓库范围时补齐，已有列表则原样保留。需要重新识别时使用 `loom init --refresh-repositories`，不需要 `--force`，也不会替换其他配置。

识别包含被父仓库忽略的嵌套仓库，但跳过符号链接/junction 目录及常规元数据、依赖、缓存和构建目录（`.git`、`.loom`、`.claude`、`node_modules`、`vendor`、`.venv`、`venv`、`__pycache__`、`.tox`、`.cache`、`.pytest_cache`、`.mypy_cache`、`build`、`dist`、`target`、`.gradle`）。可检查生成的列表，确需纳入被排除目录时直接维护配置。项目目录没有外层 Git 根时，普通 init 仍创建项目骨架，但不虚构仓库范围。示例：

```yaml
git:
  repositories:
    - "."
    - "services/app"
    - "clients/site"
```

路径相对项目根，不是业务角色名称，需包含外层 Git 根 `.`。显式纳入的内层仓库即使被外层忽略也会独立捕获，仓库内部仍遵循自身 ignore 和 Git attributes。缺少该配置时保留旧单仓库行为；配置使用缩进的 block list，不使用行内 YAML 列表。

新 attempt 将仓库范围冻结到 SQLite，配置修改只影响后续 attempt；旧 attempt 保留原有快照语义。各仓库通过临时 index 采集，内容导入并组成一个证据 tree，Reviewer 仍消费一份冻结 Git diff；任何已纳入仓库的后续代码修改都会使旧 seal 失效。不修改真实 index、HEAD 或源码，不生成每仓库 JSON/patch 文件。

本次要求项目外层仓库已有 HEAD。配置中涉及已跟踪 submodule/gitlink、重复文件所有权、混合 Git 对象格式或 sparse checkout 时明确报告限制，不静默漏捕获。未纳入的 gitlink 仍是指针，不代表审查了内层源码。仓库缺失和 diff 失败不会被当作空改动成功。旧 attempt 缺失的历史基线不会自动重建，Git 快照对象也不是永久源码归档。
- do 阶段使用当前 task 作为直接执行边界；只有 task 指向、上下文不清或发现冲突时，才回读 `spec.md` / `plan.md`。

## 验证

```powershell
uv run pytest
uv run python -m compileall codeloom
```
