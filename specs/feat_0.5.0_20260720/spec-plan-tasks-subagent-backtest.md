# Spec → Plan → Tasks Subagent Backtest

## Purpose and Result Status

This record tests whether subagents can evaluate the current Spec, Plan, and Tasks Agent designs together with the mechanical runtime that moves artifacts through the chain.

```text
Spec semantics
→ Plan design
→ Tasks packets
→ Kernel registration and drift routing
```

The intended output is not a new semantic Kernel gate. It distinguishes:

1. Agent-design behavior that must be improved in a stage prompt, reviewer, template, or Host projection;
2. mechanical Kernel/Host failures that can block or misroute a valid stage artifact;
3. intentional safety routing; and
4. semantic judgment that must remain outside the weak Kernel.

## Primary Backtest Blocker: The Subagent Did Not Receive Current Sources

All four read-only remote subagents received an isolated worktree snapshot rather than the parent working directory's current uncommitted source state. Observable evidence:

- current `quality_cases/spec`, `quality_cases/plan`, and `quality_cases/tasks` resources were absent from the isolated worktrees;
- a Plan subagent still observed deleted `scout.md`;
- a Tasks subagent observed an older `artifacts.py` without the current `TaskPacket` implementation;
- one subagent read case files from the parent root as a fallback, while another could not read the requested case at all.

Therefore the broad subagent reports are **not valid evidence about the then-current uncommitted Spec/Plan/Tasks Prompts**. Their Agent-quality observations are retained only as snapshot-limited hypotheses. At the time of this backtest, the Kernel path had not yet been modified; mechanical findings independently consistent with current source/test behavior still required local-source confirmation before later implementation.

This is a test-harness/Agent-isolation blocker, not a CodeLoom stage Kernel gate. A reliable rerun needs one of:

- a read-only child that operates directly on the parent checkout;
- a Host mechanism that injects exact current Prompt/template/case contents into the child context; or
- a deliberately refreshed snapshot that includes the intended sources and case assets.

Do not commit merely to make a test harness see uncommitted work.

## Narrow Current Tasks Candidate Exercises

Two additional read-only child exercises used an explicitly supplied cross-layer Tasks candidate.

### First exercise: packet-boundary failure

The Planner simulation put only `Lane`, `Complexity`, and `Revision` directly under T1/T2, then placed the result, guards, stopping conditions, and proof in later `Task Notes`, maps, and tables. Its same-run Reviewer incorrectly treated that later material as packet-local and returned no material counterexample.

This is a valid failure signal: a packet ends at the next task or a new top-level section, so later notes cannot make the execution packet self-contained.

The current Planner Prompt, Reviewer Prompt, and Tasks template were tightened to make metadata-only items invalid and to require the Reviewer to isolate packet boundaries before consumer simulation. Source tests passed after that prompt/template correction.

### Second exercise: fresh candidate and fresh review

The post-correction Planner simulation produced `tasks-backtest-cross-layer-v2` with all result, landing, guard, stop, and proof-handoff facts directly under T1 and T2. A fresh Reviewer inspected only that exact candidate identity and found three material candidate gaps:

1. verification omitted support submission creating the pending-review state;
2. verification omitted approve/reject attempts from already-terminal states;
3. packets referred generically to Plan-settled state/write/transaction semantics instead of carrying the compact accepted contract and exact losing-concurrency outcome.

This is not a Kernel finding. It shows the desired double-Agent loop working at candidate level: an initially plausible result-oriented task plan was falsified by a downstream consumer counterexample. A Planner revision and affected-scope re-review were not run in this exercise.

Because the child still used an isolated source snapshot and could not read the current quality case from its own worktree, this supports only the stated candidate-level observation, not a claim that the current Prompt is stable across repositories.

## Kernel and Host Blocking Cards

### K1 — Host artifact root mismatch

