from __future__ import annotations

from pathlib import Path

from codeloom.prompt_evals.cases import PromptEvalCase, PromptEvalResult, PromptEvalRun, load_prompt_eval_cases
from codeloom.prompt_evals.surfaces import MissingPromptSurfaceError, resolve_prompt_surface, surface_label


def run_prompt_evals(case_dir: Path) -> PromptEvalRun:
    results = tuple(_run_case(case) for case in load_prompt_eval_cases(case_dir))
    return PromptEvalRun(results=results)


def _run_case(case: PromptEvalCase) -> PromptEvalResult:
    surface_texts: list[str] = []
    surfaces_checked: list[str] = []
    missing_surfaces: list[str] = []

    for surface in case.surfaces:
        label = surface_label(surface)
        try:
            surface_texts.append(f"\n--- {label} ---\n{resolve_prompt_surface(surface)}")
            surfaces_checked.append(label)
        except MissingPromptSurfaceError:
            missing_surfaces.append(label)

    if missing_surfaces and (case.skip_if_missing_surface or not surface_texts):
        return PromptEvalResult(
            case_id=case.id,
            status="skip",
            missing_required=(),
            forbidden_hits=(),
            score=0,
            max_score=sum(signal.weight for signal in case.required_signals),
            surfaces_checked=tuple(surfaces_checked),
            missing_surfaces=tuple(missing_surfaces),
        )

    combined = "".join(surface_texts)
    missing_required = tuple(signal.text for signal in case.required_signals if signal.text not in combined)
    forbidden_hits = tuple(signal.text for signal in case.forbidden_signals if signal.text in combined)
    max_score = sum(signal.weight for signal in case.required_signals)
    score = sum(signal.weight for signal in case.required_signals if signal.text in combined)

    status = "pass"
    if forbidden_hits:
        status = "fail"
    elif missing_required:
        status = "partial"

    return PromptEvalResult(
        case_id=case.id,
        status=status,
        missing_required=missing_required,
        forbidden_hits=forbidden_hits,
        score=score,
        max_score=max_score,
        surfaces_checked=tuple(surfaces_checked),
        missing_surfaces=tuple(missing_surfaces),
    )
