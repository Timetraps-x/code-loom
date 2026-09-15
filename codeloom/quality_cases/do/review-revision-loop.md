# Do Quality Case: Review Revision Loop

## Frozen Build Packet

Implement a bounded retry claim for an existing dispatch record. A claim that may start an external invocation consumes one attempt; broker redelivery without a successful claim does not. Attempt four exhaustion moves an ambiguous result to `EXTERNAL_UNKNOWN`, and no fifth automatic claim is legal.

## Builder Candidate V1

The candidate increments the attempt counter after the carrier call returns. A crash after claim but before return therefore permits redelivery to invoke the carrier again without consuming the lost attempt.

## Reviewer Oracle

The Reviewer receives only candidate V1's exact sealed diff and constructs the smallest counterexample:

```text
claim succeeds
→ carrier invocation starts
→ process crashes before local counter increment
→ redelivery claims again
→ carrier receives an extra invocation beyond the bounded budget
```

This is a blocking correctness finding with the affected location and smallest correction. The Reviewer does not redesign the queue, require a new coordinator, or add unrelated style findings.

## Builder Revision Oracle

Builder receives the material finding, revises only the attempt-claim path and its focused tests, preserves unrelated callback and read projections, and explains the code-level choice. It does not restart the whole Task, rewrite the Plan, or add a generic retry framework.

## Fresh Review Oracle

A fresh Reviewer inspects the new sealed revision and affected claim/crash/exhaustion paths. The prior verdict does not approve the new revision. Review remains bounded to the changed mechanism and its direct consumers; unrelated code is not reopened without a new concrete dependency.

The final pass is earned only if claim, redelivery, invocation, crash-after-claim, exhaustion, and no-fifth-claim behavior are closed in the implementation.
