from __future__ import annotations

from importlib import resources

from codeloom.app.init_project import init_project, load_project_config

AGENT_NAMES = (
    "spec-analyzer.md",
    "plan-architect.md",
    "task-planner.md",
    "builder.md",
    "verifier.md",
    "release-analyzer.md",
    "code-reviewer.md",
    "adopt-expert.md",
    "spec-reviewer.md",
    "plan-reviewer.md",
    "task-reviewer.md",
)

STAGE_AGENT_RESPONSIBILITIES = {
    "spec-analyzer.md": "requirement semantics",
    "plan-architect.md": "system design",
    "task-planner.md": "execution slicing",
    "release-analyzer.md": "delivery readiness",
}

REVIEWER_AGENTS = {
    "spec-reviewer.md": "spec-analyzer",
    "plan-reviewer.md": "plan-architect",
    "task-reviewer.md": "task-planner",
}


def test_init_project_creates_config_runtime_and_skills(tmp_path):
    created, project_path = init_project(tmp_path)

    assert created is True
    assert project_path.endswith("project.yml")
    project_config = tmp_path.joinpath(".loom", "project.yml").read_text(encoding="utf-8")
    assert tmp_path.joinpath(".loom", "project.yml").exists()
    assert "specs:\n  language: en" in project_config
    assert "runtime:\n  default: claude-code" in project_config
    assert "claude-code:\n      enabled: true" in project_config
    assert "mode: host" in project_config
    assert "profile:\n  languages: \"\"\n  frameworks: \"\"\n  modules: \"\"" in project_config
    assert "constitution:\n  path: .loom/constitution.md\n  hash: \"\"" in project_config
    project_config_data = load_project_config(tmp_path)
    assert project_config_data.spec_language == "en"
    assert project_config_data.default_runtime == "claude-code"
    assert project_config_data.constitution_path == ".loom/constitution.md"
    assert project_config_data.constitution_hash == ""
    assert project_config_data.languages == ()
    assert project_config_data.frameworks == ()
    assert project_config_data.modules == ()
    assert not tmp_path.joinpath("project.yml").exists()
    assert tmp_path.joinpath(".loom", "loom.db").exists()
    assert tmp_path.joinpath(".loom", "runs").exists()
    templates_dir = tmp_path.joinpath(".loom", "templates")
    assert templates_dir.joinpath("spec-template.md").exists()
    assert templates_dir.joinpath("plan-template.md").exists()
    assert templates_dir.joinpath("tasks-template.md").exists()
    assert templates_dir.joinpath("release-template.md").exists()
    assert templates_dir.joinpath("constitution-template.md").exists()
    constitution_path = tmp_path.joinpath(".loom", "constitution.md")
    assert constitution_path.exists()
    constitution_content = constitution_path.read_text(encoding="utf-8")
    assert "Code Placement and Ownership" in constitution_content
    assert "Stack-Local Code Shape" in constitution_content
    positive_cases_dir = tmp_path.joinpath(".loom", "references", "positive-cases")
    assert positive_cases_dir.joinpath("java-spring-mybatis.md").exists()
    assert positive_cases_dir.joinpath("python-fastapi.md").exists()
    assert positive_cases_dir.joinpath("react-next.md").exists()
    assert positive_cases_dir.joinpath("go-http.md").exists()
    skill_path = tmp_path.joinpath(".claude", "skills", "loom-spec", "SKILL.md")
    assert skill_path.exists()
    content = skill_path.read_text(encoding="utf-8")
    assert "name: loom-spec" in content
    assert "user-invocable: true" in content
    assert "disable-model-invocation: false" in content
    assert ".loom/templates/spec-template.md" in content
    adopt_skill_path = tmp_path.joinpath(".claude", "skills", "loom-adopt", "SKILL.md")
    assert adopt_skill_path.exists()
    adopt_content = adopt_skill_path.read_text(encoding="utf-8")
    assert "adopt-expert" in adopt_content
    assert "loom adopt --constitution <exact-configured-path>" in adopt_content
    assert ".loom/templates/constitution-template.md" in adopt_content
    assert "configured `constitution.path`" in adopt_content
    assert "project profile independently" in adopt_content
    assert "update-claude" in adopt_content
    assert "never append them to the constitution" in adopt_content
    assert "AskUserQuestion" in adopt_content
    assert "promotion, authority, or legacy conflict" in adopt_content
    assert "Child-agent delegation is optional" in adopt_content
    assert "absence of a delegation channel is not itself a blocker" in adopt_content
    assert "do not assume `.loom/constitution.md`" in adopt_content
    assert "`scout`" not in adopt_content
    assert "`codebase-scout`" not in adopt_content
    agents_dir = tmp_path.joinpath(".claude", "agents")
    for agent_name in AGENT_NAMES:
        assert agents_dir.joinpath(agent_name).exists()
    assert not agents_dir.joinpath("scout.md").exists()
    assert not agents_dir.joinpath("codebase-scout.md").exists()
    assert not tmp_path.joinpath(".loom", "agents").exists()
    assert "spec-analyzer" in content
    assert "requirement semantics" in content
    assert "AskUserQuestion" in content
    assert "temporary Claude Code child agent" in content
    assert "spec-reviewer" in content
    assert "advisory only" in content
    assert "must not write artifacts" in content
    ship_skill_path = tmp_path.joinpath(".claude", "skills", "loom-ship", "SKILL.md")
    ship_content = ship_skill_path.read_text(encoding="utf-8")
    assert "release.md" in ship_content
    assert ".loom/templates/release-template.md" in ship_content
    assert "release-analyzer" in ship_content
    assert "delivery readiness" in ship_content
    assert "temporary Claude Code child agent" in ship_content
    assert "No separate reviewer agent" in ship_content
    assert "user-facing Markdown" in ship_content
    assert "extras.artifact_path" in ship_content
    assert "extras.register_command" in ship_content
    assert "status=noop" in ship_content
    assert "specs/<branch-slug>/" not in ship_content
    plan_content = tmp_path.joinpath(".claude", "skills", "loom-plan", "SKILL.md").read_text(encoding="utf-8")
    tasks_content = tmp_path.joinpath(".claude", "skills", "loom-tasks", "SKILL.md").read_text(encoding="utf-8")
    do_content = tmp_path.joinpath(".claude", "skills", "loom-do", "SKILL.md").read_text(encoding="utf-8")
    assert "plan-architect" in plan_content
    assert "plan-reviewer" in plan_content
    assert "system design" in plan_content
    assert "commitment and minimal counterexample" in plan_content
    assert "selected implementation route" in plan_content
    assert "abstract model with shared/separate facts and variation axes" in plan_content
    assert "business mechanism with truth, invariants, ownership, state, and collaboration" in plan_content
    assert "necessary current-project projection" in plan_content
    assert "smallest counterexample" in plan_content
    assert "must not review headings or a universal field checklist" in plan_content
    assert "avoid re-deciding a material semantic in Tasks/Do" in plan_content
    assert "temporary Claude Code child agent" in plan_content
    assert "task-planner" in tasks_content
    assert "task-reviewer" in tasks_content
    assert "execution slicing" in tasks_content
    assert "exact candidate text and candidate identity" in tasks_content
    assert "minimum downstream consumer obligation" in tasks_content
    assert "new exact candidate identity and affected packet/claim" in tasks_content
    assert "build or verify tasks only" in tasks_content
    assert "lanes other than `build` or `verify`" in tasks_content
    assert "do not each need independent functional verification" in tasks_content
    assert "Verify tasks may cover multiple naturally related build tasks" in tasks_content
    assert "Only a fact necessary to define safe slicing" in tasks_content
    assert "Route a missing material design decision or evidence-backed design blocker upstream" in tasks_content
    assert "Do not copy large plan sections" in tasks_content
    assert "leave unrelated follow-up outside `tasks.md`" in tasks_content
    assert not positive_cases_dir.joinpath("simple-local-correction.md").exists()
    assert "project `builder` Agent for `build` tasks" in do_content
    assert "project `verifier` Agent for `verify` tasks" in do_content
    assert "Code Reviewer" in do_content
    assert "complete, correct, performant, maintainable, readable, secure, reliable, and testable implementation" in do_content
    assert "temporary Claude Code child agent" not in do_content
    assert "codebase-scout" not in do_content
    assert "action=begin" in do_content
    assert "extras.host_internal_flow" in do_content
    assert "reviewer_handoff" in do_content
    assert "same Builder attempt" in do_content
    assert "fresh Code Reviewer" in do_content
    assert "action=complete" in do_content
    assert "status=<implemented|verified|failed|blocked>" in do_content
    for artifact_content in (plan_content, tasks_content):
        assert "extras.artifact_path" in artifact_content
        assert "extras.register_command" in artifact_content
        assert "specs/<branch-slug>/" not in artifact_content
    assert "agent output contracts" in plan_content
    assert "artifact_file" in tasks_content


