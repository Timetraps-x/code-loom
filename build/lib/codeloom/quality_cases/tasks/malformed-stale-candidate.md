# Tasks Quality Case: Malformed or Stale Candidate

## Accepted Spec and Plan Signals

A selected Plan design requires a shared refund review transition, durable history, conditional terminal update, aligned customer projection, and verification of direct API authorization and concurrent decisions.

## Candidate Identity Contract

The Host supplied candidate identity is `tasks-candidate-refund-v2`. Review is valid only for the exact supplied candidate text. The prior candidate was `tasks-candidate-refund-v1`.

## Seeded Bad Candidate

```markdown
# Tasks

- [ ] T1: Add refund review
  - Lane: build
  - Complexity: non-trivial
  - Revision: 1
  - Context: Update the enum and pages.

- [ ] T1: Verify refund review
  - Lane: verify
  - Complexity: small
  - Revision: 1

## Optional Reader Notes

- Boundaries: the server must enforce role and current state, persist immutable history, use conditional terminal update, and align customer projection.
- Handoff: T1 verifies direct API bypass and concurrent decisions.
```

The reviewer is deliberately given `tasks-candidate-refund-v1` while the text above is labelled `tasks-candidate-refund-v2`.

## Reviewer Oracle

The Reviewer must first reject candidate review because the supplied identity does not match the candidate it is asked to inspect. It must not use on-disk tasks or invent candidate findings.

When supplied a matching identity, it must construct smallest downstream failures: duplicate T1 causes ambiguous Task Packet identity; the build packet leaves material server/history/conditional-update design outside its captured context; the verify packet lacks covered relation, counterexamples, and proof limit because those facts are only in later notes. The correction is packet-local and identity-specific, not a replacement sequence.

## Non-Findings

The Reviewer must not require a diagram, database task title, one verify task per build, or an ideal end-to-end harness merely because the candidate is malformed.
