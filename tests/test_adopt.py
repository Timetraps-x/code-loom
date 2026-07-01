from __future__ import annotations

import json
from importlib import resources

from codeloom.app.init_project import init_project, load_project_config
from codeloom.cli.main import main


def test_adopt_registers_constitution_hash(tmp_path, capsys):
    init_project(tmp_path)
    constitution_path = tmp_path / ".loom" / "constitution.md"
    constitution_path.write_text("# Constitution\n\nProject rulebook / quality baseline.\n", encoding="utf-8")

    exit_code = main(["adopt", "--cwd", str(tmp_path), "--json"])
    output = capsys.readouterr().out
    payload = json.loads(output)
    config = load_project_config(tmp_path)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["constitution"]["path"] == ".loom/constitution.md"
    assert payload["constitution"]["matches_registered"] is True
    assert config.constitution_path == ".loom/constitution.md"
    assert config.constitution_hash == payload["constitution"]["current_hash"]


def test_adopt_requires_initialized_project_and_existing_constitution(tmp_path, capsys):
    exit_code = main(["adopt", "--cwd", str(tmp_path), "--json"])
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["errors"]

def test_constitution_template_uses_cross_language_quality_sections():
    content = resources.files("codeloom.templates").joinpath("constitution-template.md").read_text(encoding="utf-8")

    assert "Code Placement and Ownership" in content
    assert "Business, Data, and State Flow Visibility" in content
    assert "Abstraction, Reuse, and Naming Thresholds" in content
    assert "Stack-Local Code Shape" in content
    assert "Change Risk Boundaries" in content
    assert "Rule Stability Boundary" in content
    assert "Do not keep generic template instructions" in content
    assert "Stack Profiles" not in content
    assert "Project Identity and Quality Baseline" not in content


def test_adopt_expert_requires_stack_detection_before_positive_case_loading():
    content = resources.files("codeloom.agents").joinpath("adopt-expert.md").read_text(encoding="utf-8")

    assert "Detect the project's real stack" in content
    assert "Read only matching stack material under `.loom/references/positive-cases/`" in content
    assert "Positive cases are interpretation aids" in content
    assert "short guidance only for stacks actually present" in content


def test_adopt_expert_claude_md_suggestions_are_update_claude_only():
    content = resources.files("codeloom.agents").joinpath("adopt-expert.md").read_text(encoding="utf-8")

    default_section = content.split("Explicit `update-claude` mode:", 1)[0]
    assert "Read project `CLAUDE.md` files when present" in default_section
    assert "Do not emit `CLAUDE.md` rewrite suggestions" in default_section
    assert "Do not modify any `CLAUDE.md`" in default_section
    assert "Only when the user argument clearly requests `update-claude`" in content
    assert "Default mode: return clean `.loom/constitution.md` content only" in content


def test_adopt_expert_defaults_constitution_to_english_for_llm_consumption():
    content = resources.files("codeloom.agents").joinpath("adopt-expert.md").read_text(encoding="utf-8")

    assert "Write `.loom/constitution.md` in English by default" in content
    assert "downstream prompt surface" in content
    assert "Use another language only when the user explicitly requests it" in content


def test_adopt_expert_rejects_constitution_scaffold_prose():
    content = resources.files("codeloom.agents").joinpath("adopt-expert.md").read_text(encoding="utf-8")

    assert "Every final bullet must name a concrete project owner" in content
    assert "Do not write self-describing scaffold prose" in content
    assert "Omit any section that has no project-specific content" in content


def test_adopt_expert_has_evidence_classification_and_user_question_gate():
    content = resources.files("codeloom.agents").joinpath("adopt-expert.md").read_text(encoding="utf-8")

    assert "Evidence classification and promotion rules" in content
    assert "untracked_or_in_progress_code" in content
    assert "target_state_design" in content
    assert "Only `stable_existing_convention`, `stable_positive_shape`, `repository_rule`, and confirmed user decisions" in content
    assert "Required evidence delegation when classification is unsafe" in content
    assert "Use `codebase-scout` for code facts" in content
    assert "repository/document scout" in content
    assert "Conflict and user-decision gate" in content
    assert "promotion` conflict" in content
    assert "authority` conflict" in content
    assert "legacy` conflict" in content
def test_positive_case_resources_are_packaged():
    positive_cases = resources.files("codeloom.quality_cases.positive")

    for case_name in ("java-spring-mybatis.md", "python-fastapi.md", "react-next.md", "go-http.md"):
        content = positive_cases.joinpath(case_name).read_text(encoding="utf-8")
        assert "Positive Code Shape" in content
        assert "What Not To Copy Blindly" in content


def test_java_spring_positive_case_carries_stack_specific_verification_guidance():
    content = resources.files("codeloom.quality_cases.positive").joinpath("java-spring-mybatis.md").read_text(encoding="utf-8")

    assert "Verification Evidence Shape" in content
    assert "legacy Spring/MyBatis/XML modules" in content
    assert "mapper XML/static SQL inspection" in content
    assert "broad Spring `ApplicationContext` test" in content
    assert "mark runtime/page/API behavior as not end-to-end verified" in content

def test_java_spring_positive_case_carries_defensive_code_thresholds():
    content = resources.files("codeloom.quality_cases.positive").joinpath("java-spring-mybatis.md").read_text(encoding="utf-8")

    assert "Defensive Code Threshold" in content
    assert "defensive null checks" in content
    assert "nullable database columns" in content
    assert "legacy dirty data" in content
    assert "fallback normalization" in content
    assert "compatibility shims" in content
    assert "impossible states" in content
    assert "Context" in content
    assert "Assembler" in content
    assert "Wrapper" in content