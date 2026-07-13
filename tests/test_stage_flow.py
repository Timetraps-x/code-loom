from __future__ import annotations

import json
import subprocess

from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import init_repo, run_stage, write_project_config


def _host_artifact_dir(repo, branch="master"):
    artifact_dir = repo / "specs" / branch
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _write_host_spec(repo, branch="master"):
    _host_artifact_dir(repo, branch).joinpath("spec.md").write_text("# Spec\n\n## Requirement\nHost spec\n", encoding="utf-8")


def _write_host_plan(repo, branch="master"):
    _host_artifact_dir(repo, branch).joinpath("plan.md").write_text("# Plan\n\n## Design\nHost plan\n", encoding="utf-8")


def _write_host_tasks(repo, branch="master"):
    _host_artifact_dir(repo, branch).joinpath("tasks.md").write_text(
        "# Tasks\n\n"
        "## build\n\n"
        "- [ ] T1: Build host task\n"
        "  - Lane: build\n"
        "  - Complexity: small\n"
        "  - Covered by: T2\n\n"
        "## verify\n\n"
        "- [ ] T2: Verify host task\n"
        "  - Lane: verify\n"
        "  - Complexity: non-trivial\n"
        "  - Validates: T1\n",
        encoding="utf-8",
    )


def _register_host_artifacts(repo, branch="master"):
    _write_host_spec(repo, branch)
    run_stage(repo, "spec", branch=branch, artifact_file=f"specs/{branch}/spec.md")
    _write_host_plan(repo, branch)
    run_stage(repo, "plan", branch=branch, artifact_file=f"specs/{branch}/plan.md")
    _write_host_tasks(repo, branch)
    run_stage(repo, "tasks", branch=branch, artifact_file=f"specs/{branch}/tasks.md")


def _init_git_repo(repo):
    subprocess.run(["git", "init", "-b", "master"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)


def _commit_all(repo, message="initial"):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)


def _complete_build_with_passed_review(repo, attempt_id, **kwargs):
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert sealed.status == "ok"
    return run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(attempt_id),
        status="implemented",
        review_status="pass",
        seal_revision=str(sealed.extras["seal_revision"]),
        **kwargs,
    )

