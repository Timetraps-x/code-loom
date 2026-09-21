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
- `do` executes only the current task. SQLite holds frozen inputs, sealed change manifests, review/verification conclusions, and completion recovery state; `.loom/runs/` holds non-empty logs and file-based evidence worth inspecting.
- `ship` runs after all current Build and Verify tasks have effective results, then generates `release.md` stating what was delivered, what was proven, and whether the change is ready to release.

## Project Layout

After initialization, a project contains:

```text
.loom/project.yml           # Project configuration
.claude/skills/loom-*/      # Stage Skills plus current-Main role references
.claude/agents/*.md         # Bounded reviewers and Adopt subagent
.loom/templates/            # Project-customizable artifact templates
.loom/loom.db               # Local SQLite runtime state
.loom/runs/<branch_slug>/   # Non-empty logs and file-based evidence
specs/<branch_slug>/        # spec.md / plan.md / tasks.md / release.md
```

`.loom/templates/` is the project template area. Teams may edit or replace these templates directly. Running `loom init` again preserves existing templates unless `--force` is used. `loom upgrade --claude-code` updates only the managed `.claude/agents/` and `.claude/skills/` projection; use `loom init --force` when you intentionally want to refresh bundled project templates.
Main Role prompts under each Skill are managed CodeLoom resources: the current Main loads them directly instead of launching a stage-owner subagent. `.claude/agents/` contains only bounded reviewers and the Adopt expert.

`.loom/project.yml`, `.loom/loom.db`, and `.loom/runs/` are local project configuration and runtime data. Small execution records belong in SQLite, not one JSON file per internal step. `.loom/runs/` is for inspectable or larger evidence, not a long-term audit archive or source-code duplicate. `specs/<branch_slug>/` contains deliverable Markdown artifacts.

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
uv tool install codeloom --from git+https://github.com/Timetraps-x/code-loom.git@v0.5.3
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
# First request each artifact handoff without artifact_file.
loom stage spec --branch <branch>
loom stage plan --branch <branch>
loom stage tasks --branch <branch>
loom stage do --branch <branch> --arg task_id=T1 --arg action=begin
loom stage do --branch <branch> --arg action=complete --arg attempt_id=<attempt-id> --arg status=implemented --arg summary=<summary>
loom stage ship --branch <branch>
# Write the artifact, then execute the exact register_command returned by its handoff.
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
- Artifact Markdown files are working copies. Only the exact `register_command` returned by the current handoff creates an authoritative revision; Plan, Tasks, and Ship commands include a frozen input token.
- New Do attempts require current registered Spec → Plan → Tasks lineage. Existing attempts resume from their frozen Task Packet instead of rebuilding context from the current `tasks.md`.
- `action=unlock` is an explicit user recovery command. Without `status`, it releases an erroneous mechanical block, preserves evidence, and leaves the attempt non-successful.
- If the user explicitly says the task was completed manually, `action=unlock` with the exact `attempt_id`, `status=implemented|verified`, and a summary records that manual completion and can unblock dependents. Later Do work still passes current lineage, task identity, and remaining dependency checks.
- Successful build tasks are recorded as `implemented`; successful verify tasks are recorded as `verified`.
- Verify tasks require evidence. Missing evidence downgrades a claimed `verified` completion to `blocked`.
- Blocked attempts can be retried explicitly for the same task without editing `tasks.md`; unrelated tasks remain blocked while a blocking finding is open.
- New Do attempts do not generate Task Packet, attempt-changes, review, completion-candidate, or verification-summary JSON files. Those records live in SQLite and reach the Host through normal handoffs. Non-empty stdout/stderr remain files; verification-summary input files are read without being copied into `.loom/runs/`. Existing file-backed attempts remain readable, and upgrades do not delete their evidence. No-log attempts need no Do files; full patch archives are not added.

### Projects with nested Git repositories

`loom init` discovers project Git roots and records them in `.loom/project.yml`. Adopt does not maintain repository scope; Do uses the configured scope rather than discovering more repositories. Ordinary init fills a missing scope and preserves an existing list. Use `loom init --refresh-repositories` to explicitly rediscover roots and update their scope without `--force` or replacing unrelated configuration.

Discovery includes nested roots even when ignored by the parent, but skips symlink/junction directories and conventional metadata, dependency, cache and build directories (`.git`, `.loom`, `.claude`, `node_modules`, `vendor`, `.venv`, `venv`, `__pycache__`, `.tox`, `.cache`, `.pytest_cache`, `.mypy_cache`, `build`, `dist`, `target`, `.gradle`). Review the generated list; maintain intentionally excluded roots directly in configuration. Without an outer Git root, normal init still creates the project skeleton but does not invent repository scope. Example:

```yaml
git:
  repositories:
    - "."
    - "services/app"
    - "clients/site"
```

Paths are relative to the project root, not business-role names. Include the outer Git root (`.`). Explicitly configured nested repositories are captured even when the outer repository ignores them; each repository's own ignore and Git attributes still apply. Omitted configuration retains legacy single-root behavior. Use an indented block list, not an inline YAML list.

A new attempt freezes the scope in SQLite. Scope edits apply to future attempts; old attempts keep their original snapshot semantics. Do collects each repository with a temporary index and imports its content into one aggregate evidence tree. Review still uses one frozen Git diff; later edits in any included repository invalidate the old seal. Real indexes, HEADs and source files are not changed. No per-repository JSON or patch files are generated.

This repair requires an outer repository with HEAD. Configured tracked submodules/gitlinks, overlapping tracked ownership, mixed Git object formats and sparse checkouts report explicit limitations instead of silently losing evidence. Unconfigured gitlinks remain pointers, not reviewed inner source. Missing repositories or failed diffs are errors, not empty successful changes. Historical missing baselines are not reconstructed, and Git snapshot objects are not a permanent source archive.
- The do stage treats the current task as the direct execution boundary. It only rereads `spec.md` / `plan.md` when the task points there, context is ambiguous, or implementation reveals a conflict.

## Verification

```powershell
uv run pytest
uv run python -m compileall codeloom
```
