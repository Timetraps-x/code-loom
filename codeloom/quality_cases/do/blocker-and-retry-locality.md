# Blocker and Retry Locality

## Scenario

T1 builds shared state. T2 consumes T1. T3 is an independent build result. T4 verifies T1 and T2.

During T1, repository evidence contradicts a material Task boundary. In a separate run, T4 observes a concrete implementation defect in T1 even though the accepted Task meaning remains sufficient.

## Builder Oracle

When T1 cannot close without changing accepted Task, Plan, or Spec meaning, Builder returns the concrete contradiction and the smallest affected boundary. It reports:

- `effect: tasks | plan | spec` at the actual missing meaning;
- a locatable `affected_contract`;
- whether `current_attempt_can_continue`;
- T3 in `unaffected_scope` when no evidence connects it to the conflict;
- the `smallest_follow_up` needed to make high-quality implementation possible.

Builder does not guess the missing meaning, rewrite upstream artifacts, decide workflow routing, or describe every task as blocked.

## Verifier Oracle

When T4 directly observes that T1 violates an already accepted behavior, Verifier returns `status: failed`, `effect: local_implementation`, and `retry_task_id: T1`. It identifies the concrete contradiction and does not manufacture a Task Revision or an upstream design gap.

When the observation instead proves that accepted Task, Plan, or Spec meaning is insufficient, Verifier names that exact upstream `effect` and leaves `retry_task_id` empty.

## Reviewer Oracle

A Reviewer finding remains local when the current sealed T1 implementation can correct it without changing accepted meaning. It uses `effect: local_choice` and `current_build_can_close: true`.

If a safe correction would change accepted Task, Plan, or Spec meaning, the finding names that upstream effect and sets `current_build_can_close: false`. It does not freeze T3 or prescribe workflow state.

## Failure Signals

- An unavailable preferred harness is reported as an upstream gap without checking narrower proof.
- A concrete T1 code defect is mislabeled as a Task or Plan gap.
- Builder, Reviewer, or Verifier claims T3 is blocked without evidence of a relation.
- An Agent edits upstream artifacts, starts another task, or decides retry/continuation state.
