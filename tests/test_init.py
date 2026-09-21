from __future__ import annotations

from importlib import resources
import pytest


from codeloom.app.init_project import init_project, load_project_config

AGENT_NAMES = (
    "code-reviewer.md",
    "adopt-expert.md",
    "spec-reviewer.md",
    "plan-reviewer.md",
    "task-reviewer.md",
)

ROLE_NAMES = (
    "spec-analyzer.md",
    "plan-architect.md",
    "task-planner.md",
    "builder.md",
    "verifier.md",
    "release-analyzer.md",
)

STAGE_ROLE_RESPONSIBILITIES = {
    "spec-analyzer.md": "requirement semantics",
    "plan-architect.md": "system design",
    "task-planner.md": "execution slicing",
    "release-analyzer.md": "delivery conclusion",
}

ROLE_REFERENCES = (
    ("loom-spec", "main-role.md"),
    ("loom-plan", "main-role.md"),
    ("loom-tasks", "main-role.md"),
    ("loom-do", "builder-role.md"),
    ("loom-do", "verifier-role.md"),
    ("loom-ship", "main-role.md"),
)

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
    for role_name in ROLE_NAMES:
        assert not agents_dir.joinpath(role_name).exists()
    for skill_name, reference_name in ROLE_REFERENCES:
        role_path = tmp_path.joinpath(".claude", "skills", skill_name, "references", reference_name)
        assert role_path.exists()
        assert "In the current Main conversation" in role_path.read_text(encoding="utf-8")
    assert not agents_dir.joinpath("scout.md").exists()
    assert not agents_dir.joinpath("codebase-scout.md").exists()
    assert not tmp_path.joinpath(".loom", "agents").exists()
    assert "spec-analyzer" in content
    assert "requirement semantics" in content
    assert "AskUserQuestion" in content
    assert "current Main" in content
    assert "use its clarification gate rather than a generic `unclear input` rule" in content
    assert "If required user input is unclear" not in content
    assert "spec-reviewer" in content
    assert "advisory only" in content
    assert "must not write artifacts" in content
    ship_skill_path = tmp_path.joinpath(".claude", "skills", "loom-ship", "SKILL.md")
    ship_content = ship_skill_path.read_text(encoding="utf-8")
    assert "release.md" in ship_content
    assert ".loom/templates/release-template.md" in ship_content
    assert "release-analyzer" in ship_content
    assert "current Main owns this stage's semantic analysis" in ship_content
    assert "current Main" in ship_content
    assert "No separate reviewer agent" in ship_content
    assert "user-facing Markdown" in ship_content
    assert "extras.artifact_path" in ship_content
    assert "extras.register_command" in ship_content
    assert "status=noop" in ship_content
    assert "specs/<branch-slug>/" not in ship_content
    plan_content = tmp_path.joinpath(".claude", "skills", "loom-plan", "SKILL.md").read_text(encoding="utf-8")
    tasks_content = tmp_path.joinpath(".claude", "skills", "loom-tasks", "SKILL.md").read_text(encoding="utf-8")
    do_content = tmp_path.joinpath(".claude", "skills", "loom-do", "SKILL.md").read_text(encoding="utf-8")

    for skill_content, role_name, reviewer_name in (
        (plan_content, "plan-architect", "plan-reviewer"),
        (tasks_content, "task-planner", "task-reviewer"),
    ):
        assert f"extras.main_role={role_name}" in skill_content
        assert reviewer_name in skill_content
        assert "current Main owns this stage's semantic analysis" in skill_content
        assert "compute its SHA-256" in skill_content
        assert "Supply the exact candidate body" in skill_content
        assert "Review only finding closure and that delta" in skill_content
        assert "extras.artifact_path" in skill_content
        assert "extras.register_command" in skill_content
        assert "specs/<branch-slug>/" not in skill_content

    for semantic_method in (
        "complete and proportionate design",
        "Mechanism deletion must not silently become property deletion",
        "startup/request placement",
        "accepted result, selected mechanism",
    ):
        assert semantic_method not in plan_content
        assert semantic_method not in tasks_content

    assert not positive_cases_dir.joinpath("simple-local-correction.md").exists()
    assert "extras.main_role=builder" in do_content
    assert "extras.main_role=verifier" in do_content
    assert "Code Reviewer" in do_content
    assert "temporary Claude Code child agent" not in do_content
    assert "codebase-scout" not in do_content
    assert "action=begin" in do_content
    assert "extras.host_internal_flow" in do_content
    assert "reviewer_handoff" in do_content
    assert "same Build attempt" in do_content
    assert "fresh Code Reviewer" in do_content
    assert "action=complete" in do_content
    assert "status=<implemented|verified|failed|blocked>" in do_content
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
    agent_path = tmp_path.joinpath(".claude", "agents", "spec-reviewer.md")
    agent_path.write_text("custom spec reviewer", encoding="utf-8")

    init_project(tmp_path)

    assert agent_path.read_text(encoding="utf-8") == "custom spec reviewer"


