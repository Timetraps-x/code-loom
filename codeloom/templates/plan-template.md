# <Requirement Name> Plan

based_on_spec_hash: `<spec-hash>`

Use this as a flexible delivery guide, not a checklist or schema. A completed Plan is a readable implementation-level design in which accepted requirement → abstract model and protected truth → enforcing mechanism → current-to-target project landing → cross-layer concrete design → observable scenario evidence. Do not add `N/A` sections or technical inventory for completeness. A small closed correction may merge sections and omit unrelated surfaces and diagrams.

`based_on_spec_hash` identifies the accepted Spec artifact revision; it does not replace readable traceability.

## 1. Design Basis and Route

State the accepted results, prohibited consequences, scope boundaries, confirmed decisions, and only the current-project or external facts that change the design. Explain what the evidence proves, why it applies, and where it remains insufficient; do not reproduce the full Spec or inventory the repository.

Summarize the target capability model and the overall current-to-target route. Existing paths are not automatically correct design. Make readable which behavior is preserved as evidenced correct coverage, which target change reuses, extends, corrects, replaces, or adds a responsibility, and which real difference remains intentionally separate. These are design judgments, not required status fields.

## 2. Business Implementation Design

Organize the Plan around coherent capabilities or mechanisms, not technical layers, pages, tables, APIs, Jobs, or files. Repeat the following design block only for material capability slices. Several accepted results may share one block; a simple closed correction may express the whole design in one concise narrative.

### <Capability / Mechanism>

#### Result, boundary, and counterexample

<Identify the accepted result and scope, actor/trigger, representative scenario, and smallest wrong or prohibited result this design must make unreachable.>

#### Abstract model and protected truths

<Define the stable capability and work contexts; core concepts; authoritative, derived, attached, historical, and external snapshot facts; lifecycle and legal transitions; fact/judgment/state/side-effect owners; permissions, consumers, invariants, shared variation axes, and differences that must remain separate. Explain the selected model and decisive trade-off.>

Do not substitute physical pages, tables, modules, or class names for this model. A common model needs shared truth, lifecycle, authority, responsibility, invariant, or real change pressure; a split needs a real authority, lifecycle, permission, query/evolution, or non-coexisting-fact boundary.

#### Enforcing mechanism

<Close the applicable causal chain: `trigger/actor → authoritative fact/observation → judgment/current state → accountable command/owner → atomic local change → external collaboration/wait → duplicate/failure/retry/recovery/terminal meaning → observable result and allowed/rejected next action`. State the gates and invariants that make the counterexample unreachable.>

#### Current-project landing

For each material landing, make the following legible in prose, bullets, or a compact table:

```text
current path and semantic owner
→ established evidence and its limit
→ reuse / extend / correct / replace / add / preserve difference
→ concrete target responsibility, contract, state, or data path
→ affected callers, consumers, or historical data
→ protected truth, invariant, or counterexample
```

Name a real module, service, class, API, table, query, page, Job, message, or integration only with its role in the mechanism. If the repository fact is not yet established, qualify the design recommendation and the evidence needed; do not invent a landing point.

#### Material cross-layer design

A technical surface is material when omitting it would let implementation choose a fact meaning, state transition, permission, external consequence, consistency rule, evolution boundary, cost boundary, or proof interpretation that can change correctness. Design every triggered surface concretely and omit the rest.

When applicable, include only the decisions this mechanism needs:

- **UI/work surface:** actor and entry, visible/editable facts, state-dependent actions, blocked/recovery feedback, client visibility, server authorization.
- **Command/query/API/RPC/Job:** owner and consumers, inputs, results and refusals, state effects, re-entry, duplicate, timeout, retry, and terminal meaning.
- **Data/schema/read model:** authority, relations and keys, history or snapshot meaning, states and constraints, write owner, migration/backfill, and read projection.
- **SQL/DAO/query:** filter intersection, empty-set behavior, deduplication, aggregation, pagination, batch loading, and index direction where they protect correctness or a stated cost boundary.
- **Module/code responsibility:** existing semantic owner, justified new boundary, dependency direction, and responsibilities that cannot be duplicated or bypassed.
- **Transaction/concurrency/idempotency/integration:** atomic boundary, competing writes, conditional transition or lock, business idempotency identity, message/callback correlation, delivery/order/duplicate behavior, external unknown result, and recovery owner.
- **Performance/evolution/observability:** only the material scale, latency, fan-out, compatibility, rollout/rollback, audit, logs, metrics, alerts, or correlation tied to this mechanism.
- **Verification design:** future evidence for normal and prohibited results plus applicable permission, duplicate, concurrent, asynchronous, migration, recovery, and performance scenarios; state what each observation can and cannot prove.

UI, contracts, code ownership, stored state, queries, Jobs, messages, external results, diagrams, and proof must use the same facts, states, owners, and terminal meanings.

#### PlantUML design evidence

Include the smallest useful PlantUML diagram when correctness depends on a material:

- object relationship, cardinality, key, or authority relation;
- state lifecycle, legal gate, illegal transition, or recovery state;
- cross-system synchronous/asynchronous sequence, callback, retry, or compensation;
- multi-role or multi-entry workflow.

Choose a relationship, state, sequence, or activity diagram that exposes the actual decision. A diagram is evidence, not decoration or a quota. Omit it for a closed local correction when the relevant relationship and control are already unambiguous. Diagram names and transitions must match the abstract model, concrete landing, and scenarios.

#### Scenario evidence

<Show representative `input facts → action → persisted fact/state → external result or failure → next action allowed/rejected → observable result`. Include the success chain, the Spec-prohibited chain, and only applicable duplicate, authorization, concurrency, asynchronous, migration, failure, or recovery chains. Static existence of a surface or HTTP success is not proof of a business result.>

## 3. Shared Cross-Block Decisions

Collect a schema, permission, contract, transaction, middleware, migration, performance, observability, or verification decision here only when several design blocks genuinely share it. For each shared decision, identify the participating mechanisms and the facts or invariants it protects. Do not introduce technical surfaces here that have no explained role in a design block.

## 4. Evidence and Implementation Freedom

Distinguish established project facts, evidence-backed recommendations, bounded validation assumptions, and evidence gaps. A missing fact that prevents a correct model, mechanism, or landing must be resolved before presenting a final Plan; do not hide it in an assumption or unknown section. Keep ordinary reversible choices open only when they cannot change the accepted result, model, protected truth, public/data contract, consistency, evolution, or proof meaning.

Do not write task slicing, file lists, execution order, function bodies, DDL or source patches, commands, executed-test claims, release conclusions, or operational runbooks.
