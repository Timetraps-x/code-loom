# Spec → Plan → Tasks Recovery-First Refactor

## 1. Purpose

This change removes avoidable dead ends between Spec, Plan, Tasks, and Do without moving semantic judgment into the Kernel.

The target flow is:

```text
stage owner investigates available evidence
→ exact candidate
→ advisory counterexample review
→ smallest current-stage revision
→ final artifact registration
```

Only when a correctness-changing upstream fact or decision remains unresolved does the stage owner return a continuation route:

```text
semantic gap selected by the stage owner
→ Host submits source stage, target stage, and reason
→ Kernel persists one mechanical continuation route
→ downstream calls are redirected to the target
→ successful artifact registration clears the route automatically
```

The route is not an approval gate or blocking finding. It has one action, one recovery destination, and no manual resolve lifecycle.

## 2. Verified Current Implementation

The current runtime path is:

```text
StageRunner.run
→ _context
→ _sync_artifact_state
→ _derive_recommendation
→ _run_spec | _run_plan | _run_tasks | _run_do | _run_ship
```

`_context()` recreates the recommendation from current artifact and attempt state on every invocation. Therefore updating only `branch_sessions.recommended_next` cannot preserve a stage return: the next invocation derives `/loom-do Tn` again from an unchanged valid `tasks.md`.

Artifact stages already preserve the useful mechanical boundary:

- Spec registration records the canonical path and content hash, then recommends Plan.
- Plan requires Spec, records `based_on_spec_hash`, then recommends Tasks.
- Tasks requires Spec and Plan, parses tasks, records lineage and task snapshots, then recommends the next task.
- Do and Ship consult artifact lineage before accepting stale downstream evidence.

The current gaps are:

1. A stage owner can withhold an unsafe candidate, but cannot persist a first-class return destination.
2. Using `findings.severity=blocking` for this purpose would mix stage recovery with Do attempt failure/retry/supersede behavior.
3. Claude Host skills hard-code `specs/<branch-slug>/...` although `artifacts.root` is configurable.
4. A no-`artifact_file` Host handoff is represented as a failed/blocked call even though it is an expected two-step protocol.
5. Missing or non-canonical `artifact_file` errors do not return the canonical retry path and registration command.
6. `parse_tasks()` silently turns explicit invalid metadata into defaults and accepts duplicate task IDs.

## 3. Backtest Findings That Must Change Agent Behavior

### 3.1 Spec

`chain-spec-v1` preserved the required one-logical-dispatch, unknown-result, compatibility, and non-regression commitments while treating a proposed queue as a method. No new Spec Prompt gate is justified. Existing behavior remains under regression coverage.

### 3.2 Plan

The first Plan candidate allowed three candidate-conforming failures:

1. the bounded retry budget had no authority defining whether lease claim, broker redelivery, or carrier invocation consumed an attempt;
2. support and customer reads could derive external success from different facts;
3. manual recovery could create a second carrier request despite the one-dispatch invariant.

The revised Plan closed them by defining invocation attempts, exhaustion, separate local submission/external outcome facts, and one invariant over every recovery entry. These are general material-design triggers that should occur in the first Architect pass and be attacked directly by the Reviewer.

### 3.3 Tasks

The Tasks exercises exposed four distinct problems:

1. execution facts placed in later notes were unavailable to a consumer receiving only the captured packet;
2. the same-run Reviewer incorrectly used those later notes to repair a metadata-only packet;
3. a later candidate omitted proof of support submission creating pending state and omitted approve/reject attempts against already-terminal states;
4. the full-chain candidate disguised carrier-contract investigation as a verify task even though the answers determined Plan mechanism and safe slicing.

The packet-boundary wording is already present and must remain. This refactor adds the missing evidence-vs-verification, packet-local contract, creation-entry, and terminal-re-entry behaviors.

## 4. Ownership and Boundaries

| Layer | Owns | Does not own |
| --- | --- | --- |
| Spec Analyzer/Reviewer | requirement meaning, evidence-backed commitments, real Owner decisions, requirement counterexamples | technical design, stage routing state |
| Plan Architect/Reviewer | abstract model, enforcing mechanism, current-project landing, material evidence gaps, design counterexamples | Spec acceptance, task slicing, Kernel workflow state |
| Task Planner/Reviewer | implementation result chain, build/verify boundaries, packet-local context, proof coverage, Revision locality | missing material Plan design, task execution |
| Host | exact candidate identity, Reviewer invocation, reconciliation loop, final artifact write, translating a stage-owner gap into a Kernel route call | semantic readiness judgment of its own, SQLite writes |
| Kernel | canonical path, artifact hashes, lineage, continuation route, task execution identity, attempt/evidence state, mechanical next action | commitment coverage, design closure, proof sufficiency, Reviewer approval |
| SQLite | branch/runtime facts needed across invocations | semantic evaluation or approval records |

