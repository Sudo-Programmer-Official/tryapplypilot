from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class InterviewPreparationEvidenceReference:
    reference_id: str
    source_type: str
    source_id: str
    label: str
    excerpt: str
    evidence_id: str = ""
    relevance_explanation: str = ""
    confidence: float = 0.0
    entity_type: str = ""
    entity_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InterviewParticipant:
    participant_id: str
    name: str
    email: str = ""
    title: str = ""
    role: str = "interviewer"
    source_contact_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InterviewPreparationItem:
    item_id: str
    label: str
    status: str
    detail: str = ""
    reason: str = ""
    estimated_effort: str = ""
    priority: str = "normal"
    category: str = "preparation"
    source: str = "system"
    due_at: str | None = None
    completed_at: str | None = None
    generated: bool = True
    updated_at: str | None = None
    supporting_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["supporting_evidence"] = [item.to_dict() for item in self.supporting_evidence]
        return payload


@dataclass(frozen=True)
class InterviewTimelineEvent:
    event_type: str
    label: str
    detail: str = ""
    occurred_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InterviewAuditEntry:
    event_type: str
    detail: str = ""
    actor_user_id: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InterviewRecord:
    interview_id: str
    application_id: str
    user_id: str
    interview_type: str
    interview_round: str
    interview_status: str
    preparation_status: str
    scheduled_start_at: str | None = None
    scheduled_end_at: str | None = None
    timezone: str = "UTC"
    meeting_url: str = ""
    recruiter_name: str = ""
    recruiter_email: str = ""
    recruiter_contact_id: str = ""
    notes: str = ""
    source: str = "manual"
    interviewers: list[InterviewParticipant] = field(default_factory=list)
    preparation_checklist: list[InterviewPreparationItem] = field(default_factory=list)
    timeline: list[InterviewTimelineEvent] = field(default_factory=list)
    audit_history: list[InterviewAuditEntry] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "interview_id": self.interview_id,
            "application_id": self.application_id,
            "user_id": self.user_id,
            "interview_type": self.interview_type,
            "interview_round": self.interview_round,
            "interview_status": self.interview_status,
            "preparation_status": self.preparation_status,
            "scheduled_start_at": self.scheduled_start_at,
            "scheduled_end_at": self.scheduled_end_at,
            "timezone": self.timezone,
            "meeting_url": self.meeting_url,
            "recruiter_name": self.recruiter_name,
            "recruiter_email": self.recruiter_email,
            "recruiter_contact_id": self.recruiter_contact_id,
            "notes": self.notes,
            "source": self.source,
            "interviewers": [item.to_dict() for item in self.interviewers],
            "preparation_checklist": [item.to_dict() for item in self.preparation_checklist],
            "timeline": [item.to_dict() for item in self.timeline],
            "audit_history": [item.to_dict() for item in self.audit_history],
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }


@dataclass(frozen=True)
class InterviewPreparationSection:
    section_key: str
    title: str
    content: list[str] = field(default_factory=list)
    evidence_references: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    confidence: float = 0.0
    generated_at: str | None = None
    strategy_version: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "section_key": self.section_key,
            "title": self.title,
            "content": list(self.content),
            "evidence_references": [item.to_dict() for item in self.evidence_references],
            "confidence": self.confidence,
            "generated_at": self.generated_at,
            "strategy_version": self.strategy_version,
        }


@dataclass(frozen=True)
class InterviewPreparationRisk:
    risk_id: str
    title: str
    detail: str
    recommendation: str = ""
    severity: str = "medium"
    confidence: float = 0.0
    evidence_references: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    generated_at: str | None = None
    strategy_version: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "risk_id": self.risk_id,
            "title": self.title,
            "detail": self.detail,
            "recommendation": self.recommendation,
            "severity": self.severity,
            "confidence": self.confidence,
            "evidence_references": [item.to_dict() for item in self.evidence_references],
            "generated_at": self.generated_at,
            "strategy_version": self.strategy_version,
        }


