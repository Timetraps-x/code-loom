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
    "scout.md",
    "codebase-scout.md",
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
    project_config_data = load_project_config(tmp_path)
    assert project_config_data.spec_language == "en"
    assert project_config_data.default_runtime == "claude-code"
    assert not tmp_path.joinpath("project.yml").exists()
    assert tmp_path.joinpath(".loom", "loom.db").exists()
    assert tmp_path.joinpath(".loom", "runs").exists()
    templates_dir = tmp_path.joinpath(".loom", "templates")
    assert templates_dir.joinpath("spec-template.md").exists()
    assert templates_dir.joinpath("plan-template.md").exists()
    assert templates_dir.joinpath("tasks-template.md").exists()
    assert templates_dir.joinpath("release-template.md").exists()
    skill_path = tmp_path.joinpath(".claude", "skills", "loom-spec", "SKILL.md")
    assert skill_path.exists()
    content = skill_path.read_text(encoding="utf-8")
    assert "name: loom-spec" in content
    assert "user-invocable: true" in content
    assert "disable-model-invocation: false" in content
    assert ".loom/templates/spec-template.md" in content
    agents_dir = tmp_path.joinpath(".claude", "agents")
    for agent_name in AGENT_NAMES:
        assert agents_dir.joinpath(agent_name).exists()
    assert not tmp_path.joinpath(".loom", "agents").exists()
    assert "spec-analyzer" in content
    assert "requirement semantics" in content
    assert "AskUserQuestion" in content
    assert "scout" in content
    assert "spec-reviewer" in content
    assert "advisory only" in content
    assert "must not write artifacts" in content
    ship_skill_path = tmp_path.joinpath(".claude", "skills", "loom-ship", "SKILL.md")
    ship_content = ship_skill_path.read_text(encoding="utf-8")
    assert "release.md" in ship_content
    assert ".loom/templates/release-template.md" in ship_content
    assert "release-analyzer" in ship_content
    assert "delivery readiness" in ship_content
    assert "scout" in ship_content
    assert "No separate reviewer agent" in ship_content
    assert "user-facing Markdown" in ship_content
    assert "specs/<branch-slug>/release.md" in ship_content
    assert "artifact_file" in ship_content
    plan_content = tmp_path.joinpath(".claude", "skills", "loom-plan", "SKILL.md").read_text(encoding="utf-8")
    tasks_content = tmp_path.joinpath(".claude", "skills", "loom-tasks", "SKILL.md").read_text(encoding="utf-8")
    do_content = tmp_path.joinpath(".claude", "skills", "loom-do", "SKILL.md").read_text(encoding="utf-8")
    assert "plan-architect" in plan_content
    assert "plan-reviewer" in plan_content
    assert "system design" in plan_content
    assert "scout" in plan_content
    assert "task-planner" in tasks_content
    assert "task-reviewer" in tasks_content
    assert "execution slicing" in tasks_content
    assert "generic large rubric" in tasks_content
    assert "scout" in tasks_content
    assert "build or verify tasks only" in tasks_content
    assert "do not create scout" in tasks_content
    assert "do not each need independent functional verification" in tasks_content
    assert "Verify tasks may cover multiple naturally related build tasks" in tasks_content
    assert "Missing facts that block safe slicing" in tasks_content
    assert "Do not copy large plan sections" in tasks_content
    assert "Optional `## Ship inputs` content is non-executable" in tasks_content
    assert "builder" in do_content
    assert "code-reviewer" in do_content
    assert "verifier" in do_content
    assert "codebase-scout" in do_content
    assert "narrow read-only repository fact questions" in do_content
    assert "Build attempts must complete as `implemented`, `failed`, or `blocked`" in do_content
    assert "action=begin" in do_content
    assert "action=complete" in do_content
    assert "builder` is the build-lane main agent" in do_content
    assert "verifier` is the verify-lane main agent" in do_content
    assert "specs/<branch-slug>/plan.md" in plan_content
    assert "agent output contracts" in plan_content
    assert "specs/<branch-slug>/tasks.md" in tasks_content
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


