# Do Quality Case: Cross-Layer Review State

## Frozen Build Packet

Implement the accepted support-review flow as one coherent result:

```text
support submission
→ authoritative pending state and durable history
→ authorized approve or reject from pending only
→ one terminal outcome visible to customer and support
```

Direct API entry must enforce the same permission and current-state rules as the UI. Concurrent approve/reject has one winner; the loser observes the persisted terminal result and creates neither a second transition nor duplicate history. Approve or reject from already-approved or already-rejected is prohibited.

## Current Project Facts

- The application service owns the transaction and transition check.
- The controller currently hides actions in the UI but does not enforce state ownership itself.
- History and current state are persisted separately inside the same transaction.
- Customer and support read the authoritative persisted outcome.

## Seeded Bad Implementation

The candidate adds a support button and controller endpoint, writes history after the transaction, checks only the caller role in the controller, and updates the state without a conditional pending-state write. Its tests seed an existing pending row and cover one successful approval only.

## Builder Oracle

A strong Builder follows the real entry through authorization, application service, conditional transition, transaction, history, and both read surfaces. It preserves the accepted owner and implements the complete result without splitting it into cosmetic controller, service, and mapper patches.

If the repository cannot support the accepted conditional transition or authoritative read contract without changing Plan design, Builder returns that concrete contradiction instead of inventing a second state authority or silent fallback.

## Reviewer Oracle

A strong Reviewer constructs concrete counterexamples:

- direct API bypass performs an unauthorized transition;
- concurrent approve/reject both appear successful;
- history is missing after a crash between state and history writes;
- an already-terminal request re-enters another terminal state;
- customer and support derive different outcomes.

It asks for only the smallest correction needed inside the Task. It does not request new middleware, event infrastructure, or a state-machine framework without a demonstrated need.

## Verifier Oracle

Verification starts at support submission, proves pending state and history creation, exercises direct API permission, concurrent winner/loser behavior, both terminal outcomes, repeated terminal entry, and customer/support reads. A pre-seeded pending row alone is insufficient.
