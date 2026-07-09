# Python / FastAPI Positive Code Shape

## Code Placement

- Routes should parse request input, call the usecase/service path, and return declared schemas without owning persistence details.
- Usecase or service functions should make business decisions, transaction scope, external calls, and state changes visible.
- Repository/query functions should express reusable data-access intent and avoid route-specific names unless the query is truly route-owned.

## Flow Visibility

- Keep request schema, domain update, persistence query, response schema, and side-effect order easy to follow.
- Make ORM loading strategy, pagination, relationship access, copy/update semantics, and validation/default behavior visible when they affect correctness.
- Prefer direct, typed Pydantic/schema transformations over hidden dict mutation chains for business-facing responses.

## Abstraction Threshold

- Extract dependencies, helpers, or services only when they represent stable usecase ownership, framework integration, or repeated rules.
- Avoid generic processors/managers or decorators that hide data loading, authorization, transaction, or response-shaping behavior.

## Change Risk Signals

- Watch for lazy relationship access in loops, accidental N+1 queries, implicit session lifetime assumptions, partial updates that overwrite fields, and swallowed external-call failures.
- Contract, migration, auth, background task, and integration changes need evidence beyond static source inspection.

## What Not To Copy Blindly

- Do not force Java-style layered classes into small Python flows that are clearer as focused functions.
- Do not hide framework dependency injection or session boundaries behind generic wrappers unless the project already standardizes that shape.
