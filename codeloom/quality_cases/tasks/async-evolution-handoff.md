# Tasks Quality Case: Async Evolution Handoff

## Accepted Spec and Plan Signals

Shipment creation must establish one logical carrier dispatch, retain local submission separately from the carrier's authoritative result, tolerate at-least-once redelivery, duplicate and delayed callbacks, unknown external outcomes, historical rows without correlation, and legacy `submitted=true` consumers. The accepted Plan settles stable dispatch identity, transaction-outbox reuse, callback correlation, conditional state advancement, reconciliation, staged compatibility, observability, migration meaning, and state/sequence evidence.

## Confirmed Project Facts

- Shipment and `delivery_outbox` share one transaction.
- The broker is at-least-once and can reorder after retry.
- Current consumer creates a random carrier request ID on every delivery.
- Callback lookup overwrites status by tracking number.
- Historical rows may lack tracking/correlation and legacy consumers read `submitted=true`.

## Planner Oracle

The Planner must form results around durable dispatch identity/outbox evolution, consumer/callback state safety, compatibility/read projection, and a natural risk-oriented verify window. It may choose a different equivalent grouping when it preserves the Plan's state, external-effect, migration, and recovery boundaries. Each packet must identify its local stop and the handoff needed by the next result.

A verify packet must prove duplicate delivery, timeout/unknown outcome, delayed or duplicate callback, historical row behavior, and legacy/new response semantics. It must not be a generic `run tests` task, and it must not require a new queue, generic coordinator, or full integration harness when narrower existing evidence can prove the stated result.

## Seeded Bad Candidate

> T1 adds a new queue. T2 retries the consumer three times. T3 adds a correlation field. T4 exposes v2. T5 runs tests.

## Reviewer Oracle

The Reviewer should construct a failure where a retry generates a second external request, a delayed callback overwrites a newer result, a historical row is assigned invented correlation, or legacy `submitted=true` appears to mean carrier acceptance. It must bind the finding to a packet consumer and proof handoff, not merely say middleware, migration, or observability is absent.
