from __future__ import annotations

import json

from codeloom.app import managed_projection
from codeloom.app.init_project import init_project
from codeloom.app.managed_projection import MANIFEST_PATH, normalized_digest, upgrade_claude_projection


def _resource_payload(payload, path: str):
    return next(resource for resource in payload["resources"] if resource["path"] == path)


def test_fresh_init_registers_claude_projection_manifest(tmp_path):
    init_project(tmp_path)

    manifest = json.loads((tmp_path / MANIFEST_PATH).read_text(encoding="utf-8"))

    assert manifest["integration"] == "claude-code"
    assert ".claude/agents/plan-architect.md" in manifest["files"]
    assert ".claude/skills/loom-plan/SKILL.md" in manifest["files"]


def test_upgrade_preserves_modified_managed_resource(tmp_path):
    init_project(tmp_path)
    agent_path = tmp_path / ".claude" / "agents" / "plan-architect.md"
    agent_path.write_text("custom agent\n", encoding="utf-8")

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert payload["status"] == "conflict"
    assert _resource_payload(payload, ".claude/agents/plan-architect.md")["status"] == "conflict"
    assert agent_path.read_text(encoding="utf-8") == "custom agent\n"


def test_upgrade_adopts_exact_legacy_projection(tmp_path, monkeypatch):
    legacy = "legacy fixture\n"
    agent_path = tmp_path / ".claude" / "agents" / "plan-architect.md"
    agent_path.parent.mkdir(parents=True)
    agent_path.write_text(legacy, encoding="utf-8")
    monkeypatch.setattr(
        managed_projection,
        "_legacy_hashes",
        lambda: {".claude/agents/plan-architect.md": {normalized_digest(legacy)}},
    )

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    assert _resource_payload(payload, ".claude/agents/plan-architect.md")["status"] == "updated"


def test_upgrade_restores_missing_resource_only_after_explicit_resolution(tmp_path):
    init_project(tmp_path)
    agent_path = tmp_path / ".claude" / "agents" / "plan-architect.md"
    agent_path.unlink()

    missing = upgrade_claude_projection(tmp_path, dry_run=True)
    assert missing["status"] == "conflict"
    assert _resource_payload(missing, ".claude/agents/plan-architect.md")["status"] == "missing"

    restored = upgrade_claude_projection(
        tmp_path,
        resolve_bundle_paths={".claude/agents/plan-architect.md=bundle"},
    )
    assert restored["status"] == "ok"
    assert _resource_payload(restored, ".claude/agents/plan-architect.md")["status"] == "created"
    assert agent_path.exists()


def test_upgrade_only_manages_selected_group(tmp_path):
    init_project(tmp_path)
    skill_path = tmp_path / ".claude" / "skills" / "loom-plan" / "SKILL.md"
    skill_path.write_text("custom skill\n", encoding="utf-8")

    payload = upgrade_claude_projection(tmp_path, group="agents", dry_run=True)

    assert all(resource["group"] == "agents" for resource in payload["resources"])
    assert skill_path.read_text(encoding="utf-8") == "custom skill\n"

def test_upgrade_preserves_retired_scout_projections(tmp_path, monkeypatch):
    init_project(tmp_path)
    legacy_paths = (
        ".claude/agents/scout.md",
        ".claude/agents/codebase-scout.md",
    )
    manifest_path = tmp_path / MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    resources = list(managed_projection.bundled_claude_resources())
    for path in legacy_paths:
        agent_path = tmp_path / path
        agent_path.write_text(f"legacy {agent_path.name}\n", encoding="utf-8")
        manifest["files"][path] = {
            "group": "agents",
            "source": f"legacy:{agent_path.name}",
            "digest": normalized_digest(agent_path.read_text(encoding="utf-8")),
        }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(
        managed_projection,
        "bundled_claude_resources",
        lambda: tuple(resource for resource in resources if resource.path.as_posix() not in legacy_paths),
    )

    payload = upgrade_claude_projection(tmp_path, dry_run=True)

    for path in legacy_paths:
        result = _resource_payload(payload, path)
        assert result["status"] == "retired"
        assert result["message"] == "resource is no longer bundled and was preserved"
        assert (tmp_path / path).read_text(encoding="utf-8") == f"legacy {path.rsplit('/', 1)[-1]}\n"