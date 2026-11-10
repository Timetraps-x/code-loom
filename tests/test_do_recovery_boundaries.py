from __future__ import annotations

import json
import sqlite3

import pytest

from codeloom.app import stages
from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import run_stage
from tests.test_do_serial_retry import _complete_verify
from tests.test_stage_flow import _complete_build_with_passed_review, _prepare_host_repo


@pytest.fixture
def claimed_build(tmp_path, monkeypatch):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])

    def interrupted(*args, **kwargs):
        raise RuntimeError("interrupted after claim")

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteStore, "finalize_attempt_completion", interrupted)
        with pytest.raises(RuntimeError, match="after claim"):
            _complete_build_with_passed_review(repo, attempt_id, summary="accepted build", stdout="original\n")
    store = SQLiteStore(repo)
    assert store.attempt(attempt_id)["status"] == "completing"
    return repo, store, attempt_id


@pytest.mark.parametrize("resubmit", [False, True])
@pytest.mark.parametrize("change", ["source", "snapshot_unavailable"])
def test_claimed_build_recovers_frozen_result(claimed_build, monkeypatch, change, resubmit):
    repo, store, attempt_id = claimed_build
    before = store.attempt(attempt_id)
    seals = store.sealed_changes_for_attempt(attempt_id)
    review = store.review_for_seal(attempt_id, before["latest_seal_revision"])
    if change == "source":
        (repo / "after_claim.py").write_text("value = 2\n", encoding="utf-8")
    else:
        def unavailable(*args):
            raise AssertionError("Recovery must not capture the current working tree")
        monkeypatch.setattr(stages, "_capture_attempt_snapshot", unavailable)
    begin = run_stage(repo, "do", action="begin")
    assert begin.extras["host_recovery"]["internal_action"] == "resume_complete"
    args = {"status": "implemented", "summary": "accepted build", "stdout": "original\n"} if resubmit else {}
    completed = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id), **args)
    assert completed.status == "ok"
    assert store.attempt(attempt_id)["completion_token"] == before["completion_token"]
    assert store.sealed_changes_for_attempt(attempt_id) == seals
    assert store.review_for_seal(attempt_id, before["latest_seal_revision"]) == review
    duplicate = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert duplicate.extras["idempotent"] is True
    assert len([ref for ref in store.runtime_refs(attempt_id) if ref["kind"] == "stdout"]) == 1
    verify = run_stage(repo, "do", action="begin", task_id="T2")
    assert _complete_verify(repo, verify.extras["attempt_id"]).status == "ok"
    assert run_stage(repo, "ship").extras["ship_packet"]["status"] == "ready"


def test_claimed_build_rejects_new_candidate_before_writing_logs(claimed_build):
    repo, store, attempt_id = claimed_build
    before = store.attempt(attempt_id)
    files = set((repo / ".loom/runs/master").iterdir())
    conflict = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id),
                         status="blocked", summary="different", stdout="unaccepted output")
    assert conflict.errors == ["completion_conflict"]
    assert set((repo / ".loom/runs/master").iterdir()) == files
    assert store.attempt(attempt_id)["completion_candidate_json"] == before["completion_candidate_json"]
    assert run_stage(repo, "do", action="complete", attempt_id=str(attempt_id)).status == "ok"


@pytest.mark.parametrize("damage", ["seal", "review", "candidate"])
def test_claimed_evidence_damage_offers_executable_recovery(claimed_build, damage):
    repo, store, attempt_id = claimed_build
    with store.connect() as conn:
        if damage == "seal":
            conn.execute("UPDATE sealed_changes SET manifest_json = '{}' WHERE attempt_id = ?", (attempt_id,))
        elif damage == "review":
            conn.execute("UPDATE review_records SET summary_json = '{}' WHERE attempt_id = ?", (attempt_id,))
        else:
            conn.execute("UPDATE attempts SET completion_candidate_json = '{}' WHERE id = ?", (attempt_id,))
    blocked = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert blocked.status == "blocked"
    assert "action=unlock" in blocked.extras["unlock_command"]
    assert blocked.extras.get("host_recovery", {}).get("internal_action") != "seal_changes"
    if damage == "candidate":
        assert run_stage(repo, "do", action="complete", attempt_id=str(attempt_id),
                         status="implemented", summary="accepted build", stdout="original\n").status == "ok"
    else:
        assert store.attempt(attempt_id)["status"] == "completing"
        assert run_stage(repo, "do", action="unlock", attempt_id=str(attempt_id)).status == "ok"
        restarted = run_stage(repo, "do", action="begin", task_id="T1")
        assert restarted.extras["attempt_no"] == 2
        assert _complete_build_with_passed_review(repo, restarted.extras["attempt_id"]).status == "ok"


