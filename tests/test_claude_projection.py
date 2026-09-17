from __future__ import annotations

import json
from pathlib import Path


import pytest

from codeloom.app import managed_projection
from codeloom.app.init_project import init_project
from codeloom.app.managed_projection import MANIFEST_PATH, normalized_digest, upgrade_claude_projection


RETIRED_PLAN_AGENT = ".claude/agents/plan-architect.md"
PLAN_ROLE_REFERENCE = ".claude/skills/loom-plan/references/main-role.md"


def _resource_payload(payload, path: str):
    return next(resource for resource in payload["resources"] if resource["path"] == path)


def _register_retired_agent(repo, content: str = "managed owner agent\n"):
    agent_path = repo / RETIRED_PLAN_AGENT
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(content, encoding="utf-8")
    manifest_path = repo / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][RETIRED_PLAN_AGENT] = {
        "group": "agents",
        "source": "codeloom.agents/plan-architect.md",
        "installed_sha256": normalized_digest(content),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return agent_path


def test_fresh_init_registers_role_references_without_owner_agents(tmp_path):
    init_project(tmp_path)

    manifest = json.loads((tmp_path / MANIFEST_PATH).read_text(encoding="utf-8"))

    assert manifest["integration"] == "claude-code"
    assert RETIRED_PLAN_AGENT not in manifest["files"]
    assert ".claude/skills/loom-plan/SKILL.md" in manifest["files"]
    assert PLAN_ROLE_REFERENCE in manifest["files"]
    assert not (tmp_path / RETIRED_PLAN_AGENT).exists()


def test_upgrade_preserves_modified_active_resource(tmp_path):
    init_project(tmp_path)
    role_path = tmp_path / PLAN_ROLE_REFERENCE
    role_path.write_text("custom role\n", encoding="utf-8")

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, PLAN_ROLE_REFERENCE)["status"] == "conflict"
    assert role_path.read_text(encoding="utf-8") == "custom role\n"


def test_upgrade_removes_clean_managed_owner_agent(tmp_path):
    init_project(tmp_path)
    agent_path = _register_retired_agent(tmp_path)

    dry_run = upgrade_claude_projection(tmp_path, dry_run=True)
    assert _resource_payload(dry_run, RETIRED_PLAN_AGENT)["status"] == "removed"
    assert agent_path.exists()

    payload = upgrade_claude_projection(tmp_path)
    assert payload["status"] == "ok"
    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "removed"
    assert not agent_path.exists()
    manifest = json.loads((tmp_path / MANIFEST_PATH).read_text(encoding="utf-8"))
    assert RETIRED_PLAN_AGENT not in manifest["files"]


def test_upgrade_preserves_modified_retired_owner_agent(tmp_path):
    init_project(tmp_path)
    agent_path = _register_retired_agent(tmp_path)
    agent_path.write_text("custom owner agent\n", encoding="utf-8")

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "migration_conflict"
    assert agent_path.read_text(encoding="utf-8") == "custom owner agent\n"


def test_upgrade_removes_exact_legacy_owner_agent(tmp_path, monkeypatch):
    init_project(tmp_path)
    legacy = "legacy owner agent\n"
    agent_path = tmp_path / RETIRED_PLAN_AGENT
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text(legacy, encoding="utf-8")
    monkeypatch.setattr(
        managed_projection,
        "_legacy_hashes",
        lambda: {RETIRED_PLAN_AGENT: {normalized_digest(legacy)}},
    )

    payload = upgrade_claude_projection(tmp_path)

    assert payload["status"] == "ok"
    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "removed"
    assert not agent_path.exists()


def test_upgrade_cleans_missing_retired_agent_manifest_entry(tmp_path):
    init_project(tmp_path)
    agent_path = _register_retired_agent(tmp_path)
    agent_path.unlink()

    payload = upgrade_claude_projection(tmp_path)

    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "removed"
    manifest = json.loads((tmp_path / MANIFEST_PATH).read_text(encoding="utf-8"))
    assert RETIRED_PLAN_AGENT not in manifest["files"]


def test_upgrade_explicitly_removes_modified_retired_agent(tmp_path):
    init_project(tmp_path)
    agent_path = _register_retired_agent(tmp_path)
    agent_path.write_text("custom owner agent\n", encoding="utf-8")

    payload = upgrade_claude_projection(
        tmp_path,
        resolve_bundle_paths={f"{RETIRED_PLAN_AGENT}=remove"},
    )

    assert payload["status"] == "ok"
    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "removed"
    assert not agent_path.exists()


def test_upgrade_does_not_retire_owner_when_replacement_conflicts(tmp_path):
    init_project(tmp_path)
    agent_path = _register_retired_agent(tmp_path)
    (tmp_path / PLAN_ROLE_REFERENCE).write_text("custom role\n", encoding="utf-8")

    payload = upgrade_claude_projection(tmp_path)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, PLAN_ROLE_REFERENCE)["status"] == "conflict"
    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "migration_conflict"
    assert agent_path.exists()


