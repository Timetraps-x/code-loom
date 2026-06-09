from __future__ import annotations

from tests.helpers import init_repo, run_stage


def test_stage_uses_content_file_candidate(tmp_path):
    repo = init_repo(tmp_path)
    candidate = repo / "candidate-spec.md"
    candidate.write_text("# Spec\n\n## Requirement\nHost generated candidate.\n", encoding="utf-8")

    response = run_stage(repo, "spec", content_file=str(candidate))

    assert response.status == "ok"
    assert repo.joinpath("specs", "master", "spec.md").read_text(encoding="utf-8") == candidate.read_text(encoding="utf-8")


def test_missing_content_file_fails_explicitly(tmp_path):
    repo = init_repo(tmp_path)

    response = run_stage(repo, "spec", content_file=str(repo / "missing.md"))

    assert response.status == "failed"
    assert response.errors == ["missing_content_file"]


def test_tasks_content_file_requires_parseable_tasks(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    candidate = repo / "candidate-tasks.md"
    candidate.write_text("# Tasks\n\n## Task 1\nDo the thing.\n", encoding="utf-8")

    response = run_stage(repo, "tasks", content_file=str(candidate))

    assert response.status == "failed"
    assert response.errors == ["invalid_tasks_format"]
    assert not repo.joinpath("specs", "master", "tasks.md").exists()