def test_init_project_force_overwrites_existing_templates(tmp_path):
    init_project(tmp_path)
    plan_template = tmp_path.joinpath(".loom", "templates", "plan-template.md")
    plan_template.write_text("custom plan template", encoding="utf-8")

    init_project(tmp_path, force=True)

    content = plan_template.read_text(encoding="utf-8")
    assert "# <Requirement Name> Technical Plan" in content
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
                assert "Produce clean `spec.md` content following `spec-template.md`" in content
                assert "Do not include agent process notes" in content
                assert "bounded clarification" in content
            else:
                assert "Produce clean" in content
                assert "Do not include agent process notes" in content
                assert "bounded clarification" in content
            if agent_name == "task-planner.md":
                assert "Every executable task must be either" in content
                assert "A build task does not need to independently prove the whole feature works" in content
                assert "## Ship inputs" in content
                assert "Do not copy large plan sections" in content
                assert "verification coverage map" in content
                assert "full verify task set collectively covers requested behavior and material impacted regression surfaces" in content
                assert "do not merge build tasks merely because they share a grouped verify task" in content
        if agent_name == "builder.md":
            assert "build-lane main agent" in content
            assert "code-reviewer" in content
            assert "Do not self-mark the task verified" in content
            assert "Treat the current task as the direct execution boundary" in content
            assert "existing-code consistency, correctness, performance, maintainability, change cost, and verification cost" in content
            assert "report which upstream artifact needs revision" in content
            assert "codebase-scout" in content
            assert "generic `scout` only when artifact/runtime/external evidence is needed" in content
            assert "reasonable content density" in content
            assert "repeated `collectXxx(...)` helper traversals" in content
            assert "stable reusable capability" in content
        if agent_name == "verifier.md":
            assert "verify-lane main agent" in content
            assert "revise_spec_plan_tasks" in content
            assert "Do not broaden verification to the whole plan" in content
            assert "missing evidence" in content
            assert "codebase-scout" in content
            assert "existing verification conventions inside the current task boundary" in content
        if agent_name == "code-reviewer.md":
            assert "required subagent" in content
            assert "Return findings to `builder`" in content
            assert "current task boundary" in content
            assert "boundary_violation" in content
            assert "content_density_risk" in content
            assert "cosmetic_extraction" in content
            assert "n_plus_one_query" in content
            assert "query_naming_risk" in content
            assert "full-sentence method or test names" in content
            assert "concise behavior names" in content
        if agent_name == "scout.md":
            assert "bounded specialist evidence agent supporting a CodeLoom main agent" in content
            assert "codebase mode" in content
            assert "external mode" in content
            assert "Answer only the delegated factual question" in content
            assert "Do not write final stage artifacts" in content
            assert "Do not turn missing evidence into a positive claim" in content
            assert "runtime evidence refs" in content
            assert "Open questions are evidence gaps for the main agent" in content
            assert "Do not push uncertainty to the next stage as if it were resolved evidence" in content
        if agent_name == "codebase-scout.md":
            assert "bounded specialist codebase evidence agent supporting a CodeLoom do-stage main agent" in content
            assert "Answer only the delegated codebase fact question" in content
            assert "Do not run commands" in content
            assert "Do not decide task status" in content
            assert "Open questions are evidence gaps for the do-stage main agent" in content
            assert "Do not push uncertainty to `builder`, `verifier`, or later stages as if it were resolved evidence" in content
            assert "reusable data-access capabilities" in content
            assert "SQL/query naming conventions" in content
            assert "visible N+1 or repeated-query risks" in content
        if agent_name in REVIEWER_AGENTS:
            assert "Do not" in content
            assert REVIEWER_AGENTS[agent_name] in content
            if agent_name == "spec-reviewer.md":
                assert "bounded specialist reviewer supporting `spec-analyzer`" in content
                assert "Do not decide pass/fail" in content
            else:
                assert f"bounded specialist reviewer supporting `{REVIEWER_AGENTS[agent_name]}`" in content
                assert "Do not make final stage readiness decisions" in content
            if agent_name == "task-reviewer.md":
                assert "Grouped verification is allowed" in content
                assert "Do not require every build task to have independent functional verification" in content
