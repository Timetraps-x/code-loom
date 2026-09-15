from __future__ import annotations

from codeloom.kernel.artifacts import TaskPacket, parse_tasks, task_identity_errors, task_relation_errors
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


def test_parse_tasks_raw_includes_inline_task_context_but_not_later_reader_notes():
    task = parse_tasks(
        """# Tasks

- [ ] T1: Establish shared state
  - Lane: build
  - Complexity: non-trivial
  - Revision: 1
  - Context: `C:fulfillment` through `D:fulfillment-state`.
  - Implementation direction: services/fulfillment.py:transition; critical path before T2.
  - Boundaries: preserve the idempotency invariant; stop after the state transition exists.
  - Handoff: Covered by T2 for repeated submission and downstream consumption.

## Optional Reader Notes

- Context: this must not be passed to Do.
"""
    )[0]

    assert "C:fulfillment" in task.raw
    assert "D:fulfillment-state" in task.raw
    assert "critical path before T2" in task.raw
    assert "Optional Reader Notes" not in task.raw
    assert task.lane == "build"
    assert task.complexity == "non-trivial"
    assert task.revision == "1"


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


def test_task_packet_round_trips_canonical_execution_context():
    task = parse_tasks(
        """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Complexity: non-trivial
  - Revision: 3
  - Context: `C:orders` through `D:order-state`.
  - Boundaries: Preserve idempotency.
  - Suggested validation: Run the focused order test.
"""
    )[0]
    packet = TaskPacket.from_task(task)
    restored = TaskPacket.from_canonical_json(packet.canonical_json())

    assert restored == packet
    assert packet.payload()["fields"] == {
        "boundaries": ["Preserve idempotency."],
        "complexity": ["non-trivial"],
        "context": ["`C:orders` through `D:order-state`."],
        "lane": ["build"],
        "revision": ["3"],
        "suggested validation": ["Run the focused order test."],
    }
    assert packet.content_hash


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
    assert TaskPacket.from_task(notes_changed).content_hash != TaskPacket.from_task(original).content_hash


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


def test_task_identity_diagnostics_preserve_tolerant_missing_metadata():
    content = """# Tasks

## build

- [ ] T1: Build behavior

- [ ] T2: Verify behavior
"""

    assert task_identity_errors(content) == []
    assert [(task.task_id, task.lane, task.complexity, task.revision) for task in parse_tasks(content)] == [
        ("T1", "build", "small", "1"),
        ("T2", "build", "small", "1"),
    ]


def test_task_identity_diagnostics_reject_duplicate_ids_and_invalid_explicit_values():
    content = """# Tasks

- [ ] T1: Build behavior
  - Lane: review
  - Complexity: M
  - Revision:

- [ ] T1: Duplicate behavior
  - Lane: build later
  - Complexity: non-trivial later
  - Revision: two words
"""

    assert set(task_identity_errors(content)) == {
        "duplicate_task_id:T1",
        "invalid_task_lane:T1:review",
        "invalid_task_complexity:T1:M",
        "invalid_task_revision:T1:<empty>",
        "invalid_task_lane:T1:build later",
        "invalid_task_complexity:T1:non-trivial later",
        "invalid_task_revision:T1:two words",
    }


def test_task_identity_diagnostics_reject_conflicting_immediate_metadata():
    content = """# Tasks

- [ ] T1: Build behavior
  - Lane: build
  - Lane: verify
  - Complexity: small
  - Complexity: non-trivial
  - Revision: 1
  - Revision: v2
"""

    assert task_identity_errors(content) == [
        "conflicting_task_lane:T1",
        "conflicting_task_complexity:T1",
        "conflicting_task_revision:T1",
    ]


def test_task_identity_diagnostics_allow_identical_metadata_and_revision_tokens():
    content = """# Tasks

- [ ] T1: Build behavior
  - Lane: BUILD
  - Lane: build
  - Complexity: small
  - Complexity: SMALL
  - Revision: v2
  - Revision: v2

- [ ] T2: Verify behavior
  - Lane: verify
  - Complexity: non-trivial
  - Revision: 01
"""

    assert task_identity_errors(content) == []


def test_parse_tasks_captures_serial_and_verification_relations():
    tasks = parse_tasks(
        """# Tasks

- [ ] T1: Build state
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Depends on: None
  - Covered by: T3

- [ ] T2: Build independent report
  - Lane: build
  - Complexity: small
  - Revision: 1
  - Depends on: None
  - Covered by: T3

- [ ] T3: Verify results
  - Lane: verify
  - Complexity: small
  - Revision: 1
  - Depends on: T1, T2
  - Validates: T1, T2
"""
    )

    assert tasks[0].depends_on == ()
    assert tasks[0].covered_by == ("T3",)
    assert tasks[1].depends_on == ()
    assert tasks[2].depends_on == ("T1", "T2")
    assert tasks[2].validates == ("T1", "T2")
    assert all(task.relations_declared for task in tasks)
    packet = TaskPacket.from_task(tasks[2])
    assert TaskPacket.from_canonical_json(packet.canonical_json()) == packet
    assert packet.payload()["validates"] == ["T1", "T2"]


def test_task_relation_diagnostics_reject_invalid_graph_references():
    content = """# Tasks

- [ ] T1: Build state
  - Lane: build
  - Depends on: T2
  - Covered by: T2

- [ ] T2: Verify state
  - Lane: verify
  - Depends on: T1, T1
  - Validates: T9
"""

    errors = set(task_relation_errors(content))
    assert "unordered_task_relation:T1:depends_on:T2" in errors
    assert "duplicate_task_relation:T2:depends_on:T1" in errors
    assert "dangling_task_relation:T2:validates:T9" in errors
    assert "task_coverage_mismatch:T1:T2" in errors


def test_task_relation_diagnostics_allow_relationless_legacy_tasks():
    content = """# Tasks

- [ ] T1: Build state
  - Lane: build

- [ ] T2: Verify state
  - Lane: verify
"""

    assert task_relation_errors(content) == []


def test_task_relation_diagnostics_reject_duplicate_and_conflicting_fields():
    content = """# Tasks

- [ ] T1: Build state
  - Lane: build
  - Depends on: None
  - Depends on: T2
  - Covered by: T2

- [ ] T2: Verify state
  - Lane: verify
  - Depends on: T1
  - Validates: T1
"""

    errors = set(task_relation_errors(content))
    assert "duplicate_task_relation_field:T1:depends_on" in errors
    assert "conflicting_task_relation:T1:depends_on" in errors
