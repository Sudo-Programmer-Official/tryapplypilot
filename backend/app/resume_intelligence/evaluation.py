from __future__ import annotations

from dataclasses import dataclass, field

from .models import ResumeEvaluationCheck, ResumeEvaluationScorecard, ResumeIntelligenceAnalysis


@dataclass(frozen=True)
class ResumeEvaluationThresholds:
    min_selection_confidence_warn: int = 55
    min_selection_confidence_pass: int = 70
    min_requirement_coverage_rate: int = 60
    min_supported_evidence_rate_warn: int = 40
    min_supported_evidence_rate_pass: int = 65
    min_change_explainability_rate: int = 100
    max_blocked_requirement_rate_warn: int = 40
    max_blocked_requirement_rate_pass: int = 20
    min_ats_score_delta: int = 0
    max_time_to_reviewable_draft_ms: int = 60_000


@dataclass(frozen=True)
class ResumeBenchmarkExpectation:
    name: str
    expected_selection_status: str
    expected_change_set_status: str
    expected_critique_verdict: str
    min_score: int = 70
    allowed_scorecard_statuses: tuple[str, ...] = ("pass", "warn")
    required_covered_requirements: tuple[str, ...] = ()
    required_weak_requirements: tuple[str, ...] = ()
    required_missing_requirements: tuple[str, ...] = ()
    max_blocked_requirements: int | None = None


@dataclass(frozen=True)
class ResumeBenchmarkResult:
    name: str
    passed: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "passed": self.passed,
            "failures": list(self.failures),
        }


