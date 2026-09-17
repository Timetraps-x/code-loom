from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
from tempfile import TemporaryDirectory, TemporaryFile
from typing import Any


_ROUTING_ENV = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX",
    "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS",
    "GIT_ICASE_PATHSPECS",
}


def git_environment(index: Path | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _ROUTING_ENV}
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    return env


def _git(root: Path, *args: str, index: Path | None = None, data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=root, env=git_environment(index), input=data,
        capture_output=True, timeout=120,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"{root}: git {args[0]} failed: {detail}")
    return result.stdout


def _roots(project: Path, repositories: tuple[str, ...]) -> list[str]:
    if not repositories:
        raise ValueError("snapshot repository scope is empty")
    roots: dict[str, str] = {}
    object_format = None
    for value in repositories:
        if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
            raise ValueError("repository paths must be nonempty project-relative paths using forward slashes")
        path = PurePosixPath(value)
        if path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts:
            raise ValueError(f"repository path escapes project: {value}")
        relative = path.as_posix()
        root = project / relative
        if ".git" in path.parts or ".loom" in path.parts:
            raise ValueError(f"repository path is reserved: {value}")
        if not root.is_dir() or root.resolve() != root.absolute():
            raise ValueError(f"repository path is missing or uses a symlink: {value}")
        actual = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
        if actual != root.resolve():
            raise ValueError(f"repository path is not a Git root: {value}")
        fmt = _git(root, "rev-parse", "--show-object-format").strip()
        if object_format is not None and fmt != object_format:
            raise ValueError(f"mixed Git object formats are unsupported: {value}")
        object_format = fmt
        roots[os.path.normcase(str(root))] = relative
    result = sorted(roots.values(), key=lambda item: (len(PurePosixPath(item).parts), item))
    if "." not in result:
        raise ValueError("snapshot repositories must include the outer project Git root '.'")
    return result


def _descendants(relative: str, roots: list[str]) -> list[str]:
    parent = PurePosixPath(relative)
    return [PurePosixPath(item).relative_to(parent).as_posix() for item in roots
            if item != relative and PurePosixPath(item).is_relative_to(parent)]


def _capture_repository(root: Path, children: list[str], index: Path, *, require_head: bool) -> tuple[str, str, list[str]]:
    if _git(root, "ls-files", "--unmerged", "-z"):
        raise ValueError(f"snapshot conflicted index: {root}")
    sparse = subprocess.run(["git", "config", "--bool", "core.sparseCheckout"], cwd=root,
                            env=git_environment(), capture_output=True, timeout=120)
    if sparse.stdout.strip() == b"true":
        raise ValueError(f"snapshot sparse checkout unsupported: {root}")
    head_result = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                                 env=git_environment(), capture_output=True, timeout=120)
    head = head_result.stdout.decode("ascii", errors="replace").strip() if head_result.returncode == 0 else ""
    if not head:
        if require_head:
            raise ValueError(f"snapshot HEAD unavailable: {root}")
        # Only an unborn branch may start empty; corrupt or detached HEAD is not an empty baseline.
        ref = _git(root, "symbolic-ref", "HEAD").decode("utf-8").strip()
        exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref], cwd=root,
                                env=git_environment(), capture_output=True, timeout=120)
        if exists.returncode != 1:
            raise ValueError(f"snapshot HEAD unavailable: {root}")
    tracked = _git(root, "ls-files", "--stage", "-z")
    baseline = _git(root, "ls-tree", "-r", "-z", head) if head else b""
    for entry in (tracked + baseline).split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        path = os.fsdecode(raw_path)
        for child in children:
            if path == child or path.startswith(child + "/"):
                kind = "tracked gitlink" if metadata.startswith(b"160000 ") else "overlapping tracked ownership"
                raise ValueError(f"snapshot {kind} unsupported: {root / child}")
    _git(root, "read-tree", "--empty", index=index)
    if tracked:
        _git(root, "update-index", "-z", "--index-info", index=index, data=tracked)
    exclusions = []
    for child in [".loom", *children]:
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", child],
                                 cwd=root, env=git_environment(), capture_output=True, timeout=120)
        if ignored.returncode not in (0, 1):
            raise ValueError(f"snapshot ignore check failed: {root / child}")
        if ignored.returncode == 1:
            exclusions.append(f":(top,exclude,literal){child}")
    _git(root, "add", "-A", "--", ".", *exclusions, index=index)
    _git(root, "rm", "-r", "--cached", "--ignore-unmatch", "--", ".loom", index=index)
    tree = _git(root, "write-tree", index=index).decode("ascii").strip()
    gitlinks = []
    for entry in _git(root, "ls-tree", "-r", "-z", tree).split(b"\0"):
        if entry.startswith(b"160000 "):
            gitlinks.append(os.fsdecode(entry.split(b"\t", 1)[1]))
    return tree, head, gitlinks


def _import_tree(source: Path, destination: Path, tree: str) -> None:
    # Persist the complete object closure: reviewer commands must not depend on temporary alternates.
    with TemporaryFile() as pack:
        result = subprocess.run(["git", "pack-objects", "--stdout", "--revs"], cwd=source,
                                env=git_environment(), input=(tree + "\n").encode("ascii"),
                                stdout=pack, stderr=subprocess.PIPE, timeout=120)
        if result.returncode:
            raise ValueError(f"snapshot object export failed: {source}: {result.stderr.decode(errors='replace')}")
        pack.seek(0)
        result = subprocess.run(["git", "index-pack", "--stdin"], cwd=destination,
                                env=git_environment(), stdin=pack, capture_output=True, timeout=120)
        if result.returncode:
            raise ValueError(f"snapshot object import failed: {destination}: {result.stderr.decode(errors='replace')}")


def _aggregate(project: Path, roots: list[str]) -> dict[str, Any]:
    with TemporaryDirectory(prefix="codeloom-index-") as directory:
        trees = {}
        heads = {}
        gitlinks = {}
        for number, relative in enumerate(roots):
            root = project / relative
            tree, head, links = _capture_repository(
                root, _descendants(relative, roots), Path(directory) / str(number), require_head=relative == ".",
            )
            trees[relative] = tree
            heads[relative] = head
            gitlinks[relative] = links
            if relative != ".":
                _import_tree(root, project, tree)
        index = Path(directory) / "aggregate"
        _git(project, "read-tree", trees["."], index=index)
        for relative in roots:
            if relative != ".":
                _git(project, "read-tree", f"--prefix={relative}/", trees[relative], index=index)
        tree = _git(project, "write-tree", index=index).decode("ascii").strip()
    return {"tree": tree, "head": heads["."], "status_summary": {
        "repository_heads": heads, "unexpanded_gitlinks": gitlinks,
    }}


def capture_repository_snapshot(project: Path, repositories: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "snapshot_semantics": "repository_content_v1", "modifies_real_index": False,
        "ignored_included": False, "status_summary": {}, "errors": [],
    }
    try:
        project = project.resolve()
        roots = _roots(project, repositories)
        first = _aggregate(project, roots)
        second = _aggregate(project, roots)
        if first["tree"] != second["tree"] or first["status_summary"] != second["status_summary"]:
            raise ValueError("snapshot repositories changed during capture; retry after writers stop")
        result.update(second)
        result["repositories"] = {"version": 1, "roots": roots}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result["errors"].append(str(exc))
    return result