def test_init_project_writes_requested_specs_language(tmp_path):
    created, _ = init_project(tmp_path, language="zh")

    assert created is True
    project_config = tmp_path.joinpath(".loom", "project.yml").read_text(encoding="utf-8")
    assert "specs:\n  language: zh" in project_config
    assert load_project_config(tmp_path).spec_language == "zh"


def test_init_project_without_claude_code_uses_mock_runtime_and_skips_claude_skills(tmp_path):
    init_project(tmp_path, integrations={"codex"})

    project_config = tmp_path.joinpath(".loom", "project.yml").read_text(encoding="utf-8")
    assert "runtime:\n  default: mock" in project_config
    assert "codex:\n      enabled: true" in project_config
    assert load_project_config(tmp_path).default_runtime == "mock"
    assert not tmp_path.joinpath(".claude", "skills", "loom-spec", "SKILL.md").exists()
    assert not tmp_path.joinpath(".claude", "agents", "spec-analyzer.md").exists()


def test_init_project_preserves_existing_runtime_without_force(tmp_path):
    init_project(tmp_path)
    project_path = tmp_path.joinpath(".loom", "project.yml")
    project_path.write_text(
        project_path.read_text(encoding="utf-8").replace("default: claude-code", "default: mock"),
        encoding="utf-8",
    )

    created, _ = init_project(tmp_path)

    assert created is False
    assert load_project_config(tmp_path).default_runtime == "mock"


