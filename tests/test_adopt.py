from __future__ import annotations

import json
from importlib import resources

from codeloom.app.constitution import constitution_status
from codeloom.app.init_project import init_project, load_project_config
from codeloom.cli.main import main


def test_adopt_rejects_seed_scaffold(tmp_path, capsys):
    init_project(tmp_path)

    exit_code = main(["adopt", "--cwd", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    config = load_project_config(tmp_path)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["errors"] == ["constitution_not_adopted"]
    assert payload["constitution"]["seeded"] is True
    assert payload["constitution"]["usable"] is False
    assert config.constitution_hash == ""


def test_adopt_registers_non_seed_constitution_hash(tmp_path, capsys):
    init_project(tmp_path)
    constitution_path = tmp_path / ".loom" / "constitution.md"
    constitution_path.write_text("# Project Constitution\n\n## Ownership\n\n- Services own durable workflow transitions.\n", encoding="utf-8")

    exit_code = main(["adopt", "--cwd", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    config = load_project_config(tmp_path)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["constitution"]["path"] == ".loom/constitution.md"
    assert payload["constitution"]["seeded"] is False
    assert payload["constitution"]["matches_registered"] is True
    assert payload["constitution"]["usable"] is True
    assert config.constitution_hash == payload["constitution"]["current_hash"]


def test_adopt_human_output_reports_seed_and_usable_state(tmp_path, capsys):
    init_project(tmp_path)
    constitution_path = tmp_path / ".loom" / "constitution.md"
    constitution_path.write_text("# Project Constitution\n\n- Services own workflow transitions.\n", encoding="utf-8")

    exit_code = main(["adopt", "--cwd", str(tmp_path)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Seeded: False" in output
    assert "Usable: True" in output


def test_constitution_drift_stays_unusable_until_reregistered(tmp_path, capsys):
    init_project(tmp_path)
    constitution_path = tmp_path / ".loom" / "constitution.md"
    constitution_path.write_text("# Project Constitution\n\n- Initial project rule.\n", encoding="utf-8")
    assert main(["adopt", "--cwd", str(tmp_path), "--json"]) == 0
    capsys.readouterr()
    registered_hash = load_project_config(tmp_path).constitution_hash

    constitution_path.write_text("# Project Constitution\n\n- Revised project rule.\n", encoding="utf-8")
    init_project(tmp_path)
    config = load_project_config(tmp_path)
    status = constitution_status(tmp_path, config.constitution_path, config.constitution_hash)

    assert config.constitution_hash == registered_hash
    assert status["registered"] is True
    assert status["matches_registered"] is False
    assert status["usable"] is False

    assert main(["adopt", "--cwd", str(tmp_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["constitution"]["usable"] is True
    assert payload["constitution"]["registered_hash"] != registered_hash


def test_adopt_registers_custom_path_under_loom(tmp_path, capsys):
    init_project(tmp_path)
    custom_path = tmp_path / ".loom" / "governance" / "engineering.md"
    custom_path.parent.mkdir(parents=True)
    custom_path.write_text("# Engineering Rules\n\n- Domain packages own exported identifiers.\n", encoding="utf-8")

    exit_code = main([
        "adopt",
        "--cwd",
        str(tmp_path),
        "--constitution",
        ".loom/governance/engineering.md",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)
    config = load_project_config(tmp_path)

    assert exit_code == 0
    assert payload["constitution"]["path"] == ".loom/governance/engineering.md"
    assert payload["constitution"]["usable"] is True
    assert config.constitution_path == ".loom/governance/engineering.md"


def test_adopt_requires_initialized_project_and_existing_constitution(tmp_path, capsys):
    exit_code = main(["adopt", "--cwd", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["errors"]


def test_constitution_template_is_an_unadopted_cross_language_seed():
    content = resources.files("codeloom.templates").joinpath("constitution-template.md").read_text(encoding="utf-8")

    assert "CODELOOM_CONSTITUTION_SEED" in content
    for heading in (
        "Code Placement and Ownership",
        "Business, Data, and State Flow Visibility",
        "Abstraction, Reuse, and Naming Thresholds",
        "Stack-Local Code Shape",
        "Change Risk Boundaries",
        "Rule Stability Boundary",
    ):
        assert heading in content
    assert "Record only project-specific" in content
    assert "Stack Profiles" not in content
    assert "Project Identity and Quality Baseline" not in content


def test_adopt_expert_separates_promotion_profile_and_suggestions():
    content = resources.files("codeloom.agents").joinpath("adopt-expert.md").read_text(encoding="utf-8")

    for expected in (
        "# Promotion Judgment",
        "**promote**",
        "**target-only**",
        "**non-propagation**",
        "**material conflict**",
        "# Project Profile",
        "Keep commands out of the constitution",
        "# CLAUDE.md Suggestions",
        "Never mix these suggestions into the constitution candidate",
        "# Optional Bounded Delegation",
        "Delegation is optional",
        "If no delegation channel is available, continue with bounded direct investigation",
        "Write in English by default",
        "downstream prompt surface",
    ):
        assert expected in content

    assert "SQLite" not in content
    assert "register_constitution" not in content
    assert "workflow state" not in content
    assert "temporary Claude Code child agent before writing" not in content


def test_adopt_quality_cases_are_packaged():
    cases = resources.files("codeloom.quality_cases.adopt")

    for case_name, expected in {
        "mature-single-stack.md": "Do not emit generic advice",
        "legacy-majority.md": "Do not promote the numerically dominant",
        "current-branch-target.md": "Classify the proposed module as target-only",
        "multi-stack.md": "Produce one shared constitution",
        "positive-case-conflict.md": "interpretation aid only",
    }.items():
        assert expected in cases.joinpath(case_name).read_text(encoding="utf-8")


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

    for expected in (
        "Defensive Code Threshold",
        "defensive null checks",
        "nullable database columns",
        "legacy dirty data",
        "fallback normalization",
        "compatibility shims",
        "impossible states",
        "Context",
        "Assembler",
        "Wrapper",
    ):
        assert expected in content
