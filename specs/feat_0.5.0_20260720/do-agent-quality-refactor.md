# Do Agent Quality Refactor

## 1. Purpose

Do exists to implement accepted requirements and design as high-quality code in the current project.

```text
frozen Task Packet
→ current-project implementation judgment
→ complete task-scoped result
→ concrete code review
→ behavior verification
```

High quality includes functional and business correctness, visible data/state/side-effect flow, performance and resource cost, maintainability, readability, architecture and domain ownership, security, reliability, and testability wherever they are material to the task.

Review, verification, attempt state, and runtime references protect or demonstrate that implementation. They are not the primary product of Do, and Agent quality is not measured by filling evidence fields.

## 2. Stage Boundary

### Builder

Builder owns the quality of one build task implementation. The frozen Task Packet supplies the accepted result, boundary, guard, stop, and proof handoff. Current repository evidence supplies the concrete code location, reuse point, code shape, and proportional local checks.

Builder resolves ordinary implementation choices locally. It returns upstream only when high-quality implementation requires changing requirement meaning, an accepted public/data/external contract, a material Plan mechanism, or the Task result/boundary/proof obligation.

### Code Reviewer

Code Reviewer is a bounded adversarial reviewer of the exact sealed attempt-scoped diff. It tries to construct the smallest concrete failure, performance cost, maintenance hazard, or task-boundary violation that a candidate-conforming implementation permits.

It does not edit code, review the full worktree, count checklist rules, or create findings merely to strengthen style.

### Verifier

Verifier owns verification of one verify task and its covered build results. It selects proof proportional to the behavior and risk, executes or inspects the strongest useful path available in the current project, and does not claim more than was observed.

It distinguishes contradiction from absence of proof. A broad harness failure does not erase narrower completed checks, while static or mock evidence does not become real-flow proof.

### Host

Host owns Agent invocation and the internal Builder → seal → Reviewer → revision → completion loop. Runtime actions remain invisible to the user and are driven by the exact current attempt/seal data returned by the Kernel.

### Kernel

Kernel owns task/attempt identity, frozen packet identity, snapshots, sealed revision identity, review and verification record binding, terminal attempt status, and mechanical next routing. It does not evaluate code quality, performance, maintainability, review correctness, or proof sufficiency.

## 3. Current Design Problems

1. `builder.md` repeats detailed quality rules across responsibilities, quality, actions, and guardrails. The complete task result is obscured by a standing catalog.
2. Builder is told both to invoke/request review and to consume a host-managed review flow, mixing execution ownership with orchestration.
3. Builder and Verifier require temporary child-agent delegation even though their declared tool surfaces do not provide that capability. Investigable facts should not become a delegation gate.
4. `code-reviewer.md` carries a large category taxonomy that rewards classification and low-value style findings rather than concrete counterexamples.
5. Verifier describes `not_verified` as a result but does not clearly map a necessary unproved item to the available top-level `blocked` status.
6. All three Agent outputs emphasize evidence/deviation fields more than implementation, review, or observed behavior.
7. Do Prompt tests mostly assert phrase presence. No packaged `quality_cases/do` suite exercises actual implementation, review revision, proof selection, simple-task proportionality, or upstream-boundary behavior.
8. Host projection duplicates substantial runtime orchestration prose and does not make the Builder revision loop explicit enough.

## 4. Builder Redesign

The new Builder Prompt uses a compact implementation method:

```text
Recover the task result and limits
→ inspect the real implementation surface
→ select a code-level route inside accepted design
→ implement the complete result
→ challenge material quality risks
→ run proportional local checks
→ return the implementation or one concrete upstream conflict
```

Quality is triggered by the task and code, not applied as a universal checklist:

- preserve complete behavior, state, data, side effects, permissions, and feedback;
- keep important business/data/performance flow visible;
- examine query count, traversal, external calls, bounds, transactions, concurrency, and idempotency when the implementation can materially affect them;
- place stable facts and responsibilities with their semantic owner;
- introduce abstraction only for real reuse, current complexity, a stable business operation, or a genuine boundary;
- match current-project conventions without copying legacy defects or allowing governance prose to override accepted design;
- run the smallest set of checks that can find current-task defects before review.

Builder does not invoke Code Reviewer, capture snapshots, generate diffs, write runtime evidence, update SQLite, or claim verification. It returns a concise implementation result that the Host can send to review.

## 5. Code Reviewer Redesign

The new Reviewer first reconstructs the minimum correct implementation from the frozen Task Packet independently of Builder explanation, then inspects the exact sealed diff and affected callers/consumers/state/query/test paths.

It challenges only material risks:

```text
result and contract break
state/data/side-effect break
performance/resource break
maintainability/ownership break
task-boundary break
review-object integrity break
```

A finding is valid only when it states:

- the relevant location;
- a concrete input, state, scale, concurrency, failure, or maintenance scenario;
- the wrong result or material cost;
- the smallest useful correction;
- whether the current build result can close without it.

Equivalent local style, speculative hardening, generic clean-code preference, and non-material strengthening are not findings.

The output keeps only the mechanical fields the Host needs—status and seal revision—plus concise findings and a non-empty review summary.

## 6. Verifier Redesign

The new Verifier:

1. recovers the material behaviors and boundaries the verify packet requires;
2. inspects the final implementation and relevant build/review results;
3. selects a proportional proof path from the real project surface;
4. runs or observes that path;
5. compares the actual result with the required behavior;
6. states what was verified, contradicted, or not verified without inflating proof strength.

Result meaning is explicit:

- `verified`: every material obligation in this verify packet is proved strongly enough;
- `failed`: an observation contradicts required behavior;
- `blocked`: one or more necessary obligations remain not verified and cannot be closed in the current task;
- `not_verified` and `not_applicable`: item-level descriptions, never aliases for success.