def test_init_project_force_overwrites_existing_agents(tmp_path):
    init_project(tmp_path)
    agent_path = tmp_path.joinpath(".claude", "agents", "spec-reviewer.md")
    agent_path.write_text("custom spec reviewer", encoding="utf-8")

    init_project(tmp_path, force=True)

    content = agent_path.read_text(encoding="utf-8")
    assert "name: spec-reviewer" in content
    assert "current Main acting in the `spec-analyzer` role" in content
    assert "custom spec reviewer" not in content


def test_init_project_preserves_existing_role_reference_without_force(tmp_path):
    init_project(tmp_path)
    role_path = tmp_path.joinpath(".claude", "skills", "loom-plan", "references", "main-role.md")
    role_path.write_text("custom plan role", encoding="utf-8")

    init_project(tmp_path)

    assert role_path.read_text(encoding="utf-8") == "custom plan role"


def test_init_project_force_overwrites_existing_role_reference(tmp_path):
    init_project(tmp_path)
    role_path = tmp_path.joinpath(".claude", "skills", "loom-plan", "references", "main-role.md")
    role_path.write_text("custom plan role", encoding="utf-8")

    init_project(tmp_path, force=True)

    content = role_path.read_text(encoding="utf-8")
    assert "CodeLoom `plan-architect` role" in content
    assert "custom plan role" not in content


def test_init_project_rejects_role_reference_symlink(tmp_path):
    init_project(tmp_path)
    role_path = tmp_path.joinpath(".claude", "skills", "loom-plan", "references", "main-role.md")
    role_path.unlink()
    outside_target = tmp_path.parent / f"{tmp_path.name}-outside-role.md"
    try:
        role_path.symlink_to(outside_target)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="symbolic link"):
        init_project(tmp_path, force=True)

    assert role_path.is_symlink()
    assert not outside_target.exists()