def test_upgrade_restores_missing_role_reference_after_explicit_resolution(tmp_path):
    init_project(tmp_path)
    role_path = tmp_path / PLAN_ROLE_REFERENCE
    role_path.unlink()

    missing = upgrade_claude_projection(tmp_path, dry_run=True)
    assert missing["status"] == "conflict"
    assert _resource_payload(missing, PLAN_ROLE_REFERENCE)["status"] == "missing"

    restored = upgrade_claude_projection(
        tmp_path,
        resolve_bundle_paths={f"{PLAN_ROLE_REFERENCE}=bundle"},
    )
    assert restored["status"] == "ok"
    assert _resource_payload(restored, PLAN_ROLE_REFERENCE)["status"] == "created"
    assert role_path.exists()


def test_upgrade_only_manages_selected_group(tmp_path):
    init_project(tmp_path)
    agent_path = _register_retired_agent(tmp_path)
    skill_path = tmp_path / ".claude" / "skills" / "loom-plan" / "SKILL.md"
    skill_path.write_text("custom skill\n", encoding="utf-8")

    agents = upgrade_claude_projection(tmp_path, group="agents", dry_run=True)
    assert all(resource["group"] == "agents" for resource in agents["resources"])
    assert _resource_payload(agents, RETIRED_PLAN_AGENT)["status"] == "migration_conflict"
    assert agent_path.exists()
    assert skill_path.read_text(encoding="utf-8") == "custom skill\n"

    skills = upgrade_claude_projection(tmp_path, group="skills", dry_run=True)
    assert all(resource["group"] == "skills" for resource in skills["resources"])
    assert all(resource["path"] != RETIRED_PLAN_AGENT for resource in skills["resources"])
    assert agent_path.exists()


def test_upgrade_reports_retired_owner_directory_as_migration_conflict(tmp_path):
    init_project(tmp_path)
    agent_path = tmp_path / RETIRED_PLAN_AGENT
    agent_path.mkdir(parents=True)

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "migration_conflict"
    assert agent_path.is_dir()


def test_upgrade_reports_broken_owner_symlink_as_migration_conflict(tmp_path):
    init_project(tmp_path)
    agent_path = tmp_path / RETIRED_PLAN_AGENT
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        agent_path.symlink_to(tmp_path / "missing-owner-agent.md")
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, RETIRED_PLAN_AGENT)["status"] == "migration_conflict"
    assert agent_path.is_symlink()


def test_upgrade_is_idempotent_after_owner_retirement(tmp_path):
    init_project(tmp_path)
    _register_retired_agent(tmp_path)

    first = upgrade_claude_projection(tmp_path)
    second = upgrade_claude_projection(tmp_path)

    assert first["status"] == "ok"
    assert _resource_payload(first, RETIRED_PLAN_AGENT)["status"] == "removed"
    assert second["status"] == "ok"
    assert all(resource["path"] != RETIRED_PLAN_AGENT for resource in second["resources"])


def test_upgrade_preserves_retired_scout_projections(tmp_path):
    init_project(tmp_path)
    path = ".claude/agents/scout.md"
    scout_path = tmp_path / path
    scout_path.write_text("legacy scout\n", encoding="utf-8")
    manifest_path = tmp_path / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][path] = {
        "group": "agents",
        "source": "legacy:scout.md",
        "installed_sha256": normalized_digest("legacy scout\n"),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    result = _resource_payload(payload, path)
    assert result["status"] == "retired"
    assert result["message"] == "resource is no longer bundled and was preserved"
    assert scout_path.read_text(encoding="utf-8") == "legacy scout\n"


def test_upgrade_reports_active_role_directory_as_conflict(tmp_path):
    init_project(tmp_path)
    role_path = tmp_path / PLAN_ROLE_REFERENCE
    role_path.unlink()
    role_path.mkdir()

    payload = upgrade_claude_projection(
        tmp_path,
        dry_run=True,
        resolve_bundle_paths={f"{PLAN_ROLE_REFERENCE}=bundle"},
    )

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, PLAN_ROLE_REFERENCE)["status"] == "conflict"
    assert role_path.is_dir()


def test_upgrade_reports_active_role_symlink_as_conflict(tmp_path):
    init_project(tmp_path)
    role_path = tmp_path / PLAN_ROLE_REFERENCE
    role_path.unlink()
    try:
        role_path.symlink_to(tmp_path / "missing-role.md")
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, PLAN_ROLE_REFERENCE)["status"] == "conflict"
    assert role_path.is_symlink()


def test_upgrade_reports_unreadable_active_role_as_conflict(tmp_path, monkeypatch):
    init_project(tmp_path)
    role_path = tmp_path / PLAN_ROLE_REFERENCE
    original_read_text = Path.read_text

    def read_text(path, *args, **kwargs):
        if path == role_path:
            raise PermissionError("test unreadable role")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, PLAN_ROLE_REFERENCE)["status"] == "conflict"


def test_upgrade_reports_invalid_utf8_manifest(tmp_path):
    init_project(tmp_path)
    (tmp_path / MANIFEST_PATH).write_bytes(b"\xff\xfe")

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, MANIFEST_PATH.as_posix())["status"] == "invalid_manifest"