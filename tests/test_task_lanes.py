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


def test_parse_tasks_revision_changes_fingerprint_but_notes_do_not():
    original = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Notes: initial context
"""
    )[0]
    notes_changed = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Notes: expanded context
"""
    )[0]
    revision_changed = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 2
  - Notes: expanded context
"""
    )[0]

    assert original.revision == "1"
    assert notes_changed.fingerprint == original.fingerprint
    assert revision_changed.fingerprint != original.fingerprint


def test_parse_tasks_missing_revision_matches_explicit_revision_one():
    implicit = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
"""
    )[0]
    explicit = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
"""
    )[0]

    assert implicit.revision == "1"
    assert explicit.revision == "1"
    assert implicit.fingerprint == explicit.fingerprint


def test_parse_tasks_ignores_revision_in_later_task_notes():
    checklist_revision = parse_tasks(
        """# Tasks

## 5. Task List

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 1

## 6. Task Notes

### T1: Build behavior

- Revision: 9
- Notes: human-only context changed
"""
    )[0]
    notes_revision_changed = parse_tasks(
        """# Tasks

## 5. Task List

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 1

## 6. Task Notes

### T1: Build behavior

- Revision: 10
- Notes: human-only context changed again
"""
    )[0]

    assert checklist_revision.revision == "1"
    assert notes_revision_changed.revision == "1"
    assert checklist_revision.fingerprint == notes_revision_changed.fingerprint


def test_parse_tasks_missing_immediate_metadata_ignores_later_task_notes_metadata():
    tasks = parse_tasks(
        """# Tasks

## 5. Task List

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small

- [ ] T2: Verify behavior

## 6. Task Notes

### T2: Verify behavior

- Lane: build
- Complexity: non-trivial
- Revision: 9
"""
    )

    assert [(task.task_id, task.lane, task.complexity, task.revision) for task in tasks] == [
        ("T1", "build", "small", "1"),
        ("T2", "verify", "small", "1"),
    ]


def test_parse_tasks_uses_first_revision_metadata_when_duplicated():
    task = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 2
  - Revision: 3
"""
    )[0]

    assert task.revision == "2"


def test_parse_tasks_revision_token_is_exact_contract_value():
    revision_one = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
"""
    )[0]
    revision_zero_padded = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 01
"""
    )[0]
    revision_named = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: v2
"""
    )[0]

    assert revision_zero_padded.revision == "01"
    assert revision_named.revision == "v2"
    assert revision_zero_padded.fingerprint != revision_one.fingerprint
    assert revision_named.fingerprint != revision_one.fingerprint


def test_parse_tasks_title_and_lane_changes_fingerprint():
    original = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
"""
    )[0]
    title_changed = parse_tasks(
        """# Tasks

- [ ] T1: Build changed behavior
  - Lane: build
  - Complexity: small
  - Revision: 1
"""
    )[0]
    lane_changed = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: verify
  - Complexity: small
  - Revision: 1
"""
    )[0]

    assert title_changed.fingerprint != original.fingerprint
    assert lane_changed.fingerprint != original.fingerprint

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

    assert small.revision == "1"
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

    assert [(task.task_id, task.lane, task.complexity, task.revision) for task in tasks] == [
        ("T1", "build", "trivial", "1"),
        ("T2", "verify", "small", "1"),
    ]


def test_attempt_status_uses_lane_success_semantics():
    assert attempt_status("build", True, False) == "implemented"
    assert attempt_status("verify", True, False) == "verified"
    assert attempt_status("build", False, False) == "failed"
    assert attempt_status("verify", True, True) == "failed"
