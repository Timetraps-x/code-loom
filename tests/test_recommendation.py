from __future__ import annotations

from tests.helpers import init_repo, run_stage


def test_recommendation_moves_task_by_task(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    tasks = run_stage(repo, "tasks")

    assert tasks.recommended_next == "/loom:do T1"
    assert tasks.recommended_task_id == "T1"

    first = run_stage(repo, "do")
    assert first.recommended_next == "/loom:do T2"
    assert first.recommended_task_id == "T2"

    second = run_stage(repo, "do")
    assert second.recommended_next == "/loom:ship"
    assert second.recommended_task_id is None
