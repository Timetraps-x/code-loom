from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from codeloom.app.status import get_status
from codeloom.persistence.sqlite import SQLiteStore
from codeloom.stores.file_evidence import FileEvidenceStore
from tests.helpers import run_stage
from tests.test_stage_flow import _complete_build_with_passed_review, _prepare_host_repo


def test_database_completion_recovers_logs_and_verification_after_claim(tmp_path, monkeypatch):
    repo = _prepare_host_repo(tmp_path)
    build = run_stage(repo, "do", action="begin", task_id="T1")
    assert _complete_build_with_passed_review(repo, build.extras["attempt_id"]).status == "ok"
    verify = run_stage(repo, "do", action="begin", task_id="T2")
    attempt_id = int(verify.extras["attempt_id"])
    store = SQLiteStore(repo)
    output = "实际检查\n" * 10000
    proof = "checked: real entry\nlimit: one instance\n"

    def interrupted(*args, **kwargs):
        raise RuntimeError("interrupted after claim")

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteStore, "finalize_attempt_completion", interrupted)
        with pytest.raises(RuntimeError, match="after claim"):
            run_stage(repo, "do", action="complete", attempt_id=str(attempt_id), status="verified",
                      summary="checked", stdout=output, verification_summary=proof)

    attempt = store.attempt(attempt_id)
    assert attempt["status"] == "completing"
    assert attempt["completion_candidate_ref"] is None
    candidate = json.loads(attempt["completion_candidate_json"])
    assert candidate["version"] == "2"
    assert len(attempt["completion_candidate_json"]) < 2000
    assert repo.joinpath(candidate["stdout"]).read_text(encoding="utf-8") == output
    assert hashlib.sha256(repo.joinpath(candidate["stdout"]).read_bytes()).hexdigest() == candidate["stdout_hash"]
    assert get_status(repo, "master")["status"] != "failed"
    begin = run_stage(repo, "do", action="begin")
    assert begin.extras["host_recovery"]["internal_action"] == "resume_complete"
    completed = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert completed.status == "ok"
    duplicate = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert duplicate.extras["idempotent"] is True
    rows = store.verifications_for_attempt(attempt_id)
    assert len(rows) == 1
    assert rows[0]["summary_text"] == proof
    assert rows[0]["summary_ref"] is None
    assert [ref["kind"] for ref in store.runtime_refs(attempt_id)] == ["stdout"]
    files = list((repo / ".loom/runs/master").iterdir())
    assert files == [repo / candidate["stdout"]]

    ship = run_stage(repo, "ship")
    packet = ship.extras["ship_packet"]
    assert packet["verifications"][0]["summary_text"] == proof
    assert packet["reviews"][0]["summary_json"]
    assert packet["status"] == "ready"
    seal = packet["sealed_changes"][0]
    assert seal["sealed_tree"] == store.attempt(int(build.extras["attempt_id"]))["latest_sealed_tree"]
    changed_manifest = json.loads(seal["manifest_json"])
    changed_manifest["summary"]["files_changed"] += 1
    changed_text = json.dumps(changed_manifest, ensure_ascii=False, sort_keys=True)
    with store.connect() as conn:
        conn.execute("UPDATE sealed_changes SET manifest_json = ?, content_hash = ? WHERE attempt_id = ?",
                     (changed_text, hashlib.sha256(changed_text.encode("utf-8")).hexdigest(), build.extras["attempt_id"]))
    changed_ship = run_stage(repo, "ship")
    assert changed_ship.extras["ship_input_hash"] != ship.extras["ship_input_hash"]
    with store.connect() as conn:
        conn.execute("UPDATE verifications SET summary_text = 'changed' WHERE attempt_id = ?", (attempt_id,))
    damaged = run_stage(repo, "ship")
    assert any("verification summary hash mismatch" in gap for gap in damaged.extras["ship_packet"]["readiness_blockers"])


