from __future__ import annotations

from codeloom.kernel.artifacts import parse_tasks
from codeloom.kernel.attempts import attempt_status


def test_parse_tasks_reads_explicit_and_section_lanes():
    tasks = parse_tasks(
        """# Tasks

## build

- [ ] T1: Implement thing
  - Covered by: T2

## verify

- [ ] T2: Check thing
  - Lane: verify
  - Validates: T1
"""
    )

    assert [(task.task_id, task.lane) for task in tasks] == [("T1", "build"), ("T2", "verify")]
    assert [task.complexity for task in tasks] == ["small", "small"]


def test_parse_tasks_defaults_to_build_but_detects_verify_titles():
    tasks = parse_tasks(
        """# Tasks

- [ ] T1: Update behavior
- [ ] T2: Verify behavior
"""
    )

    assert [(task.task_id, task.lane) for task in tasks] == [("T1", "build"), ("T2", "verify")]


def test_parse_tasks_raw_includes_task_notes():
    tasks = parse_tasks(
        """# Tasks

- [ ] T1: Build marker
  - Lane: build
  - Notes: preserve boundary context
"""
    )

    assert "Notes: preserve boundary context" in tasks[0].raw


def test_parse_tasks_reads_complexity_and_defaults_to_small():
    tasks = parse_tasks(
        """# Tasks

- [ ] T1: Build small slice
  - Lane: build
  - Complexity: trivial

- [ ] T2: Verify impacted flow
  - Lane: verify
  - Complexity: non-trivial

- [ ] T3: Build legacy default
  - Lane: build
"""
    )

    assert [(task.task_id, task.complexity) for task in tasks] == [
        ("T1", "trivial"),
        ("T2", "non-trivial"),
        ("T3", "small"),
    ]


def test_parse_tasks_complexity_changes_fingerprint():
    small = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
"""
    )[0]
    non_trivial = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: non-trivial
"""
    )[0]

    assert small.fingerprint != non_trivial.fingerprint


def test_parse_tasks_prefers_checklist_adjacent_metadata_over_later_task_notes():
    tasks = parse_tasks(
        """# Tasks

## 5. Task List

- [ ] T1: Build thing
  - Lane: build
  - Complexity: trivial

- [ ] T2: Verify thing
  - Lane: verify
  - Complexity: small

## 6. Task Notes

### T1: Build thing

- Lane: build
- Complexity: trivial

### T2: Verify thing

- Lane: build
- Complexity: non-trivial
"""
    )

    assert [(task.task_id, task.lane, task.complexity) for task in tasks] == [
        ("T1", "build", "trivial"),
        ("T2", "verify", "small"),
    ]


def test_parse_tasks_does_not_read_later_task_notes_as_metadata():
    tasks = parse_tasks(
        """# Tasks

## 5. Task List

- [ ] T1: Build thing
  - Lane: build
  - Complexity: trivial

- [ ] T2: Verify thing

## 6. Task Notes

### T1: Build thing

- Lane: build
- Complexity: trivial
"""
    )

    assert [(task.task_id, task.lane, task.complexity) for task in tasks] == [
        ("T1", "build", "trivial"),
        ("T2", "verify", "small"),
    ]


def test_attempt_status_uses_lane_success_semantics():
    assert attempt_status("build", True, False) == "implemented"
    assert attempt_status("verify", True, False) == "verified"
    assert attempt_status("build", False, False) == "failed"
    assert attempt_status("verify", True, True) == "failed"
