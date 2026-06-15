# Release Plan

based_on_spec_hash: `<hash>`
based_on_plan_hash: `<hash>`
based_on_tasks_hash: `<hash>`

## 1. Release Conclusion

- Status: ready | blocked | partial
- Decision reason:
- Required next action:

说明当前是否具备发版条件。不能判断时写 `blocked` 或 `partial`，并说明缺什么。

## 2. Change Summary

按用户或系统影响整理，不要只按文件罗列。

| Area | Change | Related Tasks | Notes |
|---|---|---|---|
| 后端 / API / CLI | <变更项> | T1 | <说明> |
| 前端 / UI | <变更项> | T2 | <说明> |
| SQL / 数据 | <变更项> | T3 | <说明> |
| 配置 / 权限 | <变更项> | T4 | <说明> |
| 测试 / 验证 | <变更项> | T5 | <说明> |

## 3. Completed Tasks

| Task | Lane | Status | Evidence |
|---|---|---|---|
| T1 | build | verified / blocked / not_run | <证据路径或说明> |
| T2 | verify | verified / blocked / not_run | <证据路径或说明> |

## 4. Verification Summary

这里整理验证结果，不伪造未执行的验证。

| 验收 | Result | Evidence |
|---|---|---|
| AC-1 | PASS / BLOCKED / NOT_RUN / N/A | <证据> |
| AC-2 | PASS / BLOCKED / NOT_RUN / N/A | <证据> |

## 5. Release Preconditions

如果不涉及发布动作，写 `N/A，原因：...`。

- [ ] 构建通过
- [ ] 自动测试通过
- [ ] 手工验证完成
- [ ] SQL 执行段已确认
- [ ] SQL 回滚段已确认
- [ ] 配置 / 开关已确认
- [ ] 权限 / 角色影响已确认
- [ ] 监控 / 日志观察点已确认
- [ ] 相关人员或业务方已确认

## 6. Configuration / Switches

如果不涉及，写 `N/A，原因：...`。

| Key | Value | Timing | Notes |
|---|---|---|---|
| <config key> | <value> | before release / after deploy / rollback | <说明> |

## 7. SQL / Data Changes

如果不涉及，写 `N/A，原因：...`。

### 7.1 Execute

- <执行段说明或文件路径>

### 7.2 Rollback

- <回滚段说明或文件路径>

### 7.3 Check

- <检查段说明或文件路径>

## 8. Release Steps

如果只是代码合并，无额外发布步骤，写 `N/A，原因：...`。

1. <步骤 1>
2. <步骤 2>

## 9. Rollback Plan

说明失败时如何退回。不可自动回滚时必须写清楚。

1. <回滚步骤 1>
2. <回滚步骤 2>

## 10. Runtime Risks and Monitoring

| Risk | Signal | Response |
|---|---|---|
| <风险> | <观察信号> | <响应方式> |

## 11. Known Gaps

| Gap | Blocking | Decision |
|---|---|---|
| <缺口> | yes / no | <如何处理> |

## 12. Not Automatically Reversible

- <例如已产生业务单据、已迁移数据、已通知外部系统等>

## 13. Final Readiness

- ready_for_release: yes / no
- blockers:
- manual_actions:
- owner_decisions:
