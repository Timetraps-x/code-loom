# Do Quality Case: Performance and Data Flow

## Frozen Build Packet

Extend the device list response with owner organization and latest activation facts while preserving pagination and existing response meaning. The result must remain suitable for pages containing hundreds of devices without per-row database or service calls.

## Current Project Facts

- The primary page query returns device rows and their owner ids.
- Existing mapper capabilities can batch-load owner organizations and latest activation rows by id set.
- Response assembly currently occurs in one application-service method.
- The project has no generic read-model framework and no need for one in this task.

## Seeded Bad Implementation

The candidate extracts `collectOwnerNames`, `collectLatestActivations`, and `buildDeviceView` helpers. Each helper traverses the full page, and the final loop calls owner and activation services once per device. The code looks short at the call site but turns one page into `1 + 2N` queries and hides the cost behind generic helper names.

## Builder Oracle

A strong Builder makes the data and cost path visible:

```text
query page
→ collect required ids in one useful pass
→ batch-load owner and activation facts
→ assemble response in a clear pass
```

It reuses current mapper capabilities, preserves pagination semantics, and does not introduce an assembler, context object, cache, middleware, or speculative abstraction merely to shorten the service method.

## Reviewer Oracle

A valid performance finding names a concrete scale and cost: a page of `N` devices produces `1 + 2N` queries instead of a bounded batch pattern. It points to the looped calls and explains the smallest batch correction. “This could be optimized” without an observed code path and growth mechanism is not a finding.

The Reviewer also challenges duplicate traversal or an abstraction only when it hides material data dependencies, ownership, or cost. A longer method with a clear batch data flow is not itself a maintainability defect.

## Verifier Oracle

Verification uses the strongest available project mechanism to establish bounded query behavior and response correctness—for example focused service tests with call counts, mapper inspection plus executable tests, or a bounded measurement. A successful compile alone does not prove the query-count requirement, while the absence of a full application context does not erase a valid narrower query-count test.
