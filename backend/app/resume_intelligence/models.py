from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ResumeIntelligenceJobContext:
    job_id: str
    user_id: str
    company: str
    title: str
    location: str
    remote_policy: str
    apply_url: str
    description_text: str
    connector_key: str = ""
    published_at: str | None = None
    match_score: int | None = None
    decision: str = ""
    recommended_resume: str = ""
    why: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class JobRequirement:
    label: str
    category: str
    keywords: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResumeSelectionReason:
    label: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResumeSelectionResult:
    status: str
    confidence: int
    resume_id: str | None = None
    display_name: str = ""
    original_filename: str = ""
    role_focus: str = ""
    matched_requirements: list[str] = field(default_factory=list)
    reason_summary: list[ResumeSelectionReason] = field(default_factory=list)
    fallback_behavior: str = ""

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reason_summary"] = [reason.to_dict() for reason in self.reason_summary]
        return payload


@dataclass(frozen=True)
class GapEvidence:
    source_type: str
    source_id: str
    excerpt: str
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RequirementAssessment:
    label: str
    category: str
    status: str
    source: str
    confidence: int
    reason: str
    evidence: list[GapEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


@dataclass(frozen=True)
class GapAnalysisResult:
    covered_requirements: list[RequirementAssessment] = field(default_factory=list)
    weak_requirements: list[RequirementAssessment] = field(default_factory=list)
    missing_requirements: list[RequirementAssessment] = field(default_factory=list)
    keyword_opportunities: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "covered_requirements": [item.to_dict() for item in self.covered_requirements],
            "weak_requirements": [item.to_dict() for item in self.weak_requirements],
            "missing_requirements": [item.to_dict() for item in self.missing_requirements],
            "keyword_opportunities": list(self.keyword_opportunities),
            "risk_flags": list(self.risk_flags),
        }


@dataclass(frozen=True)
class RetrievedRequirementEvidence:
    requirement_label: str
    category: str
    support_level: str
    rationale: str
    entity_names: list[str] = field(default_factory=list)
    evidence: list[GapEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "requirement_label": self.requirement_label,
            "category": self.category,
            "support_level": self.support_level,
            "rationale": self.rationale,
            "entity_names": list(self.entity_names),
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class EvidenceRetrievalResult:
    items: list[RetrievedRequirementEvidence] = field(default_factory=list)
    missing_proof_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "items": [item.to_dict() for item in self.items],
            "missing_proof_flags": list(self.missing_proof_flags),
        }


@dataclass(frozen=True)
class ResumeChange:
    change_id: str
    section: str
    entry_id: str
    operation: str
    original_text: str
    suggested_text: str
    rationale: str
    job_requirements: list[str] = field(default_factory=list)
    evidence: list[GapEvidence] = field(default_factory=list)
    confidence: int = 0
    risk_level: str = "low"
    status: str = "pending"

    def to_dict(self) -> dict[str, object]:
        return {
            "change_id": self.change_id,
            "section": self.section,
            "entry_id": self.entry_id,
            "operation": self.operation,
            "original_text": self.original_text,
            "suggested_text": self.suggested_text,
            "rationale": self.rationale,
            "job_requirements": list(self.job_requirements),
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "status": self.status,
        }


@dataclass(frozen=True)
class ResumeChangeSet:
    status: str
    source_resume_id: str | None = None
    source_resume_name: str = ""
    changes: list[ResumeChange] = field(default_factory=list)
    blocked_requirements: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_resume_id": self.source_resume_id,
            "source_resume_name": self.source_resume_name,
            "changes": [item.to_dict() for item in self.changes],
            "blocked_requirements": list(self.blocked_requirements),
            "summary": self.summary,
            "added_count": len([item for item in self.changes if item.operation == "add"]),
            "modified_count": len([item for item in self.changes if item.operation == "modify"]),
            "removed_count": len([item for item in self.changes if item.operation == "remove"]),
        }


@dataclass(frozen=True)
class ResumeChangeReviewInput:
    change_id: str
    decision: str
    edited_text: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CritiqueDimensionScore:
    label: str
    before: int
    after: int
    rationale: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResumeCritiqueResult:
    verdict: str
    overall_before: int
    overall_after: int
    dimensions: list[CritiqueDimensionScore] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "overall_before": self.overall_before,
            "overall_after": self.overall_after,
            "dimensions": [item.to_dict() for item in self.dimensions],
            "issues": list(self.issues),
            "strengths": list(self.strengths),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ResumeVersionRecord:
    version_id: str
    user_id: str
    job_id: str
    source_resume_id: str | None
    source_resume_name: str
    file_name: str
    pdf_storage_path: str
    text_storage_path: str
    status: str
    version_signature: str
    accepted_changes: list[dict[str, object]] = field(default_factory=list)
    rejected_changes: list[dict[str, object]] = field(default_factory=list)
    blocked_requirements: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResumeEvaluationCheck:
    key: str
    label: str
    status: str
    actual: float
    target: float
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResumeEvaluationScorecard:
    status: str
    score: int
    time_to_reviewable_draft_ms: int
    metrics: dict[str, float] = field(default_factory=dict)
    checks: list[ResumeEvaluationCheck] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "score": self.score,
            "time_to_reviewable_draft_ms": self.time_to_reviewable_draft_ms,
            "metrics": dict(self.metrics),
            "checks": [item.to_dict() for item in self.checks],
            "alerts": list(self.alerts),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ResumeIntelligenceAnalysis:
    generated_at: str
    job: ResumeIntelligenceJobContext
    requirements: list[JobRequirement]
    selection: ResumeSelectionResult
    gap_analysis: GapAnalysisResult
    evidence_retrieval: EvidenceRetrievalResult
    change_set: ResumeChangeSet
    critique: ResumeCritiqueResult
    evaluation: ResumeEvaluationScorecard | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "job": self.job.to_dict(),
            "requirements": [requirement.to_dict() for requirement in self.requirements],
            "selection": self.selection.to_dict(),
            "gap_analysis": self.gap_analysis.to_dict(),
            "evidence_retrieval": self.evidence_retrieval.to_dict(),
            "change_set": self.change_set.to_dict(),
            "critique": self.critique.to_dict(),
            "evaluation": self.evaluation.to_dict() if self.evaluation is not None else None,
        }
