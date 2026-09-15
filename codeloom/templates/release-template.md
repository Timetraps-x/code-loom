# Release

based_on_spec_hash: `<hash>`
based_on_plan_hash: `<hash>`
based_on_tasks_hash: `<hash>`
based_on_execution_hash: `<hash>`

## 1. Delivery Conclusion

- Release readiness: ready | blocked
- Goal result confidence: proven | partially_proven | not_proven
- Conclusion:

State what is ready to release and why. Keep the actual release-owner decision separate from this readiness analysis.

## 2. Delivered Outcomes and Boundaries

Organize by observable user or system result, not by changed files alone. Include a boundary only when it materially qualifies the delivered result.

| Outcome | Delivered Result | Boundaries / Preserved Behavior |
|---|---|---|
| <User or system outcome> | <What now occurs> | <Material boundary or N/A> |

## 3. Proof and Limitations

Do not make completed tasks or successful commands stand in for goal achievement. State the strongest supported proof and what it cannot establish.

| Goal / Result | Conclusion | Evidence Strength | Evidence | Limitation |
|---|---|---|---|---|
| <Goal or acceptance result> | proven / partially_proven / not_proven | static / automated / real-flow / experiment / human-needed | <Evidence reference> | <Remaining limitation or N/A> |

## 4. Release-impact Actions

Include only involved SQL/data, configuration, permissions, UI/menu, external-system, rollout, or manual actions. If none are involved, write one concise `N/A` statement rather than completing a fixed checklist.

| Impact / Action | Timing or Owner | Verification / Rollback Note |
|---|---|---|
| <Material action or N/A> | <When or who> | <Check, rollback, or limitation> |

## 5. Risks, Manual Actions, and Owner Decisions

A risk is accepted only when an identified owner explicitly accepted it. Routine release execution belongs here without becoming an implementation gap.

| Type | Item | Blocking | Owner / Acceptance | Required Handling |
|---|---|---|---|---|
| risk / limitation / manual action / owner decision | <Item or N/A> | yes / no | <Owner, acceptance evidence, or N/A> | <Handling> |

## 6. Rollback and Monitoring

Include this section only when rollback or runtime observation is material. State any action that is not automatically reversible.

- Rollback:
- Monitoring signal:
- Response boundary:
- Not automatically reversible:

## 7. Evidence References

List only the compact references needed to support the conclusions above; do not dump the complete runtime history.

- Verification:
- Attempt changes / runtime evidence:
- Other material evidence:
