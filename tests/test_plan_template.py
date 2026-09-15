from __future__ import annotations

from importlib import resources

from codeloom.llm_clients.mock import MockLlmClient


def test_mock_plan_traces_commitments_without_claiming_concrete_design():
    spec = "# Spec\n\n- `C:device-bind`: Bind a device.\n- `C:device-unbind`: Unbind a device.\n"
    plan = MockLlmClient().draft_plan(spec, spec_hash="abc123")

    for reference in ("C:device-bind", "C:device-unbind"):
        assert f"`{reference}` through `D:design-{reference.removeprefix('C:')}`" in plan
    assert "based_on_spec_hash: `abc123`" in plan
    assert "C:current-requirement" not in plan
    assert "D:current-capability" not in plan
    assert "## 1. Design Basis and Route" in plan
    assert "## 2. Business Implementation Design" in plan
    assert "## 3. Shared Cross-Block Decisions" in plan
    assert "## 4. Evidence and Implementation Freedom" in plan
    assert "Mock cannot decide whether a real project path should be reused" in plan
    assert "project-specific UI, API, data, query, integration, evolution, and proof decisions remain unresolved" in plan


def test_mock_plan_accepts_readable_spec_without_optional_anchor():
    plan = MockLlmClient().draft_plan("# Spec\n\n## Requirement\nLegacy behavior.")

    assert "Accepted requirement: readable Spec semantics are present without an optional label" in plan
    assert "Mock cannot select an abstract model, mechanism, or current-project landing" in plan
    assert "C:current-requirement" not in plan
    assert "D:current-capability" not in plan
    assert "based_on_spec_hash: unavailable" in plan


def test_mock_spec_revision_keeps_readable_prior_context_without_forcing_anchor():
    client = MockLlmClient()
    initial = client.draft_spec("Bind a device")
    revision = client.draft_spec("Unbind a device", initial)

    assert "Bind a device" in revision
    assert "Unbind a device" in revision
    assert "Optional anchor" not in initial
    assert "Revision Lineage" not in revision


def test_mock_spec_legacy_revision_keeps_prior_context_without_mapping_protocol():
    legacy_spec = "# Spec\n\n## Requirement\nKeep the legacy device behavior.\n"
    revision = MockLlmClient().draft_spec("Add device audit", legacy_spec)

    assert "## Existing Context" in revision
    assert "Keep the legacy device behavior." in revision
    assert "Explicit Legacy Mapping" not in revision
    assert "Mapping boundary:" not in revision


def test_mock_plan_uses_zh_when_configured():
    spec = "# 规格\n\n- `C:设备绑定`: 绑定设备。\n"
    plan = MockLlmClient().draft_plan(spec, language="zh", spec_hash="zh123")

    for expected in (
        "## 1. 设计依据与路线",
        "## 2. 业务实现设计",
        "## 3. 跨设计块共享决定",
        "## 4. 证据与实施自由",
        "当前到目标的承接",
        "触发与权威事实",
        "复用、扩展、修正、替换、新增或保留差异",
        "具体 UI、契约、数据/查询、代码责任",
        "表、接口、图或 HTTP 成功不能证明",
        "C:设备绑定",
        "D:design-",
        "based_on_spec_hash: `zh123`",
    ):
        assert expected in plan

    assert "C:current-requirement" not in plan
    assert "D:current-capability" not in plan
    assert "Plan 处置" not in plan


def _template(name: str) -> str:
    return resources.files("codeloom.templates").joinpath(name).read_text(encoding="utf-8")


