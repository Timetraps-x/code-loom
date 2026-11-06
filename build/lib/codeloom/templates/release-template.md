# Release

based_on_spec_hash: `<hash>`
based_on_plan_hash: `<hash>`
based_on_tasks_hash: `<hash>`
based_on_execution_hash: `<hash>`

Write a short delivery summary using the current accepted context and recorded observations. Read the relevant accepted passages when the supplied context leaves the result or its important conditions unclear. The headings below are optional prose guides; combine them for a small delivery and omit irrelevant sections. Group a larger delivery by coherent user or system results. Omit per-property tables, task recaps, and N/A inventories.

## Delivery Conclusion

- Release readiness: ready | blocked
- Goal result confidence: proven | partially_proven | not_proven

State the observable change and its important boundary. Combine the tasks that contribute to the same result, and explain conditions that matter to its use. Set confidence from the evidence for the accepted results and readiness from that evidence plus actual release constraints. A proven behavior can still have an unmet release prerequisite. The release owner decides actual merge, deployment, rollout, and risk acceptance.

## Verification and Limitations

Connect the recorded observations to the delivered results, including the relevant environment or operating range. Explain the practical effect of a known issue or unverified required behavior and the smallest follow-up. A human assertion requires an explicit recorded statement and source; describe the method actually used. Put compact evidence references beside the claims they support and consolidate shared limitations.

## Release Notes, When Needed

Mention material release actions or cautions, including SQL/data, configuration, rollout, rollback, or monitoring where actually involved. Omit this section when there are none. An unmet required precondition remains blocking; state what must happen before use or enablement. Leave ordinary release execution with the release owner. Use only recorded owners, timing, completed actions, and risk-acceptance decisions.
