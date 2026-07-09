# Go / HTTP Positive Code Shape

## Code Placement

- Handlers should decode input, call the usecase/service path, map errors, and encode responses without owning persistence details.
- Usecase/service code should expose business decisions, state changes, transactions, and external calls directly.
- Repositories and clients should describe reusable I/O boundaries; define small interfaces at the consumer side when they help testing or ownership.

## Flow Visibility

- Keep request parsing, validation, authorization, domain action, persistence call, side effect, and response mapping visible in the owning function.
- Prefer explicit error returns and context propagation over hidden global state or broad middleware side effects.
- Make batching, pagination, retry, timeout, and idempotency behavior visible when they affect correctness or scale.

## Abstraction Threshold

- Extract helpers when they name stable behavior, not just to reduce line count.
- Avoid Java-style managers, deep package hierarchies, or generic frameworks that obscure direct Go control flow.
- Keep interfaces small and local unless the repository already owns a broader boundary.

## Change Risk Signals

- Watch for ignored errors, context loss, goroutine leaks, unbounded memory, hidden retries, broad transactions, and inconsistent response/error mapping.
- External calls, migrations, concurrency, and public contract changes need targeted evidence.

## What Not To Copy Blindly

- Do not force class-oriented layering or generic DI containers into Go code.
- Do not create interfaces for every concrete type unless the consumer boundary benefits from it.
