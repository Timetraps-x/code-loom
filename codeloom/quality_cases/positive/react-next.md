# React / Next.js Positive Code Shape

## Code Placement

- Keep server data loading, client interactivity, route/page composition, feature components, hooks, and stores in the boundaries the project already uses.
- Server components/actions/API routes should own server-only data access and secrets; client components should own browser interaction and local UI state.
- Shared components should represent stable UI concepts, not one-off page fragments renamed as reusable abstractions.

## Flow Visibility

- Make server state, URL state, form state, local UI state, and cache/revalidation behavior visible where the feature is maintained.
- Keep submit flows readable: input state, validation, mutation/action, optimistic or loading behavior, error handling, and resulting navigation/cache update.
- Avoid hiding critical data dependencies or side effects behind broad hooks with vague names.

## Abstraction Threshold

- Extract hooks when they own a reusable interaction or state lifecycle, not merely to shorten a component.
- Extract components when they have stable visual/behavioral meaning across call sites.
- Prefer feature-local clarity over premature shared UI or state managers.

## Change Risk Signals

- Watch for server/client boundary leaks, stale cache/revalidation assumptions, duplicate sources of state truth, hydration mismatches, accessibility regressions, and unverified form edge cases.
- User-facing UI changes need browser/manual evidence when feasible, not only type checks.

## What Not To Copy Blindly

- Do not import backend service layering into frontend code.
- Do not make every page fragment a hook/component/store unless the project has a real reuse or lifecycle reason.