Performance checks are required only when performance is a requirement, accepted design invariant, Task guard, or concrete risk introduced by the implementation.

The output is a concise conclusion, actual checks/observations, contradicted or unproved material behavior, and the smallest useful follow-up. It is not an evidence-field completeness exercise.

## 7. Host Projection

The Do Host projection remains the runtime owner:

### Build

```text
begin
→ run Builder on the frozen packet
→ if locally implemented, seal exact current changes
→ run Code Reviewer on the exact reviewer handoff
→ record the verdict for that seal revision
→ changes requested: resume Builder with only material findings, reseal, and fresh-review
→ pass: complete implemented
→ blocked: complete blocked and surface the smallest semantic recovery
```

### Verify

```text
begin
→ run Verifier on the frozen packet and available completed work
→ convert the actual conclusion into the compact verification summary
→ complete verified | failed | blocked
```

Internal seal, record, stale-reseal, repeated begin, and repeated completion recovery remain user-invisible. Missing optional Agent fields never become a workflow blocker.

## 8. Behavior Oracles

Add `codeloom/quality_cases/do/` with five focused cases:

1. **Simple local correction** — proves high quality remains proportional and does not invent architecture, performance work, or broad verification.
2. **Cross-layer state implementation** — tests complete behavior, direct-entry protection, durable state/history, concurrency, and terminal re-entry.
3. **Performance and data flow** — distinguishes a visible batch-load path from N+1 queries, repeated traversal, hidden I/O, and cosmetic abstraction.
4. **Review revision loop** — requires a concrete Reviewer counterexample, affected-scope Builder revision, and fresh review without unrelated findings.
5. **Verification strength and recovery** — distinguishes contradiction, not-verified behavior, narrower valid checks, and unavailable broad harnesses.

A later real-model backtest must use exact frozen packets and exact candidates. Prompt phrase checks remain regression guards but are not evidence that Agent behavior is stable.

## 9. Tests

Update Prompt/init tests to require:

- Builder's high-quality implementation objective and compact working method;
- material performance/maintainability judgment without a universal checklist;
- clean Builder/Host/Reviewer ownership;
- Reviewer independent baseline and concrete counterexample threshold;
- Verifier result semantics and proof proportionality;
- absence of child-agent requirements unavailable to these Agents;
- absence of Host, Kernel, SQLite, seal, and runtime-ref duties from Agent Prompts;
- packaging and required semantic anchors for every Do quality case;
- Host's exact attempt/seal handoff and affected-scope review loop.

## 10. Non-Goals

This refactor does not add:

- a Do orchestrator Agent;
- Scout or a renamed scouting role;
- frontend/backend/database/security Agent teams;
- a code-quality scoring engine;
- semantic quality validation in Kernel;
- an evidence-field completeness gate;
- a dependency graph or scheduler;
- mandatory benchmarks, real environments, broad harnesses, or full-suite verification for every task;
- automatic architecture revision by Builder or Verifier;
- changes to attempt, snapshot, seal, review-record, or Ship integrity semantics.

## 11. Validation Boundary

The source and packaged Prompt/resource tests can validate the implemented contracts. A current-working-tree read-only subagent backtest must not use a remote or worktree snapshot under the repository's caller constraints; if no direct shared-checkout Agent call is available, the real-model rerun remains explicitly unexecuted rather than being simulated or claimed as passed.

## 12. Implementation and Validation Status

As of 2026-09-14, the Do Agent refactor described above is implemented in source.

### Implemented

- `builder.md` now centers complete high-quality task implementation, material quality judgment, direct repository investigation, proportional local checks, and one concrete upstream contradiction only when the task cannot close.
- `code-reviewer.md` now uses an independent baseline and candidate-conforming counterexamples. The former category catalog and evidence/deviation structure were replaced by concrete failure scenario, consequence, correction, and blocking impact.
- `verifier.md` now treats verification as behavior judgment, defines `verified`/`failed`/`blocked` against material obligations, preserves partial truth when broad harnesses fail, and does not use evidence-field completion as its objective.
- Builder and Verifier no longer require a temporary child Agent that their declared tool surfaces cannot invoke.
- Agent Prompts contain no Host, Kernel, SQLite, runtime-ref, or internal seal orchestration duties.
- The Do Host projection now makes Builder ownership, exact internal-flow use, sealed review input, affected-scope Builder revision, fresh review, verification conclusion mapping, and automatic internal recovery explicit.
- Five packaged Do behavior-oracle cases cover proportional local correction, cross-layer state, performance/data flow, review revision, and verification strength/recovery.

### Validation

Prompt and initialization/resource tests:

```text
45 passed
```

Do-focused stage, task, CLI, Prompt, and initialization regression suite:

```text
133 passed
```

Source compilation and diff integrity:

```text
.venv\Scripts\python.exe -B -m compileall -q codeloom
git diff --check
```

Both passed. `git diff --check` emitted only existing LF-to-CRLF working-copy warnings.

Complete suite:

```text
207 passed, 1 failed
```

The sole failure remains `tests/test_plan_template.py::test_packaged_plan_resources_match_source_resources`, caused by the intentionally untouched stale `build/lib/codeloom` mirror. No source semantic or Do regression failed.

### Real-model backtest

A current-source read-only subagent backtest was not executed because the available Agent caller requires `isolation: worktree | remote`, while repository instructions prohibit creating either for read-only subagent analysis. No substitute snapshot was created, and this document does not claim that an unexecuted real-model backtest passed. The new behavior cases define the exact future backtest inputs and oracles.
