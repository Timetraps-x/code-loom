# Plan Quality Case: Cross-Layer Review-State Transition

## Accepted Spec Signals

A support agent may submit a refund for supervisor review but may not approve it. A supervisor may approve or reject a pending review. Customers must see whether a refund is awaiting review, approved, or rejected, and the system must preserve who made each decision and when. Hiding an action in the UI is not authorization; direct API calls must obey the same role and state rules.

## Confirmed Project Facts

- The support and supervisor screens use the same refund detail API.
- The UI currently hides the approve button for support users, but `POST /refund/{id}/status` accepts an arbitrary target status for any authenticated support user.
- `refund.status` is overwritten in place; no decision actor, reason, or history is persisted.
- The customer list query maps unknown or missing status to `PROCESSING`.
- Existing authentication provides user id and role to the service layer.

## Architect Oracle

A strong design must form one review-decision capability and settle:

- the authority and meaning of submit, approve, reject, and customer-visible states;
- legal transitions and the server-side owner that checks role plus current state;
- refusal semantics for unauthorized, stale, duplicate, and terminal requests;
- whether the existing status field is corrected or supplemented, and how actor/time/reason history becomes durable;
- the current-to-target route for both role-specific UI actions, the shared API/command, service responsibility, schema/history, list/detail read models, and customer projection;
- transaction or conditional-update behavior that prevents two supervisors from producing contradictory terminal decisions;
- scenario evidence for direct unauthorized API calls, concurrent decisions, history, and customer-visible results.

A state PlantUML is material because legal and illegal transitions determine correctness. Other diagrams are optional unless the candidate introduces cross-system collaboration.

No message broker, external integration, Job, compatibility layer, or broad performance design is required by the confirmed facts.

## Seeded Bad Candidate

> Add `PENDING_REVIEW`, `APPROVED`, and `REJECTED` to the existing status enum. Hide approve/reject buttons for support users and reuse `POST /refund/{id}/status`. Add an audit log statement after each update. The customer query will display the enum label. Tests cover both role-specific pages.

This candidate looks cross-layer but leaves the API able to accept arbitrary transitions, treats a log line as durable decision history, does not define concurrent terminal updates, and assumes the customer query can no longer map missing values to `PROCESSING`.

## Expected Reviewer Findings

The Reviewer must independently identify server authorization, legal transition ownership, durable decision history, concurrent terminal-state control, and customer projection as minimum obligations. It should construct concrete candidate-conforming failures such as:

- a support user directly calls the reused endpoint and approves the refund;
- two supervisors concurrently approve and reject, with last-write-wins history loss;
- the log is unavailable or detached from the transaction, so the decision actor cannot be established;
- a customer still sees `PROCESSING` because the read mapping was not redesigned.

It must not merely say “missing authorization/database/concurrency sections,” prescribe a replacement architecture, or demand middleware and extra diagrams. No Owner decision is expected.