The Kernel must never decide whether carrier idempotency is sufficient, whether a Plan model is correct, or whether Tasks prove the accepted behavior.

## 5. Recovery-First Decision Order

Every stage follows this order:

```text
1. Inspect accepted artifacts and locatable repository/runtime/external evidence.
2. Resolve ordinary reversible choices in the accountable Agent.
3. Review the exact candidate and revise only affected meaning.
4. Continue with unaffected material when one bounded claim is still being recovered.
5. Return only when the unresolved fact changes requirement meaning, Plan mechanism,
   safe Tasks slicing, or another correctness boundary owned upstream.
```

Routes are:

```text
Spec  → Spec
Plan  → Plan | Spec
Tasks → Tasks | Plan
```

Examples:

- Plan cannot yet verify a carrier technical contract: `Plan → Plan`.
- Plan discovers an unresolved business rule governing whether a second dispatch is allowed: `Plan → Spec`.
- Tasks discovers that callback correlation is not designed: `Tasks → Plan`.
- Tasks needs to correct packet identity or recover a prior Revision baseline: `Tasks → Tasks`.

Tasks does not jump directly to Spec. Plan owns the judgment of whether its missing design is caused by a requirement gap.

## 6. Continuation Route Runtime Design

### 6.1 State

Add nullable branch-session fields:

```text
continuation_source_stage
continuation_stage
continuation_reason
```

No new table or finding is created.

### 6.2 Input

```text
loom stage <source> --branch <branch>
  --arg action=route
  --arg target_stage=<target>
  --arg reason=<compact evidence-backed reason>
```

The Kernel validates only:

- source is Spec, Plan, or Tasks;
- target is allowed for that source;
- reason is non-empty;
- `artifact_file` is not part of the same route call.

It does not classify or approve the reason.

### 6.3 Recommendation and redirect

Missing prerequisite artifacts remain the earliest recovery route. Once prerequisites exist, `continuation_stage` takes precedence over task/ship recommendation.

While continuation is present:

- target stage and stages earlier than target may run;
- later stages return `status=noop` with the same `recommended_next` and reason;
- no attempt, artifact revision, or finding is created by the redirect.

### 6.4 Automatic clearing

Any successful Spec/Plan/Tasks artifact registration clears all continuation fields and writes the normal stage recommendation. This is safe because the Host/stage owner is explicitly submitting a final artifact; the Kernel does not inspect whether the semantic reason was resolved.

No `resolve`, `unlock`, `force`, approval, or retry action exists.

## 7. Canonical Host Artifact Handoff

In claude-code Host mode, the first artifact-stage call without `artifact_file` returns:

```text
status: noop
recommended_next: current stage
artifact_paths: [canonical configured path]
extras:
  handoff: author_artifact
  stage
  main_agent
  reviewer_agent
  artifact_path
  register_command
errors: []
```

The generated Host skill must:

1. make this preflight call with user stage args;
2. stop on prerequisite/continuation responses;
3. use the exact `extras.artifact_path` for the final Markdown;
4. register with `extras.register_command`.

No generated skill may construct `specs/<branch-slug>/...` itself.

If a supplied artifact path is missing or non-canonical, the response retains its stable error code but also returns current-stage `recommended_next`, canonical `artifact_paths`, and the same handoff extras. The failure is immediately retryable and never creates a finding.

## 8. Tasks Identity Diagnostics

`parse_tasks()` remains tolerant for existing and readable artifacts. Missing metadata continues to use current deterministic section/title/default behavior, avoiding broad legacy reruns.

A separate mechanical diagnostic examines the same checklist block boundaries and reports only:

- duplicate `Tn`;
- explicit empty or unsupported `Lane`;
- explicit empty or unsupported `Complexity`;
- explicit `Revision` that is not one non-whitespace token;
- conflicting duplicate values for one immediate identity field.

Identical repeated metadata is deterministic and may remain accepted. The diagnostic does not inspect packet prose or infer whether a Revision should have changed.

Tasks registration rejects a malformed candidate before recording revision/snapshot state and recommends Tasks. External sync does not auto-register malformed current Tasks. Do does not create an attempt from malformed current Tasks. Correcting and registering the file restores normal progression with no persistent blocker.

## 9. Agent Design Changes

### 9.1 Plan

When bounded retries are material, the Architect closes:

```text
attempt authority
→ event that consumes an attempt
→ claim/redelivery/invocation/crash relation
→ exhaustion transition
→ allowed automatic/manual action after exhaustion
```

An invariant over state or external effects covers every material entry that can cause the effect: automatic, scheduled, manual/support, admin, callback, and reconciliation paths.

Each material actor or read consumer uses the authoritative fact. Local submission, external unknown, and external terminal outcome remain distinct wherever conflating them enables a wrong action or display.

The Reviewer tries the concrete counterexamples rather than checking for named sections.

### 9.2 Tasks

