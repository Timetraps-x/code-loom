from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import run_stage
from tests.test_stage_flow import _prepare_host_repo


@pytest.mark.parametrize("initial_status", ["changes_requested", "blocked"])
def test_same_seal_can_complete_after_independent_rereview(tmp_path, initial_status):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    first = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                      seal_revision="1", status=initial_status, review_summary="Need to inspect the registered handler.")
    resealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert resealed.extras["seal_reused"] is True
    assert resealed.extras["sealed_tree"] == sealed.extras["sealed_tree"]
    revised = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                        seal_revision="1", status="pass", review_summary="The registered handler satisfies the contract.",
                        supersedes_review_id=str(first.extras["review_record_id"]))
    assert revised.status == "ok"
    assert revised.extras["review_record_id"] != first.extras["review_record_id"]
    duplicate = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                          seal_revision="1", status="pass", review_summary="The registered handler satisfies the contract.",
                          supersedes_review_id=str(first.extras["review_record_id"]))
    assert duplicate.status == "ok"
    assert duplicate.extras["review_record_id"] == revised.extras["review_record_id"]
    stale = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                      seal_revision="1", status="blocked", review_summary="Delayed review based on the old finding.",
                      supersedes_review_id=str(first.extras["review_record_id"]))
    assert stale.errors == ["review_already_recorded"]
    assert stale.extras["review_record_id"] == revised.extras["review_record_id"]
    store = SQLiteStore(repo)
    with store.connect() as conn:
        history = conn.execute("SELECT status, summary_json FROM review_records WHERE attempt_id = ? ORDER BY id", (attempt_id,)).fetchall()
    assert [row["status"] for row in history] == [initial_status, "pass"]
    assert "registered handler" in history[0]["summary_json"]
    assert store.review_for_seal(attempt_id, 1)["id"] == revised.extras["review_record_id"]
    completed = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id),
                          status="implemented", summary="Implemented and independently reviewed.")
    assert completed.status == "ok"


def test_same_verdict_with_new_evidence_is_preserved(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    first = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id), seal_revision="1",
                      status="changes_requested", review_summary="Two findings remain.")
    revised = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id), seal_revision="1",
                        status="changes_requested", review_summary="One finding resolved by existing evidence; one remains.",
                        supersedes_review_id=str(first.extras["review_record_id"]))
    assert revised.status == "ok"
    assert revised.extras["review_record_id"] != first.extras["review_record_id"]
    record = SQLiteStore(repo).review_for_seal(attempt_id, 1)
    assert "one remains" in record["summary_json"]


@pytest.mark.parametrize("expired", ["attempt", "seal"])
def test_review_write_checks_current_attempt_and_seal_in_transaction(tmp_path, expired):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    first = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                      seal_revision="1", status="pass", review_summary="No material finding.")
    if expired == "attempt":
        assert run_stage(repo, "do", action="complete", attempt_id=str(attempt_id),
                         status="implemented", summary="Done.").status == "ok"
        error = "attempt_not_running"
    else:
        (repo / "new-behavior.txt").write_text("changed", encoding="utf-8")
        assert run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id)).extras["seal_revision"] == 2
        error = "seal_revision_mismatch"
    store = SQLiteStore(repo)
    with pytest.raises(ValueError, match=error):
        store.record_review(attempt_id, 1, sealed.extras["sealed_tree"], "blocked", None,
                            hashlib.sha256(b"late").hexdigest(), "late",
                            supersedes_review_id=int(first.extras["review_record_id"]))
    assert store.review_for_seal(attempt_id, 1)["id"] == first.extras["review_record_id"]


def test_concurrent_rereviews_cannot_replace_a_newer_verdict(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    first = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                      seal_revision="1", status="blocked", review_summary="Initial observation unavailable.")
    store = SQLiteStore(repo)

    def record(status):
        try:
            return store.record_review(attempt_id, 1, sealed.extras["sealed_tree"], status, None,
                                       hashlib.sha256(status.encode()).hexdigest(), status,
                                       supersedes_review_id=int(first.extras["review_record_id"]))
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(record, ["pass", "changes_requested"]))
    assert results.count("review_already_recorded") == 1
    winner = next(result for result in results if isinstance(result, int))
    latest = store.review_for_seal(attempt_id, 1)
    assert latest["id"] == winner
    assert store.attempt(attempt_id)["latest_review_status"] == latest["status"]
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM review_records WHERE attempt_id = ?", (attempt_id,)).fetchone()[0] == 2


def test_schema_upgrade_preserves_nullable_review_history_and_allows_rereview(tmp_path):
    store = SQLiteStore(tmp_path)
    with store.connect() as conn:
        conn.execute("""CREATE TABLE review_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL,
            seal_revision INTEGER NOT NULL, sealed_tree TEXT NOT NULL, status TEXT NOT NULL,
            review_scope TEXT NOT NULL, summary_ref TEXT, summary_json TEXT, summary_hash TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(attempt_id, seal_revision))""")
        conn.execute("INSERT INTO review_records VALUES (7, 1, 1, 'tree', 'blocked', 'attempt_scoped', NULL, 'original', 'hash', 'now')")
        conn.execute("PRAGMA user_version = 13")
    store.initialize()
    store.initialize()
    original = store.review_for_seal(1, 1)
    assert original["id"] == 7 and original["summary_json"] == "original"
    with store.connect() as conn:
        conn.execute("""INSERT INTO review_records
            (attempt_id, seal_revision, sealed_tree, status, review_scope, summary_json, summary_hash, created_at)
            VALUES (1, 1, 'tree', 'pass', 'attempt_scoped', 'revised', 'hash2', 'later')""")
        assert conn.execute("SELECT COUNT(*) FROM review_records").fetchone()[0] == 2
    latest = store.review_for_seal(1, 1)
    assert latest["id"] > 7 and latest["summary_json"] == "revised"


@pytest.mark.parametrize("revised_status", ["pass", "changes_requested", "blocked"])
def test_completion_consumes_the_review_identity_checked_before_claim(tmp_path, monkeypatch, revised_status):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    first = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                      seal_revision="1", status="pass", review_summary="Original accepted review.")
    original_claim = SQLiteStore.claim_attempt_completion

    def interleaved_claim(store, *args, **kwargs):
        revised = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                            seal_revision="1", status=revised_status, review_summary="Reconsidered with new evidence.",
                            supersedes_review_id=str(first.extras["review_record_id"]))
        assert revised.status == "ok"
        return original_claim(store, *args, **kwargs)

    monkeypatch.setattr(SQLiteStore, "claim_attempt_completion", interleaved_claim)
    completed = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id),
                          status="implemented", summary="Delivery complete.")
    assert completed.status == "noop"
    assert completed.errors == ["review_changed"]
    store = SQLiteStore(repo)
    assert store.attempt(attempt_id)["status"] == "running"
    assert store.review_for_seal(attempt_id, 1)["status"] == revised_status
    monkeypatch.setattr(SQLiteStore, "claim_attempt_completion", original_claim)
    retried = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id),
                        status="implemented", summary="Delivery complete.")
    if revised_status == "pass":
        assert retried.status == "ok"
    else:
        assert retried.errors == ["review_not_passed"]
