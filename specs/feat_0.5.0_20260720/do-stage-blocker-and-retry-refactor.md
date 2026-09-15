# Do Stage Blocker and Retry Refactor

## Purpose

Do executes one task attempt at a time and preserves completed work across requirement and design correction. A local failure must block only the task results that consume it; an upstream revision must re-enter only tasks whose execution identity or recorded inputs are no longer current.

```text
current tasks.md
→ serial eligibility
→ frozen Task Packet and input attempts
→ build/review or verification
→ effective result reuse, local retry, or scoped continuation
```

## Ownership

- Task Planner owns task order, `Depends on`, `Validates`, `Covered by`, and packet-local Revision judgment.
- Task Reviewer challenges missing or over-expanded relations and incorrect Revision propagation.
- Builder, Code Reviewer, and Verifier diagnose task-local or upstream conflicts; they do not route workflow state.
- Host invokes one Agent at a time, performs internal recovery, targets implementation retry, and submits continuation.
- Kernel parses declared task references, maintains attempt/snapshot/seal/review/input identity, and computes serial eligibility. It does not infer business dependencies or Revision meaning.
- SQLite stores only runtime facts needed across invocations.

## Task Relations

`Depends on` names results that must be current before a task can begin. `Validates` names build results whose current implementation a verify task proves. `Covered by` is the reverse coverage declaration and must not contradict `Validates`.

New task packets declare these references explicitly. Relationless existing artifacts retain safe list-order execution and do not lose historical completion solely because the runtime gained relation parsing.

Task identity remains `ID + title + Lane + Complexity + Revision`. The recorded prerequisite attempt mapping is a separate validity dimension. This preserves Revision locality while making a changed input invalidate only its real consumers.

## Effective Results and Eligibility

A completed attempt is effective when its lane-specific terminal status and task fingerprint are current and every explicitly recorded input still names the effective attempt for that prerequisite.

Do permits at most one active `running` or `completing` attempt per branch. With no active attempt it scans tasks in listed order and selects the first eligible task without an effective completion. A requested `task_id` remains subject to the same prerequisite check.

```text
T1 blocked
T2 Depends on T1
T3 Depends on None

T2 is ineligible.
T3 may run on a later serial invocation.
```

A terminal blocked or failed task does not automatically loop forever. It remains the recovery root for itself and its consumers while independent eligible work remains available.

## Affected-Scope Re-entry

After Spec, Plan, or Tasks correction:

- unchanged task identity and unchanged recorded inputs reuse the existing completion;
- a changed task fingerprint creates a new attempt;
- a changed prerequisite effective attempt invalidates its consumers;
- a changed validated build attempt invalidates prior verification;
- unrelated completed tasks remain effective.

For example, changing T1 re-enters T1, T2 that depends on T1, and T4 that validates them, while independent unchanged T3 is skipped.

## Recovery Classes

### Host-internal recovery

Repeated begin/complete, transient snapshot or seal failure, missing review record, stale sealed changes, and recoverable verification-summary input remain on the same attempt. These actions are not user steps.

Reviewer `changes_requested` stays on the same attempt, followed by changed code, a new seal revision, and a fresh review. Re-sealing the same tree reuses the current revision and cannot bypass an existing verdict.

### Local implementation retry

When verification identifies a defect in an already implemented build result, Host names that build task and cause attempt. Kernel creates a new build attempt without inventing a Task Revision. Its consumers and validators become stale through their recorded input mappings.

### Scoped upstream continuation

A Do attempt may continue to Tasks, Plan, or Spec when its accepted boundary cannot close safely. The attempt becomes terminal blocked and continuation records its root task. The affected closure redirects upstream; an independent task may still run serially when no active attempt exists. Ship remains blocked.

### Owner or external blocker

Only unresolved requirement meaning, public/data/external contract, irreversible direction, risk acceptance, required credentials/permission, or unavoidable human observation becomes a user-visible blocker.

## Mechanical Consistency

Attempt creation is transactional and resumes an existing active attempt only while its task fingerprint and recorded effective-input mapping remain current. A removed, fingerprint-drifted, or input-drifted active attempt is superseded before replacement.

Completion canonicalizes the full candidate (`status`, `summary`, `stdout`, `stderr`, and verification summary) into a content-addressed file before claim. SQLite stores its ref/hash with the deterministic token and recoverable `completing` state, so a later Host session can resume from `attempt_id` alone. Only the winning candidate writes authoritative runtime refs, verification record, finding, and terminal status. Repeating the same candidate resumes or returns idempotently; a different candidate cannot overwrite it.

Review recording uses a write transaction and content-addressed summary evidence. Sealing atomically claims the tree/revision before conditionally attaching tree-addressed changes evidence; a stale attachment cannot replace a newer seal. Duplicate identical input is idempotent, while conflicting input returns a stable error.

## Non-goals

This design does not add task or Agent parallelism, a general scheduler, inferred business dependencies, semantic Kernel review, automatic global Revision bumps, full-artifact invalidation, evidence scoring, a new user-facing workflow artifact, or a separate evidence platform.
