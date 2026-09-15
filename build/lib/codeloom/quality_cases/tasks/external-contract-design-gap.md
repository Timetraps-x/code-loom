# Tasks Quality Case: External Contract Design Gap

## Accepted Spec and Plan Signals

A shipment must produce at most one carrier dispatch identity across initial send, three retries, timeout, reconciliation, and delayed callbacks. Local submission and the carrier's authoritative outcome are separate facts. The current Plan recommends stable identity and correlated recovery but explicitly leaves the carrier's deduplication, callback correlation, status lookup, and identity-retention behavior as an unresolved evidence gap.

## Confirmed Project Facts

- The existing worker generates a new carrier request ID for each invocation.
- Broker delivery is at-least-once and may redeliver after a lease expires.
- The carrier documentation available in the repository does not establish whether resending one identity prevents a second dispatch.
- It does not establish whether callbacks always contain that identity, whether status lookup can create a request, or how long terminal identities remain queryable.
- Those answers determine whether stable-identity retry and reconciliation can enforce one external dispatch or whether the Plan needs a different mechanism.

## Planner Oracle

The Planner must recover every available named source, then withhold final `tasks.md` because the remaining carrier facts change the selected external-effect mechanism and safe build slicing. It should return one smallest Plan evidence gap covering:

1. stable-identity resend behavior;
2. callback correlation;
3. non-creating status/reconciliation lookup; and
4. identity retention and terminal behavior across initial send, all retries, timeout, and delayed callback.

It must not create a research, discovery, build, or `verify` task to answer these questions. Verification can prove a selected mechanism only after Plan has enough evidence to select it.

## Seeded Bad Candidate

> T1 verifies carrier retry, callback, and lookup semantics. T2 adds stable dispatch identity and retries three times. T3 verifies that only one dispatch occurred.

## Reviewer Oracle

The Reviewer should show that T1 is design fact gathering disguised as verification: one evidence result supports T2 while another requires a different idempotency, recovery, or external-effect design. Therefore the candidate has no safe implementation result chain yet. It should return the smallest Plan evidence gap, not expand T1 into a larger test task or prescribe a carrier adapter, queue, coordinator, or fallback mechanism.

## Must Not Be Reported

- The exact carrier client class, SQL dialect, test filename, and local helper structure are not the gap.
- The absence of a full carrier sandbox is not independently a defect if authoritative contract evidence can resolve the facts.
- The Reviewer must not turn the external evidence question into an Owner decision unless evidence later establishes incompatible business consequences that technical recommendation cannot decide.
