from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from codeloom.app.status import get_status
from codeloom.persistence.sqlite import SQLiteStore
from codeloom.stores.file_evidence import FileEvidenceStore
from tests.helpers import run_stage
from tests.test_stage_flow import _complete_build_with_passed_review, _prepare_host_repo


def _register_graph_tasks(repo):
    handoff = run_stage(repo, "tasks")
    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        """# Tasks

## build

- [ ] T1: Build shared state
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Depends on: None
  - Covered by: T4

- [ ] T2: Build dependent behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Depends on: T1
  - Covered by: T4

- [ ] T3: Build independent behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Depends on: None
  - Covered by: T5

## verify

- [ ] T4: Verify shared path
  - Lane: verify
  - Complexity: small
  - Revision: 1
  - Depends on: T2
  - Validates: T1, T2

- [ ] T5: Verify independent path
  - Lane: verify
  - Complexity: small
  - Revision: 1
  - Depends on: T3
  - Validates: T3
""",
        encoding="utf-8",
    )
    registered = run_stage(
        repo,
        "tasks",
        artifact_file="specs/master/tasks.md",
        input_token=handoff.extras["input_token"],
    )
    assert registered.status == "ok"
    return tasks_path


def _complete_verify(repo, attempt_id, summary="verified"):
    return run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(attempt_id),
        status="verified",
        summary=summary,
        verification_summary='{"status":"verified"}',
    )


def test_active_attempt_and_failed_prerequisite_only_block_affected_tasks(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    _register_graph_tasks(repo)

    t1 = run_stage(repo, "do", task_id="T1", action="begin")
    assert t1.status == "ok"

    while_t1_running = run_stage(repo, "do", task_id="T3", action="begin")
    assert while_t1_running.status == "blocked"
    assert while_t1_running.errors == ["active_attempt_exists"]
    assert while_t1_running.recommended_task_id == "T1"

    blocked = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(t1.extras["attempt_id"]),
        status="blocked",
        summary="T1 needs recovery",
    )
    assert blocked.status == "blocked"

    t2 = run_stage(repo, "do", task_id="T2", action="begin")
    assert t2.status == "blocked"
    assert t2.errors == ["task_prerequisite_incomplete"]
    assert t2.extras["root_task_id"] == "T1"
    assert t2.extras["affected_task_ids"] == ["T1", "T2", "T4"]

    t3 = run_stage(repo, "do", task_id="T3", action="begin")
    assert t3.status == "ok"
    assert t3.extras["task_id"] == "T3"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    active = store.active_attempt(int(session["id"]))
    assert active is not None
    assert active["task_id"] == "T3"


def test_concurrent_begin_creates_only_one_active_attempt(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    _register_graph_tasks(repo)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda task_id: run_stage(repo, "do", task_id=task_id, action="begin"),
                ("T1", "T3"),
            )
        )

    assert sorted(response.status for response in responses) == ["blocked", "ok"]
    blocked = next(response for response in responses if response.status == "blocked")
    assert blocked.errors == ["active_attempt_exists"]

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    assert len([attempt for attempt in attempts if attempt["status"] in {"running", "completing"}]) == 1


def test_running_attempt_is_replaced_when_its_effective_inputs_change(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    tasks_path = _register_graph_tasks(repo)

    t1 = run_stage(repo, "do", task_id="T1", action="begin")
    assert _complete_build_with_passed_review(repo, t1.extras["attempt_id"]).status == "ok"
    first_t3 = run_stage(repo, "do", task_id="T3", action="begin")
    assert first_t3.status == "ok"
    assert first_t3.extras["resumed"] is False

    tasks_handoff = run_stage(repo, "tasks")
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace(
            "- [ ] T3: Build independent behavior\n  - Lane: build\n  - Complexity: small\n  - Revision: 1\n  - Depends on: None",
            "- [ ] T3: Build independent behavior\n  - Lane: build\n  - Complexity: small\n  - Revision: 1\n  - Depends on: T1",
        ),
        encoding="utf-8",
    )
    registered = run_stage(
        repo,
        "tasks",
        artifact_file="specs/master/tasks.md",
        input_token=tasks_handoff.extras["input_token"],
    )
    assert registered.status == "ok"

    resumed_t3 = run_stage(repo, "do", task_id="T3", action="begin")
    assert resumed_t3.status == "ok"
    assert resumed_t3.extras["attempt_id"] == first_t3.extras["attempt_id"]
    assert resumed_t3.extras["task_packet"]["depends_on"] == []

    store = SQLiteStore(repo)
    first_attempt = store.attempt(int(first_t3.extras["attempt_id"]))
    assert first_attempt is not None
    assert first_attempt["status"] == "running"