@pytest.mark.parametrize("damage", ["candidate", "log", "missing_log"])
def test_database_completion_detects_damage_and_accepts_original_resubmission(tmp_path, monkeypatch, damage):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    store = SQLiteStore(repo)
    args = dict(action="complete", attempt_id=str(attempt_id), status="blocked", summary="waiting", stdout="original\n")

    def interrupted(*args, **kwargs):
        raise RuntimeError("interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(SQLiteStore, "finalize_attempt_completion", interrupted)
        with pytest.raises(RuntimeError):
            run_stage(repo, "do", **args)
    candidate = json.loads(store.attempt(attempt_id)["completion_candidate_json"])
    log = repo / candidate["stdout"]
    if damage == "candidate":
        candidate["summary"] = "changed"
        with store.connect() as conn:
            conn.execute("UPDATE attempts SET completion_candidate_json = ? WHERE id = ?",
                         (json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")), attempt_id))
        error = "completion_candidate_hash_mismatch"
    elif damage == "log":
        log.write_text("changed", encoding="utf-8")
        error = "completion_log_hash_mismatch"
    else:
        log.unlink()
        error = "completion_log_unreadable"
    blocked = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert blocked.errors == [error]
    assert store.attempt(attempt_id)["status"] == "completing"
    assert not store.runtime_refs(attempt_id)
    assert run_stage(repo, "do", **args).status == "blocked"
    assert run_stage(repo, "do", action="complete", attempt_id=str(attempt_id)).extras["idempotent"] is True
    assert log.read_text(encoding="utf-8") == "original\n"
    session = store.branch_session("master")
    assert len(store.findings(int(session["id"]))) == 1
    assert len(list((repo / ".loom/runs/master").iterdir())) == 1


def test_legacy_packet_is_read_without_rewriting_or_hiding_database_damage(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    store = SQLiteStore(repo)
    packet = store.attempt(attempt_id)["task_packet_json"]
    ref = FileEvidenceStore(repo, "master").write_attempt_file("T1", 1, "legacy-task-packet.json", packet)
    with store.connect() as conn:
        conn.execute("UPDATE attempts SET task_packet_json = NULL, task_packet_ref = ? WHERE id = ?", (ref, attempt_id))
    (repo / "specs/master/tasks.md").unlink()
    resumed = run_stage(repo, "do", action="begin")
    assert resumed.extras["task_packet"] == begin.extras["task_packet"]
    assert store.attempt(attempt_id)["task_packet_json"] is None
    with store.connect() as conn:
        conn.execute("UPDATE attempts SET task_packet_json = '{}' WHERE id = ?", (attempt_id,))
    assert run_stage(repo, "do", action="begin").errors == ["task_packet_integrity_error"]
    assert repo.joinpath(ref).read_text(encoding="utf-8") == packet
    with store.connect() as conn:
        conn.execute("UPDATE attempts SET task_packet_json = NULL WHERE id = ?", (attempt_id,))
    repo.joinpath(ref).write_text("{}", encoding="utf-8")
    assert run_stage(repo, "do", action="begin").errors == ["task_packet_integrity_error"]


def test_seal_history_and_reviews_are_available_without_files(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    first = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    review = run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id),
                       seal_revision=str(first.extras["seal_revision"]), status="changes_requested", review_summary="fix behavior")
    assert review.status == "ok"
    (repo / "implementation.txt").write_text("fixed\n", encoding="utf-8")
    second = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert second.extras["seal_revision"] == 2
    prior = second.extras["prior_sealed_evidence"]
    assert len(prior) == 1
    assert prior[0]["sealed_tree"] == first.extras["sealed_tree"]
    assert "fix behavior" in prior[0]["review"]["summary_json"]
    assert len(run_stage(repo, "do", action="begin").extras["sealed_evidence"]) == 2
    store = SQLiteStore(repo)
    assert not store.attach_sealed_changes(attempt_id, 1, first.extras["sealed_tree"], None, "bad", "{}")
    assert len(store.sealed_changes_for_attempt(attempt_id)) == 2
    assert not list((repo / ".loom/runs/master").glob("*"))


def test_schema_upgrade_preserves_legacy_review_and_nullable_reference(tmp_path):
    store = SQLiteStore(tmp_path)
    store.db_path.parent.mkdir()
    with store.connect() as conn:
        conn.execute("""CREATE TABLE review_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL,
            seal_revision INTEGER NOT NULL, sealed_tree TEXT NOT NULL, status TEXT NOT NULL,
            review_scope TEXT NOT NULL, summary_ref TEXT NOT NULL, summary_hash TEXT NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(attempt_id, seal_revision))""")
        conn.execute("INSERT INTO review_records VALUES (7, 1, 1, 'tree', 'pass', 'attempt_scoped', 'old.json', 'hash', 'now')")
        conn.execute("PRAGMA user_version = 11")
    store.initialize()
    store.initialize()
    old = store.review_for_seal(1, 1)
    assert old["id"] == 7 and old["summary_ref"] == "old.json" and old["summary_json"] is None
    with store.connect() as conn:
        conn.execute("""INSERT INTO review_records
                     (attempt_id, seal_revision, sealed_tree, status, review_scope, summary_ref, summary_json, summary_hash, created_at)
                     VALUES (2, 1, 'tree2', 'pass', 'attempt_scoped', NULL, '{}', 'hash2', 'now')""")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO review_records SELECT * FROM review_records WHERE id = 7")
        assert {row["name"] for row in conn.execute("PRAGMA table_info(attempts)")} >= {"task_packet_json", "completion_candidate_json"}
        assert {row["name"] for row in conn.execute("PRAGMA table_info(verifications)")} >= {"summary_text", "summary_hash"}



def test_legacy_seal_and_review_remain_available_across_reseal(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id), seal_revision="1",
              status="changes_requested", review_summary="legacy finding")
    store = SQLiteStore(repo)
    manifest = store.sealed_changes_for_attempt(attempt_id)[0]
    review = store.review_for_seal(attempt_id, 1)
    evidence = FileEvidenceStore(repo, "master")
    seal_ref = evidence.write_attempt_file("T1", 1, "legacy-changes.json", manifest["manifest_json"])
    review_ref = evidence.write_attempt_file("T1", 1, "legacy-review.json", review["summary_json"])
    with store.connect() as conn:
        conn.execute("DELETE FROM sealed_changes WHERE attempt_id = ?", (attempt_id,))
        conn.execute("UPDATE attempts SET latest_sealed_changes_ref = ? WHERE id = ?", (seal_ref, attempt_id))
        conn.execute("UPDATE review_records SET summary_ref = ?, summary_json = NULL WHERE attempt_id = ?", (review_ref, attempt_id))
        conn.execute("INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at) VALUES (?, 'attempt_changes', ?, ?, 'now')",
                     (attempt_id, seal_ref, manifest["content_hash"]))
    resumed = run_stage(repo, "do", action="begin")
    prior = resumed.extras["sealed_evidence"][0]
    assert prior["manifest_json"] == manifest["manifest_json"]
    assert "legacy finding" in prior["review"]["summary_json"]
    (repo / "changed.txt").write_text("fixed", encoding="utf-8")
    resealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert resealed.extras["seal_revision"] == 2
    assert resealed.extras["prior_sealed_evidence"][0] == prior
    assert len(run_stage(repo, "do", action="begin").extras["sealed_evidence"]) == 2
    assert repo.joinpath(seal_ref).exists() and repo.joinpath(review_ref).exists()


@pytest.mark.parametrize("damage", ["hash", "identity"])
def test_damaged_seal_is_not_supplied_as_trusted_review_input(tmp_path, damage):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id), seal_revision="1",
                     status="pass", review_summary="No material findings.").status == "ok"
    manifest = {**sealed.extras["sealed_changes"], "task_id": "WRONG"}
    text = json.dumps(manifest)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest() if damage == "identity" else "wrong"
    with SQLiteStore(repo).connect() as conn:
        conn.execute("UPDATE sealed_changes SET manifest_json = ?, content_hash = ? WHERE attempt_id = ?", (text, digest, attempt_id))
    evidence = run_stage(repo, "do", action="begin").extras["sealed_evidence"][0]
    assert "manifest_json" not in evidence
    assert "integrity_error" in evidence
    completed = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id), status="implemented")
    assert completed.errors == ["sealed_evidence_integrity_error"]



