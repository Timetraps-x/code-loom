# Tasks Quality Case: Revision Locality

## Accepted Plan Change

The prior Tasks candidate has:

```markdown
- [ ] T1: Establish stable carrier dispatch identity
  - Lane: build
  - Complexity: non-trivial
  - Revision: 1
  - Context: Persist one dispatch identity with shipment and outbox.
  - Handoff: Covered by T3 for redelivery and unknown-result recovery.

- [ ] T2: Preserve legacy shipment response semantics
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Context: Keep `submitted=true` as local submission intent.
  - Handoff: Covered by T3 for legacy/new consumer compatibility.

- [ ] T3: Verify carrier dispatch safety and compatibility
  - Lane: verify
  - Complexity: non-trivial
  - Revision: 1
  - Context: Covers T1 and T2.
```

New Plan evidence changes only the target callback rule: callbacks now require a durable carrier event identity and uniqueness guard in addition to the existing dispatch identity. The legacy response semantics are unchanged. A prose-only edit also changes T2's Context wording without changing its result, guard, stop, order, or proof.

## Attempt Baseline

- T1 Revision 1 was implemented but not independently verified.
- T2 Revision 1 was implemented.
- T3 Revision 1 has not started.

## Planner Oracle

The Planner preserves T1 and T2 IDs. It increments only the packet whose result/boundary now includes callback event identity, and increments T3 only if its covered proof obligation changes. The prose-only T2 edit preserves both title and Revision. It preserves the unaffected attempt context and never globally bumps every task because the Plan changed.

## Seeded Bad Candidate

> Rename every task for consistency and set all tasks to Revision 2 because the Plan hash changed. Alternatively, change T1's callback boundary but leave Revision 1 because its title remains stable.

## Reviewer Oracle

The Reviewer must identify the smallest wrong reattempt or skipped reattempt. It should find a missed material Revision bump for a changed packet and a false global bump/title churn for unchanged packets. It must not demand new IDs for the existing logical work or invalidate T2 merely because its prose changed.
