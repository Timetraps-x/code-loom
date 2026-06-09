from __future__ import annotations

from codeloom.app.init_project import init_project


def test_init_project_creates_config_runtime_and_skills(tmp_path):
    created, project_path = init_project(tmp_path)

    assert created is True
    assert project_path.endswith("project.yml")
    assert tmp_path.joinpath("project.yml").exists()
    assert tmp_path.joinpath(".loom", "loom.db").exists()
    assert tmp_path.joinpath(".loom", "runs").exists()
    assert tmp_path.joinpath(".claude", "skills", "loom", "skills", "spec", "SKILL.md").exists()
