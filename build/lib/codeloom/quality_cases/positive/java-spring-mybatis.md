# Java / Spring / MyBatis Positive Code Shape

## Code Placement

- Controllers should translate web/API input and delegate business orchestration instead of owning persistence or response assembly policy.
- Application or domain services should own cross-entity orchestration, transaction boundaries, state changes, and integration calls.
- MyBatis mappers should expose query intent clearly; names should describe reusable data access, not one button, page variant, or temporary task.

## Flow Visibility

- For list/export/read-model flows, keep the useful sequence visible: query primary rows, collect related IDs, batch-load associations, then assemble output rows.
- Prefer one clear pass that collects multiple association ID sets when it improves readability and avoids repeated traversal.
- Keep copy semantics, null/default behavior, enum/status conversion, and response shaping visible where maintainers review the business result.

## Abstraction Threshold

- Extract a helper only when it names a stable business operation, shared query capability, repeated conversion rule, integration boundary, or unavoidable framework seam.
- Avoid cosmetic `Context`, `Assembler`, `Builder`, `Manager`, `Processor`, `Handler`, `Helper`, or `Wrapper` objects that only shorten a method, group parameters, or make generated code look layered.
- Keep logic inline in the owning controller/service/domain method when extraction would hide query dependencies, transaction boundaries, state mutation, side-effect order, or performance cost.
- A longer method is acceptable when it keeps the main data flow and performance cost easier to inspect.

## Defensive Code Threshold

- Add null, empty, default, or fallback handling only at real Java/Spring/MyBatis boundaries: external request input, nullable database columns, optional associations, legacy dirty data, documented caller compatibility, or framework APIs that can actually return absent values.
- Do not add defensive null checks for values already guaranteed by controller binding, prior validation, mapper result contracts, local construction, or current method invariants.
- Do not introduce fallback normalization, compatibility shims, broad default branches, or catch-and-continue behavior unless the current requirement or an existing caller contract proves that state can occur.
- Prefer exposing invalid invariants near the owning service over silently converting impossible states into empty DTOs, empty lists, default enum labels, or success responses.

## Change Risk Signals

- Watch for N+1 queries, looped mapper/service calls, repeated collection traversal, unbounded exports, broad transactions, and hidden side effects.
- Public response contracts, DTO/VO/entity boundaries, mapper XML, SQL aliases, and pagination behavior require direct evidence when changed.

## Verification Evidence Shape

- For legacy Spring/MyBatis/XML modules, prefer targeted module compile, mapper XML/static SQL inspection, service-level logic checks, or existing passing tests that can close inside the repository.
- Do not create or depend on a new broad Spring `ApplicationContext` test unless current repository evidence shows a comparable context already starts with the required beans.
- When only compile, static inspection, mapper, or service evidence is available, mark runtime/page/API behavior as not end-to-end verified.
## What Not To Copy Blindly

- Do not force Controller/ApplicationService/Mapper wording into projects that use different Java boundaries.
- Do not make every flow a new service or assembler just because the example uses explicit phases.
