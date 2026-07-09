from __future__ import annotations

from codeloom.kernel.artifacts import parse_tasks
from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import init_repo, run_stage, write_project_config


def test_failed_verify_lane_can_retry_same_task(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")
    write_project_config(repo, 'python -c "raise SystemExit(1)"')

    failed = run_stage(repo, "do", task_id="T2")
    assert failed.status == "failed"
    assert failed.recommended_next == "/loom-do T2"

    write_project_config(repo, 'python -c "raise SystemExit(0)"')
    retried = run_stage(repo, "do", task_id="T2")
    assert retried.status == "ok"
    assert retried.recommended_next == "/loom-ship"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    findings = store.findings(int(session["id"]))
    assert [finding for finding in findings if finding["kind"] == "verification_failure" and finding["status"] == "open"] == []


def test_changed_task_definition_creates_new_attempt_without_rewriting_old_attempt(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        "# Tasks\n\n"
        "- [ ] T1: Implement current CodeLoom requirement\n"
        "  - Lane: build\n"
        "  - Revision: 2\n\n"
        "- [ ] T2: Verify current CodeLoom requirement\n"
        "  - Lane: verify\n",
        encoding="utf-8",
    )
    response = run_stage(repo, "do", task_id="T1")

    assert response.status == "ok"
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert [attempt["status"] for attempt in attempts] == ["implemented", "implemented"]


def test_task_notes_change_does_not_create_new_attempt(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("- [ ] T2:", "  - Notes: expanded human context only\n\n- [ ] T2:", 1),
        encoding="utf-8",
    )
    response = run_stage(repo, "do", task_id="T1")

    assert response.status == "ok"
    assert response.recommended_next == "/loom-do T2"
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    t1_attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert [attempt["status"] for attempt in t1_attempts] == ["implemented"]


def test_task_notes_revision_metadata_does_not_create_new_attempt(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8")
        + "\n\n## 6. Task Notes\n\n### T1: Implement current CodeLoom requirement\n\n- Revision: 9\n- Notes: human-only context\n",
        encoding="utf-8",
    )
    response = run_stage(repo, "do", task_id="T1")

    assert response.status == "ok"
    assert response.recommended_next == "/loom-do T2"
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    t1_attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert [attempt["status"] for attempt in t1_attempts] == ["implemented"]


def test_ship_does_not_supersede_stale_attempts_after_task_definition_change(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")
    write_project_config(repo, test_command="python --version")
    run_stage(repo, "do", task_id="T2")

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("T1: Implement current CodeLoom requirement", "T1: Implement changed CodeLoom requirement", 1),
        encoding="utf-8",
    )
    ship = run_stage(repo, "ship")

    assert ship.status == "blocked"
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    t1_attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert [attempt["status"] for attempt in t1_attempts] == ["implemented"]

def test_removed_task_does_not_rewrite_old_attempt_when_other_task_runs(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")

    tasks_path = repo / "specs" / "master" / "tasks.md"
    original_tasks = parse_tasks(tasks_path.read_text(encoding="utf-8"))
    assert original_tasks[0].task_id == "T1"
    tasks_path.write_text("# Tasks\n\n- [ ] T2: Verify current CodeLoom requirement\n", encoding="utf-8")
    write_project_config(repo, test_command="python --version")
    response = run_stage(repo, "do")

    assert response.status == "ok"
    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    t1_attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert [attempt["status"] for attempt in t1_attempts] == ["implemented"]