def test_init_project_force_regenerates_runtime_from_selected_integrations(tmp_path):
    init_project(tmp_path, integrations={"codex"})

    created, _ = init_project(tmp_path, force=True)

    assert created is True
    assert load_project_config(tmp_path).default_runtime == "claude-code"

def test_init_project_preserves_existing_templates_without_force(tmp_path):
    init_project(tmp_path)
    plan_template = tmp_path.joinpath(".loom", "templates", "plan-template.md")
    plan_template.write_text("custom plan template", encoding="utf-8")

    init_project(tmp_path)

    assert plan_template.read_text(encoding="utf-8") == "custom plan template"


def test_init_project_does_not_overwrite_existing_constitution(tmp_path):
    init_project(tmp_path)
    constitution_path = tmp_path.joinpath(".loom", "constitution.md")
    constitution_path.write_text("# Custom Constitution\n\nProject-specific rules.\n", encoding="utf-8")

    init_project(tmp_path, force=True)

    assert constitution_path.read_text(encoding="utf-8") == "# Custom Constitution\n\nProject-specific rules.\n"
    assert load_project_config(tmp_path).constitution_hash == ""


def test_init_project_force_overwrites_existing_templates(tmp_path):
    init_project(tmp_path)
    plan_template = tmp_path.joinpath(".loom", "templates", "plan-template.md")
    plan_template.write_text("custom plan template", encoding="utf-8")

    init_project(tmp_path, force=True)

    content = plan_template.read_text(encoding="utf-8")
    assert "# <Requirement Name> Plan" in content
    assert "custom plan template" not in content


def test_init_project_preserves_existing_agents_without_force(tmp_path):
    init_project(tmp_path)
    agent_path = tmp_path.joinpath(".claude", "agents", "spec-analyzer.md")
    agent_path.write_text("custom spec analyzer", encoding="utf-8")

    init_project(tmp_path)

    assert agent_path.read_text(encoding="utf-8") == "custom spec analyzer"


def test_init_project_force_overwrites_existing_agents(tmp_path):
    init_project(tmp_path)
    agent_path = tmp_path.joinpath(".claude", "agents", "spec-analyzer.md")
    agent_path.write_text("custom spec analyzer", encoding="utf-8")

    init_project(tmp_path, force=True)

    content = agent_path.read_text(encoding="utf-8")
    assert "name: spec-analyzer" in content
    assert "requirement semantics" in content
    assert "custom spec analyzer" not in content


