from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SpecEvalCase:
    id: str
    title: str
    source_path: str
    source_sha256: str
    language: str
    entry_request: str
    evidence_packet: tuple[str, ...]
    review_focus: tuple[str, ...]
    quality_dimensions: tuple[str, ...]
    rubric_id: str
    narrative: str

    def context_text(self) -> str:
        evidence = "\n".join(f"- {item}" for item in self.evidence_packet)
        focus = ", ".join(self.review_focus) or "none specified"
        return (
            f"Case: {self.title} ({self.id})\n"
            f"Entry request:\n{self.entry_request.strip()}\n\n"
            f"Evidence packet:\n{evidence}\n\n"
            f"Review focus: {focus}\n\n"
            f"Case guidance:\n{self.narrative.strip()}"
        )


@dataclass(frozen=True)
class AgentInvocation:
    role: str
    prompt: str
    case_id: str
    draft: str | None = None
    reviewer_findings: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class AgentTurn:
    role: str
    content: str
    executor: str
    model: str | None = None
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: int | None = None
    prompt_sha256: str | None = None


@dataclass(frozen=True)
class ReviewerFinding:
    id: str
    severity: str
    claim_or_counterexample: str
    evidence_basis: str
    recommendation: str
    uncertainty: str = ""
    impact: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "severity": self.severity,
            "claim_or_counterexample": self.claim_or_counterexample,
            "evidence_basis": self.evidence_basis,
            "uncertainty": self.uncertainty,
            "impact": self.impact,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class Disposition:
    finding_id: str
    action: str
    rationale: str

    def to_dict(self) -> dict[str, str]:
        return {
            "finding_id": self.finding_id,
            "action": self.action,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class RubricResult:
    rubric_id: str
    failures: tuple[str, ...] = ()
    manual_review: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class SpecEvalResult:
    run_id: str
    case: SpecEvalCase
    turns: tuple[AgentTurn, ...]
    reviewer_findings: tuple[ReviewerFinding, ...]
    dispositions: tuple[Disposition, ...]
    final_artifact: str
    rubric: RubricResult
    status: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    output_paths: dict[str, str] = field(default_factory=dict)
    initial_rubric: RubricResult | None = None


@dataclass(frozen=True)
class SpecEvalRun:
    run_id: str
    results: tuple[SpecEvalResult, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> tuple[SpecEvalResult, ...]:
        return tuple(result for result in self.results if result.status in {"fail", "execution_error"})

    @property
    def passed(self) -> tuple[SpecEvalResult, ...]:
        return tuple(result for result in self.results if result.status == "pass")

    @property
    def needs_human_review(self) -> tuple[SpecEvalResult, ...]:
        return tuple(result for result in self.results if result.status == "needs_human_review")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "metadata": self.metadata,
            "results": [_result_to_dict(result) for result in self.results],
        }


def _result_to_dict(result: SpecEvalResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "case": {
            "id": result.case.id,
            "title": result.case.title,
            "source_path": result.case.source_path,
            "source_sha256": result.case.source_sha256,
            "language": result.case.language,
            "entry_request": result.case.entry_request,
            "evidence_packet": list(result.case.evidence_packet),
            "review_focus": list(result.case.review_focus),
            "quality_dimensions": list(result.case.quality_dimensions),
            "rubric_id": result.case.rubric_id,
        },
        "turns": [turn.__dict__ for turn in result.turns],
        "reviewer_findings": [finding.to_dict() for finding in result.reviewer_findings],
        "dispositions": [disposition.to_dict() for disposition in result.dispositions],
        "final_artifact": result.final_artifact,
        "rubric": {
            "rubric_id": result.rubric.rubric_id,
            "failures": list(result.rubric.failures),
            "manual_review": list(result.rubric.manual_review),
        },
        "initial_rubric": None
        if result.initial_rubric is None
        else {
            "rubric_id": result.initial_rubric.rubric_id,
            "failures": list(result.initial_rubric.failures),
            "manual_review": list(result.initial_rubric.manual_review),
        },
        "status": result.status,
        "error": result.error,
        "metadata": result.metadata,
        "output_paths": result.output_paths,
    }
