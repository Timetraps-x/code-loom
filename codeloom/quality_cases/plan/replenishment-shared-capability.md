# Plan Quality Case: Shared Fulfillment Capability With Distinct Work Surfaces

## Accepted Spec Signals

A warehouse operator must be able to create a replenishment request from a shortage dashboard and see whether the supplier actually accepted it. A nightly Job may create the same request while the source shortage remains unresolved. The supplier acknowledges receipt immediately but reports final acceptance asynchronously; only the final supplier result is authoritative for acceptance.

An operator may cancel a request before supplier acceptance. A requester sees only warehouses they may operate. A procurement supervisor sees every request and supplier history but cannot cancel on the operator's behalf. Duplicate clicks, Job re-entry, retries, and delayed callbacks must not create two supplier orders for the same shortage and requested date.

## Confirmed Project Facts

- The dashboard controller directly inserts `replenishment_request` with `status=NEW`.
- `ShortageReplenishmentJob` creates the same rows through a different deduplication query.
- `ErpPurchaseClient` returns an acknowledgement that proves receipt, not supplier acceptance.
- The detail page currently renders acknowledgement as `SUBMITTED` and has no supplier-result history.
- The dashboard uses the shared warehouse authorization service; the Job does not.
- The table has a unique key on `(shortage_id, requested_date)`, but a migration-era nullable `requested_date` path bypasses it.
- Current code proves that these paths exist. It does not prove that they are correct target behavior.

## Owner-Bearing Decision

Evidence does not establish the meaning of cancellation after supplier acknowledgement but before final acceptance: send an external cancellation, retain a local cancellation intent, or forbid cancellation. This choice changes public state meaning, external consequences, recovery, and the supplier contract. It is the only Owner decision in this case.

## Architect Oracle

A strong design must:

1. Model one stable replenishment-request capability shared by dashboard, Job, callback, detail view, and cancellation while preserving their role and permission differences.
2. Separate local request acceptance, supplier acknowledgement, supplier final acceptance, cancellation intent, and terminal failure as facts with explicit authority and legal transitions.
3. Give authorization, request identity, deduplication, state transitions, supplier side effects, and callback handling defensible semantic owners; do not add a generic `Context`, `Coordinator`, `Workflow`, or wrapper merely because several entry points exist.
4. Make the current-to-target route concrete for the controller, Job, authorization service, `ErpPurchaseClient`, table/key, write/query paths, detail UI, and supplier history. Each reuse, correction, or replacement decision names the protected fact or invariant.
5. Resolve the nullable deduplication path through an explicit data, constraint, query, migration/backfill, and concurrent-write design. Naming the existing unique key is insufficient.
6. Define the Job trigger, re-entry, authorization or accountable system scope, idempotency identity, retry/timeout behavior, terminal meaning, and recovery.
7. Define callback correlation, duplicate and delayed callback behavior, conditional state advancement, supplier-result history, and the boundary between local success and authoritative external completion.
8. Align UI actions and feedback, server authorization, command/API refusal semantics, stored state, list/detail query projections, Job behavior, external calls, and observability with the same lifecycle.
9. Include the smallest state PlantUML for legal/illegal transitions and sequence PlantUML for submission, acknowledgement, callback, duplicate/retry, and recovery because both are material to correctness.
10. Specify evidence for duplicate prevention, permission, acknowledgement versus acceptance, cancellation, delayed callback, Job re-entry, migration, and recovery without claiming that an endpoint or HTTP success proves supplier acceptance.
11. Ask only the supplier cancellation question. DAO shape, lock syntax, service placement, batching, and token use remain evidence-backed technical recommendations unless a project fact makes them material.

The exact class names, lock primitive, SQL syntax, and diagram layout may vary. A different route passes when it preserves the same authorities, invariants, current-to-target responsibilities, and observable results.

## Seeded Candidate Defects

Use one or more of these defects to evaluate `plan-reviewer`:

- Treat supplier acknowledgement as final acceptance because the current page does so.
- Keep dashboard and Job deduplication separate and describe both as covered by the existing unique key.
- Leave nullable `requested_date` unchanged while claiming duplicate prevention.
- Make the Job bypass warehouse scope without identifying another accountable authorization rule.
- Store only the latest supplier status, with no authority/correlation/history decision for delayed callbacks.
- Add a retrying consumer without a business idempotency identity or terminal recovery meaning.
- Hide cancellation in the UI but leave the server command callable after acceptance.
- Silently choose an external cancellation behavior instead of surfacing the Owner fork.
- List UI, Job, ERP client, table, MQ, and tests as independent changes without one capability model and mechanism.
- Draw a diagram whose `SUBMITTED` state means acknowledgement while prose says it means final acceptance.

## Expected Reviewer Behavior

The Reviewer must derive a minimum design baseline from the accepted signals and confirmed facts before adopting the candidate's model. Each finding must construct a smallest candidate-conforming implementation and concrete failure: duplicate supplier orders, false accepted state, unauthorized action, lost delayed result, unsafe retry/recovery, migration bypass, or silent external cancellation.

It must not report a missing field, class, index, diagram, middleware, or section merely as a checklist omission. It may accept an alternative schema or synchronization mechanism when the candidate closes the same counterexample. It must not replace the shared-capability recommendation with a list of evidence gaps because ordinary DAO, lock, batching, or placement details remain locally unverified.