A verify task proves an established behavior. It cannot discover a fact whose answer changes Plan mechanism or safe slicing.

A Plan reference is traceability, not execution context. A packet carries the compact exact contract needed by its consumer, including authoritative state, legal transition, losing-concurrency result, external-effect guard, stop, and proof when material.

Verification starts at a real behavior entry and covers prohibited terminal re-entry when those facts protect the result. A seeded intermediate state alone cannot prove creation behavior.

The Reviewer explicitly tests fact-gathering verify work, generic Plan references, skipped creation entry, and skipped repeated/illegal terminal transitions.

## 10. Verification Scenarios

### Host and path

- custom `artifacts.root` produces the same path in preflight, file write, and registration;
- preflight is a successful noop handoff, not a blocked error;
- missing/wrong file returns one exact retry route.

### Continuation

- Plan→Spec, Plan→Plan, Tasks→Plan, and Tasks→Tasks persist across invocations;
- status exposes source, target, and reason outside `open_findings`;
- later-stage invocation redirects without creating an attempt;
- target/upstream artifact registration clears continuation automatically;
- invalid route input leaves previous recommendation and artifact state unchanged.

### Task identity

- duplicate ID, illegal lane, `M/L` complexity, empty/invalid Revision, and conflicting immediate metadata are rejected precisely;
- missing metadata still follows tolerant legacy parsing;
- malformed externally edited Tasks are neither auto-registered nor executed;
- corrected Tasks register and immediately resume normal recommendation.

### Agent behavior

- simple local corrections do not acquire async/retry/DB/diagram work;
- async Plan defines retry authority, all recovery entries, and authoritative consumer projection;
- Tasks with unresolved carrier semantics return Plan evidence gap rather than emitting verify work;
- closed cross-layer Plan yields self-contained packets covering state creation and terminal re-entry;
- exact candidate identity and affected-scope re-review remain intact.

## 11. Non-Goals

This change does not add:

- semantic Kernel validation of Spec, Plan, or Tasks;
- a dependency graph or scheduler;
- a Reviewer pass/approval gate;
- stage-gap blocking findings;
- automatic Revision impact inference;
- new task lanes;
- changes to Builder, Code Reviewer, Verifier, Do seal/review/attempt semantics;
- a `build/lib` synchronization workaround.

## 12. Implementation and Validation Status

As of 2026-09-14, the source implementation described above is complete.

### 12.1 Implemented

- Plan Architect/Reviewer now cover bounded-attempt authority, exhaustion, all effect-producing recovery entries, and authoritative consumer reads.
- Task Planner/Reviewer now separate design evidence recovery from verification, require packet-local material contracts, and test real creation entries plus prohibited repeated/terminal re-entry.
- The Plan and Tasks quality cases and Tasks template carry the corresponding behavior oracles without imposing those concerns on simple unrelated work.
- Claude Host artifact stages now use the Kernel's exact `extras.artifact_path`, `extras.main_agent`, `extras.reviewer_agent`, and `extras.register_command`; no Host-generated skill constructs `specs/<branch-slug>/...`.
- Expected Host authoring is a `status=noop` handoff rather than a failed or blocked call. Missing or non-canonical artifact files return the same canonical handoff data for immediate retry.
- Schema version 8 persists one nullable continuation route in `branch_sessions`. Legal Spec/Plan/Tasks routes redirect only later stages and clear automatically when a Spec, Plan, or Tasks artifact is successfully registered.
- Tasks identity diagnostics reject only duplicate or explicitly malformed execution identity while preserving tolerant defaults for omitted metadata.
- Unsupported `gap=` input is rejected as `unsupported_stage_argument` before it can overwrite an existing Spec. It creates no finding, attempt, continuation, or artifact revision.

### 12.2 Validation

The focused source suite passed after the final handoff rename and unsupported-argument recovery change:

```text
147 passed, 1 deselected
```

The source tree also passed:

```text
.venv\Scripts\python.exe -B -m compileall -q codeloom
git diff --check
```

`git diff --check` emitted only existing LF-to-CRLF working-copy warnings; it reported no whitespace error or conflict marker.

The complete suite produced:

```text
206 passed, 1 failed
```

The sole failure is `tests/test_plan_template.py::test_packaged_plan_resources_match_source_resources`: the existing `build/lib/codeloom` mirror does not match current source resources. This refactor intentionally did not edit or manually synchronize `build/lib`.

### 12.3 Current-source Agent backtest limitation

A separate read-only subagent backtest against the final working tree was not executed. The available Agent caller requires `isolation: worktree | remote`, while repository instructions prohibit creating a worktree or remote snapshot for read-only subagent analysis. No substitute snapshot was created, and this record does not claim that an unexecuted current-source backtest passed. The earlier exact-contract injected chain remains historical evidence for the changes, while the final source behavior is covered by the Prompt/template/oracle regression suite above.