def test_templates_preserve_coding_goal_anchors():
    spec = _template("spec-template.md")
    plan = _template("plan-template.md")
    tasks = _template("tasks-template.md")
    release = _template("release-template.md")

    for expected in (
        "Current problem and branch commitment",
        "Proof direction",
        "A page, API 200, compile, screenshot, mock, or isolated test does not by itself prove",
        "Readable commitment anchors, when useful",
        "`C:<meaningful-slug>` example",
    ):
        assert expected in spec

    for expected in (
        "flexible delivery guide, not a checklist or schema",
        "accepted requirement → abstract model and protected truth",
        "## 1. Design Basis and Route",
        "## 2. Business Implementation Design",
        "## 3. Shared Cross-Block Decisions",
        "## 4. Evidence and Implementation Freedom",
        "overall current-to-target route",
        "#### Result, boundary, and counterexample",
        "#### Abstract model and protected truths",
        "#### Enforcing mechanism",
        "#### Current-project landing",
        "reuse / extend / correct / replace / add / preserve difference",
        "protected truth, invariant, or counterexample",
        "#### Material cross-layer design",
        "A technical surface is material when omitting it",
        "**UI/work surface:**",
        "**Command/query/API/RPC/Job:**",
        "**Data/schema/read model:**",
        "**SQL/DAO/query:**",
        "**Transaction/concurrency/idempotency/integration:**",
        "UI, contracts, code ownership, stored state, queries, Jobs, messages, external results, diagrams, and proof",
        "#### PlantUML design evidence",
        "object relationship, cardinality, key, or authority relation",
        "state lifecycle, legal gate, illegal transition, or recovery state",
        "cross-system synchronous/asynchronous sequence",
        "multi-role or multi-entry workflow",
        "Omit it for a closed local correction",
        "#### Scenario evidence",
        "input facts → action → persisted fact/state",
        "participating mechanisms and the facts or invariants it protects",
        "based_on_spec_hash` identifies the accepted Spec artifact revision",
        "does not replace readable traceability",
    ):
        assert expected in plan

    for forbidden in (
        "## 1. Background",
        "Goal, Way, and Proof",
        "Validation Matrix",
        "Release Order",
        "Rollback Order",
        "Recommended minimum automated verification",
        "Commitment disposition",
        "supersession/withdrawal",
        "Critical Files for Implementation",
    ):
        assert forbidden not in plan

    for expected in (
        "Implementation Path",
        "Task List",
        "flexible delivery guide, not a checklist or field schema",
        "implementation result chain",
        "Task execution identity is expressed by `Tn`, title, `Lane`, `Complexity`, and `Revision`",
        "Revision protects execution meaning, not Markdown wording",
        "Planner's recommendation, not a runtime dependency graph or runnable gate",
        "Do not split mechanically by file, class, function, page, API, table, or technical layer",
        "accepted Plan already supplies the material result, boundary, current-project landing, protected invariant, and proof direction",
        "return the smallest design gap before producing final tasks",
        "A Task List item with only metadata is invalid",
        "Context:",
        "Implementation direction:",
        "Boundaries:",
        "Handoff:",
        "One verify task may cover several naturally related build tasks",
        "implementation result, stopping point, failure isolation, or ownership boundary",
        "prior ID, title, Lane, Complexity, Revision, complete task block, and relevant attempt baseline",
        "upstream artifact change does not imply a global bump",
        "Optional Reader Notes",
        "cannot be the sole source of task context",
        "A Plan reference provides traceability but cannot be the only source of a material state, transition, concurrency outcome, external-effect guard, stop, or proof obligation",
        "a fact whose answer would change the Plan mechanism or safe slicing returns as the smallest Plan evidence gap",
        "prove its real creation entry and prohibited repeated or terminal re-entry",
    ):
        assert expected in tasks

    for expected in (
        "based_on_execution_hash",
        "Delivery Conclusion",
        "Release readiness: ready | blocked",
        "Goal result confidence: proven | partially_proven | not_proven",
        "Delivered Outcomes and Boundaries",
        "Proof and Limitations",
        "Do not make completed tasks or successful commands stand in for goal achievement",
        "Include only involved SQL/data, configuration, permissions, UI/menu, external-system",
        "rather than completing a fixed checklist",
        "Risks, Manual Actions, and Owner Decisions",
        "A risk is accepted only when an identified owner explicitly accepted it",
        "Keep the actual release-owner decision separate",
        "Evidence References",
    ):
        assert expected in release

    for forbidden in ("Final Readiness", "ready_for_release", "SQL execute block confirmed"):
        assert forbidden not in release


def test_tasks_template_declares_task_metadata_contract():
    tasks = _template("tasks-template.md")

    for expected in (
        "flexible delivery guide, not a checklist or field schema",
        "Lane`, `Complexity`, and `Revision`",
        "material landing/proof surface",
        "Keep ID, title, and Revision unchanged for wording, formatting, links, explanatory evidence",
        "why, what, where, guard, stop, order, or proof",
        "One verify task may cover several naturally related build tasks",
        "Keep each `Tn` unique and stable across revisions",
        "prior ID, title, Lane, Complexity, Revision, complete task block, and relevant attempt baseline",
        "Preserve unrelated IDs, titles, Revisions, contexts, and attempts",
    ):
        assert expected in tasks

def test_agent_templates_define_main_and_subagent_contracts():
    main_agent = _template("agent-template.md")
    subagent = _template("subagent-template.md")

    for expected in (
        "Canonical template for CodeLoom stage-owner agents",
        "description: Use this agent to <create/revise/execute/verify/release> <stage artifact or stage work>.",
        "A subagent result is evidence, not authority",
        "Do not delegate the stage decision, artifact ownership, or readiness conclusion to a subagent",
        "Intent",
        "Boundary",
        "Task",
        "Evidence",
        "Readiness",
    ):
        assert expected in main_agent

    for expected in (
        "Canonical template for CodeLoom bounded specialist agents",
        "You do not own the stage artifact or readiness decision",
        "Do not make final stage readiness decisions",
        "Do not turn missing evidence into a positive claim",
        "- finding:",
        "- evidence:",
        "- uncertainty:",
        "- impact:",
    ):
        assert expected in subagent