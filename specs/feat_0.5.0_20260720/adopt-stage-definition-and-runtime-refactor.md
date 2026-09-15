# Adopt Stage Definition and Runtime Refactor

## Purpose

Adopt analyzes the whole project after initialization and turns stable project evidence into two distinct results:

- `.loom/constitution.md`: durable, project-specific code-quality and code-shape rules;
- `.loom/project.yml`: explicit mechanical profile facts such as languages, frameworks, module families, and verified test/lint/typecheck/build entry points.

Adopt normally runs after `loom init` and before the first delivery workflow. It runs again only when the project's stable architecture, stack, or engineering conventions materially change. It is not a branch or task stage.

## Seed Is Not Adoption

`loom init` creates a constitution scaffold so the target and section directions are discoverable. The scaffold is not an adopted project baseline and must not be registered or consumed by downstream agents.

A constitution is usable only when:

1. its configured path stays under `.loom`;
2. the file exists;
3. the seed marker has been removed;
4. a non-empty registered hash exists;
5. the current byte hash equals the registered hash.

Seeded, unregistered, missing, or changed constitutions are advisory conditions. They do not block Spec, Plan, Tasks, Do, or Ship; those stages continue from current requirements, accepted design, repository evidence, and repository/host rules without consuming the unusable constitution.

## Responsibility Boundary

### Adopt Expert

Adopt Expert selects high-signal evidence, distinguishes stable positive conventions from current work and legacy shapes, decides which facts deserve durable promotion, and produces the constitution candidate plus a separate project-profile result.

A direct constitution rule requires stable project evidence or an explicit owner promotion decision. Current branch artifacts, untracked or in-progress code, and target-state designs are not durable rules by default.

### Host

Host reads the configured constitution target and existing profile, invokes Adopt Expert, routes a material promotion/authority/legacy conflict to the user, keeps constitution/profile/CLAUDE suggestions separate, writes the selected files, and invokes explicit constitution registration.

### Kernel

Kernel validates path containment, detects the seed marker, hashes file bytes, records the configured path/hash, parses explicit project profile values, and projects whether the current constitution is usable. It does not judge rule quality, architectural correctness, or applicability.

## Evidence and Promotion

Adopt Expert investigates repository rules, CLAUDE.md, documentation and accepted design records, representative source paths, public contracts, persistence/schema/query surfaces, tests, scripts, CI/build conventions, and existing constitution content.

It first detects the actual stack, then reads only matching positive cases. Positive cases are interpretation aids, never proof that this repository follows the same pattern.

Evidence is reduced to four decisions:

- durable project rule or positive local shape;
- current/target-state evidence that is not yet durable;
- legacy/non-propagation evidence;
- material promotion, authority, or legacy conflict requiring an owner decision.

A useful rule is durable, project-specific, actionable, evidence-backed, and capable of changing a future placement, reuse, flow, risk, or verification judgment.

## Delegation

A temporary read-only child agent is optional and bounded to one fact whose isolated investigation can materially change classification. Broad repository scope alone does not require delegation. If no child channel exists, the main agent performs bounded direct investigation. Adopt blocks only when a necessary durable rule or explicit profile fact remains unsafe to determine after available investigation.

## Constitution and Profile Separation

The constitution contains semantic engineering guidance: ownership, visible business/data/state flow, abstraction and reuse thresholds, actual stack-local code shape, change-risk evidence, and concrete non-propagation rules.

The project profile contains explicit mechanical facts:

```yaml
profile:
  languages: "python, typescript"
  frameworks: "fastapi, react"
  modules: "api, web"
commands:
  test: "..."
  lint: "..."
  typecheck: "..."
  build: "..."
```

Unknown values remain empty. The Host updates only evidence-backed values and preserves existing explicit values unless a material conflict is resolved. Kernel parses these strings but never discovers or guesses them.

## CLAUDE.md Suggestions

Default Adopt reads CLAUDE.md as project evidence but does not propose or apply edits.

Explicit `update-claude` mode may return a separate bounded suggestion result for host-runtime context such as commands, verification entry points, safety/no-touch rules, and a pointer to the constitution. Suggestions are never appended to constitution content and are not applied without a separate explicit request.

## Output Quality

The adopted constitution contains only project rules. It does not retain the seed marker, template instructions, empty sections, project profile fields, commands, current task details, stage mechanics, prompt-eval policy, or CLAUDE.md suggestions.

A section is omitted when no project-specific rule survives. A line that could be copied unchanged into any repository is not an adopted project rule.

## Non-goals

- No semantic Kernel evaluator, constitution score, approval workflow, or SQLite rule history.
- No automatic promotion of common code, current branch designs, or positive-case guidance.
- No workflow blocking when constitution is missing, seeded, unregistered, or changed.
- No automatic CLAUDE.md changes.
- No repeated Adopt execution for each branch or task.
