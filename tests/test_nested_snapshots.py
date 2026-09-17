from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

from codeloom.app import stages
from codeloom.app.init_project import load_project_config
from codeloom.kernel.snapshots import capture_repository_snapshot
from codeloom.persistence.sqlite import SQLiteStore
from tests.helpers import run_stage
from tests.test_stage_flow import _init_git_repo, _commit_all, _prepare_host_repo


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True).stdout


def repository(root, *, unborn=False):
    root.mkdir(parents=True, exist_ok=True)
    _init_git_repo(root)
    (root / "source.txt").write_text("before\n", encoding="utf-8")
    if not unborn:
        _commit_all(root)
    return root


def snapshot(root, roots=(".", "child")):
    result = capture_repository_snapshot(root, roots)
    assert not result["errors"], result
    return result


def configure(root, roots):
    path = root / ".loom/project.yml"
    text = path.read_text(encoding="utf-8").split("\ngit:", 1)[0]
    path.write_text(text + "\ngit:\n  repositories:\n" + "".join(f'    - "{item}"\n' for item in roots), encoding="utf-8")


def test_nested_content_diff_is_frozen_without_changing_real_indexes(tmp_path):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    sibling = repository(root / "another repo")
    roots = (".", "child", "another repo")
    (child / "source.txt").write_text("preexisting\n", encoding="utf-8")
    indexes = {repo: (repo / ".git/index").read_bytes() for repo in (root, child, sibling)}
    heads = {repo: git(repo, "rev-parse", "HEAD") for repo in indexes}
    first = snapshot(root, roots)
    (child / "source.txt").write_text("after\n", encoding="utf-8")
    (child / "new.txt").write_text("new\n", encoding="utf-8")
    git(child, "add", "new.txt")
    indexes[child] = (child / ".git/index").read_bytes()
    (sibling / "source.txt").unlink()
    second = snapshot(root, roots)
    assert snapshot(root, roots)["tree"] == second["tree"]
    patch = git(root, "diff", first["tree"], second["tree"]).decode()
    assert "child/source.txt" in patch and "-preexisting" in patch and "+after" in patch
    assert "child/new.txt" in patch and "another repo/source.txt" in patch
    for repo in indexes:
        assert (repo / ".git/index").read_bytes() == indexes[repo]
        assert git(repo, "rev-parse", "HEAD") == heads[repo]
    child.rename(root / "moved-child")
    assert git(root, "diff", first["tree"], second["tree"]).decode() == patch


