# Tasks

based_on_plan_hash: `<plan-hash>`

Use this as a flexible delivery guide, not a checklist or field schema. A complete Tasks artifact projects accepted Plan design into an implementation result chain, coherent `build` slices, behavior/risk-oriented `verify` coverage, self-contained task packets, and packet-local Revision decisions. Omit optional labels and reader sections when concise prose is clearer.

Task execution identity is expressed by `Tn`, title, `Lane`, `Complexity`, and `Revision`. The complete captured task block carries its execution context. Revision protects execution meaning, not Markdown wording.

## Implementation Path

Describe the usable results and their consumers before listing work. Explain a shared prerequisite, recommended order, independent track, critical path, integration window, or natural verification window only when it changes execution judgment. Work backward from what the consumer needs to run and prove, then place producers first. List order is the Planner's recommendation, not a runtime dependency graph or runnable gate.

Do not split mechanically by file, class, function, page, API, table, or technical layer. Keep a split when an independent result, safe local stop, rollback boundary, or useful failure/proof isolation outweighs its handoff and repeated review cost; otherwise merge related work into a coherent result. Neither shared repository/release nor a target task count decides the boundary.

## Task List

Create a parseable task only when the accepted Plan already supplies the material result, boundary, current-project landing, protected invariant, and proof direction needed for safe slicing. A decision missing from the candidate packet is not necessarily missing from Plan: carry the settled decision into the packet and repair slicing, order, relations, handoff, stops, coverage, and proof expression here. Only when task construction would choose or change a material Plan-owned semantic, return the smallest design gap before producing final tasks; never disguise design-selecting research as build/verify work. Locating an existing environment or preparing bounded reversible fixtures is ordinary execution, not unresolved product design.

Before reporting that gap, recover relevant accepted artifacts, named sources, prior packet/attempt evidence, and locatable project facts. State the unresolved claim, inspected scope, affected slice, and smallest recovery route; preserve unrelated supported work. Missing ideal evidence alone does not block a supported slice.

Put tasks in recommended execution order. Keep each `Tn` unique and stable across revisions. Each item begins with immediate metadata, then includes only the context required by that task. A Task List item with only metadata is invalid: its block ends before the next task or new top-level section, so a table, delivery map, or later reader note cannot supply missing execution context. A Plan reference provides traceability but cannot be the only source of a material state, transition, concurrency outcome, external-effect guard, stop, or proof obligation. The labels below are examples, not required fields. Simple work may use compact prose; expand only when cross-layer, public-contract, state, permission, transaction, migration, asynchronous, performance, or verification complexity makes the detail material.

- [ ] T1: <deliver a bounded implementation result>
  - Lane: build
  - Complexity: trivial | small | non-trivial
  - Revision: 1
  - Depends on: None
  - Covered by: T2
  - Context: <accepted business or system result and property; selected Plan decision; local result this task establishes>.
  - Implementation direction: <current responsibility and target landing; material relation to earlier or later work>.
  - Boundaries: <invariant/contract/risk/out-of-scope guard>; stop when <local completion condition>.
  - Handoff: Supply <usable result or input and its locatable source; necessary implementation-level test support, if any>; distinguish <local evidence> from <proof left to verification>.

- [ ] T2: <prove a behavior, risk boundary, or regression surface>
  - Lane: verify
  - Complexity: trivial | small | non-trivial
  - Revision: 1
  - Depends on: T1
  - Validates: T1
  - Context: <accepted business or system result and selected Plan decision>; validates <covered build results and the transferred result premise>; uses <actual input/entry and existing or task-supplied preparation, when material>.
  - Boundaries: From <real behavior or inspection entry>, observe <result that distinguishes success from the material counterexample>; identify <known unavailable prerequisite and smallest recovery action, if any>; do not claim <stronger result than the evidence supports>.
  - Handoff: Record <automated/static/real-flow/experiment/human-needed evidence> and its limitations.

One verify task may cover several naturally related build tasks. This does not merge their implementation result, stopping point, failure isolation, or ownership boundary. Avoid vague verify work such as `run tests`, `verify the feature`, or `check everything`. Verification proves behavior established by accepted design; a fact whose answer would change the Plan mechanism or safe slicing returns as the smallest Plan evidence gap rather than becoming a research or verify task. When a material state or invariant is involved, prove its real creation entry and prohibited repeated or terminal re-entry instead of relying only on a pre-seeded intermediate state.

Explain each material dependency or coverage relation's transferred result premise in the consuming task's context, not new metadata. Match the producer's usable output to the consumer's actual input and the applicability of reused evidence. `Depends on` is not merely list order, and related evidence does not automatically require an execution dependency. Distinguish inputs needed to start implementation, runnable conditions needed for integration, and proof required for final acceptance; place each on its actual consuming task without weakening its stop or required proof.

Assign needed code-level test entries or observability to the appropriate build result; leave existing-environment discovery and bounded reversible setup with verify. Do not invent a separate harness task for every fixture or hide missing implementation in verification. Prove the changed integration without re-qualifying unchanged shared infrastructure; retain the source and limits of any reused guarantee.

## Revision Guidance

Compare an affected task with its prior ID, title, Lane, Complexity, Revision, complete task block, and relevant attempt baseline. After a blocked attempt, show what changes the actual missing condition or recovery route; merely reissuing tasks or repeating narrower checks is not resolution. Do not remove required proof just to pass.

- Keep ID, title, and Revision unchanged for wording, formatting, links, explanatory evidence, and context changes that cannot alter why, what, where, guard, stop, order, or proof.
- When the delivered result, done boundary, material landing/proof surface, invariant/contract/risk, lane, or implementation-before/after relation changes, preserve the ID, update the title only if needed, and increment only that task's Revision.
- Revise a verify task when its covered behavior, required input/preparation, material proof route, or proof obligation changes, not merely when a resource is located or a result reference is added.
- Give genuinely new logical work a new ID and `Revision: 1`.
- Preserve unrelated IDs, titles, Revisions, contexts, and attempts; an upstream artifact change does not imply a global bump.
- Inspect direct consumers and validators when a transferred premise changes; revise only packets whose result, input, guard, stop, order, or proof changes, then follow actual downstream premise changes. Relation reachability alone does not require a bump. Repair evidenced missing dependencies without inventing global ones.

## Optional Reader Notes

Use this section only for navigation or non-critical summaries. A Task List item with only metadata remains invalid even when a later note repeats its ID. Delivery maps, coverage maps, order tables, and later notes cannot be the sole source of task context. If information changes why, what, where, guard, stop, or proof, place it inside the affected task block.
