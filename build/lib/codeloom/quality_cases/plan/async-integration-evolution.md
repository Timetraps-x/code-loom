# Plan Quality Case: Asynchronous Dispatch Evolution

## Accepted Spec Signals

Creating a shipment must eventually submit one logical dispatch request to the carrier and show the carrier's authoritative result. Local acceptance or message publication must not appear as carrier acceptance. Broker redelivery, worker retry, callback duplication, and delayed callbacks must not create a second carrier dispatch. Existing API consumers must continue reading the legacy shipment response during a staged rollout.

## Confirmed Project Facts

- Shipment creation and the existing `delivery_outbox` row are written in one database transaction.
- The current broker is at-least-once and may reorder messages after retry.
- `CarrierDispatchConsumer` calls the carrier with a new random request id on every delivery.
- `POST /carrier/callback` looks up a shipment by tracking number and overwrites `dispatch_status`.
- Some historical shipments have no tracking number or correlation id.
- The legacy response exposes `submitted=true`; a new consumer needs explicit `PENDING_CARRIER`, `ACCEPTED`, and `REJECTED` meanings.
- Existing logs contain message ids but no stable shipment-to-carrier correlation.

## Architect Oracle

A strong design must:

1. Reuse or explicitly correct the existing transaction-outbox and broker path rather than introduce a parallel queue without evidence.
2. Define one business dispatch identity, its relation to shipment, outbox event, carrier request, callback, and attempt history.
3. Separate local shipment acceptance, publication, carrier submission, unknown external result, and authoritative carrier terminal result.
4. Specify one retry-attempt authority: what consumes the bounded budget, how claim, broker redelivery, actual carrier invocation, and crash-after-claim relate, the exhaustion transition, and what remains legal afterward.
5. Apply the one-dispatch invariant to consumer re-entry, automatic retry, scheduled repair, manual support/admin recovery, callback repair, reconciliation, timeout, delayed callback, and conditional state advancement.
6. Settle schema/keys/constraints/history, read and write owners, callback correlation, relevant SQL/query behavior, and the migration/backfill treatment of historical rows without identifiers.
7. Bind customer, support, and recovery projections to distinct local submission and authoritative external-outcome facts.
8. Define staged old/new response semantics, consumer compatibility, rollout and rollback boundaries without making `submitted=true` mean carrier acceptance.
9. Tie logs, metrics, alerts, and correlation to observable stuck, duplicate, unknown-result, terminal, and recovery facts.
10. Include a sequence PlantUML for transaction → outbox → broker → consumer → carrier → callback and a state PlantUML for local/external result meanings. The diagrams must agree with the prose and data model.
11. Define future evidence for duplicate delivery, timeout-after-carrier-acceptance, out-of-order callback, migration, compatibility, and recovery.

The exact broker API, SQL dialect, retry count, and class layout may remain project-local when they do not change these semantics. No Owner decision is expected because the accepted signals already define result authority and compatibility behavior.

## Seeded Bad Candidate

> Keep the outbox and add a `DispatchRequested` consumer plus the existing webhook. Retry consumer failures three times and move failures to the DLQ. Add `correlation_id` to the callback table and expose the new status enum in v2. Monitor DLQ size. A sequence diagram shows API → MQ → carrier → callback.

## Expected Reviewer Findings

The Reviewer should derive the business identity, authoritative result, duplicate/order/unknown-result behavior, historical evolution, old/new consumer semantics, and recovery observability as minimum obligations. It should find concrete candidate-conforming failures:

- broker redelivery generates a new carrier request id and creates two dispatches;
- a lease claim followed by a crash is counted differently from an invocation, allowing more than the bounded carrier attempts or exhausting them too early;
- a carrier accepts during a timeout, retry sends again, and DLQ handling cannot determine the external truth;
- manual support or scheduled recovery bypasses the consumer identity and issues a second request;
- support reads local `submitted=true` as carrier success while the customer projection retains an unknown external outcome;
- delayed callback overwrites a newer terminal state because no authority or conditional transition is defined;
- historical rows cannot populate the new correlation path, yet rollout assumes every callback can use it;
- legacy `submitted=true` still appears to mean carrier acceptance;
- the sequence diagram names components but omits duplicate, timeout, callback authority, or state changes and therefore does not evidence the mechanism.

It must not demand another queue, a generic orchestration wrapper, an arbitrary retry count, or a full platform redesign. It must bind every finding to a smallest failure rather than a missing middleware/schema/diagram checklist item.
