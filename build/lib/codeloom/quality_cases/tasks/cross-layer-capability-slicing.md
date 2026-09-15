# Tasks Quality Case: Cross-Layer Capability Slicing

## Accepted Spec and Plan Signals

A support agent may submit a refund for supervisor review but may not approve it. A supervisor may approve or reject a pending review. Customers must see pending, approved, or rejected state, with durable decision actor, reason, and time. The accepted Plan defines one review-decision capability: action-based server command, role-plus-current-state guard, immutable history, conditional terminal transition, aligned UI/API/read projection, and a state diagram.

## Confirmed Project Facts

- Support and supervisor views use one refund detail API.
- Existing arbitrary status endpoint currently permits direct support approval.
- `refund.status` is overwritten and customer reads default missing status to `PROCESSING`.
- Authentication supplies user identity and role to the service layer.
- The Plan already settles the state/write owner, transaction boundary, customer projection, and verification direction.

## Planner Oracle

The Planner must slice stage results, not UI/API/service/DAO layers. A coherent result may establish support submission creating pending review, server-owned action transitions, durable history, and conditional terminal update; a separate result may align role-specific work surfaces and customer projections only when the resulting execution/rollback/proof boundaries are independent. A verify packet must start from the real support submission entry and cover pending/history creation, direct API bypass, concurrent approve/reject, approve and reject attempts from already-approved and already-rejected states, durable history, and customer-visible state without forcing each build into an isolated end-to-end test.

The Planner must not create a fact-gathering task or ask Builder to decide transition authority, history meaning, or transaction semantics.

## Seeded Bad Candidate

> T1 hides approve/reject buttons. T2 adds enum values. T3 changes the Controller. T4 changes the Service. T5 changes the Mapper. T6 runs tests.

## Reviewer Oracle

The Reviewer should show how a Builder completing T1–T5 can still leave direct API approval, a state/history split, last-write-wins terminal decisions, or a stale customer projection. It must request the smallest result-oriented packet correction, not write a replacement task list or demand middleware, a queue, or a new diagram.
