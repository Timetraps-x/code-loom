# Tasks Stage Planning and Handoff

## Purpose

The Tasks stage turns accepted Spec results and Plan design into an executable path of `build | verify` task packets. It decides how the selected design becomes implemented and proved in the current project. It does not reproduce the Plan, complete missing design, create a technical-layer checklist, or ask Kernel to infer task semantics.

The closure chain is:

```text
accepted Plan design
→ implementation result chain
→ coherent build slices
→ behavior/risk verify coverage
→ self-contained task packets
→ packet-local Revision judgment
→ downstream-consumer counterexample review
```

Readable `C:` or `D:` labels may help navigation but are never required IDs, schemas, or stage contracts.

## Planner Method

`task-planner` owns execution slicing:

```text
select accepted design
→ form the current-to-target result chain
→ identify shared prerequisites, independent results, and integration windows
→ slice coherent build outcomes
→ attach behavior/risk verification
→ compile only packet-local execution context
→ compare prior and target packets for local Revision
```

A build slice is defined by a deliverable result, inseparable design consistency, failure isolation, a local stopping point, a rollback boundary, and a natural proof destination. It is not defined by a file, class, function, page, API, database table, or technical layer. A state transition, transaction, public contract, or invariant that would become unsafe when split stays in one build boundary or in one explicit atomic integration result.

A verify slice is defined by behavior, risk, contract, permission/state/transaction/query/performance path, or regression surface. One verify task may cover several naturally related build tasks, but their implementation results, stopping points, ownership boundaries, and independent failure modes remain distinct.

## Executable-Design Boundary

A parseable task is ready only when the accepted Plan already establishes the result, material boundary, current-project landing, protected invariant, and proof direction needed for safe execution. Tasks project those decisions; they do not infer, replace, or finish them.

When a material relationship, state/write owner, contract, permission, migration meaning, external-effect protocol, consistency boundary, or proof interpretation is still undecided, Planner returns the smallest evidence-backed design gap. It does not turn the gap into a research, build, or verify task. Ordinary local code organization, helper naming, fixture detail, or implementation choice remains free when it cannot change task correctness.

## Self-Contained Task Packet

The runtime captures each checklist item and its following indented block as one task packet. Any fact required by the task's downstream consumer must therefore be inside that block.

After `Lane`, `Complexity`, and `Revision`, a packet may use concise labels or prose to answer:

```text
why   — accepted result and selected design
what  — implementation or verification result that becomes true
where — current responsibility and target landing when material
guard — invariant, contract, risk, out-of-scope boundary
stop  — local completion boundary
proof — verification handoff, counterexample, evidence, and limits
```

The labels are optional and do not create a field schema. Simple work may use a short packet. Complex cross-layer, stateful, transactional, asynchronous, migration, permission, or performance work expands only the facts needed for its own execution judgment. Later notes, maps, and summaries may aid readers but cannot be the sole location of execution-critical context.

Task List order is Planner's recommended execution order. Dependencies, parallel tracks, critical paths, integration windows, and grouped verification are human/Agent planning context; Kernel does not parse them into a graph, scheduler, or runnable gate.

## Reviewer Method

`task-reviewer` performs an independent downstream-consumer falsification:

```text
Baseline
→ Simulate Consumer
→ Falsify
→ Hand back
```

It first recovers the minimum result, guard, stopping point, relation, proof obligation, and identity stability that the accepted design requires. It then simulates a reasonable implementation, review, or verification consumer using only the exact candidate task packet. A material finding needs the smallest candidate-conforming execution that still forces a design decision, violates an invariant, stops at the wrong boundary, proves too little, or invalidates the wrong prior work.

The Reviewer does not author a preferred replacement task sequence. Missing headings, optional labels, named files, one verification task per build, or an ideal harness are not defects unless their absence enables a concrete downstream failure.

## Revision Locality

Task execution continuity is keyed by `ID + title + Lane + Complexity + Revision`; the complete packet context has a separate content hash and is not part of the task fingerprint. Planner and Reviewer therefore own the semantic distinction between a changed explanation and a changed execution contract.

Preserve ID, title, and Revision for wording, formatting, links, explanatory evidence, and context changes that cannot alter why, what, where, guard, stop, order, or proof. When the delivered result, done boundary, material landing/proof surface, invariant/contract/risk, lane, or implementation-before/after relation changes, preserve the ID, update the title only if needed, and increment only that packet's Revision. A verify packet changes only when its covered behavior or proof obligation changes. New logical work receives a new ID and `Revision: 1`.

An upstream artifact change may require regenerating `tasks.md`, but it does not justify a global Revision bump. Unrelated packet IDs, titles, Revisions, contexts, and attempts remain stable.

## Runtime Boundary

Kernel parses the checklist identity and immediate `Lane`, `Complexity`, and `Revision`, stores task snapshots and attempt evidence, and passes the captured packet to execution. It uses list order for recommendations and the task fingerprint for execution continuity. It does not judge semantic coverage, dependencies, slicing, verification adequacy, or Revision materiality.

This boundary remains deliberately mechanical. Planner and Reviewer provide the semantic strength; Kernel does not become a task graph, semantic validator, or workflow scheduler.

## Maintainer Behavior Oracles

`codeloom/quality_cases/tasks/` contains maintainer-only prompt-tuning assets for proportional local correction, cross-layer capability slicing, asynchronous evolution handoff, Revision locality, and malformed or stale candidates. They define accepted signals, confirmed facts, seeded failures, permitted freedom, and expected Planner/Reviewer behavior without prescribing one canonical task list.

These cases are package resources for source tests and targeted model exercises. They are not copied into `.loom/references/positive-cases/`, do not become user-project guidance, and do not introduce a production Tasks evaluator, runtime graph, semantic Kernel parser, database state, or CLI command. A limited fixture or model run can support only the stated case-level observation; it cannot prove stable behavior across repositories, models, or unprepared requirements.
