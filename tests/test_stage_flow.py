from __future__ import annotations

import subprocess

from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import init_repo, run_stage, write_project_config


def _prepare_host_repo(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    return repo

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


def test_claude_code_host_runtime_begin_complete_flow(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    one_shot = run_stage(repo, "do", task_id="T1")
    assert one_shot.status == "blocked"
    assert one_shot.errors == ["host_runtime_requires_begin_complete"]
    assert one_shot.extras["main_agent"] == "builder"

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert begin.status == "ok"
    assert begin.extras["task_id"] == "T1"
    assert begin.extras["lane"] == "build"
    assert begin.extras["main_agent"] == "builder"
    assert begin.extras["reviewer_agent"] == "code-reviewer"
    attempt_id = str(begin.extras["attempt_id"])

    repeated_begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert repeated_begin.extras["attempt_id"] == begin.extras["attempt_id"]

    complete_build = run_stage(repo, "do", action="complete", attempt_id=attempt_id, status="implemented", summary="built T1")
    assert complete_build.status == "ok"
    assert complete_build.recommended_next == "/loom-do T2"
    assert complete_build.recommended_task_id == "T2"

    begin_verify = run_stage(repo, "do", task_id="T2", action="begin")
    assert begin_verify.extras["lane"] == "verify"
    assert begin_verify.extras["main_agent"] == "verifier"
    verify_attempt_id = str(begin_verify.extras["attempt_id"])

    complete_verify = run_stage(repo, "do", action="complete", attempt_id=verify_attempt_id, status="verified", summary="verified T2")
    assert complete_verify.status == "ok"
    assert complete_verify.recommended_next == "/loom-ship"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    assert [(attempt["task_id"], attempt["status"]) for attempt in attempts] == [("T1", "implemented"), ("T2", "verified")]


def test_claude_code_host_runtime_rejects_bad_actions_and_attempt_ids(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    unsupported = run_stage(repo, "do", task_id="T1", action="cancel")
    assert unsupported.status == "failed"
    assert unsupported.errors == ["unsupported_do_action"]

    missing_attempt = run_stage(repo, "do", action="complete", status="implemented")
    assert missing_attempt.status == "failed"
    assert missing_attempt.errors == ["missing_attempt_id"]

    invalid_attempt = run_stage(repo, "do", action="complete", attempt_id="abc", status="implemented")
    assert invalid_attempt.status == "failed"
    assert invalid_attempt.errors == ["invalid_attempt_id"]

    not_found = run_stage(repo, "do", action="complete", attempt_id="9999", status="implemented")
    assert not_found.status == "failed"
    assert not_found.errors == ["attempt_not_found"]


def test_claude_code_host_runtime_rejects_wrong_lane_success_status(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    build_wrong = run_stage(repo, "do", action="complete", attempt_id=str(build_begin.extras["attempt_id"]), status="verified")
    assert build_wrong.status == "failed"
    assert build_wrong.errors == ["invalid_completion_status"]

    build_ok = run_stage(repo, "do", action="complete", attempt_id=str(build_begin.extras["attempt_id"]), status="implemented")
    assert build_ok.status == "ok"

    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")
    verify_wrong = run_stage(repo, "do", action="complete", attempt_id=str(verify_begin.extras["attempt_id"]), status="implemented")
    assert verify_wrong.status == "failed"
    assert verify_wrong.errors == ["invalid_completion_status"]


def test_claude_code_host_runtime_rejects_duplicate_complete(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = str(begin.extras["attempt_id"])
    first = run_stage(repo, "do", action="complete", attempt_id=attempt_id, status="implemented")
    assert first.status == "ok"

    duplicate = run_stage(repo, "do", action="complete", attempt_id=attempt_id, status="implemented")
    assert duplicate.status == "failed"
    assert duplicate.errors == ["attempt_not_running"]


def test_claude_code_host_runtime_blocked_completion_creates_blocking_finding(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    blocked = run_stage(repo, "do", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="blocked", summary="needs upstream task revision")
    assert blocked.status == "blocked"
    assert blocked.recommended_next == "/loom-do T1"

    next_do = run_stage(repo, "do", task_id="T1")
    assert next_do.status == "blocked"
    assert next_do.findings[0]["kind"] == "execution_blocked"


def test_claude_code_host_runtime_rejects_cross_branch_attempt_completion(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")

    run_stage(repo, "spec", branch="other")
    run_stage(repo, "plan", branch="other")
    run_stage(repo, "tasks", branch="other")
    mismatch = run_stage(repo, "do", branch="other", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="implemented")

    assert mismatch.status == "failed"
    assert mismatch.errors == ["attempt_session_mismatch"]


def test_claude_code_host_runtime_rejects_completion_after_task_drift(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("T1:", "T1: changed ", 1), encoding="utf-8")

    drifted = run_stage(repo, "do", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="implemented")

    assert drifted.status == "failed"
    assert drifted.errors == ["attempt_not_running"]


def test_claude_code_host_runtime_diff_lists_untracked_files_without_content(tmp_path, monkeypatch):
    repo = _prepare_host_repo(tmp_path)
    untracked_file = repo / "untracked-note.txt"
    untracked_file.write_text("SENTINEL_UNTRACKED_CONTENT", encoding="utf-8")

    def fake_run(command, cwd=None, capture_output=False, text=False):
        if command == ["git", "diff", "--"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command == ["git", "status", "--short"]:
            return subprocess.CompletedProcess(command, 0, "?? untracked-note.txt\n", "")
        raise AssertionError(command)

    monkeypatch.setattr("codeloom.app.stages.subprocess.run", fake_run)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    completed = run_stage(repo, "do", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="implemented")
    assert completed.status == "ok"

    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    diff_ref = next(ref for ref in refs if ref["kind"] == "diff")
    diff_content = repo.joinpath(diff_ref["path"]).read_text(encoding="utf-8")
    assert "untracked-note.txt" in diff_content
    assert "SENTINEL_UNTRACKED_CONTENT" not in diff_content


def test_claude_code_host_runtime_redoes_task_after_fingerprint_change(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    first_begin = run_stage(repo, "do", task_id="T1", action="begin")
    first_attempt_id = first_begin.extras["attempt_id"]
    first_complete = run_stage(repo, "do", action="complete", attempt_id=str(first_attempt_id), status="implemented")
    assert first_complete.status == "ok"

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("T1:", "T1: changed ", 1),
        encoding="utf-8",
    )

    second_begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert second_begin.status == "ok"
    assert second_begin.extras["attempt_id"] != first_attempt_id
    assert second_begin.extras["attempt_no"] == 2

    second_complete = run_stage(repo, "do", action="complete", attempt_id=str(second_begin.extras["attempt_id"]), status="implemented")
    assert second_complete.status == "ok"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    t1_attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert [attempt["status"] for attempt in t1_attempts] == ["superseded", "implemented"]