def test_task_revision_invalidates_only_dependents_and_validators(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    tasks_path = _register_graph_tasks(repo)

    t1 = run_stage(repo, "do", task_id="T1", action="begin")
    assert _complete_build_with_passed_review(repo, t1.extras["attempt_id"]).status == "ok"
    t2 = run_stage(repo, "do", task_id="T2", action="begin")
    assert _complete_build_with_passed_review(repo, t2.extras["attempt_id"]).status == "ok"
    t3 = run_stage(repo, "do", task_id="T3", action="begin")
    assert _complete_build_with_passed_review(repo, t3.extras["attempt_id"]).status == "ok"
    t4 = run_stage(repo, "do", task_id="T4", action="begin")
    assert _complete_verify(repo, t4.extras["attempt_id"]).status == "ok"
    t5 = run_stage(repo, "do", task_id="T5", action="begin")
    assert _complete_verify(repo, t5.extras["attempt_id"]).status == "ok"

    tasks_handoff = run_stage(repo, "tasks")
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace(
            "- [ ] T1: Build shared state\n  - Lane: build\n  - Complexity: small\n  - Revision: 1",
            "- [ ] T1: Build shared state\n  - Lane: build\n  - Complexity: small\n  - Revision: 2",
        ),
        encoding="utf-8",
    )
    registered = run_stage(
        repo,
        "tasks",
        artifact_file="specs/master/tasks.md",
        input_token=tasks_handoff.extras["input_token"],
    )
    assert registered.status == "ok"
    assert registered.recommended_task_id == "T1"

    status_by_task = {item["task_id"]: item for item in get_status(repo, "master")["latest_attempts"]}
    assert status_by_task["T1"]["effective_status"] == "stale"
    assert status_by_task["T2"]["effective_status"] == "blocked"
    assert status_by_task["T2"]["blocked_by"] == ["T1"]
    assert status_by_task["T3"]["effective_status"] == "effective"
    assert status_by_task["T4"]["effective_status"] == "blocked"
    assert status_by_task["T5"]["effective_status"] == "effective"

    t3_reused = run_stage(repo, "do", task_id="T3", action="begin")
    assert t3_reused.extras["skipped"] is True
    assert t3_reused.extras["effective_attempt_id"] == t3.extras["attempt_id"]
    t5_reused = run_stage(repo, "do", task_id="T5", action="begin")
    assert t5_reused.extras["skipped"] is True
    assert t5_reused.extras["effective_attempt_id"] == t5.extras["attempt_id"]

    t2_stale = run_stage(repo, "do", task_id="T2", action="begin")
    assert t2_stale.status == "blocked"
    assert t2_stale.extras["blocked_by"] == ["T1"]
    t4_stale = run_stage(repo, "do", task_id="T4", action="begin")
    assert t4_stale.status == "blocked"
    assert t4_stale.extras["blocked_by"] == ["T2", "T1"]
    assert t4_stale.extras["root_task_id"] == "T1"

    t1_retry = run_stage(repo, "do", task_id="T1", action="begin")
    assert t1_retry.status == "ok"
    assert t1_retry.extras["attempt_no"] == 2

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    assert len([attempt for attempt in attempts if attempt["task_id"] == "T3"]) == 1
    assert len([attempt for attempt in attempts if attempt["task_id"] == "T5"]) == 1


def test_failed_verify_can_reopen_only_its_build_input(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    first_build = run_stage(repo, "do", task_id="T1", action="begin")
    assert _complete_build_with_passed_review(repo, first_build.extras["attempt_id"]).status == "ok"

    invalid_retry = run_stage(
        repo,
        "do",
        task_id="T1",
        action="retry",
        cause_attempt_id=str(first_build.extras["attempt_id"]),
        summary="A Build result cannot authorize its own targeted retry",
    )
    assert invalid_retry.status == "failed"
    assert invalid_retry.errors == ["invalid_retry_cause"]

    verify = run_stage(repo, "do", task_id="T2", action="begin")
    failed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify.extras["attempt_id"]),
        status="failed",
        summary="T1 contradicts the required behavior",
    )
    assert failed.status == "failed"

    retry = run_stage(
        repo,
        "do",
        task_id="T1",
        action="retry",
        cause_attempt_id=str(verify.extras["attempt_id"]),
        summary="Verifier located the defect in T1",
    )
    assert retry.status == "ok"
    assert retry.extras["task_id"] == "T1"
    assert retry.extras["attempt_no"] == 2

    store = SQLiteStore(repo)
    original = store.attempt(int(first_build.extras["attempt_id"]))
    assert original is not None
    assert original["status"] == "superseded"

    assert _complete_build_with_passed_review(repo, retry.extras["attempt_id"]).status == "ok"
    verify_retry = run_stage(repo, "do", task_id="T2", action="begin")
    assert verify_retry.status == "ok"
    assert verify_retry.extras["attempt_no"] == 2


