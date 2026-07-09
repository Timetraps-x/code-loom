from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codeloom.prompt_evals.cases import PromptEvalCase, PromptSignal, PromptSurfaceRef, load_prompt_eval_cases


@dataclass(frozen=True)
class PromptEvalCaseDraft:
    id: str
    title: str
    agent: str
    stage: str
    quality_dimensions: tuple[str, ...]
    failure_mode: str
    surfaces: tuple[PromptSurfaceRef, ...]
    badcase: str
    expected_behavior: str
    required_signals: tuple[str, ...]
    forbidden_signals: tuple[str, ...]
    rubric: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "agent": self.agent,
            "stage": self.stage,
            "quality_dimensions": list(self.quality_dimensions),
            "failure_mode": self.failure_mode,
            "surfaces": [{"kind": surface.kind, "ref": surface.ref} for surface in self.surfaces],
            "badcase": self.badcase,
            "expected_behavior": self.expected_behavior,
            "required_signals": list(self.required_signals),
            "forbidden_signals": list(self.forbidden_signals),
            "rubric": list(self.rubric),
        }


@dataclass(frozen=True)
class PromptEvalSupplementReport:
    existing_case_count: int
    required_case_count: int
    missing: tuple[PromptEvalCaseDraft, ...]

    @property
    def complete(self) -> bool:
        return not self.missing


def prompt_eval_supplement_report(case_dir: Path) -> PromptEvalSupplementReport:
    cases = load_prompt_eval_cases(case_dir)
    cases_by_id = {case.id: case for case in cases}
    missing = tuple(
        draft
        for draft in DEFAULT_SUPPLEMENTAL_CASES
        if not _case_covers_draft(cases_by_id.get(draft.id), draft)
    )
    return PromptEvalSupplementReport(
        existing_case_count=len(cases),
        required_case_count=len(DEFAULT_SUPPLEMENTAL_CASES),
        missing=missing,
    )


def missing_prompt_eval_case_drafts(case_dir: Path) -> tuple[PromptEvalCaseDraft, ...]:
    return prompt_eval_supplement_report(case_dir).missing


def write_missing_prompt_eval_cases(case_dir: Path, output_path: Path) -> PromptEvalSupplementReport:
    report = prompt_eval_supplement_report(case_dir)
    payload = {"cases": [draft.to_dict() for draft in report.missing]}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def case_has_required_metadata(case: PromptEvalCase) -> bool:
    return bool(
        case.id
        and case.title
        and case.agent
        and case.stage
        and case.quality_dimensions
        and case.failure_mode
        and case.surfaces
        and case.badcase
        and case.expected_behavior
        and case.required_signals
        and case.rubric
    )

def _case_covers_draft(case: PromptEvalCase | None, draft: PromptEvalCaseDraft) -> bool:
    if case is None:
        return False

    required = {signal.text for signal in case.required_signals}
    forbidden = {signal.text for signal in case.forbidden_signals}
    return set(draft.required_signals).issubset(required) and set(draft.forbidden_signals).issubset(forbidden)

def _draft(
    id: str,
    title: str,
    agent: str,
    stage: str,
    quality_dimensions: tuple[str, ...],
    failure_mode: str,
    surfaces: tuple[tuple[str, str], ...],
    badcase: str,
    expected_behavior: str,
    required_signals: tuple[str, ...],
    forbidden_signals: tuple[str, ...] = (),
    rubric: tuple[str, ...] = (),
) -> PromptEvalCaseDraft:
    return PromptEvalCaseDraft(
        id=id,
        title=title,
        agent=agent,
        stage=stage,
        quality_dimensions=quality_dimensions,
        failure_mode=failure_mode,
        surfaces=tuple(PromptSurfaceRef(kind=kind, ref=ref) for kind, ref in surfaces),
        badcase=badcase,
        expected_behavior=expected_behavior,
        required_signals=required_signals,
        forbidden_signals=forbidden_signals,
        rubric=rubric or (expected_behavior,),
    )


