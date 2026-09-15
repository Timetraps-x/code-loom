# Ship Stage Definition and Execution Refactor

## Purpose

Ship closes one CodeLoom delivery iteration after Do has completed the current Tasks. It produces `release.md` to state:

1. what user or system result was delivered;
2. what that result is proven to do and what remains unproven;
3. whether the current change is ready to release, including material risks, preconditions, manual actions, rollback, and monitoring.

Ship does not redesign requirements, implement or review code, rerun verification, accept risk, merge, tag, deploy, or make the release owner's actual release decision.

## Entry Condition

Ship artifact authoring begins only when every current task has an effective successful result:

- Build tasks are `implemented`;
- Verify tasks are `verified`;
- each result still matches the current task fingerprint and effective prerequisite attempt identities;
- no attempt is `running` or `completing`.

Pending, stale, failed, blocked, or prerequisite-blocked work returns the exact Do recovery recommendation. Ship does not produce an early release artifact for unfinished Do work.

This is a mechanical closure condition, not a semantic release verdict. A completed Do stage can still lead Release Analyzer to a blocked release conclusion when the recorded proof does not establish a material delivery goal or a real release precondition remains unresolved.

## Responsibility Boundary

### Kernel

Kernel projects only explicit current facts: accepted artifact hashes, task and attempt identities, terminal statuses, recorded input attempts, verification records, runtime refs, content hashes, and open findings. It checks Do closure and Ship input freshness. It does not judge goal achievement, proof strength, risk acceptance, or whether a release owner should release.

### Release Analyzer

Release Analyzer consumes the frozen Ship Packet and performs the semantic closure:

```text
accepted intent and design
+ delivered task results
+ proof and limitations
+ release-impact facts
→ delivery and release-readiness conclusion
```

It may read the smallest relevant accepted artifact or referenced evidence needed to explain a goal, boundary, release impact, limitation, rollback, or monitoring requirement. It does not reconstruct workflow state or repeat Do work.

### Host

Host passes the exact Ship Packet to Release Analyzer, routes a genuine upstream semantic gap, writes the clean artifact, and registers it with the packet hash returned by preflight. Recoverable freshness changes remain internal.

### Release Owner

The release owner decides whether and when to perform the actual merge, deployment, rollout, risk acceptance, or irreversible external action.

## Frozen Ship Packet

Before artifact handoff, Kernel derives one compact packet containing:

- Spec, Plan, and Tasks hashes;
- current task identity, lane, revision, effective attempt identity, and completion status;
- verification status and summary refs;
- structured runtime refs and their recorded hashes;
- current evidence-integrity gaps;
- current open blocking findings.

The packet references existing evidence instead of copying logs or whole artifacts. Its canonical JSON SHA-256 is the `ship_input_hash`.

The registration command carries that hash. Registration rebuilds the packet and rejects a stale candidate with `ship_inputs_changed` when attempts, verification, runtime evidence, or blocking findings changed after preflight. The accepted Ship artifact revision records this execution hash in addition to artifact lineage.

## Evidence Integrity

Runtime ref integrity gaps are derived from the current packet. Ship does not append persistent blocking findings for each scan. A restored file therefore restores eligibility on the next invocation without a repair command or stale blocker. Legacy Ship-generated `evidence_integrity_gap` findings are resolved during the new scan.

## Upstream Recovery

When Do is unfinished, Kernel returns the exact `/loom-do <task>` recommendation before Agent handoff.

After Do is mechanically complete, Release Analyzer may identify a genuine accepted-boundary gap:

- missing or conflicting requirement meaning → Spec;
- missing material design or release mechanism → Plan;
- missing implementation or proof coverage → Tasks.

Ship does not route directly to Do for newly discovered work because Tasks must first define that work. Routine deployment steps, release timing, ordinary approval, and actual risk acceptance belong to the release handoff, not an upstream artifact revision.

## Release Artifact

`release.md` is a concise delivery conclusion, not a second plan or a runtime dump. It contains only material sections:

- delivery conclusion and goal-result confidence;
- delivered outcomes and boundaries;
- proof and limitations;
- involved release-impact actions;
- risks, owner decisions, and manual actions;
- rollback and monitoring when relevant;
- compact evidence references and lineage.

Readiness and proof are separate:

```text
Release readiness: ready | blocked
Goal result confidence: proven | partially_proven | not_proven
```

A simple change does not acquire SQL, migration, permission, configuration, UI, deployment, rollback, or monitoring work merely because the template names those possible concerns.

## Non-goals

- No deployment, release approval, environment orchestration, or risk registry.
- No Ship Reviewer or repeated Do verification/code review.
- No semantic Kernel evaluator or evidence-quality score.
- No separate Ship evidence store or copied runtime logs.
- No release artifact before current Do work is effective and complete.