@pytest.mark.parametrize("target_stage", ["spec", "plan", "tasks"])
def test_do_continuation_redirects_affected_tasks_but_allows_independent_task(tmp_path, target_stage):
    repo = _prepare_host_repo(tmp_path)
    _register_graph_tasks(repo)

    t1 = run_stage(repo, "do", task_id="T1", action="begin")
    routed = run_stage(
        repo,
        "do",
        action="route",
        attempt_id=str(t1.extras["attempt_id"]),
        target_stage=target_stage,
        reason="T1 accepted boundary must change",
    )
    assert routed.status == "ok"
    assert routed.recommended_next == f"/loom-{target_stage}"
    assert routed.extras["affected_task_ids"] == ["T1", "T2", "T4"]

    affected = run_stage(repo, "do", task_id="T2", action="begin")
    assert affected.status == "noop"
    assert affected.recommended_next == f"/loom-{target_stage}"

    independent = run_stage(repo, "do", task_id="T3", action="begin")
    assert independent.status == "ok"
    assert independent.extras["task_id"] == "T3"
    assert _complete_build_with_passed_review(repo, independent.extras["attempt_id"]).status == "ok"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    assert not [finding for finding in store.findings(int(session["id"])) if finding["kind"] == "execution_blocked"]

    handoff = run_stage(repo, target_stage)
    registration_args = {"artifact_file": f"specs/master/{target_stage}.md"}
    if target_stage != "spec":
        registration_args["input_token"] = handoff.extras["input_token"]
    registered = run_stage(repo, target_stage, **registration_args)
    assert registered.status == "ok"
    session = store.branch_session("master")
    assert session is not None
    assert session["continuation_stage"] is None


