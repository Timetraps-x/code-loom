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
        "not technical layers, pages, tables, APIs, Jobs, files, individual Spec properties",
        "Artifact is not a property ledger",
        "optional thinking aids, not required fields",
        "accepted or prohibited result first, then protected truth",
        "must not replace the capability contract",
        "Do not repeat a blacklist",
        "omission prompts, not required layer fields",
        "not required layer fields or a capability-by-layer matrix",
        "State each shared design once",
        "Do not duplicate the shared design or build a capability-by-layer table",
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
        "delivered user or system result",
        "Verification and Limitations",
        "Do not make completed tasks or successful commands stand in for goal achievement",
        "Release Notes, When Needed",
        "only material release actions or cautions",
        "Do not invent owners, timing, action completion, or risk acceptance",
        "Keep the actual release-owner decision separate",
        "compact evidence references beside the claims",
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

def test_role_and_subagent_templates_define_ownership_contracts():
    main_role = _template("agent-template.md")
    subagent = _template("subagent-template.md")

    for expected in (
        "Canonical template for CodeLoom stage-owner roles loaded by generated Skills",
        "In the current Main conversation, act as the CodeLoom `<stage-role-name>` role.",
        "Its result is evidence, not authority",
        "Do not delegate the stage decision, artifact ownership, semantic classification, architecture selection, task assignment, or readiness conclusion",
        "Intent",
        "Boundary",
        "Task",
        "Evidence",
        "Readiness",
    ):
        assert expected in main_role

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

def test_tasks_template_preserves_premises_without_new_schema():
    tasks = _template("tasks-template.md")
    for text in ("accepted business or system result", "transferred result premise", "real behavior or inspection entry", "Relation reachability alone", "Missing ideal evidence alone", "labels below are examples, not required fields"):
        assert text in tasks
    main_role = _template("agent-template.md")
    assert "Dedicated Builder and Verifier prompts override" in main_role
    assert "attempt progression belongs to the Host" in main_role

def test_release_template_defaults_to_short_prose_without_table_scaffolding():
    release = _template("release-template.md")
    for text in (
        "supplied Build and Verify conclusions, not a new audit",
        "optional prose guides",
        "combine them for a small delivery",
        "explicit recorded statement and source",
        "An unmet required precondition remains blocking",
        "Omit this section when there are none",
        "Do not produce per-property tables, task recaps, or N/A inventories",
    ):
        assert text in release
    assert not any(line.startswith("|") for line in release.splitlines())


def test_plan_and_tasks_templates_carry_design_and_execution_handoffs():
    plan = _template("plan-template.md")
    for text in (
        "positive path that still guarantees the accepted properties",
        "residual failure they prevent",
        "what is avoided, and what remains input-sized",
        "Separate applicable shared-platform guarantees",
        "replace superseded decisions rather than append exceptions",
    ):
        assert text in plan
    tasks = _template("tasks-template.md")
    for text in (
        "usable result or input and its locatable source",
        "known unavailable prerequisite and smallest recovery action",
        "Do not invent a separate harness task for every fixture",
        "related evidence does not automatically require an execution dependency",
        "merely reissuing tasks or repeating narrower checks is not resolution",
        "otherwise merge related work into a coherent result",
        "Neither shared repository/release nor a target task count",
        "inputs needed to start implementation, runnable conditions needed for integration",
        "without weakening its stop or required proof",
    ):
        assert text in tasks



def test_templates_distinguish_candidate_omissions_from_upstream_meaning():
    spec = _template("spec-template.md")
    plan = _template("plan-template.md")
    tasks = _template("tasks-template.md")
    assert "current delivery, an actual rollout prerequisite, and a future concern" in spec
    assert "Do not silently defer an accepted compatibility" in spec
    assert "Missing requirement meaning cannot be repaired by inventing a design premise" in plan
    assert "A decision missing from the candidate packet is not necessarily missing from Plan" in tasks
    assert "Only when task construction would choose or change a material Plan-owned semantic" in tasks


def test_authoring_templates_separate_investigation_review_and_stage_ownership():
    main = _template("agent-template.md")
    child = _template("subagent-template.md")
    assert "Specialize the decision path to the stage" in main
    assert "A valid return identifies the missing/conflicting upstream meaning" in main
    assert "do not impose a Spec/Plan/Tasks reviewer loop" in main
    assert "fact investigation or advisory review" in child
    assert "Dedicated Do Code Reviewer protocols take precedence" in child
    assert "not adopting your remedy does not qualify" in child