from __future__ import annotations

from importlib import resources

from codeloom.app.claude_plugin import _agent_rule, _argument_rule, _content_rule
from codeloom.prompt_evals.cases import PromptSurfaceRef


class MissingPromptSurfaceError(Exception):
    pass


def resolve_prompt_surface(surface: PromptSurfaceRef) -> str:
    if surface.kind == "agent":
        return _resource_text("codeloom.agents", surface.ref)
    if surface.kind == "template":
        return _resource_text("codeloom.templates", surface.ref)
    if surface.kind == "skill_agent_rule":
        return _agent_rule(surface.ref)
    if surface.kind == "skill_content_rule":
        return _content_rule(surface.ref)
    if surface.kind == "skill_argument_rule":
        return _argument_rule(surface.ref)
    if surface.kind == "positive_case":
        return _resource_text("codeloom.quality_cases.positive", surface.ref)
    raise MissingPromptSurfaceError(f"unsupported prompt surface kind: {surface.kind}")


def surface_label(surface: PromptSurfaceRef) -> str:
    return f"{surface.kind}:{surface.ref}"


def _resource_text(package: str, name: str) -> str:
    path = resources.files(package).joinpath(name)
    if not path.is_file():
        raise MissingPromptSurfaceError(f"missing prompt surface: {package}/{name}")
    return path.read_text(encoding="utf-8")
