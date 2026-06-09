from __future__ import annotations

from codeloom.kernel.artifacts import parse_tasks
from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import init_repo, run_stage


def test_blocking_finding_suggested_do_resolves_to_task_next(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")

    tasks_content = repo.joinpath("specs", "master", "tasks.md").read_text(encoding="utf-8")
    task = parse_tasks(tasks_content)[0]
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    session_id = int(session["id"])
    attempt_id = store.create_attempt(session_id, task.task_id, 1, "mock", None, None, None, task.fingerprint)
    store.update_attempt(attempt_id, "failed", "manual failed attempt")
    store.add_finding(session_id, attempt_id, "plan_gap", "blocking", "plan is missing detail", "/loom:do")

    response = run_stage(repo, "do")

    assert response.status == "blocked"
    assert response.recommended_next == "/loom:do T1"
    assert response.recommended_task_id == "T1"
