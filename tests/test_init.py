from __future__ import annotations

from codeloom.app.init_project import init_project


def test_init_project_creates_config_runtime_and_skills(tmp_path):
    created, project_path = init_project(tmp_path)

    assert created is True
    assert project_path.endswith("project.yml")
    assert tmp_path.joinpath("project.yml").exists()
    assert tmp_path.joinpath(".loom", "loom.db").exists()
    assert tmp_path.joinpath(".loom", "runs").exists()
    skill_path = tmp_path.joinpath(".claude", "skills", "loom-spec", "SKILL.md")
    assert skill_path.exists()
    content = skill_path.read_text(encoding="utf-8")
    assert "name: loom-spec" in content
    assert "user-invocable: true" in content
    assert "disable-model-invocation: false" in content


def test_init_project_without_claude_code_skips_claude_skills(tmp_path):
    init_project(tmp_path, integrations={"codex"})

    assert not tmp_path.joinpath(".claude", "skills", "loom-spec", "SKILL.md").exists()
