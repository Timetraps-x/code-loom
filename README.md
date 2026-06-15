# CodeLoom

CodeLoom is a lightweight AI coding workflow harness. It organizes a requirement delivery into `spec -> plan -> tasks -> do -> ship`, and keeps stage artifacts, execution records, and verification evidence inside the project.

CodeLoom does not replace Claude Code and does not try to become a full AI coding platform. It owns stage boundaries, artifact projection, task execution records, and delivery convergence.

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
- `tasks.md` projects plan design facts into executable build / verify task boundaries.
- `do` executes only the current task and records runtime output, diffs, and verification results in SQLite / `.loom/runs/`.
- `ship` generates `release.md` with completed work, evidence, and remaining risk.

## Project Layout

After initialization, a project contains:

```text
.loom/project.yml           # Project configuration
.claude/skills/loom-*/      # Claude Code /loom-* project skills
.claude/agents/*.md         # CodeLoom stage / do agents
.loom/templates/            # Project-customizable artifact templates
.loom/loom.db               # Local SQLite runtime state
.loom/runs/<branch_slug>/   # do attempt evidence
specs/<branch_slug>/        # spec.md / plan.md / tasks.md / release.md
```

`.loom/templates/` is the project template area. Teams may edit or replace these templates directly. Running `loom init` again preserves existing templates unless `--force` is used.

`.loom/project.yml`, `.loom/loom.db`, and `.loom/runs/` are local project configuration and runtime state. `specs/<branch_slug>/` contains deliverable Markdown artifacts.

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
uv tool install codeloom --from git+https://github.com/Timetraps-x/code-loom.git@v0.2.2
loom --help
```

Local editable install:

```powershell
uv tool install --editable <repo-path>
```

## Quick Start

Initialize Claude Code integration in the target project:

```powershell
loom init --claude-code
```

Then move through the stages:

```powershell
loom stage spec --branch <branch>
loom stage plan --branch <branch>
loom stage tasks --branch <branch>
loom stage do --branch <branch> --arg task_id=T1
loom stage ship --branch <branch>
```

Common helper commands:

```powershell
loom status --branch <branch>
loom doctor
```

The default output is human-readable. Add `--json` for machine output.

## Claude Code Slash Commands

`loom init --claude-code` installs project-level slash commands:

```text
/loom-spec
/loom-plan
/loom-tasks
/loom-do T1
/loom-ship
```

These commands draft clean Markdown artifacts and pass them to the CodeLoom Kernel for registration. The Kernel records artifact state, maintains SQLite runtime state, and stores do-attempt evidence.

## Runtime Behavior

The current release focuses on the Python CLI + Claude Code integration:

- Successful build tasks are recorded as `implemented`.
- Successful verify tasks are recorded as `verified`.
- Runtime failures, verification failures, and blocking findings are recorded with evidence.
- The do stage treats the current task as the direct execution boundary. It only rereads `spec.md` / `plan.md` when the task points there, context is ambiguous, or implementation reveals a conflict.

## Verification

```powershell
uv run pytest
uv run python -m compileall codeloom
```
