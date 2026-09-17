from __future__ import annotations

import sqlite3

import pytest

from codeloom.app.status import get_status
from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import init_repo, run_stage, write_project_config
from tests.test_stage_flow import (
    _complete_build_with_passed_review,
    _prepare_host_repo,
    _register_host_artifacts,
    _write_host_spec,
)


def test_artifact_registration_is_append_only_and_restores_latest_content(tmp_path):
    repo = init_repo(tmp_path)
    store = SQLiteStore(repo)
    session = store.get_or_create_branch_session("master", "master", "specs")
    session_id = int(session["id"])

    first = store.register_artifact_if_inputs_current(session_id, "spec", "specs/master/spec.md", "spec-p1", None)
    second = store.register_artifact_if_inputs_current(session_id, "spec", "specs/master/spec.md", "spec-p2", None)
    third = store.register_artifact_if_inputs_current(session_id, "spec", "specs/master/spec.md", "spec-p1", None)

    assert [first["revision_id"], second["revision_id"], third["revision_id"]] == sorted({
        first["revision_id"], second["revision_id"], third["revision_id"]
    })
    assert store.latest_artifact_revision(session_id, "spec")["content_hash"] == "spec-p1"
    assert store.branch_session("master")["active_spec_hash"] == "spec-p1"
    with store.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM artifact_revisions WHERE branch_session_id = ? AND kind = 'spec'",
            (session_id,),
        ).fetchone()[0] == 3


def test_stale_artifact_registration_has_no_partial_writes_and_fresh_retry_uses_latest_parent(tmp_path):
    repo = init_repo(tmp_path)
    store = SQLiteStore(repo)
    session = store.get_or_create_branch_session("master", "master", "specs")
    session_id = int(session["id"])
    store.register_artifact_if_inputs_current(session_id, "spec", "specs/master/spec.md", "spec-v1", None)
    frozen = store.artifact_input_snapshot(session_id, "plan")
    frozen_token = store.artifact_input_token(frozen)
    store.update_branch_session(
        session_id,
        continuation_source_stage="plan",
        continuation_stage="plan",
        continuation_reason="reauthor plan",
    )
    store.register_artifact_if_inputs_current(session_id, "spec", "specs/master/spec.md", "spec-v2", None)

    rejected = store.register_artifact_if_inputs_current(
        session_id,
        "plan",
        "specs/master/plan.md",
        "plan-stale",
        frozen_token,
    )

    assert rejected["status"] == "inputs_changed"
    assert store.latest_artifact_revision(session_id, "plan") is None
    unchanged = store.branch_session("master")
    assert unchanged["active_plan_hash"] is None
    assert unchanged["continuation_stage"] == "plan"

    fresh = store.artifact_input_snapshot(session_id, "plan")
    accepted = store.register_artifact_if_inputs_current(
        session_id,
        "plan",
        "specs/master/plan.md",
        "plan-current",
        store.artifact_input_token(fresh),
    )

    assert accepted["status"] == "registered"
    assert accepted["based_on_spec_hash"] == "spec-v2"
    assert store.latest_artifact_revision(session_id, "plan")["based_on_spec_hash"] == "spec-v2"
    assert store.branch_session("master")["continuation_stage"] is None


@pytest.mark.parametrize("working_copy", ["missing", "malformed", "stale"])
def test_existing_attempt_recovers_from_frozen_packet_when_tasks_working_copy_changes(tmp_path, working_copy):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    tasks_path = repo / "specs" / "master" / "tasks.md"
    if working_copy == "missing":
        tasks_path.unlink()
    elif working_copy == "malformed":
        tasks_path.write_text("# Tasks\n\n- [ ] T1: broken\n  - Lane: review\n", encoding="utf-8")
    else:
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8") + "\nUnregistered edit.\n", encoding="utf-8")

    resumed = run_stage(repo, "do", task_id="T1", action="begin")
    completed = _complete_build_with_passed_review(repo, begin.extras["attempt_id"])

    assert resumed.status == "ok"
    assert resumed.extras["attempt_id"] == begin.extras["attempt_id"]
    assert resumed.extras["task_packet"] == begin.extras["task_packet"]
    assert completed.status == "ok"
    assert SQLiteStore(repo).attempt(int(begin.extras["attempt_id"]))["status"] == "implemented"