@pytest.mark.parametrize("boundary", ["record", "attach"])
def test_late_seal_cannot_modify_claimed_evidence(tmp_path, monkeypatch, boundary):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    assert run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id)).status == "ok"
    assert run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                     seal_revision="1", status="pass", review_summary="accepted").status == "ok"
    store = SQLiteStore(repo)
    before = store.sealed_changes_for_attempt(attempt_id)
    method = "record_sealed_changes" if boundary == "record" else "attach_sealed_changes"
    original = getattr(SQLiteStore, method)

    def interrupted(*args, **kwargs):
        raise RuntimeError("interrupted after claim")

    def interleaved(instance, *args, **kwargs):
        with monkeypatch.context() as patch:
            patch.setattr(SQLiteStore, "finalize_attempt_completion", interrupted)
            with pytest.raises(RuntimeError, match="after claim"):
                run_stage(repo, "do", action="complete", attempt_id=str(attempt_id), status="implemented", summary="accepted")
        return original(instance, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteStore, method, interleaved)
        late = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert late.status == "noop"
    assert late.extras["host_recovery"]["command_args"] == {"action": "begin", "task_id": "T1"}
    assert store.attempt(attempt_id)["status"] == "completing"
    assert store.sealed_changes_for_attempt(attempt_id) == before
    with pytest.raises(ValueError, match="attempt_not_running"):
        store.record_sealed_changes(attempt_id, "late-tree")
    assert not store.attach_sealed_changes(attempt_id, 1, store.attempt(attempt_id)["latest_sealed_tree"], None, "changed", "{}")
    assert run_stage(repo, "do", action="complete", attempt_id=str(attempt_id)).status == "ok"


def test_unlock_wins_over_late_finalize(claimed_build, monkeypatch):
    repo, store, attempt_id = claimed_build
    original = SQLiteStore.finalize_attempt_completion

    def interleaved(instance, *args, **kwargs):
        assert run_stage(repo, "do", action="unlock", attempt_id=str(attempt_id)).status == "ok"
        return original(instance, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteStore, "finalize_attempt_completion", interleaved)
        late = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert late.errors == ["completion_conflict"]
    assert store.attempt(attempt_id)["status"] == "blocked"
    assert run_stage(repo, "do", action="begin", task_id="T1").extras["attempt_no"] == 2