def _percentage(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 100
    return int(round((numerator / denominator) * 100))


def evaluate_resume_analysis(
    analysis: ResumeIntelligenceAnalysis,
    *,
    elapsed_ms: int,
    thresholds: ResumeEvaluationThresholds | None = None,
) -> ResumeEvaluationScorecard:
    resolved = thresholds or ResumeEvaluationThresholds()
    requirement_count = len(analysis.requirements)
    covered_count = len(analysis.gap_analysis.covered_requirements)
    weak_count = len(analysis.gap_analysis.weak_requirements)
    missing_count = len(analysis.gap_analysis.missing_requirements)
    blocked_count = len(analysis.change_set.blocked_requirements)
    retrieval_count = len(analysis.evidence_retrieval.items)
    supported_retrieval_count = len(
        [item for item in analysis.evidence_retrieval.items if item.support_level == "supported" and item.evidence]
    )
    explainable_changes = len(
        [
            change
            for change in analysis.change_set.changes
            if change.rationale.strip() and change.job_requirements and change.evidence
        ]
    )
    change_count = len(analysis.change_set.changes)

    requirement_coverage_rate = _percentage(covered_count + weak_count, requirement_count)
    supported_evidence_rate = _percentage(supported_retrieval_count, retrieval_count)
    evidence_integrity_rate = _percentage(
        len(
            [
                item
                for item in analysis.evidence_retrieval.items
                if item.support_level == "supported" or item.requirement_label in analysis.change_set.blocked_requirements
            ]
        ),
        retrieval_count,
    )
    explainability_rate = _percentage(explainable_changes, change_count)
    blocked_requirement_rate = _percentage(blocked_count, requirement_count)
    ats_score_delta = analysis.critique.overall_after - analysis.critique.overall_before

    checks: list[ResumeEvaluationCheck] = []
    alerts: list[str] = []

    def add_check(
        *,
        key: str,
        label: str,
        status: str,
        actual: float,
        target: float,
        detail: str,
    ) -> None:
        checks.append(
            ResumeEvaluationCheck(
                key=key,
                label=label,
                status=status,
                actual=actual,
                target=target,
                detail=detail,
            )
        )
        if status in {"warn", "fail"}:
            alerts.append(detail)

    selection_status = "pass"
    if analysis.selection.status == "no_resumes":
        selection_status = "fail"
    elif analysis.selection.status == "low_confidence" or analysis.selection.confidence < resolved.min_selection_confidence_pass:
        selection_status = "warn" if analysis.selection.confidence >= resolved.min_selection_confidence_warn else "fail"
    add_check(
        key="selection_confidence",
        label="Selection confidence",
        status=selection_status,
        actual=float(analysis.selection.confidence),
        target=float(resolved.min_selection_confidence_pass),
        detail=(
            "Resume selection has no usable baseline resume."
            if analysis.selection.status == "no_resumes"
            else "Resume selection confidence is below the preferred production threshold."
            if selection_status != "pass"
            else "Resume selection meets the production confidence threshold."
        ),
    )

    coverage_status = "pass" if requirement_coverage_rate >= resolved.min_requirement_coverage_rate else "warn"
    add_check(
        key="requirement_coverage",
        label="Requirement coverage",
        status=coverage_status,
        actual=float(requirement_coverage_rate),
        target=float(resolved.min_requirement_coverage_rate),
        detail=(
            "The selected resume already covers enough of the job requirements for a focused refinement pass."
            if coverage_status == "pass"
            else "The selected resume covers too little of the job and may need a different baseline or more profile data."
        ),
    )

    if supported_evidence_rate >= resolved.min_supported_evidence_rate_pass:
        evidence_status = "pass"
    elif supported_evidence_rate >= resolved.min_supported_evidence_rate_warn:
        evidence_status = "warn"
    else:
        evidence_status = "fail"
    if evidence_integrity_rate < 100:
        evidence_status = "fail"
    add_check(
        key="evidence_coverage",
        label="Evidence coverage",
        status=evidence_status,
        actual=float(supported_evidence_rate),
        target=float(resolved.min_supported_evidence_rate_pass),
        detail=(
            "Weak or missing requirements are supported by reusable evidence or safely blocked."
            if evidence_status == "pass"
            else "Some requirements are still under-supported and need stronger evidence before broader automation."
            if evidence_status == "warn"
            else "Evidence integrity is incomplete, so unsupported claims may be slipping through."
        ),
    )

    explainability_status = "pass" if explainability_rate >= resolved.min_change_explainability_rate else "fail"
    add_check(
        key="change_explainability",
        label="Change explainability",
        status=explainability_status,
        actual=float(explainability_rate),
        target=float(resolved.min_change_explainability_rate),
        detail=(
            "Every suggested change has rationale, linked job requirements, and evidence."
            if explainability_status == "pass"
            else "At least one suggested change is missing rationale, job linkage, or evidence."
        ),
    )

    if blocked_requirement_rate <= resolved.max_blocked_requirement_rate_pass:
        blocked_status = "pass"
    elif blocked_requirement_rate <= resolved.max_blocked_requirement_rate_warn:
        blocked_status = "warn"
    else:
        blocked_status = "fail"
    add_check(
        key="blocked_requirement_rate",
        label="Blocked requirement rate",
        status=blocked_status,
        actual=float(blocked_requirement_rate),
        target=float(resolved.max_blocked_requirement_rate_pass),
        detail=(
            "Unsupported requirements are contained within an acceptable range for review."
            if blocked_status == "pass"
            else "Several job requirements remain unsupported, so the draft needs careful human review."
            if blocked_status == "warn"
            else "Too many job requirements are unsupported for this run to be considered healthy."
        ),
    )

    ats_status = "pass"
    if ats_score_delta < resolved.min_ats_score_delta:
        ats_status = "fail"
    elif ats_score_delta == resolved.min_ats_score_delta and analysis.change_set.status != "no_changes_recommended":
        ats_status = "warn"
    add_check(
        key="ats_delta",
        label="ATS improvement",
        status=ats_status,
        actual=float(ats_score_delta),
        target=float(resolved.min_ats_score_delta),
        detail=(
            "The proposed draft improves recruiter-facing score quality."
            if ats_status == "pass"
            else "The proposed changes are neutral for ATS/readability and should be reviewed for value."
            if ats_status == "warn"
            else "The proposed changes reduce the resume quality score and should not be promoted."
        ),
    )

    latency_status = "pass" if elapsed_ms <= resolved.max_time_to_reviewable_draft_ms else "fail"
    add_check(
        key="draft_latency",
        label="Time to reviewable draft",
        status=latency_status,
        actual=float(elapsed_ms),
        target=float(resolved.max_time_to_reviewable_draft_ms),
        detail=(
            "Draft generation is within the V1 latency target."
            if latency_status == "pass"
            else "Draft generation exceeds the V1 latency target."
        ),
    )

    weighted_values = {"pass": 100, "warn": 75, "fail": 35}
    score = int(round(sum(weighted_values[item.status] for item in checks) / len(checks))) if checks else 0
    status = "pass"
    if any(item.status == "fail" for item in checks):
        status = "fail"
    elif any(item.status == "warn" for item in checks):
        status = "warn"

    summary = (
        "Resume Intelligence meets the current offline quality bar."
        if status == "pass"
        else "Resume Intelligence is usable but still has review-time quality risks to monitor."
        if status == "warn"
        else "Resume Intelligence fails the offline quality bar and needs fixes before promotion."
    )

    return ResumeEvaluationScorecard(
        status=status,
        score=score,
        time_to_reviewable_draft_ms=elapsed_ms,
        metrics={
            "requirement_count": float(requirement_count),
            "covered_requirement_count": float(covered_count),
            "weak_requirement_count": float(weak_count),
            "missing_requirement_count": float(missing_count),
            "blocked_requirement_count": float(blocked_count),
            "change_count": float(change_count),
            "selection_confidence": float(analysis.selection.confidence),
            "requirement_coverage_rate": float(requirement_coverage_rate),
            "supported_evidence_rate": float(supported_evidence_rate),
            "evidence_integrity_rate": float(evidence_integrity_rate),
            "change_explainability_rate": float(explainability_rate),
            "blocked_requirement_rate": float(blocked_requirement_rate),
            "ats_score_before": float(analysis.critique.overall_before),
            "ats_score_after": float(analysis.critique.overall_after),
            "ats_score_delta": float(ats_score_delta),
        },
        checks=checks,
        alerts=alerts,
        summary=summary,
    )


def evaluate_benchmark_result(
    analysis: ResumeIntelligenceAnalysis,
    *,
    expectation: ResumeBenchmarkExpectation,
) -> ResumeBenchmarkResult:
    failures: list[str] = []
    scorecard = analysis.evaluation

    if analysis.selection.status != expectation.expected_selection_status:
        failures.append(
            f"Expected selection status {expectation.expected_selection_status} but saw {analysis.selection.status}."
        )
    if analysis.change_set.status != expectation.expected_change_set_status:
        failures.append(
            f"Expected change-set status {expectation.expected_change_set_status} but saw {analysis.change_set.status}."
        )
    if analysis.critique.verdict != expectation.expected_critique_verdict:
        failures.append(
            f"Expected critique verdict {expectation.expected_critique_verdict} but saw {analysis.critique.verdict}."
        )
    if scorecard is None:
        failures.append("Analysis is missing an evaluation scorecard.")
    else:
        if scorecard.score < expectation.min_score:
            failures.append(f"Expected evaluation score >= {expectation.min_score} but saw {scorecard.score}.")
        if scorecard.status not in expectation.allowed_scorecard_statuses:
            failures.append(
                f"Expected scorecard status in {expectation.allowed_scorecard_statuses} but saw {scorecard.status}."
            )

    covered_labels = {item.label for item in analysis.gap_analysis.covered_requirements}
    weak_labels = {item.label for item in analysis.gap_analysis.weak_requirements}
    missing_labels = {item.label for item in analysis.gap_analysis.missing_requirements}

    for label in expectation.required_covered_requirements:
        if label not in covered_labels:
            failures.append(f"Expected covered requirement {label}.")
    for label in expectation.required_weak_requirements:
        if label not in weak_labels:
            failures.append(f"Expected weak requirement {label}.")
    for label in expectation.required_missing_requirements:
        if label not in missing_labels:
            failures.append(f"Expected missing requirement {label}.")
    if expectation.max_blocked_requirements is not None and len(analysis.change_set.blocked_requirements) > expectation.max_blocked_requirements:
        failures.append(
            f"Expected at most {expectation.max_blocked_requirements} blocked requirements but saw {len(analysis.change_set.blocked_requirements)}."
        )

    return ResumeBenchmarkResult(
        name=expectation.name,
        passed=not failures,
        failures=failures,
    )
