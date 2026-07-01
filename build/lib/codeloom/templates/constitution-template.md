# Project Constitution

<!-- Replace this scaffold with repository-specific coding rules. Do not keep generic template instructions in the adopted constitution. -->

## 1. Code Placement and Ownership

- Record where new behavior belongs in this repository's actual layers, modules, packages, pages, jobs, integrations, schemas, or other stable ownership boundaries.
- Name concrete owners only when they change future implementation choices.
- Keep public contracts, DTO/VO/entity/schema boundaries, events/jobs, external integrations, and generated artifacts aligned with their real owner.
- Do not mix UI, web adapter/controller, service/usecase/domain, persistence/SQL, infrastructure, and integration responsibilities when the repository already separates them.

## 2. Business, Data, and State Flow Visibility

- Preserve the business flow maintainers need to read at the useful level: important queries, transformations, copy semantics, validation, response shaping, state transitions, and side effects.
- Make data source, association loading, traversal cost, transaction/locking/idempotency behavior, and domain invariants visible when they affect correctness or maintainability.
- Avoid abstractions that hide the important sequence behind cosmetic context, manager, assembler, builder, processor, or helper names.
- Keep durable project style rules here; keep current-demand performance facts in plan/task constraints unless they represent a stable project baseline.

## 3. Abstraction, Reuse, and Naming Thresholds

- Prefer the current code path and established reuse surfaces before adding parallel implementations.
- Reuse existing services, usecases, repositories, mappers, DTOs, VOs, entities, enums, errors/exceptions, hooks/components, templates, utilities, and test patterns when they are the real project path.
- Add helpers, adapters, wrappers, managers, contexts, configuration switches, or new abstractions only when they represent stable ownership, real reuse, clearer business language, or unavoidable framework integration.
- Names should expose the project concept or lifecycle they own; avoid names tied only to a button, page variant, ticket, temporary scenario, or one-off task.

## 4. Stack-Local Code Shape

- Include only languages, frameworks, runtimes, and module families that actually exist in this repository.
- For each present stack, record the local positive code shape: placement, boundary style, reuse surface, flow visibility expectations, data/state/side-effect risks, and smallest meaningful verification evidence.
- Do not import conventions from absent stacks or from another repository unless this repository already uses them as a reference path.
- Keep stack guidance short enough for future agents to apply before coding, not as a broad best-practice appendix.

## 5. Change Risk Boundaries

- Record durable risks that should change implementation or review choices: public/API/UI response contracts, persistence/schema/migration changes, state machines, transactions, batch/export/import paths, background jobs, external calls, files/messages, auth/permission checks, and large-list or hot-path behavior.
- For risky surfaces, state the evidence normally needed to avoid overclaiming: source inspection, compile/test/build, browser/manual check, SQL/migration check, contract check, or configuration check.
- Distinguish static evidence from runtime evidence, and distinguish passed, failed, blocked, not run, and not verified.
- Do not turn one current task's acceptance criteria or verification output into a permanent rule.

## 6. Rule Stability Boundary

<!-- Keep this section only when the repository has concrete legacy patterns, temporary conventions, or misleading local examples that future work should not propagate. Do not fill it with generic exclusions. -->
