# <Requirement Name> Plan

based_on_spec_hash: `<spec-hash>`

Use this as a flexible expression aid, not a design checklist or schema. Organize the selected design around the actual demand and coherent capabilities; merge sections for a small correction. `based_on_spec_hash` records whole-artifact provenance, not a substitute for readable traceability. Do not fill unrelated technical surfaces with `N/A`.

## 1. Design Basis and Selected Route

Explain what this change enables, the accepted results and prohibited consequences, relevant technical and cost boundaries, and what the current project already provides. Carry forward confirmed user decisions, existing design/UI assets, and corrections with the reasons that still affect the route. Separate accepted obligations, established facts, and recommendations; a candidate mechanism is not a new requirement.

Describe the chosen way of completing the work, why it fits the actual scenario and engineering evidence, and what changes from the existing path. Preserve the decisive rationale and applicability conditions, not the discussion history. When a meaningful alternative required the user's choice, record the resulting behavior and consequence. Do not present an unanswered choice as a completed design or ask the reader to choose a level of complexity.

## 2. Concrete Design by Capability

### <Business or System Capability>

Describe who acts, which facts are used, where judgment belongs, what changes, and what the user or consumer observes and can do next. Connect the necessary business concepts, relationships, authority, permissions, and relevant states to that behavior. Include failure and recovery where the actual scenario requires them, rather than designing a generic operation lifecycle.

Land the selected route in the current project: identify the existing responsibility and evidence, the behavior preserved or changed, the target contract or data path, and affected consumers. Follow the path through the concrete UI, API/RPC, service, data, query, transaction, and integration decisions that materially affect the result. A material surface cannot remain undecided for Tasks; it does not need a separate heading or a layer matrix.

Explain new responsibilities through the current results they serve. Keep facts independent when they need not change together, and preserve shared invariants where they must. A replacement must retain each accepted property through a positive implementation path; do not delete behavior or move bounded preparation into every request in the name of simplification.

When performance or validation is material, make lifecycle cost and evidence applicability explicit: what work happens at startup, publication, write, refresh, or request time, how often and at what scale, and which actual input is validated and consumed. An inexpensive final comparison does not hide traversal, network, or serialization work. Distinguish stable input checks, mutable runtime facts, and this change's integration with evidenced shared guarantees.

Use the smallest useful PlantUML relationship, state, sequence, or activity diagram when it explains a material relationship, transition, cross-system collaboration, or multi-role workflow. Diagrams are design evidence and must agree with the prose, UI, contracts, data owners, and failure meanings. A closed local correction may omit a diagram; complex design must not lose useful visual explanation merely to shorten the Plan.

Shared decisions may be stated once where they are easiest to understand, with local differences at their consumers. Replace superseded decisions consistently after a correction; do not append contradictory exceptions or duplicate a mechanism inventory for every capability.

## 3. Evidence and Implementation Freedom

For the material scenarios, state the real entry or justified inspection boundary, representative input, distinguishing observation, necessary preparation or implementation support, and proof limit. An interface success, compilation, or source-text check alone does not prove the business result. Reuse applicable evidence without assuming undocumented guarantees or re-proving an unchanged platform.

Identify the ordinary local implementation choices that remain free. Important behavior, authority, contracts, state and data meaning, consistency, lifecycle cost, and verification meaning must already be settled. A missing decision-changing fact must be investigated, and an unresolved user choice or accepted requirement conflict must be resolved at its owner before this is presented as a final Plan.

Keep task decomposition, commands, source patches, executed-verification claims, release conclusions, internal reasoning, and review logs out of this artifact. Deliver the selected implementable design and its material reasons, not compliance with template headings.
