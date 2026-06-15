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


def test_attempt_status_uses_lane_success_semantics():
    assert attempt_status("build", True, False) == "implemented"
    assert attempt_status("verify", True, False) == "verified"
    assert attempt_status("build", False, False) == "failed"
    assert attempt_status("verify", True, True) == "failed"