@dataclass(frozen=True)
class InterviewPreparationPlan:
    plan_id: str
    interview_id: str
    application_id: str
    user_id: str
    version_number: int
    status: str = "generated"
    strategy_version: str = ""
    focus_labels: list[str] = field(default_factory=list)
    overall_confidence: float = 0.0
    sections: list[InterviewPreparationSection] = field(default_factory=list)
    checklist: list[InterviewPreparationItem] = field(default_factory=list)
    risks: list[InterviewPreparationRisk] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    generated_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "interview_id": self.interview_id,
            "application_id": self.application_id,
            "user_id": self.user_id,
            "version_number": self.version_number,
            "status": self.status,
            "strategy_version": self.strategy_version,
            "focus_labels": list(self.focus_labels),
            "overall_confidence": self.overall_confidence,
            "sections": [item.to_dict() for item in self.sections],
            "checklist": [item.to_dict() for item in self.checklist],
            "risks": [item.to_dict() for item in self.risks],
            "metadata": dict(self.metadata),
            "generated_at": self.generated_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class InterviewQuestionNote:
    note_id: str
    body: str
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InterviewQuestionFollowUp:
    follow_up_id: str
    question: str
    rationale: str = ""
    evaluation_dimensions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "follow_up_id": self.follow_up_id,
            "question": self.question,
            "rationale": self.rationale,
            "evaluation_dimensions": list(self.evaluation_dimensions),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class InterviewQuestion:
    question_id: str
    question_set_id: str
    interview_id: str
    application_id: str
    user_id: str
    category: str
    question: str
    rationale: str
    evaluation_dimensions: list[str] = field(default_factory=list)
    related_job_requirements: list[str] = field(default_factory=list)
    related_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    follow_up_questions: list[InterviewQuestionFollowUp] = field(default_factory=list)
    difficulty: str = "intermediate"
    priority: str = "medium"
    confidence: float = 0.0
    expected_answer_outline: list[str] = field(default_factory=list)
    risk_tags: list[str] = field(default_factory=list)
    sequence_order: int = 0
    preparation_status: str = "not_started"
    hidden: bool = False
    archived: bool = False
    user_notes: list[InterviewQuestionNote] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "question_id": self.question_id,
            "question_set_id": self.question_set_id,
            "interview_id": self.interview_id,
            "application_id": self.application_id,
            "user_id": self.user_id,
            "category": self.category,
            "question": self.question,
            "rationale": self.rationale,
            "evaluation_dimensions": list(self.evaluation_dimensions),
            "related_job_requirements": list(self.related_job_requirements),
            "related_evidence": [item.to_dict() for item in self.related_evidence],
            "follow_up_questions": [item.to_dict() for item in self.follow_up_questions],
            "difficulty": self.difficulty,
            "priority": self.priority,
            "confidence": self.confidence,
            "expected_answer_outline": list(self.expected_answer_outline),
            "risk_tags": list(self.risk_tags),
            "sequence_order": self.sequence_order,
            "preparation_status": self.preparation_status,
            "hidden": self.hidden,
            "archived": self.archived,
            "user_notes": [item.to_dict() for item in self.user_notes],
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class InterviewQuestionSet:
    question_set_id: str
    interview_id: str
    application_id: str
    user_id: str
    version_number: int
    status: str = "draft"
    title: str = ""
    interview_type: str = ""
    interview_round: str = ""
    strategy_version: str = ""
    source_preparation_plan_id: str = ""
    provider: str = ""
    model_key: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    generated_at: str | None = None
    updated_at: str | None = None
    superseded_by_question_set_id: str = ""
    questions: list[InterviewQuestion] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "question_set_id": self.question_set_id,
            "interview_id": self.interview_id,
            "application_id": self.application_id,
            "user_id": self.user_id,
            "version_number": self.version_number,
            "status": self.status,
            "title": self.title,
            "interview_type": self.interview_type,
            "interview_round": self.interview_round,
            "strategy_version": self.strategy_version,
            "source_preparation_plan_id": self.source_preparation_plan_id,
            "provider": self.provider,
            "model_key": self.model_key,
            "metadata": dict(self.metadata),
            "generated_at": self.generated_at,
            "updated_at": self.updated_at,
            "superseded_by_question_set_id": self.superseded_by_question_set_id,
            "questions": [item.to_dict() for item in self.questions],
        }


