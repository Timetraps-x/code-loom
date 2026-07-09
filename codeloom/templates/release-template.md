# Release Plan

based_on_spec_hash: `<hash>`
based_on_plan_hash: `<hash>`
based_on_tasks_hash: `<hash>`

## 1. Release Conclusion

- Status: ready | blocked | partial
- Decision reason:
- Required next action:

State whether this change is ready to release. If readiness cannot be determined, write `blocked` or `partial` and explain what is missing.

## 2. Change Summary

Organize by user or system impact, not just by files changed.

| Area | Change | Related Tasks | Notes |
|---|---|---|---|
| Backend / API / CLI | <Change> | T1 | <Notes> |
| Frontend / UI | <Change> | T2 | <Notes> |
| SQL / Data | <Change> | T3 | <Notes> |
| Configuration / Permissions | <Change> | T4 | <Notes> |
| Testing / Verification | <Change> | T5 | <Notes> |

## 3. Completed Tasks

| Task | Lane | Complexity | Status | Evidence |
|---|---|---|---|---|
| T1 | build | small | implemented / blocked / not_run | <Evidence path or note> |
| T2 | verify | non-trivial | verified / blocked / not_verified / not_run | <Evidence path or note> |

## 4. Verification Summary

Summarize verification results without inventing verification that was not run.

| Acceptance | Result | Evidence |
|---|---|---|
| AC-1 | PASS / BLOCKED / NOT_RUN / N/A | <Evidence> |
| AC-2 | PASS / BLOCKED / NOT_RUN / N/A | <Evidence> |

### 4.1 Not Verified

| Item | Reason | Required Decision / Next Action |
|---|---|---|
| <Item or N/A> | <Reason> | <Action> |
## 5. Release Preconditions

If release actions are not involved, write `N/A because ...`.

- [ ] Build passed
- [ ] Automated tests passed
- [ ] Manual verification completed
- [ ] SQL execute block confirmed
- [ ] SQL rollback block confirmed
- [ ] Configuration / switch confirmed
- [ ] Permission / role impact confirmed
- [ ] Monitoring / log observation points confirmed
- [ ] Stakeholder or business confirmation obtained

## 6. Configuration / Switches

If not involved, write `N/A because ...`.

| Key | Value | Timing | Notes |
|---|---|---|---|
| <config key> | <value> | before release / after deploy / rollback | <Notes> |

## 6.1 Attempt Changes / Runtime Evidence

| Kind | Paths / Evidence | Notes |
|---|---|---|
| Attempt changes | <attempt-changes ref or N/A> | <Notes> |
| Runtime logs | <stdout/stderr ref or N/A> | <Notes> |
| Verification summary | <verification-summary ref or N/A> | <Notes> |
| SQL / Data / Configuration / Permissions / UI | <evidence ref or N/A> | <Notes> |
## 7. SQL / Data Changes

If not involved, write `N/A because ...`.

### 7.1 Execute

- <Execute block note or file path>

### 7.2 Rollback

- <Rollback block note or file path>

### 7.3 Check

- <Check block note or file path>

## 8. Release Steps

If this is only a code merge with no extra release step, write `N/A because ...`.

1. <Step 1>
2. <Step 2>

## 9. Rollback Plan

Describe how to revert if release fails. If automatic rollback is not possible, state that clearly.

1. <Rollback step 1>
2. <Rollback step 2>

## 10. Runtime Risks and Monitoring

| Risk | Signal | Response |
|---|---|---|
| <Risk> | <Observed signal> | <Response> |

## 11. Known Gaps and Accepted Risks

Risks can be accepted only when the user or release owner explicitly accepted them. Do not infer acceptance from missing evidence.

| Gap / Risk | Blocking | Accepted By | Decision |
|---|---|---|---|
| <Gap or risk> | yes / no | <Owner or N/A> | <Handling decision> |

## 12. Not Automatically Reversible

- <Example: business records created, data migrated, external systems notified>

## 13. Final Readiness

- ready_for_release: yes / no
- blockers:
- manual_actions:
- owner_decisions:
