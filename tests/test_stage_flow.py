from __future__ import annotations

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
        "  - Covered by: T2\n\n"
        "## verify\n\n"
        "- [ ] T2: Verify host task\n"
        "  - Lane: verify\n"
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


def _prepare_host_repo(tmp_path):
    repo = init_repo(tmp_path)
    write_project_config(repo, runtime="claude-code")
    _register_host_artifacts(repo)
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
    assert [ref["kind"] for ref in t1_refs] == ["diff", "stdout"]
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


def test_claude_code_host_runtime_skips_empty_evidence_files(tmp_path, monkeypatch):
    repo = _prepare_host_repo(tmp_path)

    def fake_run(command, cwd=None, capture_output=False, text=False):
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("codeloom.app.stages.subprocess.run", fake_run)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    completed = run_stage(repo, "do", action="complete", attempt_id=str(begin.extras["attempt_id"]), status="implemented")
    assert completed.status == "ok"

    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    assert refs == []
    runs_dir = repo / ".loom" / "runs" / "master"
    assert not list(runs_dir.glob("T1-a001-*"))


def test_claude_code_host_runtime_writes_explicit_non_empty_logs(tmp_path, monkeypatch):
    repo = _prepare_host_repo(tmp_path)

    def fake_run(command, cwd=None, capture_output=False, text=False):
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("codeloom.app.stages.subprocess.run", fake_run)
    begin = run_stage(repo, "do", task_id="T1", action="begin")
    completed = run_stage(
        repo,
        "do",
        action="complete",
        attempt_id=str(begin.extras["attempt_id"]),
        status="implemented",
        stdout="explicit stdout",
        stderr="explicit stderr",
    )
    assert completed.status == "ok"

    store = SQLiteStore(repo)
    refs = store.runtime_refs(int(begin.extras["attempt_id"]))
    assert [ref["kind"] for ref in refs] == ["stdout", "stderr"]
    for ref in refs:
        assert repo.joinpath(ref["path"]).read_text(encoding="utf-8") == f"explicit {ref['kind']}"

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
