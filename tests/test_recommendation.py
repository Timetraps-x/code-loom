from __future__ import annotations

from codeloom.cli.render import render_kernel_response

from tests.helpers import init_repo, run_stage, write_project_config


def test_recommendation_moves_task_by_task(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, test_command="python --version")
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    tasks = run_stage(repo, "tasks")

    assert tasks.recommended_next == "/loom-do T1"
    assert tasks.recommended_task_id == "T1"
    assert tasks.recommended_task_title == "Implement current CodeLoom requirement"
    assert "Recommended task: T1-Implement current CodeLoom requirement" in render_kernel_response(tasks)

    first = run_stage(repo, "do")
    assert first.recommended_next == "/loom-do T2"
    assert first.recommended_task_id == "T2"
    assert first.recommended_task_title == "Verify current CodeLoom requirement"
    assert "Recommended task: T2-Verify current CodeLoom requirement" in render_kernel_response(first)

    second = run_stage(repo, "do")
    assert second.recommended_next == "/loom-ship"
    assert second.recommended_task_id is None
    assert second.recommended_task_title is None
