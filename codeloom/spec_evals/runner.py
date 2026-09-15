from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from importlib import resources
from typing import Iterable

from codeloom import __version__
from codeloom.spec_evals.executor import SpecEvalExecutor
from codeloom.spec_evals.models import (
    AgentInvocation,
    AgentTurn,
    Disposition,
    ReviewerFinding,
    SpecEvalCase,
    SpecEvalResult,
    SpecEvalRun,
)
from codeloom.spec_evals.report import write_run
from codeloom.spec_evals.rubric import evaluate_artifact


_ALLOWED_DISPOSITIONS = {"accepted", "rejected", "deferred_evidence", "owner_question"}


def run_spec_cases(
    cases: Iterable[SpecEvalCase],
    executor: SpecEvalExecutor,
    output_dir=None,
    run_id: str | None = None,
) -> SpecEvalRun:
    actual_run_id = run_id or uuid.uuid4().hex
    results = tuple(run_spec_case(case, executor, actual_run_id) for case in cases)
    run = SpecEvalRun(
        run_id=actual_run_id,
        results=results,
        metadata={
            "package_version": __version__,
            "executor": executor.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    if output_dir is not None:
        write_run(run, output_dir)
    return run


def run_spec_case(case: SpecEvalCase, executor: SpecEvalExecutor, run_id: str) -> SpecEvalResult:
    turns: list[AgentTurn] = []
    findings: list[ReviewerFinding] = []
    dispositions: list[Disposition] = []
    try:
        draft_turn = _invoke(executor, _analyzer_invocation(case), turns)
        review_turn = _invoke(executor, _reviewer_invocation(case, draft_turn.content), turns)
        findings = _parse_findings(review_turn.content)
        revision_turn = _invoke(executor, _revision_invocation(case, draft_turn.content, findings), turns)
        dispositions, final_artifact = _parse_revision(revision_turn.content, findings)
        initial_rubric = evaluate_artifact(case, draft_turn.content)
        rubric = evaluate_artifact(case, final_artifact)
        status = "fail" if rubric.failures else "needs_human_review" if rubric.manual_review else "pass"
        return SpecEvalResult(
            run_id=run_id,
            case=case,
            turns=tuple(turns),
            reviewer_findings=tuple(findings),
            dispositions=tuple(dispositions),
            final_artifact=final_artifact,
            rubric=rubric,
            status=status,
            metadata={"prompt_hashes": _prompt_hashes(turns)},
            initial_rubric=initial_rubric,
        )
    except Exception as exc:
        return SpecEvalResult(
            run_id=run_id,
            case=case,
            turns=tuple(turns),
            reviewer_findings=tuple(findings),
            dispositions=tuple(dispositions),
            final_artifact="",
            rubric=evaluate_artifact(case, ""),
            status="execution_error",
            error=f"{type(exc).__name__}: {exc}",
            metadata={"prompt_hashes": _prompt_hashes(turns)},
        )


def _invoke(executor: SpecEvalExecutor, invocation: AgentInvocation, turns: list[AgentTurn]) -> AgentTurn:
    started = time.perf_counter()
    turn = executor.invoke(invocation)
    if turn.role != invocation.role:
        raise ValueError(f"executor returned role {turn.role!r} for {invocation.role!r}")
    duration_ms = turn.duration_ms
    if duration_ms is None:
        duration_ms = int((time.perf_counter() - started) * 1000)
    normalized = AgentTurn(
        role=turn.role,
        content=turn.content,
        executor=turn.executor,
        model=turn.model,
        request_id=turn.request_id,
        input_tokens=turn.input_tokens,
        output_tokens=turn.output_tokens,
        duration_ms=duration_ms,
        prompt_sha256=hashlib.sha256(invocation.prompt.encode("utf-8")).hexdigest(),
    )
    turns.append(normalized)
    return normalized


def _analyzer_invocation(case: SpecEvalCase) -> AgentInvocation:
    return AgentInvocation(
        role="spec-analyzer",
        case_id=case.id,
        prompt=(
            f"You are evaluating Spec analysis for the maintainer case below.\n\n{_agent_prompt('spec-analyzer.md')}\n\n"
            "Use the case request and evidence as the only scenario context. Produce a draft user-readable Spec in free-form Markdown. "
            "Do not produce a plan, task list, runtime state, or evaluator report.\n\n"
            f"{case.context_text()}"
        ),
    )


def _reviewer_invocation(case: SpecEvalCase, draft: str) -> AgentInvocation:
    return AgentInvocation(
        role="spec-reviewer",
        case_id=case.id,
        draft=draft,
        prompt=(
            f"You are evaluating a Spec draft for the maintainer case below.\n\n{_agent_prompt('spec-reviewer.md')}\n\n"
            "Return only a JSON object with an advisory `findings` array. Each finding must contain id, severity, "
            "claim_or_counterexample, evidence_basis, uncertainty, impact, and recommendation. Do not choose the business rule, ask the owner, "
            "or mark the artifact ready/blocked.\n\n"
            f"Case context:\n{case.context_text()}\n\nDraft:\n{draft}"
        ),
    )


def _revision_invocation(case: SpecEvalCase, draft: str, findings: list[ReviewerFinding]) -> AgentInvocation:
    findings_json = json.dumps([finding.to_dict() for finding in findings], ensure_ascii=False, indent=2)
    return AgentInvocation(
        role="spec-analyzer",
        case_id=case.id,
        draft=draft,
        reviewer_findings=tuple(finding.to_dict() for finding in findings),
        prompt=(
            f"Re-evaluate the Spec case below as the stage owner.\n\n{_agent_prompt('spec-analyzer.md')}\n\n"
            "Return only a JSON object with `dispositions` and `final_artifact`. `dispositions` must contain one item for each "
            "review finding with finding_id, action (accepted, rejected, deferred_evidence, or owner_question), and rationale. "
            "The final_artifact must be only the user-readable free-form Spec Markdown; do not include evaluator metadata, "
            "review logs, or runtime state inside it.\n\n"
            f"Case context:\n{case.context_text()}\n\nInitial draft:\n{draft}\n\nAdvisory findings:\n{findings_json}"
        ),
    )


def _agent_prompt(name: str) -> str:
    return resources.files("codeloom.agents").joinpath(name).read_text(encoding="utf-8")


def _parse_findings(content: str) -> list[ReviewerFinding]:
    payload = _json_object(content)
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        raise ValueError("review response must contain a findings list")
    findings = []
    for index, item in enumerate(raw_findings, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"review finding {index} must be an object")
        required = ("id", "severity", "claim_or_counterexample", "evidence_basis", "uncertainty", "impact", "recommendation")
        missing = [field for field in required if not isinstance(item.get(field), str) or not item[field].strip()]
        if missing:
            raise ValueError(f"review finding {index} missing fields: {', '.join(missing)}")
        findings.append(
            ReviewerFinding(
                id=item["id"],
                severity=item["severity"],
                claim_or_counterexample=item["claim_or_counterexample"],
                evidence_basis=item["evidence_basis"],
                uncertainty=item["uncertainty"],
                impact=item["impact"],
                recommendation=item["recommendation"],
            )
        )
    return findings


def _parse_revision(content: str, findings: list[ReviewerFinding]) -> tuple[list[Disposition], str]:
    payload = _json_object(content)
    artifact = payload.get("final_artifact")
    if not isinstance(artifact, str) or not artifact.strip():
        raise ValueError("revision response must contain a non-empty final_artifact")
    raw_dispositions = payload.get("dispositions", [])
    if not isinstance(raw_dispositions, list):
        raise ValueError("revision response dispositions must be a list")
    dispositions = []
    for index, item in enumerate(raw_dispositions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"disposition {index} must be an object")
        finding_id = item.get("finding_id")
        rationale = item.get("rationale")
        if not isinstance(finding_id, str) or not finding_id.strip():
            raise ValueError(f"disposition {index} missing finding_id")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError(f"disposition {index} missing rationale")
        action = item.get("action")
        if action not in _ALLOWED_DISPOSITIONS:
            raise ValueError(f"invalid disposition action: {action}")
        dispositions.append(
            Disposition(
                finding_id=finding_id,
                action=action,
                rationale=rationale,
            )
        )
    finding_ids = [finding.id for finding in findings]
    disposition_ids = [disposition.finding_id for disposition in dispositions]
    if len(disposition_ids) != len(set(disposition_ids)) or set(disposition_ids) != set(finding_ids):
        raise ValueError("revision dispositions must contain exactly one item for each review finding")
    return dispositions, artifact


def _json_object(content: str) -> dict[str, object]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("structured evaluator response must be a JSON object")
    return payload


def _prompt_hashes(turns: list[AgentTurn]) -> dict[str, str]:
    return {
        f"{turn.role}-{index}": turn.prompt_sha256 or ""
        for index, turn in enumerate(turns, start=1)
    }