def _prepare_host_repo(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _register_host_artifacts(repo)
    _init_git_repo(repo)
    _commit_all(repo)
    return repo


def _assert_host_artifact_required(response, stage, artifact_path, main_agent, reviewer_agent=None):
    assert response.status == "blocked"
    assert response.errors == ["host_artifact_required"]
    assert response.recommended_next == f"/loom-{stage}"
    assert response.artifact_paths == [artifact_path]
    assert response.extras["stage"] == stage
    assert response.extras["main_agent"] == main_agent
    assert response.extras["reviewer_agent"] == reviewer_agent
    assert response.extras["artifact_path"] == artifact_path
    assert response.extras["register_command"] == f"loom stage {stage} --branch master --arg artifact_file={artifact_path}"


def _write_host_release(repo, branch="master"):
    _host_artifact_dir(repo, branch).joinpath("release.md").write_text("# Release\n\n## Result\nHost release\n", encoding="utf-8")

def test_mock_stage_flow_reaches_ship(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, test_command="python --version")

    assert run_stage(repo, "spec").recommended_next == "/loom-plan"
    assert run_stage(repo, "plan").recommended_next == "/loom-tasks"
    tasks_response = run_stage(repo, "tasks")
    assert tasks_response.recommended_next == "/loom-do T1"
    assert tasks_response.recommended_task_id == "T1"
    assert tasks_response.recommended_task_title == "Implement current CodeLoom requirement"

    first = run_stage(repo, "do", task_id="T1")
    assert first.status == "ok"
    assert first.recommended_next == "/loom-do T2"
    assert first.recommended_task_id == "T2"
    assert first.recommended_task_title == "Verify current CodeLoom requirement"

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


def test_mock_verify_without_evidence_blocks_ship_path(tmp_path):
    repo = init_repo(tmp_path)

    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")
    verify = run_stage(repo, "do", task_id="T2")

    assert verify.status == "blocked"
    assert verify.recommended_next == "/loom-do T2"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    assert [(attempt["task_id"], attempt["status"]) for attempt in attempts] == [("T1", "implemented"), ("T2", "blocked")]
    findings = store.findings(int(session["id"]))
    assert findings[-1]["kind"] == "verification_gap"


def test_claude_code_host_artifact_stages_require_artifact_file(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _write_host_spec(repo)

    _assert_host_artifact_required(run_stage(repo, "spec"), "spec", "specs/master/spec.md", "spec-analyzer", "spec-reviewer")

    registered_spec = run_stage(repo, "spec", artifact_file="specs/master/spec.md")
    assert registered_spec.status == "ok"
    _write_host_plan(repo)

    _assert_host_artifact_required(run_stage(repo, "plan"), "plan", "specs/master/plan.md", "plan-architect", "plan-reviewer")

    registered_plan = run_stage(repo, "plan", artifact_file="specs/master/plan.md")
    assert registered_plan.status == "ok"
    _write_host_tasks(repo)

    _assert_host_artifact_required(run_stage(repo, "tasks"), "tasks", "specs/master/tasks.md", "task-planner", "task-reviewer")

    registered_tasks = run_stage(repo, "tasks", artifact_file="specs/master/tasks.md")
    assert registered_tasks.status == "ok"
    assert registered_tasks.recommended_next == "/loom-do T1"

    _assert_host_artifact_required(run_stage(repo, "ship"), "ship", "specs/master/release.md", "release-analyzer")


def test_claude_code_host_artifact_inputs_do_not_bypass_artifact_file_requirement(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _write_host_spec(repo)

    _assert_host_artifact_required(
        run_stage(repo, "spec", requirement="Add another visible interaction"),
        "spec",
        "specs/master/spec.md",
        "spec-analyzer",
        "spec-reviewer",
    )

    run_stage(repo, "spec", artifact_file="specs/master/spec.md")
    _write_host_plan(repo)
    _assert_host_artifact_required(
        run_stage(repo, "plan", constraints="Reuse existing map loader"),
        "plan",
        "specs/master/plan.md",
        "plan-architect",
        "plan-reviewer",
    )

    run_stage(repo, "plan", artifact_file="specs/master/plan.md")
    _write_host_tasks(repo)
    _assert_host_artifact_required(
        run_stage(repo, "tasks", preference="Split browser validation"),
        "tasks",
        "specs/master/tasks.md",
        "task-planner",
        "task-reviewer",
    )


def test_claude_code_host_artifact_guard_does_not_create_fallback_files(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")

    response = run_stage(repo, "spec")

    _assert_host_artifact_required(response, "spec", "specs/master/spec.md", "spec-analyzer", "spec-reviewer")
    assert not repo.joinpath("specs", "master", "spec.md").exists()


def test_claude_code_host_artifact_file_must_exist(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")

    missing_spec = run_stage(repo, "spec", artifact_file="specs/master/spec.md")

    assert missing_spec.status == "failed"
    assert missing_spec.errors == ["missing_artifact_file"]


def test_claude_code_host_artifact_file_must_match_stage_path(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    wrong_path = repo / "specs" / "master" / "wrong.md"
    wrong_path.parent.mkdir(parents=True, exist_ok=True)
    wrong_path.write_text("# Wrong\n", encoding="utf-8")

    invalid = run_stage(repo, "spec", artifact_file="specs/master/wrong.md")

    assert invalid.status == "failed"
    assert invalid.errors == ["invalid_artifact_file_location"]


def test_claude_code_host_plan_and_tasks_preserve_missing_prerequisite_errors(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")

    missing_spec_for_plan = run_stage(repo, "plan")
    missing_spec_for_tasks = run_stage(repo, "tasks")

    assert missing_spec_for_plan.status == "failed"
    assert missing_spec_for_plan.errors == ["missing_spec"]
    assert missing_spec_for_tasks.status == "failed"
    assert missing_spec_for_tasks.errors == ["missing_spec"]

    _write_host_spec(repo)
    registered_spec = run_stage(repo, "spec", artifact_file="specs/master/spec.md")
    assert registered_spec.status == "ok"

    missing_plan_for_tasks = run_stage(repo, "tasks")

    assert missing_plan_for_tasks.status == "failed"
    assert missing_plan_for_tasks.errors == ["missing_plan"]


def test_claude_code_host_tasks_artifact_must_be_parseable(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _write_host_spec(repo)
    run_stage(repo, "spec", artifact_file="specs/master/spec.md")
    _write_host_plan(repo)
    run_stage(repo, "plan", artifact_file="specs/master/plan.md")
    _host_artifact_dir(repo).joinpath("tasks.md").write_text("# Tasks\n\nNo checkbox tasks here.\n", encoding="utf-8")

    invalid = run_stage(repo, "tasks", artifact_file="specs/master/tasks.md")

    assert invalid.status == "failed"
    assert invalid.errors == ["invalid_tasks_format"]


def test_claude_code_host_tasks_artifact_file_missing_is_reported_after_prerequisites(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _write_host_spec(repo)
    run_stage(repo, "spec", artifact_file="specs/master/spec.md")
    _write_host_plan(repo)
    run_stage(repo, "plan", artifact_file="specs/master/plan.md")

    missing_tasks = run_stage(repo, "tasks", artifact_file="specs/master/tasks.md")

    assert missing_tasks.status == "failed"
    assert missing_tasks.errors == ["missing_artifact_file"]


def test_claude_code_host_preregistered_artifacts_refresh_lineage_on_registration(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _write_host_spec(repo)
    _write_host_plan(repo)
    _write_host_tasks(repo)

    assert run_stage(repo, "spec", artifact_file="specs/master/spec.md").status == "ok"
    assert run_stage(repo, "plan", artifact_file="specs/master/plan.md").status == "ok"
    tasks = run_stage(repo, "tasks", artifact_file="specs/master/tasks.md")
    assert tasks.status == "ok"
    assert tasks.recommended_next == "/loom-do T1"
    _init_git_repo(repo)
    _commit_all(repo)

    begin = run_stage(repo, "do", action="begin", task_id="T1")

    assert begin.status == "ok"
    assert begin.extras["attempt_id"]


def test_claude_code_host_ship_artifact_file_errors_require_prerequisites_first(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    missing_release = run_stage(repo, "ship", artifact_file="specs/master/release.md")

    assert missing_release.status == "failed"
    assert missing_release.errors == ["missing_artifact_file"]


def test_claude_code_host_ship_registers_release_artifact_when_present(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    _write_host_release(repo)

    release = run_stage(repo, "ship", artifact_file="specs/master/release.md")

    assert release.status == "blocked"
    assert release.artifact_paths == ["specs/master/release.md"]
    assert repo.joinpath("specs", "master", "release.md").read_text(encoding="utf-8").startswith("# Release")


def test_claude_code_host_registers_absolute_artifact_file(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _write_host_spec(repo)

    registered = run_stage(repo, "spec", artifact_file=str(repo / "specs" / "master" / "spec.md"))

    assert registered.status == "ok"
    assert registered.artifact_paths == ["specs/master/spec.md"]


def test_spec_stage_treats_bare_text_as_revision_when_spec_exists(tmp_path):
    repo = init_repo(tmp_path)

    run_stage(repo, "spec", requirement="Initial dashboard requirement")
    response = run_stage(repo, "spec", **{"Preserve existing UI style": ""})

    assert response.status == "ok"
    spec = repo.joinpath("specs", "master", "spec.md").read_text(encoding="utf-8")
    assert "Preserve existing UI style" in spec
    assert "Initial dashboard requirement" in spec


def test_spec_stage_treats_gap_arg_as_revision_when_spec_exists(tmp_path):
    repo = init_repo(tmp_path)

    run_stage(repo, "spec", requirement="Initial dashboard requirement")
    response = run_stage(repo, "spec", gap="Keep the current UI style unchanged")

    assert response.status == "ok"
    spec = repo.joinpath("specs", "master", "spec.md").read_text(encoding="utf-8")
    assert "Keep the current UI style unchanged" in spec
    assert "Initial dashboard requirement" in spec


def test_mock_runtime_skips_empty_stderr_and_empty_verify_logs(tmp_path):
    repo = init_repo(tmp_path)
    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")

    run_stage(repo, "do", task_id="T1")
    run_stage(repo, "do", task_id="T2")

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    t1 = next(attempt for attempt in attempts if attempt["task_id"] == "T1")
    t2 = next(attempt for attempt in attempts if attempt["task_id"] == "T2")

    t1_refs = store.runtime_refs(int(t1["id"]))
    assert [ref["kind"] for ref in t1_refs] == ["stdout"]
    assert not (repo / ".loom" / "runs" / "master" / "T1-a001-diff.patch").exists()
    assert not (repo / ".loom" / "runs" / "master" / "T1-a001-runtime.stderr.log").exists()

    verification = store.verifications_for_attempt(int(t2["id"]))[0]
    assert verification["status"] == "skipped_config_missing"
    assert verification["stdout_ref"] is None
    assert verification["stderr_ref"] is None
    assert not list((repo / ".loom" / "runs" / "master").glob("T2-a001-verify*.log"))

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
    assert begin.extras["complexity"] == "small"
    attempt_id = str(begin.extras["attempt_id"])

    repeated_begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert repeated_begin.extras["attempt_id"] == begin.extras["attempt_id"]

    complete_build = _complete_build_with_passed_review(repo, attempt_id, summary="built T1")
    assert complete_build.status == "ok"
    assert complete_build.recommended_next == "/loom-do T2"
    assert complete_build.recommended_task_id == "T2"

    completed_begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert completed_begin.status == "ok"
    assert completed_begin.recommended_next == "/loom-do T2"
    assert completed_begin.recommended_task_id == "T2"

    begin_verify = run_stage(repo, "do", task_id="T2", action="begin")
    assert begin_verify.extras["lane"] == "verify"
    assert begin_verify.extras["main_agent"] == "verifier"
    assert begin_verify.extras["complexity"] == "non-trivial"
    verify_attempt_id = str(begin_verify.extras["attempt_id"])

    complete_verify = run_stage(repo, "do", action="complete", attempt_id=verify_attempt_id, status="verified", summary="verified T2", verification_summary='{"status":"verified"}')
    assert complete_verify.status == "ok"
    assert complete_verify.recommended_next == "/loom-ship"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    assert [(attempt["task_id"], attempt["status"]) for attempt in attempts] == [("T1", "implemented"), ("T2", "verified")]
    build_attempt = next(attempt for attempt in attempts if attempt["task_id"] == "T1")
    build_refs = store.runtime_refs(int(build_attempt["id"]))
    build_ref_kinds = {ref["kind"] for ref in build_refs}
    assert "attempt_changes" in build_ref_kinds
    assert {"git_status_begin", "git_status_complete", "diff", "change_inventory"}.isdisjoint(build_ref_kinds)
    verify_attempt = next(attempt for attempt in attempts if attempt["task_id"] == "T2")
    verify_refs = store.runtime_refs(int(verify_attempt["id"]))
    verify_ref_kinds = {ref["kind"] for ref in verify_refs}
    verification_summary_ref = next(ref for ref in verify_refs if ref["kind"] == "verification_summary")
    assert verification_summary_ref["content_hash"]
    assert {"git_status_begin", "git_status_complete", "diff", "change_inventory"}.isdisjoint(verify_ref_kinds)
    verification = store.verifications_for_attempt(int(verify_attempt["id"]))[0]
    assert verification["status"] == "passed"
    assert verification["summary_ref"] == verification_summary_ref["path"]


def test_claude_code_begin_captures_working_tree_content_snapshot(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    tracked = repo / "tracked.txt"
    tracked.write_text("before\n", encoding="utf-8")
    _commit_all(repo, "add tracked file")

    tracked.write_text("after\n", encoding="utf-8")
    (repo / "untracked.txt").write_text("new\n", encoding="utf-8")
    index_before = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo, check=True, capture_output=True, text=True).stdout

    begin = run_stage(repo, "do", task_id="T1", action="begin")

    assert begin.status == "ok"
    assert begin.extras["host_internal_flow"]["user_visible"] is False
    assert begin.extras["host_internal_flow"]["sequence"] == [
        "run_main_agent",
        "seal_changes",
        "run_reviewer_agent",
        "complete_attempt",
    ]
    assert begin.extras["host_internal_flow"]["after_main_agent"]["command_args"] == {
        "action": "seal-changes",
        "attempt_id": begin.extras["attempt_id"],
    }
    index_after = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo, check=True, capture_output=True, text=True).stdout
    assert index_after == index_before

    store = SQLiteStore(repo)
    attempt = store.attempt(int(begin.extras["attempt_id"]))
    assert attempt is not None
    assert attempt["snapshot_semantics"] == "working_tree_content"
    assert attempt["start_head"]
    assert attempt["start_tree"]
    status_summary = json.loads(attempt["start_status_json"])
    assert " M tracked.txt" in status_summary["git_status_short"]
    assert "?? untracked.txt" in status_summary["git_status_short"]


def test_claude_code_seal_changes_writes_attempt_changes(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    before_begin = repo / "before-begin.txt"
    before_begin.write_text("pre-existing\n", encoding="utf-8")

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert begin.status == "ok"

    (repo / "tracked-after.txt").write_text("before\n", encoding="utf-8")
    _commit_all(repo, "add tracked-after")
    (repo / "tracked-after.txt").write_text("after\n", encoding="utf-8")
    (repo / "untracked-after.txt").write_text("new\n", encoding="utf-8")

    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))

    assert sealed.status == "ok"
    assert sealed.extras["review_scope"] == "attempt_scoped"
    assert sealed.extras["seal_revision"] == 1
    assert "git diff --no-ext-diff --no-textconv" in sealed.extras["sealed_diff_command"]
    assert sealed.extras["reviewer_handoff"] == {
        "user_visible": False,
        "agent": "code-reviewer",
        "review_scope": "attempt_scoped",
        "seal_revision": sealed.extras["seal_revision"],
        "sealed_changes_ref": sealed.extras["sealed_changes_ref"],
        "sealed_diff_command": sealed.extras["sealed_diff_command"],
        "do_not_review_full_worktree": True,
    }

    store = SQLiteStore(repo)
    attempt = store.attempt(int(begin.extras["attempt_id"]))
    assert attempt is not None
    assert attempt["latest_sealed_tree"] == sealed.extras["sealed_tree"]
    assert attempt["latest_seal_revision"] == 1
    assert attempt["latest_review_status"] == "pending"
    assert attempt["latest_sealed_changes_ref"] == sealed.extras["sealed_changes_ref"]

    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    changes_ref = next(ref for ref in refs if ref["kind"] == "attempt_changes")
    changes = json.loads(repo.joinpath(changes_ref["path"]).read_text(encoding="utf-8"))
    paths = {item["path"] for item in changes["files"]}
    assert changes["version"] == 2
    assert changes["seal_revision"] == 1
    assert changes["diff_source"]["sealed_tree"] == sealed.extras["sealed_tree"]
    assert "tracked-after.txt" in paths
    assert "untracked-after.txt" in paths
    assert "before-begin.txt" not in paths
    for item in changes["files"]:
        assert {"old_mode", "new_mode", "old_oid", "new_oid"} <= item.keys()
    assert changes["review"]["patch_persisted"] is False
    assert not list((repo / ".loom" / "runs" / "master").glob("*-attempt-diff.patch"))

    second = run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))
    assert second.extras["seal_revision"] == 2
    assert len([ref for ref in store.runtime_refs(int(begin.extras["attempt_id"])) if ref["kind"] == "attempt_changes"]) == 1


def test_claude_code_build_implemented_requires_sealed_changes(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")

    completed = run_stage(repo, "do", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="implemented")

    assert completed.status == "blocked"
    assert completed.errors == ["sealed_changes_missing"]
    assert completed.extras["host_recovery"] == {
        "user_visible": False,
        "internal_action": "seal_changes",
        "command_args": {"action": "seal-changes", "attempt_id": begin.extras["attempt_id"]},
        "rerun_reviewer": True,
    }
    attempt = SQLiteStore(repo).attempt(int(begin.extras["attempt_id"]))
    assert attempt is not None
    assert attempt["status"] == "running"


def test_claude_code_build_implemented_requires_passed_review(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(begin.extras["attempt_id"]),
        status="implemented",
        review_status="changes_requested",
        seal_revision=str(sealed.extras["seal_revision"]),
    )

    assert completed.status == "blocked"
    assert completed.errors == ["review_not_passed"]


def test_claude_code_build_implemented_rejects_stale_sealed_changes(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))
    (repo / "after-review.txt").write_text("changed\n", encoding="utf-8")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(begin.extras["attempt_id"]),
        status="implemented",
        review_status="pass",
        seal_revision=str(sealed.extras["seal_revision"]),
    )

    assert completed.status == "blocked"
    assert completed.errors == ["sealed_changes_stale"]
    assert completed.extras["host_recovery"] == {
        "user_visible": False,
        "internal_action": "seal_changes",
        "command_args": {"action": "seal-changes", "attempt_id": begin.extras["attempt_id"]},
        "rerun_reviewer": True,
    }


def test_claude_code_build_implemented_rejects_seal_revision_mismatch(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))
    run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(begin.extras["attempt_id"]),
        status="implemented",
        review_status="pass",
        seal_revision="1",
    )

    assert completed.status == "blocked"
    assert completed.errors == ["seal_revision_mismatch"]
    assert completed.extras["host_recovery"] == {
        "user_visible": False,
        "internal_action": "seal_changes",
        "command_args": {"action": "seal-changes", "attempt_id": begin.extras["attempt_id"]},
        "rerun_reviewer": True,
    }


def test_claude_code_rejects_legacy_seal_action_and_complete_argument(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")

    legacy_action = run_stage(repo, "do", action="review-context", attempt_id=str(begin.extras["attempt_id"]))

    assert legacy_action.status == "failed"
    assert legacy_action.errors == ["legacy_do_action_not_supported"]

    sealed = run_stage(repo, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))
    legacy_argument = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(begin.extras["attempt_id"]),
        status="implemented",
        review_status="pass",
        review_context_revision=str(sealed.extras["seal_revision"]),
    )

    assert legacy_argument.status == "failed"
    assert legacy_argument.errors == ["legacy_complete_argument_not_supported"]


def test_claude_code_host_verify_completion_uses_summary_as_evidence(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify_begin.extras["attempt_id"]),
        status="verified",
        summary="claimed verification",
    )

    assert completed.status == "ok"
    store = SQLiteStore(repo)
    attempt = store.attempt(int(verify_begin.extras["attempt_id"]))
    assert attempt is not None
    assert attempt["status"] == "verified"
    refs = store.runtime_refs(int(verify_begin.extras["attempt_id"]))
    summary_ref = next(ref for ref in refs if ref["kind"] == "verification_summary")
    assert repo.joinpath(summary_ref["path"]).read_text(encoding="utf-8") == "claimed verification"
    verification = store.verifications_for_attempt(int(verify_begin.extras["attempt_id"]))[0]
    assert verification["status"] == "passed"
    assert verification["summary_ref"] == summary_ref["path"]


def test_claude_code_host_verify_completion_without_explicit_summary_still_blocks(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify_begin.extras["attempt_id"]),
        status="verified",
    )

    assert completed.status == "blocked"
    assert completed.recommended_next == "/loom-do T2"


def test_claude_code_host_verify_completion_blank_summary_still_blocks(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify_begin.extras["attempt_id"]),
        status="verified",
        summary="   ",
    )

    assert completed.status == "blocked"
    assert completed.recommended_next == "/loom-do T2"


def test_claude_code_host_verify_completion_empty_summary_file_still_blocks(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")
    summary_path = repo / "empty-verification-summary.json"
    summary_path.write_text("", encoding="utf-8")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify_begin.extras["attempt_id"]),
        status="verified",
        verification_summary_file="empty-verification-summary.json",
    )

    assert completed.status == "blocked"
    assert completed.recommended_next == "/loom-do T2"


def test_claude_code_host_verify_failed_completion_does_not_require_evidence(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify_begin.extras["attempt_id"]),
        status="failed",
        summary="verification command failed",
    )

    assert completed.status == "failed"
    assert completed.recommended_next == "/loom-do T2"

    store = SQLiteStore(repo)
    attempt = store.attempt(int(verify_begin.extras["attempt_id"]))
    assert attempt is not None
    assert attempt["status"] == "failed"

