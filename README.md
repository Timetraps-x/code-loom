# CodeLoom

CodeLoom is a lightweight project delivery harness that runs on host agent runtimes such as Claude Code. It organizes a requirement delivery into `spec -> plan -> tasks -> do -> ship`, and keeps stage artifacts, execution records, and verification evidence inside the project.

CodeLoom does not replace the host runtime, rebuild the agent loop, or become a heavy multi-agent platform. It adds project delivery structure: project engineering baselines, spec/plan/tasks/release artifacts, task attempt state, and feedback regressions so models have the context, boundaries, and evidence structure needed to deliver correct, performant, maintainable, project-fit code.

Chinese documentation: [READMEZH.md](READMEZH.md).

## Workflow

```text
spec   requirement semantics
plan   system design facts
tasks  build / verify execution boundaries
do     current task execution and evidence recording
ship   release.md delivery conclusion
```

Core principles:

- `spec.md` describes requirement semantics and observable acceptance criteria.
- `plan.md` describes design facts, constraints, risks, and verification strategy; it does not define do-stage task slicing.
- `tasks.md` projects plan design facts into executable build / verify task boundaries, plus a verification coverage map for requested behavior and material regression surfaces.
- `do` executes only the current task and records minimal current-lifecycle auxiliary evidence in SQLite / `.loom/runs/`, including attempt changes, runtime logs, and verification summaries when available.
- `ship` generates `release.md` with completed work, evidence, and remaining risk.

## Project Layout

After initialization, a project contains:

```text
.loom/project.yml           # Project configuration
.claude/skills/loom-*/      # Claude Code /loom-* project skills
.claude/agents/*.md         # CodeLoom stage / do agents
.loom/templates/            # Project-customizable artifact templates
.loom/loom.db               # Local SQLite runtime state
.loom/runs/<branch_slug>/   # Current-lifecycle do attempt auxiliary evidence
specs/<branch_slug>/        # spec.md / plan.md / tasks.md / release.md
```

`.loom/templates/` is the project template area. Teams may edit or replace these templates directly. Running `loom init` again preserves existing templates unless `--force` is used.

`.loom/project.yml`, `.loom/loom.db`, and `.loom/runs/` are local project configuration and runtime state. `.loom/runs/` stores minimal auxiliary evidence for the current Loom lifecycle, not long-term audit archives or source-code duplicates. `specs/<branch_slug>/` contains deliverable Markdown artifacts.

## Specs Artifact Language

CodeLoom writes deliverable artifacts under `specs/<branch_slug>/`. Their prose language is configured in `.loom/project.yml`:

```yaml
specs:
  language: en
```

Supported values are currently `en` and `zh`. The default is `en`.

Initialize a project with Chinese deliverable artifacts:

```powershell
loom init --language=zh
```

The bundled templates remain the default structure and governance source; `specs.language` controls the language of generated artifact prose.

## Installation

Requirements:

```text
Python >= 3.11
uv
```

Development environment:

```powershell
uv sync
uv run loom --help
```

Install from a Git tag:

```powershell
uv tool install codeloom --from git+https://github.com/Timetraps-x/code-loom.git@v0.4.0
loom --help
```

Local editable install:

```powershell
uv tool install --editable <repo-path>
```

## Quick Start

Initialize Claude Code integration in the target project. `loom init` defaults to the same Claude Code integration as `loom init --claude-code`:

```powershell
loom init
```

Then move through artifact stages and the host-runtime do handoff:

```powershell
loom stage spec --branch <branch> --arg artifact_file=specs/<branch>/spec.md
loom stage plan --branch <branch> --arg artifact_file=specs/<branch>/plan.md
loom stage tasks --branch <branch> --arg artifact_file=specs/<branch>/tasks.md
loom stage do --branch <branch> --arg task_id=T1 --arg action=begin
loom stage do --branch <branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=implemented --arg summary=<summary>
loom stage ship --branch <branch> --arg artifact_file=specs/<branch>/release.md
```

For verify tasks, complete with `status=verified` only when verification evidence exists. Large or shell-sensitive summaries can be passed with `--arg verification_summary_file=<path>` instead of inline JSON.

Common helper commands:

```powershell
loom status --branch <branch>
loom doctor
```

The default output is human-readable. Add `--json` for machine output.

## Claude Code Slash Commands

`loom init` / `loom init --claude-code` installs project-level slash commands:

```text
/loom-spec
/loom-plan
/loom-tasks
/loom-do T1
/loom-ship
```

These commands draft clean Markdown artifacts and register them through the local CodeLoom harness. CodeLoom records artifact state, maintains SQLite runtime state, and stores do-attempt evidence.

## Runtime Behavior

The current release focuses on the Python CLI + Claude Code integration:

- A normal `loom init` creates `.loom/project.yml` with `runtime.default: claude-code`.
- In generated config, `claude-code` uses `mode: host`: the current Claude Code session runs each task with explicit `action=begin` / `action=complete` handoff instead of launching a nested `claude -p` process.
- The `mock` runtime remains available for tests and explicit fallback initialization, but it is not the normal do-stage runtime.
- Successful build tasks are recorded as `implemented`; successful verify tasks are recorded as `verified`.
- Verify tasks require evidence. Missing evidence downgrades a claimed `verified` completion to `blocked`.
- Blocked attempts can be retried explicitly for the same task without editing `tasks.md`; unrelated tasks remain blocked while a blocking finding is open.
- do-attempt evidence includes lightweight `attempt-changes.json`, runtime stdout/stderr logs when non-empty, and optional `verification_summary` / `verification_summary_file` content; patch files and full git status snapshots are not persisted by default.
- The do stage treats the current task as the direct execution boundary. It only rereads `spec.md` / `plan.md` when the task points there, context is ambiguous, or implementation reveals a conflict.

## Verification

```powershell
uv run pytest
uv run python -m compileall codeloom
```
