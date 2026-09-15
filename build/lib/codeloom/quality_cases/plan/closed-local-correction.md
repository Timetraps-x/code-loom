# Plan Quality Case: Closed Local Presentation Correction

## Accepted Spec Signals

On the admin device list, the column backed by `ownerCustomerName` is labeled “使用单位”. It must be labeled “归属方” because the value is the device owner organization. Search, export, customer-facing pages, stored data, and the separate elevator use-unit fact must not change.

## Confirmed Project Facts

- The target admin template already receives `ownerCustomerName` from the existing list response.
- The target column header is the only occurrence of the incorrect label on this work surface.
- The API field, query, export header, and customer-facing pages already use the accepted owner meaning.
- No write path, state transition, schema, external integration, Job, or middleware participates in the result.

## Architect Oracle

A strong Plan is short. It should identify the owner fact, the exact presentation surface, the current-to-target correction, the unaffected boundaries, and the observable check that the label changes while its value and other surfaces do not.

It must not invent a domain model refactor, DTO rename, database migration, API version, query rewrite, service wrapper, Job, queue, transaction, observability platform, performance program, or PlantUML diagram. The absence of those surfaces is part of proportional design, not incompleteness.

## Seeded Candidate Defects

- Rename `ownerCustomerName` to `useUnitName`, silently changing the fact meaning.
- Change every “使用单位” label in the repository without proving that each represents owner organization.
- Delete or rewrite the elevator use-unit field because its copy looks similar.
- Claim the API and export need changes even though evidence says their semantics are already correct.

## Expected Reviewer Behavior

The Reviewer should attack only a concrete scope or meaning error. It must not produce a finding because the candidate lacks schema, middleware, migration, performance, observability, or diagram sections. A concise design that closes the label correction and protects the distinct use-unit fact is sufficient.

No Owner decision is expected.