def test_claude_code_host_verify_completion_accepts_summary_file(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")
    summary_path = repo / "verification-summary-input.json"
    summary_path.write_text('{"status":"verified","command":"targeted"}', encoding="utf-8")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify_begin.extras["attempt_id"]),
        status="verified",
        verification_summary_file="verification-summary-input.json",
    )

    assert completed.status == "ok"
    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(verify_begin.extras["attempt_id"]))
    summary_ref = next(ref for ref in refs if ref["kind"] == "verification_summary")
    assert repo.joinpath(summary_ref["path"]).read_text(encoding="utf-8") == summary_path.read_text(encoding="utf-8")
    assert summary_ref["content_hash"]
    verification = store.verifications_for_attempt(int(verify_begin.extras["attempt_id"]))[0]
    assert verification["status"] == "passed"
    assert verification["summary_ref"] == summary_ref["path"]


def test_claude_code_host_verify_completion_missing_summary_file_keeps_attempt_running(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    build_begin = run_stage(repo, "do", task_id="T1", action="begin")
    _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")

    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(verify_begin.extras["attempt_id"]),
        status="verified",
        verification_summary_file="missing-summary.json",
    )

    assert completed.status == "failed"
    assert completed.errors == ["missing_verification_summary_file"]
    store = SQLiteStore(repo)
    attempt = store.attempt(int(verify_begin.extras["attempt_id"]))
    assert attempt is not None
    assert attempt["status"] == "running"
    findings = store.findings(int(attempt["branch_session_id"]))
    assert not findings

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

    build_ok = _complete_build_with_passed_review(repo, build_begin.extras["attempt_id"])
    assert build_ok.status == "ok"

    verify_begin = run_stage(repo, "do", task_id="T2", action="begin")
    verify_wrong = run_stage(repo, "do", action="complete", attempt_id=str(verify_begin.extras["attempt_id"]), status="implemented")
    assert verify_wrong.status == "failed"
    assert verify_wrong.errors == ["invalid_completion_status"]