DEFAULT_SUPPLEMENTAL_CASES: tuple[PromptEvalCaseDraft, ...] = (
    _draft(
        id="builder.quality.visible-flow-no-cosmetic-abstraction",
        title="Builder keeps business flow visible and rejects cosmetic abstraction",
        agent="builder",
        stage="do",
        quality_dimensions=("flow_readability", "abstraction_fit", "performance_fit"),
        failure_mode="over_abstraction",
        surfaces=(("agent", "builder.md"),),
        badcase="Builder adds Context/Manager/helper extraction only to make code look short, hiding data flow and traversal cost.",
        expected_behavior="Builder keeps useful business/data flow visible and introduces helpers only for real reuse, complexity isolation, or business steps.",
        required_signals=("Keep the main business flow readable", "Avoid repeated traversal or repeated queries", "real reuse"),
        forbidden_signals=("smallest implementation",),
        rubric=("The prompt prevents cosmetic abstractions.", "The prompt preserves visible data/performance flow."),
    ),
    _draft(
        id="builder.quality.codebase-scout-before-unclear-facts",
        title="Builder uses codebase-scout for bounded repository facts",
        agent="builder",
        stage="do",
        quality_dimensions=("existing_path_fit", "reuse_surface_fit"),
        failure_mode="missed_reuse_surface",
        surfaces=(("agent", "builder.md"),),
        badcase="Builder guesses local implementation instead of checking existing code paths and reusable surfaces.",
        expected_behavior="Builder delegates narrow repository fact questions to codebase-scout when current task code facts are unclear.",
        required_signals=("Use `codebase-scout` only for narrow read-only repository facts", "existing-code consistency", "nearby code conventions"),
        forbidden_signals=("BeanUtils.copy must be used",),
        rubric=("The prompt asks for bounded codebase evidence instead of hard-coding stack-specific rules.",),
    ),
    _draft(
        id="code-reviewer.quality.hidden-flow-and-evidence-discipline",
        title="Reviewer catches hidden flow and separates blocking from observations",
        agent="code-reviewer",
        stage="do",
        quality_dimensions=("evidence_discipline", "flow_readability", "abstraction_fit"),
        failure_mode="unsupported_blocker",
        surfaces=(("agent", "code-reviewer.md"),),
        badcase="Reviewer blocks on subjective style or misses helper extraction that hides query/traversal cost.",
        expected_behavior="Reviewer flags concrete flow/performance risks and distinguishes blocking findings from observations.",
        required_signals=("Distinguish blocking findings from non-blocking observations", "cosmetic extraction", "repeated traversal", "evidence_integrity_gap"),
        rubric=("Blocking review findings require concrete task-relevant risk.", "Reviewer recognizes hidden data/performance flow."),
    ),
    _draft(
        id="verifier.evidence.no-evidence-not-verified",
        title="Verifier does not verify without evidence",
        agent="verifier",
        stage="do",
        quality_dimensions=("evidence_discipline", "verification_fit"),
        failure_mode="missing_evidence_verified",
        surfaces=(("agent", "verifier.md"),),
        badcase="Verifier accepts a narrative summary as verification without command, file, manual, browser, or inspection evidence.",
        expected_behavior="Verifier returns blocked, failed, or not verified when evidence is insufficient.",
        required_signals=("No evidence means not verified", "return blocked with the missing evidence", "not_verified"),
        rubric=("Verification status must be evidence-backed.", "Verifier stays inside current verify task coverage."),
    ),
    _draft(
        id="task-planner.quality.execution-context-and-no-lane-leakage",
        title="Task planner leaves enough execution context without scout lane leakage",
        agent="task-planner",
        stage="tasks",
        quality_dimensions=("scope_boundary", "verification_fit", "context_fit"),
        failure_mode="weak_task_context",
        surfaces=(("agent", "task-planner.md"), ("skill_content_rule", "tasks")),
        badcase="Task planner creates scout/research tasks or leaves builder without execution context.",
        expected_behavior="Task planner creates only build/verify tasks with enough execution context and verification coverage.",
        required_signals=("Enough execution context", "Do not create scout, research", "Context need", "Codebase facts to confirm", "Quality constraints"),
        rubric=("Executable tasks do not leak scout/research lanes.", "Tasks contain enough context for do-stage agents."),
    ),
    _draft(
        id="codebase-scout.quality.facts-not-design",
        title="Codebase scout returns facts and does not design final solution",
        agent="codebase-scout",
        stage="do",
        quality_dimensions=("existing_path_fit", "reuse_surface_fit", "evidence_discipline"),
        failure_mode="scout_designs_solution",
        surfaces=(("agent", "codebase-scout.md"),),
        badcase="Codebase scout decides the final abstraction or implementation instead of reporting repository facts.",
        expected_behavior="Codebase scout returns observed facts, evidence, uncertainty, impact, and bounded recommendations only.",
        required_signals=("observed repository facts", "Do not design the final abstraction", "direct answer", "source refs", "reuse surface", "verification surface"),
        rubric=("Scout output is evidence, not authority.", "Scout stays inside delegated task boundary."),
    ),
    _draft(
        id="cross-surface.do.lane-integrity",
        title="Do-stage prompt surfaces preserve build/verify lane integrity",
        agent="cross-surface",
        stage="do",
        quality_dimensions=("stage_ownership", "scope_boundary", "evidence_discipline"),
        failure_mode="lane_confusion",
        surfaces=(("agent", "builder.md"), ("agent", "verifier.md"), ("skill_agent_rule", "do")),
        badcase="Build attempt self-verifies, verify attempt edits code, or host runs do as a one-shot command.",
        expected_behavior="Build and verify lanes remain separated through skill and agent prompts.",
        required_signals=("Build attempts must complete as `implemented`, `failed`, or `blocked`", "Verify attempts must complete as `verified`, `failed`, or `blocked`", "do not run `loom stage do` as a one-shot execution command"),
        rubric=("Build lane cannot claim final verification.", "Verify lane cannot implement fixes."),
    ),
    _draft(
        id="evalcase.adopt-expert.constitution.extracts-project-rulebook",
        title="Adopt expert extracts a project constitution and quality baseline",
        agent="adopt-expert",
        stage="adopt",
        quality_dimensions=("adopt_artifact_quality", "constitution_fit", "project_style_fit", "existing_path_fit", "reuse_surface_fit"),
        failure_mode="missing_project_constraint_in_constitution",
        surfaces=(("agent", "adopt-expert.md"),),
        badcase="Adopt expert scans source code only, outputs a project encyclopedia, follows a template mechanically, writes a CodeLoom manual, or copies task context instead of filtering whole-project evidence into durable project rules.",
        expected_behavior="Adopt expert should write constitution as the project's durable code-quality baseline: synthesized from whole-project evidence through a durability, project-specificity, actionability, and evidence-backed filter, with stable project rules that shape ownership boundaries, existing paths, reuse surfaces, database/schema ownership, visible business/data/state flow, restrained abstraction, stack-local positive code shape, and evidence discipline. The final constitution must read like direct project coding rules, not like a self-describing constitution manual or template explanation.",
        required_signals=(
            "Required adoption flow",
            "repository rules",
            "README/docs/specs/design/business documents",
            "database/schema/migration/SQL/mapper surfaces",
            "Read only matching files under `.loom/references/positive-cases/`",
            "Synthesis filter",
            "Durable",
            "Project-specific",
            "Actionable",
            "Evidence-backed",
            "The constitution is not a CodeLoom manual",
            "Stack-Local Code Shape",
            "Every bullet in the final constitution must name a concrete project owner",
            "Do not write self-describing scaffold prose",
            "Omit any section that has no project-specific content",
            "Evidence classification gate",
            "untracked_or_in_progress_code",
            "target_state_design",
            "AskUserQuestion gate",
            "promotion` conflicts",
            "authority` conflicts",
            "legacy` conflicts",
        ),
        rubric=(
            "Constitution generation has a positive decision-oriented project-rulebook target, not only exclusion guardrails or generic quality headings.",
            "Adopt expert is optimized for stable project code quality guidance and stack-adaptive local rules.",
        ),
    ),
    _draft(
        id="adopt-expert.constitution.future-surface",
        title="Adopt expert constitution prompt surface exists when Phase 2 lands",
        agent="adopt-expert",
        stage="adopt",
        quality_dimensions=("constitution_fit",),
        failure_mode="constitution_project_encyclopedia",
        surfaces=(("agent", "adopt-expert.md"),),
        badcase="Adopt expert generates a long project encyclopedia, scans source code only, writes a CodeLoom manual or Phase 2 policy note, creates a language-specific manual set, or treats the template as a mechanical form instead of synthesizing durable project rules.",
        expected_behavior="Adopt expert generates a concise .loom/constitution.md from whole-project evidence, uses a synthesis filter for durable project-specific rules, loads only matching positive stack cases after stack detection, replaces scaffold text with repository-specific coding rules, and excludes workflow mechanics or task context.",
        required_signals=(".loom/constitution.md", "durable code-quality baseline", "Required adoption flow", "repository rules", "database/schema/migration/SQL/mapper surfaces", "Read only matching files under `.loom/references/positive-cases/`", "Synthesis filter", "replace scaffold text with repository-specific rules", "Do not write self-describing scaffold prose", "Stack-Local Code Shape"),
        rubric=("Adopt expert exists and is focused on project rulebook and stack-adaptive quality guidance.",),
    ),
    _draft(
        id="evalcase.adopt-expert.constitution.rejects-task-context",
        title="Adopt expert excludes task context from constitution",
        agent="adopt-expert",
        stage="adopt",
        quality_dimensions=("adopt_artifact_quality", "constitution_fit", "scope_boundary", "stage_ownership", "artifact_quality"),
        failure_mode="task_context_leaked_into_constitution",
        surfaces=(("agent", "adopt-expert.md"),),
        badcase="Adopt expert copies Order Reconciliation Phase 2, PAY-1842, /api/orders/{orderId}/reconcile, migration phase 2 backfill, T-214, acceptance criteria, task-reconcile-evidence.md, and stage-agent execution instructions into .loom/constitution.md.",
        expected_behavior="Adopt expert writes the constitution as durable project rules / quality baseline, converts recurring task evidence into stable categories, excludes concrete task context, and removes platform workflow questions before returning.",
        required_signals=(
            "Task-specific evidence often reveals a stable category",
            "Do not copy current endpoint names, task IDs, attempt IDs, acceptance criteria, evidence filenames, migration phase names, or one-off implementation details",
            "Do not turn a current task conflict into a permanent project ban",
            "future unrelated work",
            "Before returning, remove any constitution line that primarily answers",
            "What happened in the current task or attempt",
        ),
        forbidden_signals=(
            "Order Reconciliation Phase 2",
            "PAY-1842",
            "/api/orders/{orderId}/reconcile",
            "migration phase 2 backfill",
            "T-214",
            "acceptance criteria: reconciled orders must emit audit event",
            "task-reconcile-evidence.md",
            "run adopt-expert after task-planner and before builder",
        ),
        rubric=(
            "Constitution contains durable project constraints, not current task context.",
            "Concrete task values are routed to task artifacts or evidence rather than copied.",
        ),
    ),
    _draft(
        id="cross-surface.constitution.selective-consumption",
        title="Prompt surfaces consume constitution selectively without copying it into artifacts",
        agent="cross-surface",
        stage="all",
        quality_dimensions=("constitution_fit", "scope_boundary", "artifact_quality"),
        failure_mode="constitution_full_copy_or_scope_expansion",
        surfaces=(("skill_content_rule", "spec"), ("skill_content_rule", "plan"), ("skill_content_rule", "tasks"), ("skill_content_rule", "ship")),
        badcase="Generated stage skills copy constitution text into artifacts or use it to expand branch artifact scope.",
        expected_behavior="Generated stage skills read only relevant constitution sections and keep constitution as a quality baseline, not artifact content or runtime evidence.",
        required_signals=("read only sections relevant to this stage's output quality", "project rulebook / quality baseline", "Do not copy constitution text into the artifact"),
        rubric=("Constitution is consumed selectively.", "Constitution cannot expand artifact scope or replace evidence."),
    ),
    _draft(
        id="builder.constitution.no-scope-expansion",
        title="Builder treats constitution as local quality guidance only",
        agent="builder",
        stage="do",
        quality_dimensions=("constitution_fit", "scope_boundary", "evidence_discipline"),
        failure_mode="constitution_authorizes_scope_expansion",
        surfaces=(("agent", "builder.md"), ("skill_agent_rule", "do")),
        badcase="Builder uses constitution guidance to expand task scope, override requirement semantics, skip current repository evidence, or copy constitution into handoff.",
        expected_behavior="Builder reads only relevant constitution sections, treats current requirement semantics as higher authority when they conflict, applies constitution inside the task boundary, and keeps evidence separate.",
        required_signals=("read only the sections relevant to the current task's quality", "requirement authority", "Current requirement semantics", "constitution may be stale or lower-quality", "must not expand the current task boundary", "cannot replace evidence or authorize scope expansion"),
        rubric=("Builder consumes constitution without widening task scope.", "Constitution is not evidence or requirement authority."),
    ),
    _draft(
        id="review-verify.constitution.evidence-discipline",
        title="Reviewer and verifier preserve evidence discipline with constitution",
        agent="cross-surface",
        stage="do",
        quality_dimensions=("constitution_fit", "evidence_discipline", "scope_boundary"),
        failure_mode="constitution_replaces_evidence",
        surfaces=(("agent", "code-reviewer.md"), ("agent", "verifier.md"), ("agent", "codebase-scout.md")),
        badcase="Reviewer blocks on constitution opinions without evidence, verifier marks work verified from constitution text, or scout treats constitution as repository evidence.",
        expected_behavior="Reviewer, verifier, and codebase-scout use constitution as a bounded quality lens while preserving evidence and repository-fact separation.",
        required_signals=("blocking findings still require concrete evidence", "cannot mark anything verified", "no constitution text can substitute for evidence", "not as repository evidence"),
        rubric=("Constitution guides focus but does not replace evidence.", "Scout separates repository facts from constitution guidance."),
    ),
    _draft(
        id="cross-surface.real-flow.scope-separation-and-evidence",
        title="Stage artifacts separate product scope from platform validation and require evidence-backed claims",
        agent="cross-surface",
        stage="all",
        quality_dimensions=("scope_boundary", "artifact_quality", "evidence_discipline"),
        failure_mode="platform_validation_expands_product_scope",
        surfaces=(("skill_content_rule", "spec"), ("skill_content_rule", "plan"), ("skill_content_rule", "tasks"), ("skill_content_rule", "ship")),
        badcase="Artifacts turn independent artifact review, real-flow validation, or prompt/eval tuning into extra product implementation scope, then make unsupported factual claims.",
        expected_behavior="Stage prompts separate business delivery from platform validation and require artifact factual claims to be supported by current evidence or marked as assumptions, risks, or not verified.",
        required_signals=("Separate product or business delivery scope from platform validation scope", "must not authorize extra product changes", "Artifact factual claims must be backed", "mark unsupported claims as assumptions, risks, or not verified"),
        rubric=("Platform validation cannot silently widen product scope.", "Artifact claims must be evidence-backed."),
    ),
    _draft(
        id="task-planner.real-flow.platform-validation-not-build-scope",
        title="Task planner keeps platform validation out of product build tasks",
        agent="task-planner",
        stage="tasks",
        quality_dimensions=("scope_boundary", "verification_fit", "context_fit"),
        failure_mode="platform_validation_leaks_into_build_lane",
        surfaces=(("agent", "task-planner.md"), ("skill_content_rule", "tasks")),
        badcase="A request combines a product change with real-flow validation and eval tuning, and task planning creates extra product build tasks to satisfy platform validation.",
        expected_behavior="Task planning keeps product build tasks bounded and routes platform validation as do-stage verification evidence or explicit platform follow-up outside tasks.md.",
        required_signals=("platform validation, artifact review, or eval/prompt tuning", "product build-task scope", "do-stage verification evidence or explicit platform follow-up", "outside tasks.md"),
        rubric=("Business build tasks stay bounded to the accepted product change.", "Platform validation becomes evidence or platform follow-up, not extra product scope."),
    ),
    _draft(
        id="build-review.real-flow.identifier-uniqueness",
        title="Builder and reviewer require current-repository uniqueness for named identifiers",
        agent="cross-surface",
        stage="do",
        quality_dimensions=("existing_path_fit", "evidence_discipline", "regression_fit"),
        failure_mode="guessed_named_identifier",
        surfaces=(("agent", "builder.md"), ("agent", "code-reviewer.md")),
        badcase="Builder invents the next error code, message key, route, permission, feature flag, or migration name without checking current repository usage.",
        expected_behavior="Builder checks current identifiers before adding a new one, and reviewer flags missing uniqueness evidence.",
        required_signals=("named identifiers such as error codes", "check the current repository for existing identifiers", "current-repository uniqueness checking", "identifier_uniqueness_gap"),
        rubric=("Identifier choices are grounded in current repository evidence.", "Reviewer can flag guessed or conflicting identifiers."),
    ),
    _draft(
        id="verify-release.real-flow.scoped-diff-and-contract-evidence",
        title="Verifier and release separate scoped diff from dirty workspace and contract evidence from source inference",
        agent="cross-surface",
        stage="do",
        quality_dimensions=("evidence_discipline", "scope_boundary", "release_readiness"),
        failure_mode="dirty_workspace_or_contract_evidence_overclaimed",
        surfaces=(("agent", "verifier.md"), ("agent", "release-analyzer.md"), ("skill_agent_rule", "do")),
        badcase="Verifier or release treats unrelated dirty files as part of the current task, or marks API/UI response-contract behavior verified from source inspection alone.",
        expected_behavior="Verifier and release disclose unrelated dirty state, verify only scoped task changes, and mark exact response-shape behavior not verified unless exercised by suitable evidence.",
        required_signals=("scoped task diff", "unrelated pre-existing changes", "exact response shape", "end-to-end contract evidence", "unrelated dirty working tree state"),
        rubric=("Dirty worktree state cannot inflate current-task verification.", "Contract changes need response-shape evidence or explicit not-verified status."),
    ),
)