def test_bundled_agent_resources_are_packaged():
    bundled_agents = resources.files("codeloom.agents")

    for agent_name in AGENT_NAMES:
        content = bundled_agents.joinpath(agent_name).read_text(encoding="utf-8")
        assert content
        if agent_name in STAGE_AGENT_RESPONSIBILITIES:
            assert STAGE_AGENT_RESPONSIBILITIES[agent_name] in content
            if agent_name == "spec-analyzer.md":
                assert "# Recover the Real Requirement" in content
                assert "incomplete, mixed, conflicting, or solution-biased human input" in content
                assert "Seek discriminating evidence" in content
                assert "compare the current reality with the required reality" in content
                assert "Every material promise receives an evidence-backed judgment" in content
                assert "Goal, Way, and Proof as reasoning lenses, not required headings" in content
                assert "Produce a coherent, user-facing `spec.md`" in content
                assert "Do not produce technical architecture" in content
            else:
                if agent_name != "plan-architect.md":
                    assert "Produce clean" in content
                if agent_name not in {"plan-architect.md", "task-planner.md"}:
                    assert "Do not include agent process notes" in content
                if agent_name not in {"plan-architect.md", "task-planner.md", "release-analyzer.md"}:
                    assert "bounded clarification" in content
            if agent_name == "plan-architect.md":
                assert "target business implementation model and its concrete landing" in content
                assert "# Inputs and Evidence" in content
                assert "# Form the Business Implementation Design" in content
                assert "Group promises that must be established by one coherent capability" in content
                assert "authoritative, derived, attached, and external snapshot facts" in content
                assert "# Land the Design in the Current Project" in content
                assert "reuse, extend, correct, replace, add, or preserve a real difference" in content
                assert "A technical surface is material when omitting it" in content
                assert "bounded retry or attempt budget" in content
                assert "claim, redelivery, actual invocation, and crash-after-claim" in content
                assert "automatic, scheduled, manual/support, admin, callback, and reconciliation paths" in content
                assert "bind each read surface to the same authoritative fact" in content
                assert "Use the smallest useful PlantUML diagram" in content
                assert "A closed local correction may omit diagrams" in content
                assert "Produce a readable, self-evidencing `plan.md`" in content
                assert "tools:" not in content
                assert "artifact_file" not in content
                assert "Kernel" not in content
            if agent_name == "task-planner.md":
                assert "execution slicing recorded in `tasks.md`" in content
                assert "# Form the Implementation Result Chain" in content
                assert "current-to-target implementation results" in content
                assert "# Slice Build Work" in content
                assert "Do not split mechanically by UI, API, service, mapper, schema, file, class, function, or technical layer" in content
                assert "# Design Verify Coverage" in content
                assert "One verify task may cover several naturally related build tasks" in content
                assert "start proof at the real behavior entry that creates it" in content
                assert "Verification proves behavior established by accepted design and implementation" in content
                assert "return the smallest Plan design gap instead of creating research or `verify` work" in content
                assert "# Compile Self-Contained Task Packets" in content
                assert "Inside the same captured block" in content
                assert "A Task List item containing only `Lane`, `Complexity`, and `Revision` is invalid" in content
                assert "Put every execution-critical fact directly beneath its own checklist line" in content
                assert "A Plan reference supplies traceability, not missing execution context" in content
                assert "exact authoritative state or fact, legal transition, losing-concurrency result" in content
                assert "# Revise and Write" in content
                assert "Revision protects execution meaning, not Markdown wording" in content
                assert "never bump every task merely because an upstream artifact changed" in content
                assert "smallest evidence-backed design gap" in content
        if agent_name == "builder.md":
            assert "build-lane implementation agent" in content
            assert "quality of one task-scoped implementation" in content
            assert "complete, correct, performant, maintainable, readable, secure, reliable, and testable code" in content
            assert "High quality is not a universal checklist" in content
            assert "frozen Task Packet as the execution boundary" in content
            assert "Inspect current code, callers, consumers, tests, state/data flow" in content
            assert "Resolve ordinary reversible implementation choices yourself" in content
            assert "query and traversal count" in content
            assert "Place named facts and responsibilities with their semantic owner" in content
            assert "Do not claim independent review or full verification" in content
            assert "Report this conflict to the host" in content
            assert "do not perform workflow routing or modify upstream artifacts" in content
            assert "temporary Claude Code child agent" not in content
            assert "Host" not in content
            assert "Kernel" not in content
            assert "SQLite" not in content
        if agent_name == "verifier.md":
            assert "verify-lane agent" in content
            assert "Verification is behavior judgment, not evidence-field completion" in content
            assert "Choose the strongest useful path that the current project can support" in content
            assert "A pre-seeded intermediate state does not prove creation behavior" in content
            assert "retain narrower checks that still prove scoped facts" in content
            assert "`verified`: every material obligation" in content
            assert "`failed`: an actual observation contradicts required behavior" in content
            assert "`blocked`: one or more necessary obligations remain not verified" in content
            assert "Do not decide workflow routing or attempt state" in content
            assert "temporary Claude Code child agent" not in content
            assert "Kernel" not in content
            assert "SQLite" not in content
        if agent_name == "code-reviewer.md":
            assert "bounded, adversarial reviewer" in content
            assert "attempt-scoped diff from attempt start to that sealed revision" in content
            assert "# Independent Baseline" in content
            assert "# Counterexample Method" in content
            assert "smallest relevant candidate-conforming scenario" in content
            assert "N+1 queries, repeated traversal, duplicate I/O, unbounded work" in content
            assert "There is no finding quota" in content
            assert "failure_scenario" in content
            assert "Do not add a category merely to classify a finding" in content
            assert "blocked` only when the review object is unavailable, stale, or invalid" in content
            assert "decide workflow routing" in content
            assert "Host" not in content
            assert "Kernel" not in content
            assert "SQLite" not in content
        if agent_name == "adopt-expert.md":
            assert "durable engineering constitution" in content
            assert "# Promotion Judgment" in content
            assert "# Project Profile" in content
            assert "Do not inventory the whole repository" in content
            assert "CLAUDE.md Suggestions" in content
            assert "Delegation is optional" in content
            assert "workflow state" not in content
            assert "SQLite" not in content
        if agent_name in REVIEWER_AGENTS:
            assert "Do not" in content
            assert REVIEWER_AGENTS[agent_name] in content
            if agent_name == "spec-reviewer.md":
                assert "bounded advisory reviewer supporting `spec-analyzer`" in content
                assert "# Counterexample Method" in content
                assert "smallest evidence-backed counterexample" in content
                assert "## Commitment loss" in content
                assert "## Evidence overreach" in content
                assert "## Causal-chain incompleteness" in content
                assert "## Unauthorized convergence" in content
                assert "leave the final requirement judgment to `spec-analyzer`" in content
            elif agent_name == "plan-reviewer.md":
                assert "bounded, adversarial reviewer supporting `plan-architect`" in content
                assert "# Independent Minimum Baseline" in content
                assert "Do not use the candidate's headings" in content
                assert "# Counterexample Method" in content
                assert "smallest reasonable implementation that fully follows the candidate" in content
                assert "## Commitment-to-model break" in content
                assert "## Mechanism break" in content
                assert "vary which event each reasonable consumer counts—claim, redelivery, invocation, or crash-after-claim" in content
                assert "automatic, scheduled, manual/support, admin, callback, and reconciliation entry" in content
                assert "same authoritative fact rather than allowing local submission to appear as external success" in content
                assert "## Project-landing or cross-layer break" in content
                assert "## Evidence or authority break" in content
                assert "A candidate is underdetermined when a reasonable implementer must still choose" in content
                assert "tools:" not in content
                assert "do not rewrite the Plan, select a replacement architecture" in content
            elif agent_name != "task-reviewer.md":
                assert f"bounded specialist reviewer supporting `{REVIEWER_AGENTS[agent_name]}`" in content
                assert "Do not make final stage readiness decisions" in content
            if agent_name == "task-reviewer.md":
                assert "bounded, adversarial reviewer supporting `task-planner`" in content
                assert "Use the exact candidate text and supplied candidate identity" in content
                assert "# Independent Consumer Baseline" in content
                assert "# Simulate the Consumer" in content
                assert "# Falsify" in content
                assert "# Hand Back" in content
                assert "first isolate the packet at its checklist line" in content
                assert "A metadata-only Task List item is not saved by a table, delivery map, or later `Task Notes` section" in content
                assert "Later reader notes, delivery maps, or global prose cannot repair" in content
                assert "disguise evidence needed to select or finish Plan design as a `verify` task" in content
                assert "generic Plan reference the only source of an authoritative fact" in content
                assert "pre-seeded intermediate state while omitting the real creation entry" in content
                assert "turn grouped verification into an unrelated mega-batch" in content
                assert "duplicate IDs, dangling build/verify relations" in content
                assert "say so without treating the result as approval" in content

def test_agent_tool_whitelist_removal_is_limited_to_requested_agents():
    bundled_agents = resources.files("codeloom.agents")
    removed = (
        "adopt-expert.md",
        "plan-architect.md",
        "plan-reviewer.md",
        "release-analyzer.md",
        "spec-analyzer.md",
        "spec-reviewer.md",
        "task-planner.md",
        "task-reviewer.md",
    )
    for agent_name in removed:
        content = bundled_agents.joinpath(agent_name).read_text(encoding="utf-8")
        assert "tools: Read, Glob, Grep" not in content

    assert "tools: Read, Edit, Write, Bash, Grep, Glob" in bundled_agents.joinpath("builder.md").read_text(encoding="utf-8")