def test_resealing_replaces_missing_legacy_evidence_without_blocking_ship(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    store = SQLiteStore(repo)
    manifest = store.sealed_changes_for_attempt(attempt_id)[0]
    ref = FileEvidenceStore(repo, "master").write_attempt_file("T1", 1, "legacy-changes.json", manifest["manifest_json"])
    with store.connect() as conn:
        conn.execute("DELETE FROM sealed_changes WHERE attempt_id = ?", (attempt_id,))
        conn.execute("UPDATE attempts SET latest_sealed_changes_ref = ? WHERE id = ?", (ref, attempt_id))
        conn.execute("INSERT INTO runtime_refs (attempt_id, kind, path, content_hash, created_at) VALUES (?, 'attempt_changes', ?, ?, 'now')",
                     (attempt_id, ref, manifest["content_hash"]))
    repo.joinpath(ref).unlink()
    assert _complete_build_with_passed_review(repo, attempt_id).status == "ok"
    verify = run_stage(repo, "do", action="begin", task_id="T2")
    assert run_stage(repo, "do", action="complete", attempt_id=str(verify.extras["attempt_id"]),
                     status="verified", verification_summary="checked").status == "ok"
    ship = run_stage(repo, "ship")
    assert ship.extras["ship_packet"]["status"] == "ready"
    assert not ship.extras["ship_packet"]["readiness_blockers"]


def test_damaged_review_does_not_loop_through_reseal(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", action="begin", task_id="T1")
    attempt_id = int(begin.extras["attempt_id"])
    run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert run_stage(repo, "do", action="record-review", attempt_id=str(attempt_id), seal_revision="1",
                     status="pass", review_summary="No material findings.").status == "ok"
    with SQLiteStore(repo).connect() as conn:
        conn.execute("UPDATE review_records SET summary_json = '{}' WHERE attempt_id = ?", (attempt_id,))
    blocked = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id), status="implemented")
    assert blocked.errors == ["sealed_evidence_integrity_error"]
    assert "host_recovery" not in blocked.extras
    assert "action=unlock" in blocked.extras["unlock_command"]
