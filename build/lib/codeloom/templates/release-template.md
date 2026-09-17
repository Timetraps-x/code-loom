# Release

based_on_spec_hash: `<hash>`
based_on_plan_hash: `<hash>`
based_on_tasks_hash: `<hash>`
based_on_execution_hash: `<hash>`

Write a short delivery summary from the supplied Build and Verify conclusions, not a new audit. The headings below are optional prose guides; combine them for a small delivery and omit irrelevant sections. Do not produce per-property tables, task recaps, or N/A inventories.

## Delivery Conclusion

- Release readiness: ready | blocked
- Goal result confidence: proven | partially_proven | not_proven

Briefly state the delivered user or system result and its important boundary. Keep the actual release-owner decision separate from this summary.

## Verification and Limitations

Summarize what the recorded verification established, what remains unproven, and any known gap with its smallest follow-up. Do not make completed tasks or successful commands stand in for goal achievement. Human assertion requires an explicit recorded statement and source; do not present it as automated observation. Put compact evidence references beside the claims they support.

## Release Notes, When Needed

Mention only material release actions or cautions, including SQL/data, configuration, rollout, rollback, or monitoring where actually involved. Omit this section when there are none. An unmet required precondition remains blocking; ordinary release execution is not an implementation gap. Do not invent owners, timing, action completion, or risk acceptance.