def test_corrupt_packet_exposes_unlock_and_unlock_preserves_evidence(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    with SQLiteStore(repo).connect() as conn:
        conn.execute("UPDATE attempts SET task_packet_json = '{}' WHERE id = ?", (attempt_id,))
    (repo / "specs" / "master" / "tasks.md").unlink()
    store = SQLiteStore(repo)
    refs_before = store.runtime_refs(attempt_id)

    blocked = run_stage(repo, "do", task_id="T1", action="begin")
    unlocked = run_stage(repo, "do", action="unlock", attempt_id=str(attempt_id))

    assert blocked.status == "blocked"
    assert blocked.errors == ["task_packet_integrity_error"]
    assert blocked.extras["unlock_command"].endswith(f"action=unlock --arg attempt_id={attempt_id}")
    assert unlocked.status == "ok"
    assert unlocked.extras["previous_status"] == "running"
    assert unlocked.extras["status"] == "blocked"
    assert store.runtime_refs(attempt_id) == refs_before
    assert store.attempt(attempt_id)["task_packet_json"] == "{}"
    assert "no completion asserted" in store.attempt(attempt_id)["summary"]

    repeated = run_stage(repo, "do", action="unlock", attempt_id=str(attempt_id))
    assert repeated.status == "noop"
    assert repeated.errors == []
    new_attempt = run_stage(repo, "do", task_id="T1", action="begin")
    assert new_attempt.status == "noop"
    assert new_attempt.errors == ["do_inputs_not_authoritative"]
    assert new_attempt.recommended_next == "/loom-tasks"


def test_unlock_uses_blocked_do_continuation_before_artifact_parsing(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    routed = run_stage(
        repo,
        "do",
        action="route",
        attempt_id=str(attempt_id),
        target_stage="plan",
        reason="task boundary was wrong",
    )
    assert routed.status == "ok"
    packet_before = SQLiteStore(repo).attempt(attempt_id)["task_packet_json"]
    for name in ("spec.md", "plan.md", "tasks.md"):
        (repo / "specs" / "master" / name).unlink()

    unlocked = run_stage(repo, "do", action="unlock")

    assert unlocked.status == "ok"
    assert unlocked.extras["attempt_id"] == attempt_id
    assert unlocked.extras["continuation_cleared"] is True
    store = SQLiteStore(repo)
    assert store.attempt(attempt_id)["status"] == "blocked"
    assert store.branch_session("master")["continuation_stage"] is None
    assert store.attempt(attempt_id)["task_packet_json"] == packet_before


def test_unlock_rejects_cross_session_attempt_and_handles_completing_attempt(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    store = SQLiteStore(repo)
    store.update_attempt(attempt_id, "completing", "completion was interrupted")
    _register_host_artifacts(repo, "other")

    mismatch = run_stage(repo, "do", branch="other", action="unlock", attempt_id=str(attempt_id))
    assert mismatch.status == "failed"
    assert mismatch.errors == ["unlock_session_mismatch"]
    assert store.attempt(attempt_id)["status"] == "completing"

    unlocked = run_stage(repo, "do", action="unlock", attempt_id=str(attempt_id))
    assert unlocked.status == "ok"
    attempt = store.attempt(attempt_id)
    assert attempt["status"] == "blocked"
    assert "completion was interrupted" in attempt["summary"]
    assert "no completion asserted" in attempt["summary"]


def test_status_derives_missing_unregistered_current_and_stale_without_registration(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    run_stage(repo, "spec")
    assert get_status(repo, "master")["artifacts"]["spec"]["state"] == "missing"

    _write_host_spec(repo)
    unregistered = get_status(repo, "master")
    assert unregistered["artifacts"]["spec"]["state"] == "unregistered"
    assert unregistered["artifacts"]["spec"]["registered_revision_id"] is None

    registered = run_stage(repo, "spec", artifact_file="specs/master/spec.md")
    assert registered.status == "ok"
    assert get_status(repo, "master")["artifacts"]["spec"]["state"] == "current"

    spec_path = repo / "specs" / "master" / "spec.md"
    spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\nUnregistered change.\n", encoding="utf-8")
    stale = get_status(repo, "master")
    assert stale["artifacts"]["spec"]["state"] == "stale"
    assert stale["artifacts"]["spec"]["recovery_command"] == "/loom-spec"


def test_packet_write_failure_does_not_create_active_attempt(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    with SQLiteStore(repo).connect() as conn:
        conn.execute("""CREATE TRIGGER reject_packet BEFORE INSERT ON attempts
                      WHEN NEW.task_packet_json IS NOT NULL
                      BEGIN SELECT RAISE(ABORT, 'packet storage unavailable'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="packet storage unavailable"):
        run_stage(repo, "do", task_id="T1", action="begin")

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    assert store.attempts(int(session["id"])) == []

def test_explicit_manual_completion_unblocks_next_task(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    store = SQLiteStore(repo)
    refs_before = store.runtime_refs(attempt_id)

    completed = run_stage(
        repo,
        "do",
        action="unlock",
        attempt_id=str(attempt_id),
        status="implemented",
        summary="T1 was completed manually outside the host flow",
    )

    assert completed.status == "ok"
    assert completed.extras["unlock_result"] == "completed"
    assert completed.extras["previous_status"] == "running"
    assert completed.extras["status"] == "implemented"
    assert completed.recommended_next == "/loom-do T2"
    attempt = store.attempt(attempt_id)
    assert attempt["status"] == "implemented"
    assert "completed manually outside the host flow" in attempt["summary"]
    assert store.runtime_refs(attempt_id) == refs_before

    next_task = run_stage(repo, "do", task_id="T2", action="begin")
    assert next_task.status == "ok"
    assert next_task.extras["task_id"] == "T2"


def test_manual_completion_requires_explicit_attempt_and_terminal_status(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    missing_attempt = run_stage(repo, "do", action="unlock", status="implemented")
    invalid_status = run_stage(repo, "do", action="unlock", attempt_id="1", status="done")

    assert missing_attempt.status == "failed"
    assert missing_attempt.errors == ["missing_attempt_id"]
    assert invalid_status.status == "failed"
    assert invalid_status.errors == ["invalid_unlock_status"]