def test_claude_code_host_runtime_rejects_duplicate_complete(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    attempt_id = str(begin.extras["attempt_id"])
    first = _complete_build_with_passed_review(repo, attempt_id)
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

    other_task = run_stage(repo, "do", task_id="T2", action="begin")
    assert other_task.status == "blocked"
    assert other_task.recommended_next == "/loom-do T1"

    retry = run_stage(repo, "do", task_id="T1", action="begin")
    assert retry.status == "ok"
    assert retry.extras["attempt_no"] == 2

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    findings = store.findings(int(session["id"]))
    assert all(finding["status"] != "open" for finding in findings if finding["kind"] == "execution_blocked")


def test_claude_code_host_runtime_rejects_cross_branch_attempt_completion(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    begin = run_stage(repo, "do", task_id="T1", action="begin")

    _register_host_artifacts(repo, "other")
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
    assert drifted.errors == ["task_changed_during_attempt"]
    store = SQLiteStore(repo)
    attempt = store.attempt(int(begin.extras["attempt_id"]))
    assert attempt is not None
    assert attempt["status"] == "running"
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    assert "git_status_complete" not in {ref["kind"] for ref in refs}


def test_claude_code_host_runtime_can_begin_new_attempt_after_running_task_drift(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    first_begin = run_stage(repo, "do", task_id="T1", action="begin")
    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("T1:", "T1: changed ", 1), encoding="utf-8")

    drifted_complete = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(first_begin.extras["attempt_id"]),
        status="implemented",
    )
    second_begin = run_stage(repo, "do", task_id="T1", action="begin")

    assert drifted_complete.status == "failed"
    assert second_begin.status == "ok"
    assert second_begin.extras["attempt_id"] != first_begin.extras["attempt_id"]
    assert second_begin.extras["attempt_no"] == 2

    store = SQLiteStore(repo)
    first_attempt = store.attempt(int(first_begin.extras["attempt_id"]))
    second_attempt = store.attempt(int(second_begin.extras["attempt_id"]))
    assert first_attempt is not None
    assert second_attempt is not None
    assert first_attempt["status"] == "running"
    assert second_attempt["status"] == "running"


def test_claude_code_host_removed_running_task_does_not_block_other_task_begin(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    first_begin = run_stage(repo, "do", task_id="T1", action="begin")
    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        "# Tasks\n\n"
        "- [ ] T2: Verify host task\n"
        "  - Lane: verify\n"
        "  - Complexity: non-trivial\n"
        "  - Revision: 1\n",
        encoding="utf-8",
    )

    other_begin = run_stage(repo, "do", task_id="T2", action="begin")

    assert other_begin.status == "ok"
    assert other_begin.extras["task_id"] == "T2"
    store = SQLiteStore(repo)
    first_attempt = store.attempt(int(first_begin.extras["attempt_id"]))
    assert first_attempt is not None
    assert first_attempt["status"] == "running"


def test_claude_code_host_runtime_does_not_persist_legacy_evidence(tmp_path):
    repo = _prepare_host_repo(tmp_path)
    (repo / "untracked-note.txt").write_text("SENTINEL_UNTRACKED_CONTENT", encoding="utf-8")

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    completed = run_stage(repo, "do", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="blocked")

    assert completed.status == "blocked"

    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    kinds = {ref["kind"] for ref in refs}
    assert {"diff", "change_inventory", "git_status_begin", "git_status_complete"}.isdisjoint(kinds)
    run_dir = repo / ".loom" / "runs" / "master"
    assert not list(run_dir.glob("*-diff.patch"))
    assert not list(run_dir.glob("*-attempt-diff.patch"))
    assert not list(run_dir.glob("*-change-inventory.json"))
    assert not list(run_dir.glob("*-git-status-begin.json"))
    assert not list(run_dir.glob("*-git-status-complete.json"))


def test_claude_code_host_runtime_skips_empty_evidence_files(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    completed = run_stage(repo, "do", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="blocked")

    assert completed.status == "blocked"

    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    assert refs == []

def test_claude_code_host_runtime_writes_explicit_non_empty_logs(tmp_path, monkeypatch):
    repo = _prepare_host_repo(tmp_path)

    def fake_run(command, cwd=None, capture_output=False, text=False):
        return subprocess.CompletedProcess(command, 0, "", "")

    begin = run_stage(repo, "do", task_id="T1", action="begin")
    monkeypatch.setattr("codeloom.app.stages.subprocess.run", fake_run)
    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(begin.extras["attempt_id"]),
        status="blocked",
        stdout="explicit stdout",
        stderr="explicit stderr",
    )
    assert completed.status == "blocked"

    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    kinds = {ref["kind"] for ref in refs}
    assert {"stdout", "stderr"}.issubset(kinds)
    assert {"diff", "change_inventory", "git_status_begin", "git_status_complete"}.isdisjoint(kinds)
    for ref in refs:
        if ref["kind"] in {"stdout", "stderr"}:
            assert repo.joinpath(ref["path"]).read_text(encoding="utf-8") == f"explicit {ref['kind']}"

def test_ship_records_evidence_integrity_gap_for_drifted_runtime_ref(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, test_command="python --version")

    run_stage(repo, "spec")
    run_stage(repo, "plan")
    run_stage(repo, "tasks")
    run_stage(repo, "do", task_id="T1")
    run_stage(repo, "do", task_id="T2")

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    attempts = store.attempts(int(session["id"]))
    verify_attempt = next(attempt for attempt in attempts if attempt["task_id"] == "T2")
    ref = next(ref for ref in store.runtime_refs(int(verify_attempt["id"])) if ref["kind"] == "stdout")
    repo.joinpath(ref["path"]).write_text("drifted", encoding="utf-8")

    ship = run_stage(repo, "ship")

    assert ship.status == "blocked"
    session = store.branch_session("master")
    assert session is not None
    findings = store.findings(int(session["id"]))
    assert findings[-1]["kind"] == "evidence_integrity_gap"
    release = repo.joinpath("specs", "master", "release.md").read_text(encoding="utf-8")
    assert "### 4.1 Not Verified / Readiness Blockers" in release
    assert "runtime ref hash mismatch" in release
    assert "## 6.1 Attempt Changes / Runtime Evidence" in release
    assert ref["path"] in release


def test_claude_code_host_runtime_redoes_task_after_fingerprint_change_without_rewriting_old_attempt(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    first_begin = run_stage(repo, "do", task_id="T1", action="begin")
    first_attempt_id = first_begin.extras["attempt_id"]
    first_complete = _complete_build_with_passed_review(repo, first_attempt_id)
    assert first_complete.status == "ok"

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("  - Complexity: small\n", "  - Complexity: small\n  - Revision: 2\n", 1),
        encoding="utf-8",
    )

    second_begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert second_begin.status == "ok"
    assert second_begin.extras["attempt_id"] != first_attempt_id
    assert second_begin.extras["attempt_no"] == 2

    second_complete = _complete_build_with_passed_review(repo, second_begin.extras["attempt_id"])
    assert second_complete.status == "ok"

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    t1_attempts = [attempt for attempt in store.attempts(int(session["id"])) if attempt["task_id"] == "T1"]
    assert [attempt["status"] for attempt in t1_attempts] == ["implemented", "implemented"]


def test_tasks_registration_recommends_ship_when_revisions_unchanged_and_tasks_completed(tmp_path):
    repo = _prepare_host_repo(tmp_path)

    t1_begin = run_stage(repo, "do", task_id="T1", action="begin")
    assert _complete_build_with_passed_review(repo, t1_begin.extras["attempt_id"]).status == "ok"
    t2_begin = run_stage(repo, "do", task_id="T2", action="begin")
    assert run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(t2_begin.extras["attempt_id"]),
        status="verified",
        summary="verified",
    ).status == "ok"

    tasks_path = repo / "specs" / "master" / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8")
        + "\n\n## 6. Task Notes\n\n### T1: Build host task\n\n- Note: non-semantic evidence prose update\n",
        encoding="utf-8",
    )

    registered = run_stage(repo, "tasks", artifact_file="specs/master/tasks.md")

    assert registered.status == "ok"
    assert registered.recommended_next == "/loom-ship"
    assert registered.recommended_task_id is None


def test_artifact_drift_finding_resolves_after_artifact_registration(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _write_host_spec(repo)
    run_stage(repo, "spec", artifact_file="specs/master/spec.md")

    spec_path = repo / "specs" / "master" / "spec.md"
    spec_path.write_text("# Spec\n\n## Requirement\nChanged outside registration\n", encoding="utf-8")

    run_stage(repo, "plan")

    store = SQLiteStore(repo)
    session = store.branch_session("master")
    assert session is not None
    findings = store.findings(int(session["id"]))
    drift = next(finding for finding in findings if finding["kind"] == "artifact_drift")
    assert drift["status"] == "open"

    registered = run_stage(repo, "spec", artifact_file="specs/master/spec.md")

    assert registered.status == "ok"
    findings = store.findings(int(session["id"]))
    drift = next(finding for finding in findings if finding["kind"] == "artifact_drift")
    assert drift["status"] == "resolved"