def test_stale_seal_attachment_cannot_replace_newer_revision(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    store = SQLiteStore(repo)

    first_revision, first_created = store.record_sealed_changes(attempt_id, "tree-one")
    second_revision, second_created = store.record_sealed_changes(attempt_id, "tree-two")
    assert (first_revision, first_created) == (1, True)
    assert (second_revision, second_created) == (2, True)

    assert store.attach_sealed_changes(
        attempt_id,
        first_revision,
        "tree-one",
        "runs/tree-one.json",
        "hash-one",
    ) is False
    assert store.attach_sealed_changes(
        attempt_id,
        second_revision,
        "tree-two",
        "runs/tree-two.json",
        "hash-two",
    ) is True

    attempt = store.attempt(attempt_id)
    assert attempt is not None
    assert attempt["latest_seal_revision"] == 2
    assert attempt["latest_sealed_tree"] == "tree-two"
    assert attempt["latest_sealed_changes_ref"] == "runs/tree-two.json"
    changes_refs = [ref for ref in store.runtime_refs(attempt_id) if ref["kind"] == "attempt_changes"]
    assert [(ref["path"], ref["content_hash"]) for ref in changes_refs] == [("runs/tree-two.json", "hash-two")]


def test_completion_resumes_after_claim_without_duplicate_evidence(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    summary = "blocked after claim"
    stdout = "partial host result"
    candidate = {
        "status": "blocked",
        "summary": summary,
        "stdout": stdout,
        "stderr": "",
        "verification_summary": "",
    }
    candidate_content = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    token = hashlib.sha256(candidate_content.encode("utf-8")).hexdigest()
    candidate_ref = FileEvidenceStore(repo, "master").write_attempt_file(
        "T1",
        1,
        f"completion-candidate-{token}.json",
        candidate_content,
    )

    store = SQLiteStore(repo)
    assert store.claim_attempt_completion(
        attempt_id,
        token,
        "blocked",
        summary,
        candidate_ref,
        token,
    ) == "claimed"

    recovery = run_stage(repo, "do", task_id="T1", action="begin")
    assert recovery.status == "ok"
    assert recovery.extras["status"] == "completing"
    assert recovery.extras["completion_candidate_ref"] == candidate_ref
    assert recovery.extras["completion_candidate_hash"] == token
    assert recovery.extras["host_recovery"] == {
        "user_visible": False,
        "internal_action": "resume_complete",
        "command_args": {"action": "complete", "attempt_id": attempt_id},
    }

    completed = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert completed.status == "blocked"

    duplicate = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert duplicate.status == "ok"
    assert duplicate.extras["idempotent"] is True

    conflicting = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(attempt_id),
        status="blocked",
        summary="different blocked result",
        stdout=stdout,
    )
    assert conflicting.status == "failed"
    assert conflicting.errors == ["completion_conflict"]

    session = store.branch_session("master")
    assert session is not None
    refs = store.runtime_refs(attempt_id)
    assert len([ref for ref in refs if ref["kind"] == "stdout"]) == 1
    findings = [
        finding
        for finding in store.findings(int(session["id"]))
        if finding["attempt_id"] == attempt_id and finding["kind"] == "execution_blocked"
    ]
    assert len(findings) == 1


def test_tampered_completion_candidate_requires_original_candidate_for_recovery(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = int(begin.extras["attempt_id"])
    summary = "blocked with recoverable candidate"
    stdout = "original output"
    candidate = {
        "status": "blocked",
        "summary": summary,
        "stdout": stdout,
        "stderr": "",
        "verification_summary": "",
    }
    content = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    token = hashlib.sha256(content.encode("utf-8")).hexdigest()
    candidate_ref = FileEvidenceStore(repo, "master").write_attempt_file(
        "T1",
        1,
        f"completion-candidate-{token}.json",
        content,
    )
    store = SQLiteStore(repo)
    assert store.claim_attempt_completion(
        attempt_id,
        token,
        "blocked",
        summary,
        candidate_ref,
        token,
    ) == "claimed"

    tampered = {**candidate, "stdout": "tampered output"}
    repo.joinpath(candidate_ref).write_text(
        json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    damaged = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert damaged.status == "blocked"
    assert damaged.errors == ["completion_candidate_hash_mismatch"]
    assert damaged.extras["host_recovery"]["internal_action"] == "resubmit_completion_candidate"

    recovered = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(attempt_id),
        status="blocked",
        summary=summary,
        stdout=stdout,
    )
    assert recovered.status == "blocked"
    assert repo.joinpath(candidate_ref).read_text(encoding="utf-8") == content


def test_verify_completion_recovers_persisted_summary_in_new_host_session(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    build = run_stage(repo, "do", task_id="T1", action="begin")
    assert _complete_build_with_passed_review(repo, build.extras["attempt_id"]).status == "ok"
    verify = run_stage(repo, "do", task_id="T2", action="begin")
    attempt_id = int(verify.extras["attempt_id"])
    verification_summary = '{"checked":["host behavior"],"status":"verified"}'
    candidate = {
        "status": "verified",
        "summary": "verified after persisted claim",
        "stdout": "",
        "stderr": "",
        "verification_summary": verification_summary,
    }
    content = json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    token = hashlib.sha256(content.encode("utf-8")).hexdigest()
    candidate_ref = FileEvidenceStore(repo, "master").write_attempt_file(
        "T2",
        1,
        f"completion-candidate-{token}.json",
        content,
    )
    store = SQLiteStore(repo)
    assert store.claim_attempt_completion(
        attempt_id,
        token,
        "verified",
        candidate["summary"],
        candidate_ref,
        token,
    ) == "claimed"

    completed = run_stage(repo, "do", action="complete", attempt_id=str(attempt_id))
    assert completed.status == "ok"
    verification = store.verifications_for_attempt(attempt_id)
    assert len(verification) == 1
    assert verification[0]["status"] == "passed"
    assert verification[0]["summary_ref"] is None
    assert verification[0]["summary_text"] == verification_summary


def test_review_conflicts_return_stable_response_and_keep_one_record(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))

    passed = run_stage(
        repo,
        "do",
        action="record-review",
        attempt_id=str(begin.extras["attempt_id"]),
        seal_revision=str(sealed.extras["seal_revision"]),
        status="pass",
        review_summary="No material finding.",
    )
    assert passed.status == "ok"

    duplicate = run_stage(
        repo,
        "do",
        action="record-review",
        attempt_id=str(begin.extras["attempt_id"]),
        seal_revision=str(sealed.extras["seal_revision"]),
        status="pass",
        review_summary="No material finding.",
    )
    assert duplicate.status == "ok"
    assert duplicate.extras["review_record_id"] == passed.extras["review_record_id"]

    conflict = run_stage(
        repo,
        "do",
        action="record-review",
        attempt_id=str(begin.extras["attempt_id"]),
        seal_revision=str(sealed.extras["seal_revision"]),
        status="changes_requested",
        review_summary="A conflicting verdict.",
    )
    assert conflict.status == "failed"
    assert conflict.errors == ["review_already_recorded"]

    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    assert not [ref for ref in refs if ref["kind"] == "review_summary"]
    record = store.review_for_seal(int(begin.extras["attempt_id"]), int(sealed.extras["seal_revision"]))
    assert record["id"] == passed.extras["review_record_id"]
    assert record["summary_ref"] is None
    assert "No material finding." in record["summary_json"]
