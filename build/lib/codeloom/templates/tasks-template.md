# Tasks

based_on_plan_hash: `<plan-hash>`

Use this as a flexible delivery guide, not a checklist or field schema. A complete Tasks artifact projects accepted Plan design into an implementation result chain, coherent `build` slices, behavior/risk-oriented `verify` coverage, self-contained task packets, and packet-local Revision decisions. Omit optional labels and reader sections when concise prose is clearer.

Task execution identity is expressed by `Tn`, title, `Lane`, `Complexity`, and `Revision`. The complete captured task block carries its execution context. Revision protects execution meaning, not Markdown wording.

## Implementation Path

Describe only the selected design and the stage-level results that must become true. Explain a shared prerequisite, recommended order, independent track, critical path, integration window, or natural verification window only when it changes execution judgment. List order is the Planner's recommendation, not a runtime dependency graph or runnable gate.

Do not split mechanically by file, class, function, page, API, table, or technical layer. Prefer coherent delivery results, inseparable contracts/state/transaction invariants, failure isolation, local stopping points, rollback boundaries, and natural proof destinations.

## Task List

Create a parseable task only when the accepted Plan already supplies the material result, boundary, current-project landing, protected invariant, and proof direction needed for safe slicing. If one of those decisions is still missing, return the smallest design gap before producing final tasks; never encode undecided design or fact gathering as build/verify work.

Put tasks in recommended execution order. Keep each `Tn` unique and stable across revisions. Each item begins with immediate metadata, then includes only the context required by that task. A Task List item with only metadata is invalid: its block ends before the next task or new top-level section, so a table, delivery map, or later reader note cannot supply missing execution context. A Plan reference provides traceability but cannot be the only source of a material state, transition, concurrency outcome, external-effect guard, stop, or proof obligation. The labels below are examples, not required fields. Simple work may use compact prose; expand only when cross-layer, public-contract, state, permission, transaction, migration, asynchronous, performance, or verification complexity makes the detail material.

- [ ] T1: <deliver a bounded implementation result>
  - Lane: build
  - Complexity: trivial | small | non-trivial
  - Revision: 1
  - Depends on: None
  - Covered by: T2
  - Context: <accepted result and selected design; result this task establishes>.
  - Implementation direction: <current responsibility and target landing; material relation to earlier or later work>.
  - Boundaries: <invariant/contract/risk/out-of-scope guard>; stop when <local completion condition>.
  - Handoff: Prove <behavior/risk/regression surface> with <expected evidence and limits>.

- [ ] T2: <prove a behavior, risk boundary, or regression surface>
  - Lane: verify
  - Complexity: trivial | small | non-trivial
  - Revision: 1
  - Depends on: T1
  - Validates: T1
  - Context: <accepted result and selected design>; validates <covered build result(s)>.
  - Boundaries: Observe <required behavior/counterexample/contract/state/permission/transaction/query/performance path>; do not claim <stronger result than the evidence supports>.
  - Handoff: Record <automated/static/real-flow/experiment/human-needed evidence> and its limitations.

One verify task may cover several naturally related build tasks. This does not merge their implementation result, stopping point, failure isolation, or ownership boundary. Avoid vague verify work such as `run tests`, `verify the feature`, or `check everything`. Verification proves behavior established by accepted design; a fact whose answer would change the Plan mechanism or safe slicing returns as the smallest Plan evidence gap rather than becoming a research or verify task. When a material state or invariant is involved, prove its real creation entry and prohibited repeated or terminal re-entry instead of relying only on a pre-seeded intermediate state.

## Revision Guidance

Compare an affected task with its prior ID, title, Lane, Complexity, Revision, complete task block, and relevant attempt baseline.

- Keep ID, title, and Revision unchanged for wording, formatting, links, explanatory evidence, and context changes that cannot alter why, what, where, guard, stop, order, or proof.
- When the delivered result, done boundary, material landing/proof surface, invariant/contract/risk, lane, or implementation-before/after relation changes, preserve the ID, update the title only if needed, and increment only that task's Revision.
- Revise a verify task only when its covered behavior or proof obligation changes.
- Give genuinely new logical work a new ID and `Revision: 1`.
- Preserve unrelated IDs, titles, Revisions, contexts, and attempts; an upstream artifact change does not imply a global bump.

## Optional Reader Notes

Use this section only for navigation or non-critical summaries. A Task List item with only metadata remains invalid even when a later note repeats its ID. Delivery maps, coverage maps, order tables, and later notes cannot be the sole source of task context. If information changes why, what, where, guard, stop, or proof, place it inside the affected task block.