@pytest.mark.parametrize("boundary", ["attempts", "findings"])
def test_replacement_interruption_rolls_back_as_one_transaction(tmp_path, boundary):
    repo = _prepare_host_repo(tmp_path)
    initial = run_stage(repo, "do", action="begin", task_id="T1")
    old_id = initial.extras["attempt_id"]
    assert run_stage(repo, "do", action="complete", attempt_id=str(old_id), status="blocked").status == "blocked"
    store = SQLiteStore(repo)
    session_id = int(store.branch_session("master")["id"])
    finding_id = store.open_blocking_findings(session_id)[0]["id"]
    target_id = old_id if boundary == "attempts" else finding_id
    with store.connect() as conn:
        conn.execute(f"""CREATE TRIGGER interrupt_replacement BEFORE UPDATE OF status ON {boundary}
            WHEN OLD.id = {target_id} AND NEW.status = 'superseded'
            BEGIN SELECT RAISE(ABORT, 'interrupted replacement'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="interrupted replacement"):
        run_stage(repo, "do", action="begin", task_id="T1")
    assert store.active_attempt(session_id) is None
    assert len(store.attempts(session_id)) == 1
    assert store.attempt(old_id)["status"] == "blocked"
    assert len(store.open_blocking_findings(session_id)) == 1
    with store.connect() as conn:
        conn.execute("DROP TRIGGER interrupt_replacement")
    new = run_stage(repo, "do", action="begin", task_id="T1")
    assert new.extras["attempt_no"] == 2
    assert store.attempt(old_id)["status"] == "superseded"
    assert not store.open_blocking_findings(session_id)
    assert _complete_build_with_passed_review(repo, new.extras["attempt_id"]).status == "ok"
    verify = run_stage(repo, "do", action="begin", task_id="T2")
    assert _complete_verify(repo, verify.extras["attempt_id"]).status == "ok"
    assert run_stage(repo, "ship").extras["ship_packet"]["status"] == "ready"


@pytest.mark.parametrize("old_status", ["blocked", "superseded"])
@pytest.mark.parametrize("entry", ["begin", "ship"])
def test_upgrade_repairs_interrupted_replacement(tmp_path, old_status, entry):
    repo = _prepare_host_repo(tmp_path)
    old = run_stage(repo, "do", action="begin", task_id="T1")
    old_id = old.extras["attempt_id"]
    run_stage(repo, "do", action="complete", attempt_id=str(old_id), status="blocked")
    new = run_stage(repo, "do", action="begin", task_id="T1")
    if entry == "ship":
        assert _complete_build_with_passed_review(repo, new.extras["attempt_id"]).status == "ok"
        verify = run_stage(repo, "do", action="begin", task_id="T2")
        assert _complete_verify(repo, verify.extras["attempt_id"]).status == "ok"
    store = SQLiteStore(repo)
    session_id = int(store.branch_session("master")["id"])
    with store.connect() as conn:
        conn.execute("UPDATE attempts SET status = ? WHERE id = ?", (old_status, old_id))
        conn.execute("UPDATE findings SET status = 'open' WHERE attempt_id = ?", (old_id,))
        conn.execute("PRAGMA user_version = 14")
    for _ in range(2):
        result = run_stage(repo, "do", action="begin", task_id="T1") if entry == "begin" else run_stage(repo, "ship")
        if entry == "begin":
            assert result.extras["attempt_id"] == new.extras["attempt_id"]
        else:
            assert result.extras["ship_packet"]["status"] == "ready"
        assert store.attempt(old_id)["status"] == "superseded"
        assert not store.open_blocking_findings(session_id)


def test_upgrade_keeps_current_unrelated_and_active_findings(tmp_path):
    store = SQLiteStore(tmp_path)
    session = store.get_or_create_branch_session("master", "master", "specs")
    other = store.get_or_create_branch_session("other", "other", "specs")
    session_id = int(session["id"])
    replaced = []
    retained = []
    for status in ("failed", "blocked", "implemented", "verified", "superseded", "running", "completing"):
        old_id = store.create_attempt(session_id, status, 1, "mock", None, None, None, "old")
        store.update_attempt(old_id, status)
        old_finding = store.add_finding(session_id, old_id, "execution_blocked", "blocking", "old")
        new_id = store.create_attempt(session_id, status, 2, "mock", None, None, None, "new")
        store.update_attempt(new_id, "implemented")
        retained.append(store.add_finding(session_id, new_id, "execution_blocked", "blocking", "current"))
        (retained if status in {"running", "completing"} else replaced).append(old_finding)
    lone = store.create_attempt(session_id, "no-successor", 1, "mock", None, None, None, "old")
    store.update_attempt(lone, "blocked")
    store.create_attempt(int(other["id"]), "no-successor", 2, "mock", None, None, None, "new")
    retained.append(store.add_finding(session_id, lone, "execution_blocked", "blocking", "other session is not replacement"))
    retained.append(store.add_finding(session_id, None, "execution_blocked", "blocking", "session finding"))
    with store.connect() as conn:
        conn.execute("PRAGMA user_version = 14")
    store.initialize()
    store.initialize()
    statuses = {row["id"]: row["status"] for row in store.findings(session_id)}
    assert all(statuses[identity] == "superseded" for identity in replaced)
    assert all(statuses[identity] == "open" for identity in retained)