The Host projection writes and registers `specs/<branch-slug>/<artifact>.md`, while artifact storage is configurable through `ProjectConfig.artifact_root`. When a project chooses a non-default root, the Host can write the wrong file and the Kernel correctly rejects it as missing or non-canonical.

- **Classification:** actual Host/Kernel contract mismatch; can block Spec, Plan, or Tasks registration.
- **Owning layer:** Host projection in `codeloom/app/claude_plugin.py`, not semantic Kernel validation.
- **Do not solve with:** a hard-coded Kernel exception or extra Agent reasoning.

### K2 — Invalid supplied artifact file has no recovery recommendation

When Host supplies no `artifact_file`, the runtime returns an explicit `host_artifact_required` route. When Host supplies a path that is missing or wrong, the artifact-content path returns a failure without an equally explicit `recommended_next` recovery instruction.

- **Classification:** usability/recovery blocker.
- **Owning layer:** Kernel response/error routing around artifact-file validation.
- **Scope:** mechanical only; does not need an Agent Prompt change.

### K3 — Tasks parser permissiveness can create wrong execution identity

Tasks registration requires only at least one parseable `Tn` checklist line. Existing parser behavior falls back when `Lane`, `Complexity`, or `Revision` is missing/invalid and does not provide a duplicate-ID registration gate. Thus an Agent mistake such as illegal lane metadata or duplicate `T1` can register an ambiguous or incorrectly classified task instead of being mechanically rejected.

- **Classification:** mechanical task-identity integrity gap.
- **Owning layer:** task parser and Tasks registration validation, if product scope authorizes Kernel hardening.
- **Boundary:** validate only syntax/unique identity/immediate metadata. Do not add Plan semantic evaluation, verification-coverage validation, a dependency graph, scheduler, or automatic Revision inference.

### K4 — Upstream lineage drift stops Do/Ship by design

When current Spec/Plan hashes no longer match Plan/Tasks lineage, later Do and Ship route back to Plan or Tasks instead of continuing under stale artifacts.

- **Classification:** intentional safety routing, not a defect.
- **Owning layer:** none.
- **Do not weaken:** this preserves evidence integrity after upstream change.

## What Must Remain Agent-Owned

The Kernel correctly does not evaluate:

- whether Spec recovered all commitments or routed the only real Owner decision;
- whether Plan chose a correct model, mechanism, project landing, migration, or async compatibility design;
- whether Tasks packets cover all accepted behavior, contain sufficient proof, or use safe slicing;
- whether advisory review actually ran or reached the right conclusion.

These are Agent/Host responsibilities. The candidate-level Tasks counterexamples above should cause Planner revision and Reviewer re-review, not a new semantic Kernel gate.

## Current-Contract Injected Full Chain

To avoid the stale-worktree blocker, a new read-only main subagent received the current stage contracts directly in its prompt rather than reading its checkout. It consumed one fixed asynchronous carrier-dispatch fixture through:

```text
chain-spec-v1
→ chain-plan-v1
→ chain-tasks-v1
```

Fresh stage reviewers received the corresponding exact candidates and current reviewer contracts directly. No candidate was written, registered, or passed to a real stage command.

### Spec result

`chain-spec-v1` received no surviving material Spec-review counterexample. It correctly treated the proposed generic queue as a method rather than a requirement, preserved one-logical-dispatch / non-regression / unknown / compatibility promises, and retained carrier capabilities as evidence gaps rather than an Owner question.

### Plan result

`chain-plan-v1` received three material counterexamples:

1. retry-attempt authority did not define whether broker lease/redelivery or carrier invocation consumed the bounded retry budget;
2. support recovery/read landing did not require separate local submission and external-outcome visibility;
3. manual recovery could still issue a second carrier request despite the one-dispatch invariant.

The main stage owner produced `chain-plan-v2` that:

- defines initial invocation as attempt 1 and three retries as attempts 2–4;
- makes a lease claim that can start an invocation consume one attempt, while broker redelivery alone does not;
- moves a fourth-attempt ambiguity to `EXTERNAL_UNKNOWN` without a fifth automatic claim;
- binds both support and customer views to separate `submitted` and `external_outcome` facts;
- prohibits every recovery entry point from creating a request or identity, retaining unknown when evidence is absent.

A fresh affected-scope Plan reviewer reported no surviving material counterexample in this exact delta. The carrier idempotency/correlation/reconciliation contract remained an intentionally bounded evidence gap.

### Tasks result

`chain-tasks-v1` showed the critical downstream boundary:

- T1 attempted to investigate carrier contract, callback semantics, retry semantics, and concrete landing paths as a `verify` task;
- this is pre-build fact gathering and design recovery, not proof of an established build result;
- its `M` / `L` complexity values also conflict with the current `trivial | small | non-trivial` metadata contract.

The fresh Tasks reviewer correctly returned T1 upstream rather than treating it as valid verification. The main stage owner therefore withheld `chain-tasks-v2`: the carrier contract is necessary to decide whether repeated sends, callbacks, and recovery can actually preserve one external dispatch. There is no safe build/verify slicing until evidence establishes:

1. stable identity deduplicates or otherwise prevents a second carrier dispatch;
2. callbacks carry stable correlation;
3. existing-request reconciliation does not issue a new request; and
4. retention/terminal behavior spans the initial send, all three retries, timeout, and delayed callbacks.

### Kernel result

The exercise simulated only the documented mechanical contract. If the v1 candidates had been written at canonical artifact paths, the Kernel could register them because it does not evaluate Plan evidence gaps or task semantic safety. The correct stop occurred in the Agent/Host chain before registration:

```text
material Plan evidence gap
→ withhold final Plan/Tasks artifact
→ do not invoke Tasks registration
```

This is the intended weak-Kernel / strong-Agent boundary, not a new Kernel semantic gate. No actual Kernel command was invoked in this backtest.

## Post-Backtest Implementation Status

The backtest itself invoked no Kernel command and made no Kernel change. The subsequently authorized recovery-first refactor implemented the locally confirmed findings without turning them into semantic gates:

- **K1 resolved:** Host skills obtain the canonical artifact path and exact registration command from the Kernel handoff, including custom `artifacts.root` values.
- **K2 resolved:** expected authoring is now a successful `noop` handoff, and missing/non-canonical files return current-stage recovery, canonical path, and exact registration data.
- **K3 resolved:** a separate mechanical diagnostic rejects duplicate or explicitly malformed task execution identity while `parse_tasks()` remains tolerant when metadata is omitted.
- **K4 unchanged intentionally:** lineage drift still routes away from stale Do/Ship evidence.

The refactor also added one automatically cleared continuation route rather than a stage-gap blocking finding. Stage Agents still own the semantic decision to revise locally or return upstream; the Host submits the route, and the Kernel validates only the legal edge and non-empty reason.

The Plan and Tasks Agent findings from the injected chain were incorporated into their Architect/Planner and Reviewer Prompts, templates, and behavior-oracle cases: bounded-attempt authority, all recovery entries, authoritative reads, design-evidence-versus-verification, packet-local contracts, real state creation, and prohibited terminal re-entry.

Validation on 2026-09-14 produced:

```text
focused source suite: 147 passed, 1 deselected
compileall: passed
git diff --check: passed (line-ending warnings only)
complete suite: 206 passed, 1 failed
```

The sole complete-suite failure is source/package parity against the pre-existing stale `build/lib/codeloom` mirror. Per scope, `build/lib` was not manually synchronized.

A new read-only subagent run against the final working tree remains unexecuted because the available caller requires `isolation: worktree | remote`, while repository instructions prohibit a worktree or remote snapshot for read-only subagent analysis. No substitute snapshot was created, and no current-source subagent pass is claimed. The final source changes are instead covered by the Prompt/template/oracle and Kernel/Host regression tests recorded in `spec-plan-tasks-recovery-refactor.md`.
