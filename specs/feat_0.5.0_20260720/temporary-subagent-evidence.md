# 阶段主 Agent 的临时子 Agent 取证

## 目标

删除 `scout` 与 `codebase-scout` 两个持久 Agent。阶段主 Agent 将大范围代码探索和外部调研委托给临时 Claude Code 子 Agent，以压缩返回事实并隔离原始材料 context；阶段主 Agent 保留阶段判断和 artifact 责任。

## 边界

```text
阶段主 Agent：提出待证问题、解释证据、完成阶段判断、AskUserQuestion、写 artifact
临时子 Agent：收集有界事实并回传摘要
Reviewer：检查当前 artifact 是否遗漏影响本阶段结论的依据
Kernel：登记 artifact 与 runtime state
```

临时子 Agent 不是 CodeLoom catalog、投影资源、配置项、runtime state 或 artifact。它不写文件、不问用户、不选择设计、不切分任务，也不判定验证、发布或 workflow 状态。

每次委托只回答一个能改变当前阶段判断的事实问题，并返回：

```markdown
- question:
- observed facts:
- constraints or counterevidence:
- unknowns:
- decision relevance:
```

阶段主 Agent 判断事实是否适用当前项目，并独自形成 recommendation、设计、任务或回流结论。业务目标、产品偏好、风险接受或不可逆方向选择不是取证问题，应由阶段主 Agent 通过 `AskUserQuestion` 路由。

## 阶段责任

| 阶段 | 临时子 Agent 查明的事实 | 不可下放的判断 |
|---|---|---|
| Spec | 会影响业务承诺、边界、验收含义的业务现状、术语、状态、上下游关系、领域规则 | 需求承诺、非目标、验收含义、Owner 澄清 |
| Plan | 会影响抽象模型、具体投影、共享边界、迁移、兼容、性能和证明方向的项目或外部事实 | 抽象设计、具体设计、Owner 设计分叉 |
| Tasks | 已确定设计的实际落点、依赖和证明路径 | 需求或设计问题；发现后回流 Spec/Plan |
| Do | 当前任务的入口、影响面、局部约定、测试/运行证据和反例 | 扩大 task、重新设计上游 artifacts |
| Ship | 会改变 readiness 结论的已记录 artifact、运行、验证和外部交付事实 | 风险接受、发布时机、回滚归属、发布决定 |

## 适用规则

需要当前项目事实时，阶段主 Agent 委托 repository exploration 子 Agent。需要框架、标准、协议、领域规则或成熟实践等外部事实且该事实可能改变当前判断时，委托 external research 子 Agent。两者都只返回事实摘要，不替阶段主 Agent 作适用性或设计判断。

artifact 不新增固定研究日志；但影响结论的事实和适用性推导必须在对应判断附近可定位。Reviewer 不替主 Agent 做广泛取证，只报告缺少依据或将上游问题下放的缺陷。

## 兼容性

移除 bundle 后，managed projection 保留既有通用行为：已投影的旧 scout 文件被标记为 `retired` 并保留在用户项目中，不自动删除或覆盖。Kernel 不增加子 Agent 调度、审计或持久化逻辑。
