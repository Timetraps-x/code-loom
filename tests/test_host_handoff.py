from __future__ import annotations

from tests.helpers import init_repo, run_stage


def write_artifact(repo, branch_slug: str, name: str, content: str):
    artifact_dir = repo / "specs" / branch_slug
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / name
    artifact.write_text(content, encoding="utf-8")
    return artifact


def test_stage_registers_final_artifact_file(tmp_path):
    repo = init_repo(tmp_path)
    content = "# Spec\n\n## Requirement\nHost generated artifact.\n"
    artifact = write_artifact(repo, "master", "spec.md", content)

    response = run_stage(repo, "spec", artifact_file=str(artifact))

    assert response.status == "ok"
    assert repo.joinpath("specs", "master", "spec.md").read_text(encoding="utf-8") == content
    assert artifact.exists()


def test_artifact_file_under_runs_root_fails(tmp_path):
    repo = init_repo(tmp_path)
    wrong_artifact = repo / ".loom" / "runs" / "wrong_artifact-spec.md"
    wrong_artifact.write_text("# Spec\n\n## Requirement\nWrong artifact location.\n", encoding="utf-8")

    response = run_stage(repo, "spec", artifact_file=str(wrong_artifact))

    assert response.status == "failed"
    assert response.errors == ["invalid_artifact_file_location"]
    assert not repo.joinpath("specs", "master", "spec.md").exists()


def test_artifact_file_wrong_stage_path_fails(tmp_path):
    repo = init_repo(tmp_path)
    artifact = write_artifact(repo, "master", "plan.md", "# Plan\n\nWrong stage artifact.\n")

    response = run_stage(repo, "spec", artifact_file=str(artifact))

    assert response.status == "failed"
    assert response.errors == ["invalid_artifact_file_location"]
    assert not repo.joinpath("specs", "master", "spec.md").exists()


def test_missing_artifact_file_fails_explicitly(tmp_path):
    repo = init_repo(tmp_path)

    response = run_stage(repo, "spec", artifact_file=str(repo / "specs" / "master" / "spec.md"))

    assert response.status == "failed"
    assert response.errors == ["missing_artifact_file"]


def test_tasks_artifact_file_requires_parseable_tasks(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    artifact = write_artifact(repo, "master", "tasks.md", "# Tasks\n\n## Task 1\nDo the thing.\n")

    response = run_stage(repo, "tasks", artifact_file=str(artifact))

    assert response.status == "failed"
    assert response.errors == ["invalid_tasks_format"]
    assert artifact.exists()