def test_explicit_ignored_child_uses_own_ignore_and_attributes(tmp_path):
    root = repository(tmp_path / "project")
    (root / ".gitignore").write_text("child/\n", encoding="utf-8")
    child = repository(root / "child")
    (child / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (child / "ignored.txt").write_text("private", encoding="utf-8")
    (child / ".gitattributes").write_text("*.txt text eol=lf\n", encoding="utf-8")
    (child / "source.txt").write_bytes(b"normalized\r\n")
    result = snapshot(root)
    assert git(root, "show", result["tree"] + ":child/source.txt") == b"normalized\n"
    paths = git(root, "ls-tree", "-r", "--name-only", result["tree"])
    assert b"child/ignored.txt" not in paths


def test_deep_nested_and_unborn_repository(tmp_path):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    repository(child / "inner", unborn=True)
    result = snapshot(root, (".", "child", "child/inner"))
    assert git(root, "show", result["tree"] + ":child/inner/source.txt") == b"before\n"


@pytest.mark.parametrize("roots, error", [
    ((), "scope is empty"), (("child",), "outer project Git root"),
    ((".", "../outside"), "escapes project"), ((".", "/absolute"), "escapes project"),
    ((".", "C:/outside"), "escapes project"), ((".", "missing"), "missing"),
    ((".", "ordinary"), "not a Git root"), ((".", ""), "nonempty"),
])
def test_invalid_roots_fail_explicitly(tmp_path, roots, error):
    root = repository(tmp_path / "project")
    repository(root / "child")
    (root / "ordinary").mkdir()
    result = capture_repository_snapshot(root, roots)
    assert error in " ".join(result["errors"])
    assert "tree" not in result


def test_tracked_gitlink_is_not_silently_flattened(tmp_path):
    root = repository(tmp_path / "project")
    repository(root / "child")
    git(root, "add", "child")
    result = capture_repository_snapshot(root, (".", "child"))
    assert "tracked gitlink" in " ".join(result["errors"])


def test_overlapping_tracking_is_not_silently_replaced(tmp_path):
    root = repository(tmp_path / "project")
    (root / "child").mkdir()
    (root / "child/source.txt").write_text("outer", encoding="utf-8")
    _commit_all(root)
    repository(root / "child")
    result = capture_repository_snapshot(root, (".", "child"))
    assert "overlapping tracked ownership" in " ".join(result["errors"])


def test_snapshot_ignores_inherited_git_routing(tmp_path, monkeypatch):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    monkeypatch.setenv("GIT_DIR", str(child / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "wrong-index"))
    assert not capture_repository_snapshot(root, (".", "child"))["errors"]
    assert not (tmp_path / "wrong-index").exists()


def test_configuration_parses_scope_without_rewriting_other_fields(tmp_path):
    root = _prepare_host_repo(tmp_path)
    configure(root, (".", "some repo"))
    config = load_project_config(root)
    assert config.git_repositories == (".", "some repo")
    assert not config.git_repositories_error
    assert config.default_runtime == "claude-code"


@pytest.mark.parametrize("value", ["[]", "[., child]", "child"])
def test_inline_repository_config_fails_before_attempt(tmp_path, value):
    root = _prepare_host_repo(tmp_path)
    path = root / ".loom/project.yml"
    path.write_text(path.read_text(encoding="utf-8") + f"\ngit:\n  repositories: {value}\n", encoding="utf-8")
    assert load_project_config(root).git_repositories_error
    begin = run_stage(root, "do", action="begin", task_id="T1")
    assert begin.status == "blocked"
    assert SQLiteStore(root).active_attempt(int(SQLiteStore(root).branch_session("master")["id"])) is None


def test_attempt_scope_is_frozen_and_child_edits_invalidate_review(tmp_path):
    root = _prepare_host_repo(tmp_path)
    child = repository(root / "child")
    configure(root, (".", "child"))
    begin = run_stage(root, "do", action="begin", task_id="T1")
    assert begin.status == "ok", begin
    attempt_id = begin.extras["attempt_id"]
    store = SQLiteStore(root)
    frozen = json.loads(store.attempt(attempt_id)["snapshot_repositories_json"])
    assert frozen == {"version": 1, "roots": [".", "child"]}
    configure(root, (".", "now-missing"))
    (child / "source.txt").write_text("implementation\n", encoding="utf-8")
    seal = run_stage(root, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert seal.status == "ok", seal
    assert seal.extras["sealed_changes"]["repositories"] == frozen
    assert any(item["path"] == "child/source.txt" for item in seal.extras["sealed_changes"]["files"])
    review = run_stage(root, "do", action="record-review", attempt_id=str(attempt_id),
                       seal_revision=str(seal.extras["seal_revision"]), status="pass", review_summary="reviewed")
    assert review.status == "ok"
    (child / "source.txt").write_text("after review\n", encoding="utf-8")
    complete = run_stage(root, "do", action="complete", attempt_id=str(attempt_id), status="implemented")
    assert complete.errors == ["sealed_changes_stale"]
    reseal = run_stage(root, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert reseal.extras["seal_revision"] == 2
    assert run_stage(root, "do", action="record-review", attempt_id=str(attempt_id),
                     seal_revision="2", status="pass", review_summary="reviewed again").status == "ok"
    assert run_stage(root, "do", action="complete", attempt_id=str(attempt_id), status="implemented").status == "ok"
    assert not list((root / ".loom/runs/master").glob("*"))


def test_legacy_attempt_does_not_switch_snapshot_semantics(tmp_path):
    root = _prepare_host_repo(tmp_path)
    begin = run_stage(root, "do", action="begin", task_id="T1")
    configure(root, (".", "missing"))
    attempt_id = begin.extras["attempt_id"]
    assert SQLiteStore(root).attempt(attempt_id)["snapshot_repositories_json"] is None
    seal = run_stage(root, "do", action="seal-changes", attempt_id=str(attempt_id))
    assert seal.status == "ok"
    assert seal.extras["sealed_changes"]["snapshot_semantics"] == "working_tree_content"


def test_diff_failure_does_not_record_successful_seal(tmp_path, monkeypatch):
    root = _prepare_host_repo(tmp_path)
    begin = run_stage(root, "do", action="begin", task_id="T1")
    monkeypatch.setattr(stages, "_git_diff_z", lambda *args: ("", "missing object"))
    seal = run_stage(root, "do", action="seal-changes", attempt_id=str(begin.extras["attempt_id"]))
    assert seal.errors == ["sealed_diff_generation_failed"]
    assert SQLiteStore(root).attempt(begin.extras["attempt_id"])["latest_sealed_tree"] is None


def test_schema_12_upgrade_adds_nullable_scope_without_changing_attempt(tmp_path):
    root = _prepare_host_repo(tmp_path)
    begin = run_stage(root, "do", action="begin", task_id="T1")
    store = SQLiteStore(root)
    before = store.attempt(begin.extras["attempt_id"])
    with store.connect() as connection:
        connection.execute("ALTER TABLE attempts DROP COLUMN snapshot_repositories_json")
        connection.execute("PRAGMA user_version = 12")
    store.initialize()
    store.initialize()
    after = store.attempt(begin.extras["attempt_id"])
    assert before == after

def test_force_added_ignored_file_is_captured_and_changes_tree(tmp_path):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    (child / ".gitignore").write_text("generated.txt\n", encoding="utf-8")
    (child / "generated.txt").write_text("staged\n", encoding="utf-8")
    git(child, "add", "-f", "generated.txt")
    index = (child / ".git/index").read_bytes()
    first = snapshot(root)
    assert git(root, "show", first["tree"] + ":child/generated.txt") == b"staged\n"
    (child / "generated.txt").write_text("unstaged change\n", encoding="utf-8")
    second = snapshot(root)
    assert first["tree"] != second["tree"]
    assert (child / ".git/index").read_bytes() == index


@pytest.mark.parametrize("to_directory", [True, False])
def test_staged_file_directory_transition(tmp_path, to_directory):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    path = child / "switch"
    if to_directory:
        path.write_text("old\n", encoding="utf-8")
    else:
        path.mkdir()
        (path / "nested").write_text("old\n", encoding="utf-8")
    _commit_all(child)
    first = snapshot(root)
    git(child, "rm", "-r", "switch")
    if to_directory:
        path.mkdir()
        (path / "nested").write_text("new\n", encoding="utf-8")
    else:
        path.write_text("new\n", encoding="utf-8")
    git(child, "add", "switch")
    index = (child / ".git/index").read_bytes()
    second = snapshot(root)
    assert first["tree"] != second["tree"]
    assert (child / ".git/index").read_bytes() == index


def test_removed_from_index_and_ignored_is_not_recaptured(tmp_path):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    (child / ".gitignore").write_text("source.txt\n", encoding="utf-8")
    git(child, "rm", "--cached", "source.txt")
    result = snapshot(root)
    assert b"child/source.txt" not in git(root, "ls-tree", "-r", "--name-only", result["tree"])


def test_diff_uses_same_clean_git_context_as_capture(tmp_path, monkeypatch):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    first = snapshot(root)
    (child / "source.txt").write_text("after\n", encoding="utf-8")
    second = snapshot(root)
    monkeypatch.setenv("GIT_DIR", str(child / ".git"))
    files = stages._diff_name_status(root, first["tree"], second["tree"])
    assert files[0]["path"] == "child/source.txt"


def test_windows_style_executable_and_symlink_modes(tmp_path):
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    git(child, "config", "core.filemode", "false")
    git(child, "update-index", "--chmod=+x", "source.txt")
    git(child, "config", "core.symlinks", "false")
    target = b"../../outside-private-file"
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=child, input=target,
                          check=True, capture_output=True).stdout.decode().strip()
    git(child, "update-index", "--add", "--cacheinfo", f"120000,{blob},link")
    (child / "link").write_bytes(target)
    index = (child / ".git/index").read_bytes()
    result = snapshot(root)
    entries = git(root, "ls-tree", "-r", result["tree"])
    assert b"100755 blob" in entries and b"120000 blob" in entries
    assert git(root, "show", result["tree"] + ":child/link") == target
    assert (child / ".git/index").read_bytes() == index


def test_observed_concurrent_change_rejects_capture(tmp_path, monkeypatch):
    from codeloom.kernel import snapshots
    root = repository(tmp_path / "project")
    child = repository(root / "child")
    original = snapshots._aggregate
    def changing(*args):
        result = original(*args)
        (child / "source.txt").write_text(result["tree"], encoding="utf-8")
        return result
    monkeypatch.setattr(snapshots, "_aggregate", changing)
    assert "changed during capture" in " ".join(capture_repository_snapshot(root, (".", "child"))["errors"])


def test_missing_objects_are_not_an_empty_diff(tmp_path):
    root = repository(tmp_path / "project")
    good = snapshot(root, (".",))["tree"]
    with pytest.raises(ValueError):
        stages._diff_name_status(root, "0" * len(good), good)


def test_mixed_object_formats_fail_explicitly(tmp_path):
    root = repository(tmp_path / "project")
    child = root / "child"
    child.mkdir()
    git(child, "init", "--object-format=sha256")
    result = capture_repository_snapshot(root, (".", "child"))
    assert "mixed Git object formats" in " ".join(result["errors"])