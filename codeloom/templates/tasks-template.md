# Tasks

based_on_plan_hash: `<plan-hash>`

> Kernel interface:
> `/loom:do` parses checklist tasks and their immediate metadata as the runtime source of truth.
> Every executable task MUST use this format:
>
> ```markdown
> - [ ] T1: <task title>
>   - Lane: build | verify
>   - Complexity: trivial | small | non-trivial
>   - Revision: 1
> ```
>
> `Revision` changes only when this task's execution boundary, done criteria, verification coverage, lane, or dependency semantics change. Keep it unchanged for wording, formatting, evidence prose, or non-semantic Task Notes updates.
>
> `Task Notes` are for agents and humans. Do not rely on `Task Notes` to provide Kernel metadata. If Task List metadata and Task Notes conflict, Task List metadata is the runtime source of truth.

## 1. Execution Boundary Overview

Describe how design facts from `plan.md` are projected into execution boundaries. Prefer risk boundaries, delivery boundaries, dependency order, and natural verification windows. Do not split mechanically by file, class, function, or technical layer. Do not copy the plan's reasoning process, alternatives discussion, or long background sections; do extract the design facts, constraints, invariants, contracts, risks, and verification requirements needed for do-stage execution.

## 2. Execution Lanes

Executable task lanes stay deliberately small. They describe what `/loom:do` should execute, not every kind of thinking that may happen around execution.

| Lane | Purpose | Common Agent |
|---|---|---|
| build | Implement or modify deliverables, including code, SQL, configuration, UI, or documentation. | builder |
| verify | Test, accept, summarize evidence, and review risks; may cover multiple build tasks. | verifier |

Do not create executable `Tn` tasks for `scout`, `research`, `discovery`, `planning`, `release`, or `ship`. Missing facts that block safe slicing must be clarified before generating `tasks.md` or returned as blocked. Only non-blocking known constraints, risk notes, and validation notes belong in build/verify task context. Release-related information belongs in non-executable `Ship inputs`.

## 3. Delivery Map

| Task | Lane | Complexity | Plan Source | Acceptance Source | Execution Boundary |
|---|---|---|---|---|---|
| T1 | build | small | §<plan section> | AC-<id> | <Delivery or risk boundary owned by this task> |
| T2 | verify | non-trivial | §<plan section> | AC-<id> | <Behavior, risk, or regression surface verified by this task> |

## 4. Verification Coverage Map

This map links build tasks to verification coverage. It is agent/human context, not Kernel metadata. Grouped verification changes verification coverage, not build task granularity; do not merge build tasks merely because they share a verify task.

| Coverage Area | Type | Covered Build Tasks | Verify Tasks | Expected Evidence / Notes |
|---|---|---|---|---|
| <Requested behavior or material regression surface> | requested behavior \| regression \| contract \| state/permission/transaction \| performance/query | Tn | Tn | <Evidence needed to verify this coverage area> |

## 5. Execution Order

If there are no dependencies, write `Execute in Task List order`.

| Order | Tasks | Notes |
|---|---|---|
| 1 | T1 | <Prerequisite or highest-risk task> |
| 2 | T2 | <Follow-up verification or release preparation> |

## 6. Task List

- [ ] T1: <task title, outcome-oriented>
  - Lane: build
  - Complexity: small
  - Revision: 1

- [ ] T2: <task title, outcome-oriented>
  - Lane: verify
  - Complexity: small
  - Revision: 1

## 7. Task Notes

### T1: <task title>

- Runtime metadata: see `## 6. Task List` for Lane, Complexity, and Revision.
- From plan: §<section> (reference source sections only; do not copy large plan text; put execution-critical design facts in Boundary / Done / Notes)
- Acceptance: AC-<id> / N/A
- Depends on: None / Tn
- Scope:
  - `<path-or-module-or-area>`
- Suggested validation:
  - `<command-or-manual-check>`
- Covered by: Tn

#### Boundary

This section describes the execution boundary, not line-by-line implementation steps.

Allowed:

- <Behavior, module, deliverable, or configuration scope this task may handle>

Forbidden:

- <Requirement semantics, public contracts, data model semantics, major UI flows, later task boundaries, or unrelated refactors this task must not change>

#### Done

- <Observable result after completion>
- <Minimum verification or evidence>

#### Evidence

- <Command output, screenshot, SQL result, diff, explanation, or N/A>

#### Notes

- <Only design facts, constraints, invariants, contracts, risk notes, verification requirements, or non-blocking implementation hints that affect execution judgment>
- Do not copy the plan's reasoning process; preserve enough context for builder, code-reviewer, and verifier to execute or review without rereading the full plan.
- Do not enumerate ordinary local coding choices; builder should judge them from existing code style and the task boundary.

---

### T2: <task title>

- Runtime metadata: see `## 6. Task List` for Lane, Complexity, and Revision.
- From plan: §<section> (reference source sections only; do not copy large plan text; put execution-critical design facts in Boundary / Done / Notes)
- Acceptance: AC-<id> / N/A
- Depends on: None / Tn
- Scope:
  - `<path-or-module-or-area>`
- Suggested validation:
  - `<command-or-manual-check>`
- Validates: Tn / N/A

#### Boundary

This section describes the execution boundary, not line-by-line implementation steps.

Allowed:

- ...

Forbidden:

- ...

#### Done

- ...

#### Evidence

- ...

#### Notes

- <Only design facts, constraints, invariants, contracts, risk notes, verification requirements, or non-blocking implementation hints that affect execution judgment>

## 8. Global Notes

- `plan.md` remains the design truth source; `tasks.md` only slices execution. Do not copy plan text, but do extract the design facts, constraints, invariants, contracts, risks, and verification requirements needed for do-stage execution.
- Checklist tasks and their immediate `Lane` / `Complexity` / `Revision` metadata are the Kernel runtime interface; Task Notes are execution context, not the runtime source of truth.
- `Complexity` is a lightweight execution hint, not a gate. Use `small` when uncertain.
- `Revision` is the explicit execution-contract version. Increment it only when the task's execution boundary, done criteria, verification coverage, lane, or dependency semantics change.
- Executable `Tn` tasks use only the `build` or `verify` lane.
- Build tasks must describe boundaries, dependencies, stopping points, and verification coverage. Every build task must have a clear `Covered by: Tn` or grouped verify task, but each build task does not need independent full functional acceptance.
- Verification Coverage Map is agent/human context, not Kernel metadata; it maps the full verify task set to requested behavior and material impacted regression surfaces without changing build task granularity.
- Verify tasks may cover multiple build tasks by behavior, risk, or regression surface. Verify-only scenarios may have no build task, but each verify task must point to a plan section, acceptance criteria, or expected evidence.
- If execution reveals that the plan is invalid, return to `/loom:plan` or `/loom:tasks`; if it affects requirement semantics, return to `/loom:spec`. Do not expand scope inside the task.
