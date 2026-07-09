from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptSurfaceRef:
    kind: str
    ref: str


@dataclass(frozen=True)
class PromptSignal:
    text: str
    weight: int = 1
    note: str = ""


@dataclass(frozen=True)
class PromptEvalCase:
    id: str
    title: str
    agent: str
    stage: str
    quality_dimensions: tuple[str, ...]
    failure_mode: str
    surfaces: tuple[PromptSurfaceRef, ...]
    badcase: str
    expected_behavior: str
    required_signals: tuple[PromptSignal, ...]
    forbidden_signals: tuple[PromptSignal, ...]
    rubric: tuple[str, ...]
    fixture: str | None = None
    skip_if_missing_surface: bool = False


@dataclass(frozen=True)
class PromptEvalResult:
    case_id: str
    status: str
    missing_required: tuple[str, ...]
    forbidden_hits: tuple[str, ...]
    score: int
    max_score: int
    surfaces_checked: tuple[str, ...]
    missing_surfaces: tuple[str, ...]


@dataclass(frozen=True)
class PromptEvalRun:
    results: tuple[PromptEvalResult, ...]

    @property
    def failed(self) -> tuple[PromptEvalResult, ...]:
        return tuple(result for result in self.results if result.status == "fail")

    @property
    def partial(self) -> tuple[PromptEvalResult, ...]:
        return tuple(result for result in self.results if result.status == "partial")

    @property
    def skipped(self) -> tuple[PromptEvalResult, ...]:
        return tuple(result for result in self.results if result.status == "skip")


def load_prompt_eval_cases(case_dir: Path) -> tuple[PromptEvalCase, ...]:
    cases: list[PromptEvalCase] = []
    for path in sorted(case_dir.glob("*.json")):
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("cases", [])
        for item in items:
            cases.append(_case_from_dict(item))
    return tuple(sorted(cases, key=lambda case: case.id))


def _case_from_dict(data: dict[str, Any]) -> PromptEvalCase:
    return PromptEvalCase(
        id=str(data["id"]),
        title=str(data.get("title", data["id"])),
        agent=str(data.get("agent", "")),
        stage=str(data.get("stage", "")),
        quality_dimensions=tuple(data.get("quality_dimensions", ())),
        failure_mode=str(data.get("failure_mode", "")),
        surfaces=tuple(PromptSurfaceRef(kind=str(surface["kind"]), ref=str(surface["ref"])) for surface in data.get("surfaces", ())),
        badcase=str(data.get("badcase", "")),
        expected_behavior=str(data.get("expected_behavior", "")),
        required_signals=tuple(_signal_from_dict(signal) for signal in data.get("required_signals", ())),
        forbidden_signals=tuple(_signal_from_dict(signal) for signal in data.get("forbidden_signals", ())),
        rubric=tuple(str(item) for item in data.get("rubric", ())),
        fixture=data.get("fixture"),
        skip_if_missing_surface=bool(data.get("skip_if_missing_surface", False)),
    )


def _signal_from_dict(data: str | dict[str, Any]) -> PromptSignal:
    if isinstance(data, str):
        return PromptSignal(text=data)
    return PromptSignal(text=str(data["text"]), weight=int(data.get("weight", 1)), note=str(data.get("note", "")))