@dataclass(frozen=True)
class InterviewStorySection:
    section_key: str
    title: str
    content: list[str] = field(default_factory=list)
    evidence_references: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "section_key": self.section_key,
            "title": self.title,
            "content": list(self.content),
            "evidence_references": [item.to_dict() for item in self.evidence_references],
            "missing_fields": list(self.missing_fields),
        }


@dataclass(frozen=True)
class InterviewStoryGapPrompt:
    prompt_id: str
    field_key: str
    prompt: str
    reason: str = ""
    topic: str = ""
    status: str = "open"
    related_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    profile_evolution_payload: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "prompt_id": self.prompt_id,
            "field_key": self.field_key,
            "prompt": self.prompt,
            "reason": self.reason,
            "topic": self.topic,
            "status": self.status,
            "related_evidence": [item.to_dict() for item in self.related_evidence],
            "profile_evolution_payload": dict(self.profile_evolution_payload),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class InterviewStoryCoverageLink:
    question_id: str
    question: str
    category: str
    coverage_score: float = 0.0
    reason: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "question_id": self.question_id,
            "question": self.question,
            "category": self.category,
            "coverage_score": self.coverage_score,
            "reason": self.reason,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class InterviewStoryQualityDimension:
    label: str
    score: int
    rationale: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "score": self.score,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class InterviewStoryQualityAssessment:
    overall_score: int = 0
    dimensions: list[InterviewStoryQualityDimension] = field(default_factory=list)
    summary: str = ""
    generated_at: str | None = None
    strategy_version: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "overall_score": self.overall_score,
            "dimensions": [item.to_dict() for item in self.dimensions],
            "summary": self.summary,
            "generated_at": self.generated_at,
            "strategy_version": self.strategy_version,
        }


@dataclass(frozen=True)
class InterviewStory:
    story_id: str
    story_group_id: str
    user_id: str
    application_id: str | None = None
    interview_id: str | None = None
    linked_application_ids: list[str] = field(default_factory=list)
    linked_interview_ids: list[str] = field(default_factory=list)
    title: str = ""
    category: str = ""
    source_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    related_projects: list[str] = field(default_factory=list)
    related_resume_version_id: str = ""
    related_question_ids: list[str] = field(default_factory=list)
    interview_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    version_number: int = 1
    status: str = "draft"
    sections: list[InterviewStorySection] = field(default_factory=list)
    technical_decisions: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    leadership_moments: list[str] = field(default_factory=list)
    measurable_outcomes: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    interviewer_follow_ups: list[str] = field(default_factory=list)
    coverage: list[InterviewStoryCoverageLink] = field(default_factory=list)
    quality: InterviewStoryQualityAssessment = field(default_factory=InterviewStoryQualityAssessment)
    missing_information_prompts: list[InterviewStoryGapPrompt] = field(default_factory=list)
    superseded_by_story_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "story_id": self.story_id,
            "story_group_id": self.story_group_id,
            "user_id": self.user_id,
            "application_id": self.application_id,
            "interview_id": self.interview_id,
            "linked_application_ids": list(self.linked_application_ids),
            "linked_interview_ids": list(self.linked_interview_ids),
            "title": self.title,
            "category": self.category,
            "source_evidence": [item.to_dict() for item in self.source_evidence],
            "related_projects": list(self.related_projects),
            "related_resume_version_id": self.related_resume_version_id,
            "related_question_ids": list(self.related_question_ids),
            "interview_types": list(self.interview_types),
            "tags": list(self.tags),
            "version_number": self.version_number,
            "status": self.status,
            "sections": [item.to_dict() for item in self.sections],
            "technical_decisions": list(self.technical_decisions),
            "tradeoffs": list(self.tradeoffs),
            "leadership_moments": list(self.leadership_moments),
            "measurable_outcomes": list(self.measurable_outcomes),
            "lessons_learned": list(self.lessons_learned),
            "interviewer_follow_ups": list(self.interviewer_follow_ups),
            "coverage": [item.to_dict() for item in self.coverage],
            "quality": self.quality.to_dict(),
            "missing_information_prompts": [item.to_dict() for item in self.missing_information_prompts],
            "superseded_by_story_id": self.superseded_by_story_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
