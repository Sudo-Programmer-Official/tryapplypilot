from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class CommunicationEvidence:
    source_type: str
    source_id: str
    label: str
    excerpt: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CommunicationInsightSummary:
    summary_id: str
    scope_type: str
    scope_id: str
    thread_id: str
    application_id: str | None = None
    message_id: str = ""
    title: str = ""
    summary: str = ""
    communication_objective: str = ""
    key_points: list[str] = field(default_factory=list)
    pending_action: str = ""
    risks: list[str] = field(default_factory=list)
    evidence: list[CommunicationEvidence] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    strategy_version: str = ""
    generated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


@dataclass(frozen=True)
class CommunicationDraft:
    draft_id: str
    draft_group_id: str
    version_number: int
    user_id: str
    thread_id: str
    draft_kind: str
    tone: str
    status: str
    intended_recipient: str
    intended_recipient_email: str
    communication_objective: str
    subject: str
    body: str
    confidence: float
    explanation: str
    strategy_version: str
    model_key: str
    application_id: str | None = None
    source_message_id: str = ""
    parent_draft_id: str = ""
    evidence: list[CommunicationEvidence] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    user_edited: bool = False
    generated_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["evidence"] = [item.to_dict() for item in self.evidence]
        return payload


@dataclass(frozen=True)
class ConversationSla:
    waiting_on: str = "none"
    last_recruiter_message_at: str | None = None
    last_candidate_response_at: str | None = None
    last_contact_at: str | None = None
    response_latency_hours: float | None = None
    average_response_latency_hours: float | None = None
    days_since_last_contact: int | None = None
    overdue_threshold_hours: int = 0
    overdue: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ConversationState:
    application_id: str | None = None
    thread_id: str = ""
    state: str = "unknown"
    label: str = "Unknown"
    waiting_on: str = "none"
    derived_from_message_id: str = ""
    last_message_type: str = "unknown"
    last_message_at: str | None = None
    reason: str = ""
    sla: ConversationSla = field(default_factory=ConversationSla)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["sla"] = self.sla.to_dict()
        return payload


@dataclass(frozen=True)
class CommunicationHealth:
    application_id: str | None = None
    status: str = "unknown"
    label: str = "Unknown"
    score: int = 50
    waiting_on: str = "none"
    last_message_at: str | None = None
    needs_follow_up: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ConversationSuggestion:
    suggestion_id: str
    action_type: str
    label: str
    reason: str
    confidence: float
    supporting_message_id: str = ""
    supporting_message_subject: str = ""
    related_application_id: str | None = None
    due_at: str | None = None
    waiting_on: str = "none"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RecruiterContactApplicationLink:
    application_id: str
    company: str = ""
    title: str = ""
    status: str = ""
    last_contact_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RecruiterContact:
    contact_id: str
    user_id: str
    display_name: str
    email: str
    company: str = ""
    title: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CommunicationSummary:
    application_id: str | None = None
    last_message_id: str = ""
    last_thread_id: str = ""
    last_message_type: str = "unknown"
    last_message_subject: str = ""
    last_contact_date: str | None = None
    pending_action: str = ""
    conversation_status: str = "idle"
    response_overdue: bool = False
    suggested_actions: list[str] = field(default_factory=list)
    recruiter_name: str = ""
    recruiter_email: str = ""
    confidence: float = 0.0
    reason: str = ""
    waiting_on: str = "none"
    conversation_state: ConversationState = field(default_factory=ConversationState)
    health: CommunicationHealth = field(default_factory=CommunicationHealth)
    sla: ConversationSla = field(default_factory=ConversationSla)
    suggestions: list[ConversationSuggestion] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["conversation_state"] = self.conversation_state.to_dict()
        payload["health"] = self.health.to_dict()
        payload["sla"] = self.sla.to_dict()
        payload["suggestions"] = [item.to_dict() for item in self.suggestions]
        return payload


@dataclass(frozen=True)
class RecruiterThread:
    thread_id: str
    user_id: str
    application_id: str | None
    recruiter: RecruiterContact
    subject: str
    company: str = ""
    job_title: str = ""
    last_message_id: str = ""
    last_message_at: str | None = None
    message_count: int = 0
    source: str = "manual_import"
    confidence: float = 0.0
    conversation_status: str = "idle"
    pending_action: str = ""
    response_overdue: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "application_id": self.application_id,
            "recruiter": self.recruiter.to_dict(),
            "subject": self.subject,
            "company": self.company,
            "job_title": self.job_title,
            "last_message_id": self.last_message_id,
            "last_message_at": self.last_message_at,
            "message_count": self.message_count,
            "source": self.source,
            "confidence": self.confidence,
            "conversation_status": self.conversation_status,
            "pending_action": self.pending_action,
            "response_overdue": self.response_overdue,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RecruiterMessage:
    message_id: str
    thread_id: str
    user_id: str
    application_id: str | None
    recruiter: RecruiterContact
    sender: str
    recipients: list[str]
    subject: str
    body_reference: str
    body_preview: str = ""
    received_at: str | None = None
    message_type: str = "unknown"
    confidence: float = 0.0
    source: str = "manual_import"
    timeline_id: str = ""
    company: str = ""
    job_title: str = ""
    matched: bool = False
    match_confidence: float = 0.0
    match_reason: str = ""
    classification_reason: str = ""
    suggested_actions: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "application_id": self.application_id,
            "recruiter": self.recruiter.to_dict(),
            "sender": self.sender,
            "recipients": list(self.recipients),
            "subject": self.subject,
            "body_reference": self.body_reference,
            "body_preview": self.body_preview,
            "received_at": self.received_at,
            "message_type": self.message_type,
            "confidence": self.confidence,
            "source": self.source,
            "timeline_id": self.timeline_id,
            "company": self.company,
            "job_title": self.job_title,
            "matched": self.matched,
            "match_confidence": self.match_confidence,
            "match_reason": self.match_reason,
            "classification_reason": self.classification_reason,
            "suggested_actions": list(self.suggested_actions),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class CommunicationEvent:
    event_id: str
    user_id: str
    application_id: str | None
    thread_id: str
    message_id: str
    event_type: str
    title: str
    detail: str = ""
    occurred_at: str | None = None
    source: str = "manual_import"
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RecruiterMessageImportRecord:
    external_message_id: str = ""
    external_thread_id: str = ""
    application_id: str = ""
    recruiter_name: str = ""
    recruiter_email: str = ""
    sender_email: str = ""
    sender_name: str = ""
    recipients: list[str] = field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_reference: str = ""
    company: str = ""
    job_title: str = ""
    received_at: str | None = None
    source: str = "manual_import"
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RecruiterContactProfile:
    contact: RecruiterContact
    applications_connected: list[RecruiterContactApplicationLink] = field(default_factory=list)
    last_contact_at: str | None = None
    total_conversations: int = 0
    total_messages: int = 0
    average_response_time_hours: float | None = None
    waiting_on: str = "none"
    latest_conversation_state: str = "unknown"
    latest_health_status: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return {
            "contact": self.contact.to_dict(),
            "applications_connected": [item.to_dict() for item in self.applications_connected],
            "last_contact_at": self.last_contact_at,
            "total_conversations": self.total_conversations,
            "total_messages": self.total_messages,
            "average_response_time_hours": self.average_response_time_hours,
            "waiting_on": self.waiting_on,
            "latest_conversation_state": self.latest_conversation_state,
            "latest_health_status": self.latest_health_status,
        }
