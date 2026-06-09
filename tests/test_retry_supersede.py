from __future__ import annotations

from codeloom.kernel.artifacts import parse_tasks
from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import init_repo, run_stage, write_project_config


def test_failed_verification_can_retry_same_task(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    write_project_config(repo, 'python -c "raise SystemExit(1)"')

    failed = run_stage(repo, "do", task_id="T1")
    assert failed.status == "failed"
    assert failed.recommended_next == "/loom-do T1"

    write_project_config(repo, 'python -c "raise SystemExit(0)"')
    retried = run_stage(repo, "do", task_id="T1")
    assert retried.status == "ok"
    assert retried.recommended_next == "/loom-do T2"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    findings = store.findings(int(session["id"]))
    assert [finding for finding in findings if finding["kind"] == "verification_failure" and finding["status"] == "open"] == []


def test_changed_task_definition_supersedes_old_attempt(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text("# Tasks\n\n- [ ] T1: Implement changed requirement\n- [ ] T2: Verify current CodeLoom requirement\n", encoding="utf-8")
    response = run_stage(repo, "do", task_id="T1")

    assert response.status == "ok"
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert attempts[0]["status"] == "superseded"
    assert attempts[-1]["status"] == "verified"


def test_removed_task_supersedes_old_attempt(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")

    tasks_path = repo / "specs" / "master" / "tasks.md"
    original_tasks = parse_tasks(tasks_path.read_text(encoding="utf-8"))
    assert original_tasks[0].task_id == "T1"
    tasks_path.write_text("# Tasks\n\n- [ ] T2: Verify current CodeLoom requirement\n", encoding="utf-8")
    response = run_stage(repo, "do")

    assert response.status == "ok"
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    t1_attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert t1_attempts[-1]["status"] == "superseded"
