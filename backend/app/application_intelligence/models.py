from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class ApplicationJobSnapshot:
    job_id: str
    company: str
    title: str
    location: str
    remote_policy: str
    apply_url: str
    match_score: int | None = None
    decision: str = ""
    why: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    published_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationPackageArtifact:
    artifact_id: str
    kind: str
    label: str
    status: str
    version: int = 1
    source: str = ""
    url: str = ""
    file_name: str = ""
    mime_type: str = ""
    detail: str = ""
    source_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    audit_history: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationTask:
    task_id: str
    label: str
    status: str
    detail: str = ""
    action: str = ""
    action_url: str = ""
    due_at: str | None = None
    completed_at: str | None = None
    priority: str = "normal"
    category: str = "workflow"
    source: str = "system"
    generated: bool = True
    reminder_status: str = "none"
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationNote:
    note_id: str
    note_type: str
    body: str
    created_at: str | None = None
    created_by_user_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationAnswer:
    answer_id: str
    application_id: str
    question: str
    normalized_question_key: str
    answer: str
    source: str
    created_at: str | None = None
    last_used_at: str | None = None
    reusable: bool = False
    sensitive_data: bool = False
    user_approved: bool = True
    status: str = "approved"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationStructuredMetadata:
    recruiter_name: str = ""
    recruiter_email: str = ""
    hiring_manager: str = ""
    application_portal: str = ""
    external_application_id: str = ""
    confirmation_number: str = ""
    submitted_url: str = ""
    submission_timestamp: str | None = None
    deadline: str | None = None
    assessment_deadline: str | None = None
    follow_up_date: str | None = None
    referral_source: str = ""
    referral_contact: str = ""
    salary_range: str = ""
    location: str = ""
    work_arrangement: str = ""
    sponsorship_status: str = ""
    application_source: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationSubmissionRecord:
    submitted_at: str | None = None
    portal: str = ""
    confirmation_number: str = ""
    external_application_id: str = ""
    submitted_url: str = ""
    resume_version_id: str = ""
    answer_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationTimelineEvent:
    event_type: str
    label: str
    detail: str = ""
    occurred_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApplicationRecord:
    application_id: str
    user_id: str
    job_id: str
    resume_version_id: str
    status: str
    package_signature: str
    company: str
    title: str
    apply_url: str
    match_score: int | None = None
    decision: str = ""
    artifacts: list[ApplicationPackageArtifact] = field(default_factory=list)
    tasks: list[ApplicationTask] = field(default_factory=list)
    notes: list[ApplicationNote] = field(default_factory=list)
    answers: list[ApplicationAnswer] = field(default_factory=list)
    structured_metadata: ApplicationStructuredMetadata = field(default_factory=ApplicationStructuredMetadata)
    submission: ApplicationSubmissionRecord = field(default_factory=ApplicationSubmissionRecord)
    timeline: list[ApplicationTimelineEvent] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    applied_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "application_id": self.application_id,
            "user_id": self.user_id,
            "job_id": self.job_id,
            "resume_version_id": self.resume_version_id,
            "status": self.status,
            "package_signature": self.package_signature,
            "company": self.company,
            "title": self.title,
            "apply_url": self.apply_url,
            "match_score": self.match_score,
            "decision": self.decision,
            "artifacts": [item.to_dict() for item in self.artifacts],
            "tasks": [item.to_dict() for item in self.tasks],
            "notes": [item.to_dict() for item in self.notes],
            "answers": [item.to_dict() for item in self.answers],
            "structured_metadata": self.structured_metadata.to_dict(),
            "submission": self.submission.to_dict(),
            "timeline": [item.to_dict() for item in self.timeline],
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "applied_at": self.applied_at,
        }
