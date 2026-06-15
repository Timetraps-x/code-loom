from __future__ import annotations

from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import init_repo, run_stage


def test_mock_stage_flow_reaches_ship(tmp_path):
    repo = init_repo(tmp_path)

    assert run_stage(repo, "spec").recommended_next == "/loom-plan"
    assert run_stage(repo, "plan").recommended_next == "/loom-tasks"
    tasks_response = run_stage(repo, "tasks")
    assert tasks_response.recommended_next == "/loom-do T1"
    assert tasks_response.recommended_task_id == "T1"

    first = run_stage(repo, "do", task_id="T1")
    assert first.status == "ok"
    assert first.recommended_next == "/loom-do T2"
    assert first.recommended_task_id == "T2"

    second = run_stage(repo, "do", task_id="T2")
    assert second.status == "ok"
    assert second.recommended_next == "/loom-ship"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    assert [(attempt["task_id"], attempt["status"]) for attempt in attempts] == [("T1", "implemented"), ("T2", "verified")]

    ship = run_stage(repo, "ship")
    assert ship.status == "ok"
    assert ship.recommended_next is None
    assert repo.joinpath("specs", "master", "release.md").exists()