def test_bundled_agent_and_role_resources_are_packaged():
    bundled_agents = resources.files("codeloom.agents")
    bundled_roles = resources.files("codeloom.roles")

    for agent_name in AGENT_NAMES + ROLE_NAMES:
        package = bundled_roles if agent_name in ROLE_NAMES else bundled_agents
        content = package.joinpath(agent_name).read_text(encoding="utf-8")
        assert content
        if agent_name in STAGE_ROLE_RESPONSIBILITIES:
            assert STAGE_ROLE_RESPONSIBILITIES[agent_name] in content
            if agent_name == "spec-analyzer.md":
                assert "# Recover the Needed Business Chain" in content
                assert "incomplete, mixed, conflicting, or solution-biased human input" in content
                assert "Seek discriminating evidence" in content
                assert "# Investigate Decision-Changing Context" in content
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
                assert "business implementation model to its concrete landing" in content
                assert "complete, proportionate first design" in content
                assert "# Form Viable Routes and Resolve Meaningful Choices" in content
                assert "Use `AskUserQuestion` when viable routes differ" in content
                assert "A reversible or low-risk choice can still require that decision" in content
                assert "Do not ask the user to choose complexity" in content
                assert "adequacy and necessity from its first draft" in content
                assert "positive path that still carries it" in content
                assert "Use PlantUML" in content
                assert "closed local correction may omit them" in content
                assert "Produce readable `plan.md`" in content
                assert "tools:" not in content
                assert "artifact_file" not in content
                assert "Kernel" not in content
            if agent_name == "task-planner.md":
                assert "execution slicing recorded in `tasks.md`" in content
                assert "accepted business and technical properties, selected mechanisms" in content
                assert "# Form the Implementation Result Chain" in content
                assert "work backward from a usable, provable result" in content
                assert "# Slice Build Work" in content
                assert "# Make Verification Executable" in content
                assert "One verify task may cover several naturally related build tasks" in content
                assert "# Compile Self-Contained Task Packets" in content
                assert "source-derived property" in content
                assert "exact accepted business or technical property" in content
                assert "startup, refresh, write, request, or background time" in content
                assert "A generic instruction to “follow the Plan”, “optimize performance”, or “add caching”" in content
                assert "Revision protects execution meaning, not Markdown wording" in content
                assert "increment only the affected packet's Revision" in content
                assert "Do not hide a real design gap in a research/build/verify task" in content
        if agent_name == "builder.md":
            assert "In the current Main conversation, act as the CodeLoom `builder` role" in content
            assert "frozen Task Packet as the execution boundary" in content
            assert "what accepted properties must remain true" in content
            assert "which selected mechanism carries each material property" in content
            assert "Fewer lines or objects with a lost behavior" in content
            assert "before and after placement, frequency, realistic scale, and cost" in content
            assert "bounded startup, refresh, or write path into a frequent request path" in content
            assert "Place named facts and responsibilities with their semantic owner" in content
            assert "Do not claim independent review or full verification" in content
            assert "Report this conflict through the current Skill flow" in content
            assert "do not perform workflow routing or modify upstream artifacts" in content
            assert "temporary Claude Code child agent" not in content
            assert "Kernel" not in content
            assert "SQLite" not in content
        if agent_name == "verifier.md":
            assert "In the current Main conversation, act as the CodeLoom `verifier` role" in content
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
                assert "bounded advisory reviewer supporting the current Main acting in the `spec-analyzer` role" in content
                assert "exact delegated candidate text and supplied candidate identity" in content
                assert "candidate anchor" in content
                assert "candidate-conforming failure" in content
                assert "scoped_evidence_limit" in content
                assert "re-review only prior material finding closure" in content
                assert "leave the final requirement judgment to `spec-analyzer`" in content
            elif agent_name == "plan-reviewer.md":
                assert "bounded, adversarial reviewer supporting Main" in content
                assert "independent baseline is the current demand" in content
                assert "candidate-conforming failure or unsupported material cost" in content
                assert "user-owned choices" in content
                assert "cheap final comparison does not hide input-sized upstream work" in content
                assert "finding closure, the real delta" in content
                assert "do not rewrite the Plan or choose a replacement architecture" in content
            elif agent_name == "task-reviewer.md":
                assert "bounded, adversarial reviewer supporting the current Main acting in the `task-planner` role" in content
                assert "exact candidate text and supplied candidate identity" in content
                assert "exact packet/relation anchor" in content
                assert "candidate-conforming downstream failure" in content
                assert "Review only finding closure, those changes" in content
                assert "scoped evidence limit" in content
            else:
                assert "attempt-scoped diff" in content
                assert "review-object integrity" in content
                assert "blocked` only when the review object is unavailable, stale, or invalid" in content

def test_agent_tool_whitelist_removal_is_limited_to_subagents():
    bundled_agents = resources.files("codeloom.agents")
    for agent_name in AGENT_NAMES:
        content = bundled_agents.joinpath(agent_name).read_text(encoding="utf-8")
        assert "tools: Read, Glob, Grep" not in content

    bundled_roles = resources.files("codeloom.roles")
    for role_name in ROLE_NAMES:
        content = bundled_roles.joinpath(role_name).read_text(encoding="utf-8")
        assert "tools:" not in content


def test_tasks_and_do_project_updated_role_handoffs(tmp_path):
    init_project(tmp_path)
    skills = tmp_path / ".claude" / "skills"
    tasks_role = (skills / "loom-tasks/references/main-role.md").read_text(encoding="utf-8")
    tasks_skill = (skills / "loom-tasks/SKILL.md").read_text(encoding="utf-8")
    assert "transferred result premise" in tasks_role
    assert "transferred result premise" not in tasks_skill
    assert "Do not re-litigate" in (skills / "loom-do/references/builder-role.md").read_text(encoding="utf-8")
    assert "proof_limit:" in (skills / "loom-do/references/verifier-role.md").read_text(encoding="utf-8")
    assert "trustworthy seal-to-seal delta" in (skills / "loom-do/SKILL.md").read_text(encoding="utf-8")
    reviewer = tmp_path / ".claude/agents/code-reviewer.md"
    assert "obligation_source:" in reviewer.read_text(encoding="utf-8")

def test_ship_projection_matches_bundled_role_and_template(tmp_path):
    init_project(tmp_path)
    role = resources.files("codeloom.roles").joinpath("release-analyzer.md").read_text(encoding="utf-8")
    template = resources.files("codeloom.templates").joinpath("release-template.md").read_text(encoding="utf-8")
    assert (tmp_path / ".claude/skills/loom-ship/references/main-role.md").read_text(encoding="utf-8") == role
    assert (tmp_path / ".loom/templates/release-template.md").read_text(encoding="utf-8") == template