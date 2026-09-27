from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from app.application_intelligence import (
    ApplicationRecord,
    ApplicationIntelligenceService,
    build_application_intelligence_service,
)
from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import KnowledgeEntity
from app.knowledge_platform import KnowledgePlatformClient, build_knowledge_platform_client
from app.knowledge_platform.queries import entity_text
from app.recruiter_intelligence import RecruiterIntelligenceService, build_recruiter_intelligence_service
from app.resume_intelligence import ResumeIntelligenceService, build_resume_intelligence_service
from app.resume_intelligence.evidence import retrieve_requirement_evidence
from app.resume_intelligence.models import JobRequirement, ResumeIntelligenceJobContext, ResumeVersionRecord
from app.resume_intelligence.selection import extract_job_requirements
from app.resume_intelligence.versioning import ResumeVersionStore, build_resume_version_store

from .models import (
    InterviewAuditEntry,
    InterviewParticipant,
    InterviewPreparationEvidenceReference,
    InterviewPreparationItem,
    InterviewPreparationPlan,
    InterviewPreparationRisk,
    InterviewPreparationSection,
    InterviewQuestion,
    InterviewQuestionFollowUp,
    InterviewQuestionNote,
    InterviewQuestionSet,
    InterviewStory,
    InterviewStoryCoverageLink,
    InterviewStoryGapPrompt,
    InterviewStoryQualityAssessment,
    InterviewStoryQualityDimension,
    InterviewStorySection,
    InterviewRecord,
    InterviewTimelineEvent,
)
from .question_generation import (
    QUESTION_PREPARATION_STATUSES,
    QUESTION_PRIORITIES,
    QUESTION_SET_LIMITS,
    QUESTION_SET_STATUSES,
    QUESTION_STRATEGY_VERSION,
    DeterministicInterviewQuestionGenerator,
    GeneratedInterviewQuestion,
    InterviewQuestionGenerator,
    QuestionCoveragePlan,
    QuestionExample,
    QuestionGenerationContext,
    ResumeClaim,
    build_question_coverage_plan,
    generator_metadata,
)
from .story_generation import (
    STORY_CATEGORIES,
    STORY_STATUSES,
    STORY_STRATEGY_VERSION,
    DeterministicInterviewStoryGenerator,
    GeneratedInterviewStory,
    StoryGenerationContext,
    StoryQuestionContext,
    StorySeed,
    InterviewStoryGenerator,
    story_group_id,
)

_ALLOWED_INTERVIEW_TYPES = {
    "recruiter_screen",
    "hiring_manager",
    "technical",
    "coding",
    "system_design",
    "behavioral",
    "panel",
    "executive",
    "onsite",
    "final",
}
_ALLOWED_INTERVIEW_STATUSES = {"planned", "scheduled", "completed", "cancelled", "rescheduled", "no_show"}
_ALLOWED_PREPARATION_STATUSES = {"not_started", "in_progress", "ready", "completed"}
_ACTIVE_UPCOMING_STATUSES = {"planned", "scheduled", "rescheduled"}
_PREPARATION_PLAN_STATUSES = {"generated", "updated"}
_PREPARATION_STRATEGY_VERSION = "interview_preparation_v1"
_FOCUS_CATEGORY_PRIORITY: dict[str, tuple[str, ...]] = {
    "recruiter_screen": ("signal", "seniority", "domain", "capability", "technology"),
    "hiring_manager": ("capability", "domain", "technology", "seniority", "signal"),
    "technical": ("technology", "capability", "domain", "signal"),
    "coding": ("technology", "capability", "signal"),
    "system_design": ("capability", "technology", "domain", "signal"),
    "behavioral": ("capability", "seniority", "domain", "signal"),
    "panel": ("capability", "technology", "domain", "seniority"),
    "executive": ("seniority", "capability", "domain", "signal"),
    "onsite": ("capability", "technology", "domain", "seniority"),
    "final": ("capability", "domain", "technology", "seniority"),
}
_QUESTION_TEMPLATES: dict[str, tuple[str, ...]] = {
    "recruiter_screen": (
        "How does this role fit into the broader team charter and hiring plan?",
        "What are the most important success signals for the first 90 days?",
        "How does the interview process evaluate technical depth versus execution history?",
    ),
    "hiring_manager": (
        "What are the highest-priority outcomes for this team over the next two quarters?",
        "Which technical tradeoffs or platform constraints shape the role most often?",
        "How do you measure success for a new engineer in this seat?",
    ),
    "technical": (
        "Which parts of the current architecture need the most improvement or ownership?",
        "What operational metrics matter most for this team in production?",
        "How does the team balance delivery speed with reliability and maintainability?",
    ),
    "coding": (
        "How are coding exercises evaluated beyond correctness?",
        "What kinds of production constraints do engineers on this team face most often?",
        "How closely do the interview problems mirror day-to-day engineering work?",
    ),
    "system_design": (
        "What scale, reliability, or latency constraints matter most for this platform?",
        "Which architecture decisions are still actively evolving on the team?",
        "How does the team review and operationalize large design proposals?",
    ),
    "behavioral": (
        "What kinds of cross-functional collaboration are most important in this role?",
        "Where do you most need leadership, ownership, or process improvement?",
        "How does the team define strong communication during ambiguous work?",
    ),
    "panel": (
        "Which themes should I expect to come up across the panel members?",
        "How do panel interviews usually divide technical depth, execution, and collaboration topics?",
        "Which current team priorities are most useful to understand before the panel?",
    ),
    "executive": (
        "What business outcomes matter most for this role in the next year?",
        "How does leadership evaluate strategic influence and decision quality here?",
        "Where does this team need stronger leverage or org-wide alignment?",
    ),
    "onsite": (
        "How are the onsite rounds sequenced, and what does each round emphasize?",
        "Which technical or collaboration signals tend to differentiate strong candidates here?",
        "What context about team workflows or systems should I understand beforehand?",
    ),
    "final": (
        "What concerns are still open at this stage of the process?",
        "What would make someone highly effective in this role during the first six months?",
        "How does the team approach growth, feedback, and scope expansion after hiring?",
    ),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return decoded
    return []


def _json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
    return {}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "_" for character in value.strip())
    return "_".join(segment for segment in normalized.split("_") if segment)


def _interview_id(user_id: str, application_id: str, interview_type: str, interview_round: str, scheduled_start_at: str) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"interview:{user_id}:{application_id}:{interview_type}:{interview_round}:{scheduled_start_at or _iso_now()}",
        )
    )


def _participant_id(interview_id: str, name: str, email: str) -> str:
    basis = email.strip().casefold() or _normalize_text(name) or "participant"
    return str(uuid5(NAMESPACE_URL, f"interview-participant:{interview_id}:{basis}"))


def _checklist_item_id(interview_id: str, label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-preparation-item:{interview_id}:{_normalize_text(label)}"))


def _preparation_plan_id(interview_id: str, version_number: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-preparation-plan:{interview_id}:{version_number}"))


def _question_set_id(interview_id: str, version_number: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-question-set:{interview_id}:{version_number}"))


def _question_id(question_set_id: str, category: str, question: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-question:{question_set_id}:{category}:{_normalize_text(question)}"))


def _question_note_id(question_id: str, body: str, created_at: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-question-note:{question_id}:{created_at}:{_normalize_text(body)}"))


def _story_id(story_group_id: str, version_number: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-story:{story_group_id}:{version_number}"))


def _preparation_reference_id(source_type: str, source_id: str, label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-preparation-reference:{source_type}:{source_id}:{_normalize_text(label)}"))


def _preparation_risk_id(interview_id: str, title: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-preparation-risk:{interview_id}:{_normalize_text(title)}"))


def _preparation_section_id(section_key: str, title: str) -> str:
    return f"{section_key}:{_normalize_text(title) or section_key}"


def _clean_lines(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = " ".join(str(value).split()).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _clean_excerpt(value: str, *, limit: int = 240) -> str:
    excerpt = " ".join(value.split()).strip()
    if len(excerpt) <= limit:
        return excerpt
    return f"{excerpt[: max(limit - 1, 1)].rstrip()}…"


def _round_confidence(value: float) -> float:
    return round(max(0.0, min(value, 1.0)), 2)


def _average_confidence(values: list[float]) -> float:
    if not values:
        return 0.0
    return _round_confidence(sum(values) / len(values))


def _json_string_list(value: object) -> list[str]:
    return [str(item) for item in _json_list(value) if str(item).strip()]


def _flatten_profile(profile: dict[str, list[object]]) -> list[KnowledgeEntity]:
    return [
        entity
        for entities in profile.values()
        for entity in entities
        if isinstance(entity, KnowledgeEntity)
    ]


def _reference(
    *,
    source_type: str,
    source_id: str,
    label: str,
    excerpt: str,
    confidence: float,
    evidence_id: str = "",
    relevance_explanation: str = "",
    entity_type: str = "",
    entity_id: str = "",
    metadata: dict[str, object] | None = None,
) -> InterviewPreparationEvidenceReference:
    return InterviewPreparationEvidenceReference(
        reference_id=_preparation_reference_id(source_type, source_id, label),
        source_type=source_type,
        source_id=source_id,
        label=label,
        excerpt=_clean_excerpt(excerpt),
        evidence_id=evidence_id,
        relevance_explanation=relevance_explanation,
        confidence=_round_confidence(confidence),
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=dict(metadata or {}),
    )


def _parse_evidence_references(items: object) -> list[InterviewPreparationEvidenceReference]:
    references: list[InterviewPreparationEvidenceReference] = []
    for item in _json_list(items):
        if not isinstance(item, dict):
            continue
        references.append(
            InterviewPreparationEvidenceReference(
                reference_id=str(item.get("reference_id") or _preparation_reference_id(str(item.get("source_type") or ""), str(item.get("source_id") or ""), str(item.get("label") or ""))),
                source_type=str(item.get("source_type") or ""),
                source_id=str(item.get("source_id") or ""),
                label=str(item.get("label") or ""),
                excerpt=str(item.get("excerpt") or ""),
                evidence_id=str(item.get("evidence_id") or ""),
                relevance_explanation=str(item.get("relevance_explanation") or ""),
                confidence=float(item.get("confidence") or 0.0),
                entity_type=str(item.get("entity_type") or ""),
                entity_id=str(item.get("entity_id") or ""),
                metadata=_json_object(item.get("metadata")),
            )
        )
    return references


def _parse_follow_up_questions(items: object) -> list[InterviewQuestionFollowUp]:
    follow_ups: list[InterviewQuestionFollowUp] = []
    for item in _json_list(items):
        if not isinstance(item, dict):
            continue
        follow_ups.append(
            InterviewQuestionFollowUp(
                follow_up_id=str(item.get("follow_up_id") or uuid5(NAMESPACE_URL, f"question-follow-up:{item}")),
                question=str(item.get("question") or ""),
                rationale=str(item.get("rationale") or ""),
                evaluation_dimensions=_json_string_list(item.get("evaluation_dimensions")),
                confidence=_round_confidence(float(item.get("confidence") or 0.0)),
            )
        )
    return follow_ups


def _parse_question_notes(items: object) -> list[InterviewQuestionNote]:
    notes: list[InterviewQuestionNote] = []
    for item in _json_list(items):
        if not isinstance(item, dict):
            continue
        notes.append(
            InterviewQuestionNote(
                note_id=str(item.get("note_id") or uuid5(NAMESPACE_URL, f"question-note:{item}")),
                body=str(item.get("body") or ""),
                created_at=str(item.get("created_at") or "") or None,
                updated_at=str(item.get("updated_at") or "") or None,
            )
        )
    return notes


def _parse_story_sections(items: object) -> list[InterviewStorySection]:
    sections: list[InterviewStorySection] = []
    for item in _json_list(items):
        if not isinstance(item, dict):
            continue
        sections.append(
            InterviewStorySection(
                section_key=str(item.get("section_key") or ""),
                title=str(item.get("title") or ""),
                content=_clean_lines([str(value) for value in _json_list(item.get("content"))]),
                evidence_references=_parse_evidence_references(item.get("evidence_references")),
                missing_fields=_json_string_list(item.get("missing_fields")),
            )
        )
    return sections


def _parse_story_gap_prompts(items: object) -> list[InterviewStoryGapPrompt]:
    prompts: list[InterviewStoryGapPrompt] = []
    for item in _json_list(items):
        if not isinstance(item, dict):
            continue
        prompts.append(
            InterviewStoryGapPrompt(
                prompt_id=str(item.get("prompt_id") or uuid5(NAMESPACE_URL, f"story-gap:{item}")),
                field_key=str(item.get("field_key") or ""),
                prompt=str(item.get("prompt") or ""),
                reason=str(item.get("reason") or ""),
                topic=str(item.get("topic") or ""),
                status=str(item.get("status") or "open"),
                related_evidence=_parse_evidence_references(item.get("related_evidence")),
                profile_evolution_payload=_json_object(item.get("profile_evolution_payload")),
                created_at=str(item.get("created_at") or "") or None,
                updated_at=str(item.get("updated_at") or "") or None,
            )
        )
    return prompts


def _parse_story_coverage(items: object) -> list[InterviewStoryCoverageLink]:
    links: list[InterviewStoryCoverageLink] = []
    for item in _json_list(items):
        if not isinstance(item, dict):
            continue
        links.append(
            InterviewStoryCoverageLink(
                question_id=str(item.get("question_id") or ""),
                question=str(item.get("question") or ""),
                category=str(item.get("category") or ""),
                coverage_score=_round_confidence(float(item.get("coverage_score") or 0.0)),
                reason=str(item.get("reason") or ""),
                confidence=_round_confidence(float(item.get("confidence") or 0.0)),
            )
        )
    return links


def _parse_story_quality(value: object) -> InterviewStoryQualityAssessment:
    payload = _json_object(value)
    dimensions = [
        InterviewStoryQualityDimension(
            label=str(item.get("label") or ""),
            score=int(item.get("score") or 0),
            rationale=str(item.get("rationale") or ""),
        )
        for item in _json_list(payload.get("dimensions"))
        if isinstance(item, dict)
    ]
    return InterviewStoryQualityAssessment(
        overall_score=int(payload.get("overall_score") or 0),
        dimensions=dimensions,
        summary=str(payload.get("summary") or ""),
        generated_at=str(payload.get("generated_at") or "") or None,
        strategy_version=str(payload.get("strategy_version") or ""),
    )


def _timeline_item(*, event_type: str, label: str, detail: str = "", occurred_at: str | None = None) -> InterviewTimelineEvent:
    return InterviewTimelineEvent(
        event_type=event_type,
        label=label,
        detail=detail,
        occurred_at=occurred_at or _iso_now(),
    )


def _audit_entry(*, event_type: str, actor_user_id: str, detail: str = "", created_at: str | None = None) -> InterviewAuditEntry:
    return InterviewAuditEntry(
        event_type=event_type,
        actor_user_id=actor_user_id,
        detail=detail,
        created_at=created_at or _iso_now(),
    )


def _default_checklist(interview_id: str, *, interview_type: str, scheduled_start_at: str | None) -> list[InterviewPreparationItem]:
    now = _iso_now()
    labels = [
        ("review_resume", "Review submitted resume version", "context"),
        ("review_recruiter_thread", "Review recruiter communication thread", "context"),
        ("prepare_evidence", "Prepare evidence-backed stories", "stories"),
        ("prepare_questions", "Prepare questions for the interviewer", "questions"),
        ("confirm_logistics", "Confirm agenda, meeting link, and timezone", "logistics"),
    ]
    if interview_type in {"system_design", "technical", "coding"}:
        labels.insert(3, ("review_architecture", "Review architecture and technical depth examples", "technical"))
    if interview_type in {"behavioral", "hiring_manager", "executive"}:
        labels.insert(3, ("review_leadership", "Review leadership and behavioral examples", "behavioral"))
    return [
        InterviewPreparationItem(
            item_id=_checklist_item_id(interview_id, label),
            label=label,
            status="pending",
            detail="System-generated preparation step for the interview workspace.",
            reason="Generated from the interview type and current workspace context.",
            estimated_effort="20m",
            priority="medium",
            category=category,
            source="interview_intelligence",
            due_at=scheduled_start_at,
            generated=True,
            updated_at=now,
        )
        for _, label, category in labels
    ]


def _derive_preparation_status(checklist: list[InterviewPreparationItem], current: str = "") -> str:
    if current in _ALLOWED_PREPARATION_STATUSES and current == "ready":
        return current
    if checklist and all(item.status == "completed" for item in checklist):
        return "completed"
    if any(item.status in {"completed", "in_progress"} for item in checklist):
        return "in_progress"
    if current in _ALLOWED_PREPARATION_STATUSES:
        return current
    return "not_started"


def _normalize_interview_type(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in _ALLOWED_INTERVIEW_TYPES:
        raise ValueError("Unsupported interview type.")
    return normalized


def _normalize_interview_status(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in _ALLOWED_INTERVIEW_STATUSES:
        raise ValueError("Unsupported interview status.")
    return normalized


def _normalize_preparation_status(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in _ALLOWED_PREPARATION_STATUSES:
        raise ValueError("Unsupported preparation status.")
    return normalized


def _normalize_interviewers(interview_id: str, items: list[InterviewParticipant | dict[str, object]] | None) -> list[InterviewParticipant]:
    normalized: list[InterviewParticipant] = []
    if not items:
        return normalized
    for item in items:
        payload = item.to_dict() if isinstance(item, InterviewParticipant) else item
        if not isinstance(payload, dict):
            continue
        name = str(payload.get("name") or "").strip()
        email = str(payload.get("email") or "").strip()
        if not name and not email:
            continue
        normalized.append(
            InterviewParticipant(
                participant_id=str(payload.get("participant_id") or _participant_id(interview_id, name or email, email)),
                name=name or email,
                email=email,
                title=str(payload.get("title") or ""),
                role=str(payload.get("role") or "interviewer"),
                source_contact_id=str(payload.get("source_contact_id") or ""),
            )
        )
    return normalized


def _normalize_checklist(
    interview_id: str,
    items: list[InterviewPreparationItem | dict[str, object]] | None,
    *,
    scheduled_start_at: str | None,
) -> list[InterviewPreparationItem]:
    normalized: list[InterviewPreparationItem] = []
    if items is None:
        return normalized
    now = _iso_now()
    for item in items:
        payload = item.to_dict() if isinstance(item, InterviewPreparationItem) else item
        if not isinstance(payload, dict):
            continue
        label = str(payload.get("label") or "").strip()
        if not label:
            continue
        item_status = str(payload.get("status") or "pending").strip().casefold()
        if item_status not in {"pending", "in_progress", "completed", "blocked", "skipped"}:
            raise ValueError("Unsupported interview preparation item status.")
        normalized.append(
            InterviewPreparationItem(
                item_id=str(payload.get("item_id") or _checklist_item_id(interview_id, label)),
                label=label,
                status=item_status,
                detail=str(payload.get("detail") or ""),
                reason=str(payload.get("reason") or ""),
                estimated_effort=str(payload.get("estimated_effort") or ""),
                priority=str(payload.get("priority") or "normal"),
                category=str(payload.get("category") or "preparation"),
                source=str(payload.get("source") or "manual"),
                due_at=str(payload.get("due_at")) if payload.get("due_at") else scheduled_start_at,
                completed_at=str(payload.get("completed_at")) if payload.get("completed_at") else None,
                generated=bool(payload.get("generated", False)),
                updated_at=str(payload.get("updated_at")) if payload.get("updated_at") else now,
                supporting_evidence=_parse_evidence_references(payload.get("supporting_evidence")),
            )
        )
    return normalized


def _row_to_interview(row) -> InterviewRecord:
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    completed_at = row["completed_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if completed_at is not None and completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    interviewers = [
        InterviewParticipant(**item)
        for item in _json_list(row["interviewers"])
        if isinstance(item, dict)
    ]
    checklist = [
        InterviewPreparationItem(
            item_id=str(item.get("item_id") or ""),
            label=str(item.get("label") or ""),
            status=str(item.get("status") or "pending"),
            detail=str(item.get("detail") or ""),
            reason=str(item.get("reason") or ""),
            estimated_effort=str(item.get("estimated_effort") or ""),
            priority=str(item.get("priority") or "normal"),
            category=str(item.get("category") or "preparation"),
            source=str(item.get("source") or "manual"),
            due_at=str(item.get("due_at")) if item.get("due_at") else None,
            completed_at=str(item.get("completed_at")) if item.get("completed_at") else None,
            generated=bool(item.get("generated", False)),
            updated_at=str(item.get("updated_at")) if item.get("updated_at") else None,
            supporting_evidence=_parse_evidence_references(item.get("supporting_evidence")),
        )
        for item in _json_list(row["preparation_checklist"])
        if isinstance(item, dict)
    ]
    timeline = [
        InterviewTimelineEvent(**item)
        for item in _json_list(row["timeline"])
        if isinstance(item, dict)
    ]
    audit_history = [
        InterviewAuditEntry(**item)
        for item in _json_list(row["audit_history"])
        if isinstance(item, dict)
    ]
    return InterviewRecord(
        interview_id=str(row["interview_id"]),
        application_id=str(row["application_id"]),
        user_id=str(row["user_id"]),
        interview_type=str(row["interview_type"]),
        interview_round=str(row["interview_round"] or ""),
        interview_status=str(row["interview_status"]),
        preparation_status=str(row["preparation_status"]),
        scheduled_start_at=str(row["scheduled_start_at"]) if row["scheduled_start_at"] else None,
        scheduled_end_at=str(row["scheduled_end_at"]) if row["scheduled_end_at"] else None,
        timezone=str(row["timezone"] or "UTC"),
        meeting_url=str(row["meeting_url"] or ""),
        recruiter_name=str(row["recruiter_name"] or ""),
        recruiter_email=str(row["recruiter_email"] or ""),
        recruiter_contact_id=str(row["recruiter_contact_id"] or ""),
        notes=str(row["notes"] or ""),
        source=str(row["source"] or "manual"),
        interviewers=interviewers,
        preparation_checklist=checklist,
        timeline=timeline,
        audit_history=audit_history,
        metadata=_json_object(row["metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
        completed_at=completed_at.isoformat() if completed_at is not None else None,
    )


class InterviewStore(Protocol):
    async def save(self, record: InterviewRecord) -> InterviewRecord:
        ...

    async def get(self, interview_id: str, *, user_id: str | None = None) -> InterviewRecord | None:
        ...

    async def list_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_status: str | None = None,
    ) -> list[InterviewRecord]:
        ...

    async def delete(self, interview_id: str, *, user_id: str | None = None) -> InterviewRecord | None:
        ...


@dataclass
class InMemoryInterviewStore:
    records: dict[str, InterviewRecord] | None = None

    def __post_init__(self) -> None:
        self.records = {} if self.records is None else self.records

    async def save(self, record: InterviewRecord) -> InterviewRecord:
        assert self.records is not None
        self.records[record.interview_id] = record
        return record

    async def get(self, interview_id: str, *, user_id: str | None = None) -> InterviewRecord | None:
        assert self.records is not None
        item = self.records.get(interview_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return item

    async def list_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_status: str | None = None,
    ) -> list[InterviewRecord]:
        assert self.records is not None
        items = [item for item in self.records.values() if item.user_id == user_id]
        if application_id is not None:
            items = [item for item in items if item.application_id == application_id]
        if interview_status is not None:
            items = [item for item in items if item.interview_status == interview_status]
        return sorted(
            items,
            key=lambda item: (_parse_datetime(item.scheduled_start_at) or _parse_datetime(item.updated_at) or datetime.min.replace(tzinfo=timezone.utc), item.interview_id),
            reverse=True,
        )

    async def delete(self, interview_id: str, *, user_id: str | None = None) -> InterviewRecord | None:
        assert self.records is not None
        item = self.records.get(interview_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        self.records.pop(interview_id, None)
        return item


class PostgresInterviewStore:
    async def save(self, record: InterviewRecord) -> InterviewRecord:
        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO interviews (
                    interview_id,
                    application_id,
                    user_id,
                    interview_type,
                    interview_round,
                    interview_status,
                    preparation_status,
                    scheduled_start_at,
                    scheduled_end_at,
                    timezone,
                    meeting_url,
                    recruiter_name,
                    recruiter_email,
                    recruiter_contact_id,
                    notes,
                    source,
                    interviewers,
                    preparation_checklist,
                    timeline,
                    audit_history,
                    metadata,
                    created_at,
                    updated_at,
                    completed_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8::timestamptz, $9::timestamptz, $10, $11, $12, $13, $14, $15, $16,
                    $17::jsonb, $18::jsonb, $19::jsonb, $20::jsonb, $21::jsonb, COALESCE($22::timestamptz, NOW()),
                    COALESCE($23::timestamptz, NOW()), $24::timestamptz
                )
                ON CONFLICT (interview_id) DO UPDATE SET
                    interview_type = EXCLUDED.interview_type,
                    interview_round = EXCLUDED.interview_round,
                    interview_status = EXCLUDED.interview_status,
                    preparation_status = EXCLUDED.preparation_status,
                    scheduled_start_at = EXCLUDED.scheduled_start_at,
                    scheduled_end_at = EXCLUDED.scheduled_end_at,
                    timezone = EXCLUDED.timezone,
                    meeting_url = EXCLUDED.meeting_url,
                    recruiter_name = EXCLUDED.recruiter_name,
                    recruiter_email = EXCLUDED.recruiter_email,
                    recruiter_contact_id = EXCLUDED.recruiter_contact_id,
                    notes = EXCLUDED.notes,
                    source = EXCLUDED.source,
                    interviewers = EXCLUDED.interviewers,
                    preparation_checklist = EXCLUDED.preparation_checklist,
                    timeline = EXCLUDED.timeline,
                    audit_history = EXCLUDED.audit_history,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW()),
                    completed_at = EXCLUDED.completed_at
                """,
                record.interview_id,
                record.application_id,
                record.user_id,
                record.interview_type,
                record.interview_round,
                record.interview_status,
                record.preparation_status,
                record.scheduled_start_at,
                record.scheduled_end_at,
                record.timezone,
                record.meeting_url,
                record.recruiter_name,
                record.recruiter_email,
                record.recruiter_contact_id,
                record.notes,
                record.source,
                json.dumps([item.to_dict() for item in record.interviewers]),
                json.dumps([item.to_dict() for item in record.preparation_checklist]),
                json.dumps([item.to_dict() for item in record.timeline]),
                json.dumps([item.to_dict() for item in record.audit_history]),
                json.dumps(record.metadata),
                record.created_at,
                record.updated_at,
                record.completed_at,
            )
        return record

    async def get(self, interview_id: str, *, user_id: str | None = None) -> InterviewRecord | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM interviews
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                interview_id,
                user_id,
            )
        return _row_to_interview(row) if row is not None else None

    async def list_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_status: str | None = None,
    ) -> list[InterviewRecord]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM interviews
                WHERE user_id = $1
                  AND ($2::text IS NULL OR application_id = $2)
                  AND ($3::text IS NULL OR interview_status = $3)
                ORDER BY scheduled_start_at DESC NULLS LAST, updated_at DESC
                """,
                user_id,
                application_id,
                interview_status,
            )
        return [_row_to_interview(row) for row in rows]

    async def delete(self, interview_id: str, *, user_id: str | None = None) -> InterviewRecord | None:
        item = await self.get(interview_id, user_id=user_id)
        if item is None:
            return None
        async with connection() as conn:
            await conn.execute(
                """
                DELETE FROM interviews
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                interview_id,
                user_id,
            )
        return item


def _row_to_preparation_plan(row) -> InterviewPreparationPlan:
    sections = [
        InterviewPreparationSection(
            section_key=str(item.get("section_key") or ""),
            title=str(item.get("title") or ""),
            content=_clean_lines([str(value) for value in _json_list(item.get("content"))]),
            evidence_references=_parse_evidence_references(item.get("evidence_references")),
            confidence=float(item.get("confidence") or 0.0),
            generated_at=str(item.get("generated_at")) if item.get("generated_at") else None,
            strategy_version=str(item.get("strategy_version") or ""),
        )
        for item in _json_list(row["sections"])
        if isinstance(item, dict)
    ]
    checklist = _normalize_checklist(
        str(row["interview_id"]),
        [item for item in _json_list(row["checklist"]) if isinstance(item, dict)],
        scheduled_start_at=None,
    )
    risks = [
        InterviewPreparationRisk(
            risk_id=str(item.get("risk_id") or ""),
            title=str(item.get("title") or ""),
            detail=str(item.get("detail") or ""),
            recommendation=str(item.get("recommendation") or ""),
            severity=str(item.get("severity") or "medium"),
            confidence=float(item.get("confidence") or 0.0),
            evidence_references=_parse_evidence_references(item.get("evidence_references")),
            generated_at=str(item.get("generated_at")) if item.get("generated_at") else None,
            strategy_version=str(item.get("strategy_version") or ""),
        )
        for item in _json_list(row["risks"])
        if isinstance(item, dict)
    ]
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    generated_at = row["generated_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if generated_at is not None and generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return InterviewPreparationPlan(
        plan_id=str(row["preparation_plan_id"]),
        interview_id=str(row["interview_id"]),
        application_id=str(row["application_id"]),
        user_id=str(row["user_id"]),
        version_number=int(row["version_number"]),
        status=str(row["status"] or "generated"),
        strategy_version=str(row["strategy_version"] or ""),
        focus_labels=_json_string_list(row["focus_labels"]),
        overall_confidence=float(row["overall_confidence"] or 0.0),
        sections=sections,
        checklist=checklist,
        risks=risks,
        metadata=_json_object(row["metadata"]),
        generated_at=generated_at.isoformat() if generated_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


class InterviewPreparationPlanStore(Protocol):
    async def save(self, plan: InterviewPreparationPlan) -> InterviewPreparationPlan:
        ...

    async def get_latest(self, interview_id: str, *, user_id: str | None = None) -> InterviewPreparationPlan | None:
        ...

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewPreparationPlan]:
        ...

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewPreparationPlan]:
        ...


@dataclass
class InMemoryInterviewPreparationPlanStore:
    records: dict[str, InterviewPreparationPlan] | None = None

    def __post_init__(self) -> None:
        self.records = {} if self.records is None else self.records

    async def save(self, plan: InterviewPreparationPlan) -> InterviewPreparationPlan:
        assert self.records is not None
        self.records[plan.plan_id] = plan
        return plan

    async def get_latest(self, interview_id: str, *, user_id: str | None = None) -> InterviewPreparationPlan | None:
        items = await self.list_for_interview(interview_id, user_id=user_id)
        return items[0] if items else None

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewPreparationPlan]:
        assert self.records is not None
        items = [item for item in self.records.values() if item.interview_id == interview_id]
        if user_id is not None:
            items = [item for item in items if item.user_id == user_id]
        return sorted(items, key=lambda item: (item.version_number, item.updated_at or item.generated_at or "", item.plan_id), reverse=True)

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewPreparationPlan]:
        assert self.records is not None
        deleted = await self.list_for_interview(interview_id, user_id=user_id)
        for item in deleted:
            self.records.pop(item.plan_id, None)
        return deleted


class PostgresInterviewPreparationPlanStore:
    async def save(self, plan: InterviewPreparationPlan) -> InterviewPreparationPlan:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO interview_preparation_plans (
                    preparation_plan_id,
                    interview_id,
                    application_id,
                    user_id,
                    version_number,
                    status,
                    strategy_version,
                    focus_labels,
                    overall_confidence,
                    sections,
                    checklist,
                    risks,
                    metadata,
                    created_at,
                    updated_at,
                    generated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10::jsonb, $11::jsonb, $12::jsonb, $13::jsonb,
                    COALESCE($14::timestamptz, NOW()), COALESCE($15::timestamptz, NOW()), COALESCE($16::timestamptz, NOW())
                )
                ON CONFLICT (interview_id, version_number) DO UPDATE SET
                    status = EXCLUDED.status,
                    strategy_version = EXCLUDED.strategy_version,
                    focus_labels = EXCLUDED.focus_labels,
                    overall_confidence = EXCLUDED.overall_confidence,
                    sections = EXCLUDED.sections,
                    checklist = EXCLUDED.checklist,
                    risks = EXCLUDED.risks,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW()),
                    generated_at = COALESCE(EXCLUDED.generated_at, interview_preparation_plans.generated_at)
                RETURNING *
                """,
                plan.plan_id,
                plan.interview_id,
                plan.application_id,
                plan.user_id,
                plan.version_number,
                plan.status,
                plan.strategy_version,
                json.dumps(plan.focus_labels),
                plan.overall_confidence,
                json.dumps([item.to_dict() for item in plan.sections]),
                json.dumps([item.to_dict() for item in plan.checklist]),
                json.dumps([item.to_dict() for item in plan.risks]),
                json.dumps(plan.metadata),
                plan.generated_at,
                plan.updated_at,
                plan.generated_at,
            )
        assert row is not None
        return _row_to_preparation_plan(row)

    async def get_latest(self, interview_id: str, *, user_id: str | None = None) -> InterviewPreparationPlan | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM interview_preparation_plans
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY version_number DESC, updated_at DESC
                LIMIT 1
                """,
                interview_id,
                user_id,
            )
        return _row_to_preparation_plan(row) if row is not None else None

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewPreparationPlan]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM interview_preparation_plans
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY version_number DESC, updated_at DESC
                """,
                interview_id,
                user_id,
            )
        return [_row_to_preparation_plan(row) for row in rows]

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewPreparationPlan]:
        items = await self.list_for_interview(interview_id, user_id=user_id)
        async with connection() as conn:
            await conn.execute(
                """
                DELETE FROM interview_preparation_plans
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                interview_id,
                user_id,
            )
        return items


def build_interview_preparation_plan_store(settings: AppSettings | None = None) -> InterviewPreparationPlanStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryInterviewPreparationPlanStore()
    return PostgresInterviewPreparationPlanStore()


def _build_question_set(
    record: InterviewQuestionSet,
    *,
    questions: list[InterviewQuestion],
) -> InterviewQuestionSet:
    return InterviewQuestionSet(
        question_set_id=record.question_set_id,
        interview_id=record.interview_id,
        application_id=record.application_id,
        user_id=record.user_id,
        version_number=record.version_number,
        status=record.status,
        title=record.title,
        interview_type=record.interview_type,
        interview_round=record.interview_round,
        strategy_version=record.strategy_version,
        source_preparation_plan_id=record.source_preparation_plan_id,
        provider=record.provider,
        model_key=record.model_key,
        metadata=dict(record.metadata),
        generated_at=record.generated_at,
        updated_at=record.updated_at,
        superseded_by_question_set_id=record.superseded_by_question_set_id,
        questions=questions,
    )


def _row_to_question(row) -> InterviewQuestion:
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return InterviewQuestion(
        question_id=str(row["question_id"]),
        question_set_id=str(row["question_set_id"]),
        interview_id=str(row["interview_id"]),
        application_id=str(row["application_id"]),
        user_id=str(row["user_id"]),
        category=str(row["category"] or ""),
        question=str(row["question"] or ""),
        rationale=str(row["rationale"] or ""),
        evaluation_dimensions=_json_string_list(row["evaluation_dimensions"]),
        related_job_requirements=_json_string_list(row["related_job_requirements"]),
        related_evidence=_parse_evidence_references(row["related_evidence"]),
        follow_up_questions=_parse_follow_up_questions(row["follow_up_questions"]),
        difficulty=str(row["difficulty"] or "intermediate"),
        priority=str(row["priority"] or "medium"),
        confidence=float(row["confidence"] or 0.0),
        expected_answer_outline=_json_string_list(row["expected_answer_outline"]),
        risk_tags=_json_string_list(row["risk_tags"]),
        sequence_order=int(row["sequence_order"] or 0),
        preparation_status=str(row["preparation_status"] or "not_started"),
        hidden=bool(row["hidden"]),
        archived=bool(row["archived"]),
        user_notes=_parse_question_notes(row["user_notes"]),
        metadata=_json_object(row["metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


def _row_to_question_set(row, *, questions: list[InterviewQuestion]) -> InterviewQuestionSet:
    generated_at = row["generated_at"]
    updated_at = row["updated_at"]
    if generated_at is not None and generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return InterviewQuestionSet(
        question_set_id=str(row["question_set_id"]),
        interview_id=str(row["interview_id"]),
        application_id=str(row["application_id"]),
        user_id=str(row["user_id"]),
        version_number=int(row["version_number"]),
        status=str(row["status"] or "draft"),
        title=str(row["title"] or ""),
        interview_type=str(row["interview_type"] or ""),
        interview_round=str(row["interview_round"] or ""),
        strategy_version=str(row["strategy_version"] or ""),
        source_preparation_plan_id=str(row["source_preparation_plan_id"] or ""),
        provider=str(row["provider"] or ""),
        model_key=str(row["model_key"] or ""),
        metadata=_json_object(row["metadata"]),
        generated_at=generated_at.isoformat() if generated_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
        superseded_by_question_set_id=str(row["superseded_by_question_set_id"] or ""),
        questions=questions,
    )


class InterviewQuestionBankStore(Protocol):
    async def save_set(self, question_set: InterviewQuestionSet) -> InterviewQuestionSet:
        ...

    async def get_set(self, question_set_id: str, *, user_id: str | None = None) -> InterviewQuestionSet | None:
        ...

    async def get_current_set(self, interview_id: str, *, user_id: str | None = None) -> InterviewQuestionSet | None:
        ...

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewQuestionSet]:
        ...

    async def replace_questions(self, question_set_id: str, questions: list[InterviewQuestion]) -> list[InterviewQuestion]:
        ...

    async def list_questions(self, question_set_id: str, *, user_id: str | None = None) -> list[InterviewQuestion]:
        ...

    async def get_question(self, question_id: str, *, user_id: str | None = None) -> InterviewQuestion | None:
        ...

    async def save_question(self, question: InterviewQuestion) -> InterviewQuestion:
        ...

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewQuestionSet]:
        ...


@dataclass
class InMemoryInterviewQuestionBankStore:
    question_sets: dict[str, InterviewQuestionSet] | None = None
    questions: dict[str, InterviewQuestion] | None = None

    def __post_init__(self) -> None:
        self.question_sets = {} if self.question_sets is None else self.question_sets
        self.questions = {} if self.questions is None else self.questions

    async def save_set(self, question_set: InterviewQuestionSet) -> InterviewQuestionSet:
        assert self.question_sets is not None
        self.question_sets[question_set.question_set_id] = _build_question_set(question_set, questions=list(question_set.questions))
        return await self.get_set(question_set.question_set_id, user_id=question_set.user_id) or question_set

    async def get_set(self, question_set_id: str, *, user_id: str | None = None) -> InterviewQuestionSet | None:
        assert self.question_sets is not None
        record = self.question_sets.get(question_set_id)
        if record is None:
            return None
        if user_id is not None and record.user_id != user_id:
            return None
        return _build_question_set(record, questions=await self.list_questions(question_set_id, user_id=user_id))

    async def get_current_set(self, interview_id: str, *, user_id: str | None = None) -> InterviewQuestionSet | None:
        items = await self.list_for_interview(interview_id, user_id=user_id)
        active = [item for item in items if item.status == "active"]
        return active[0] if active else (items[0] if items else None)

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewQuestionSet]:
        assert self.question_sets is not None
        records = [item for item in self.question_sets.values() if item.interview_id == interview_id]
        if user_id is not None:
            records = [item for item in records if item.user_id == user_id]
        ordered = sorted(records, key=lambda item: (item.version_number, item.updated_at or item.generated_at or "", item.question_set_id), reverse=True)
        return [
            _build_question_set(item, questions=await self.list_questions(item.question_set_id, user_id=user_id))
            for item in ordered
        ]

    async def replace_questions(self, question_set_id: str, questions: list[InterviewQuestion]) -> list[InterviewQuestion]:
        assert self.questions is not None
        for item in [question for question in self.questions.values() if question.question_set_id == question_set_id]:
            self.questions.pop(item.question_id, None)
        for question in questions:
            self.questions[question.question_id] = question
        question_set = await self.get_set(question_set_id)
        if question_set is not None:
            await self.save_set(_build_question_set(question_set, questions=questions))
        return await self.list_questions(question_set_id)

    async def list_questions(self, question_set_id: str, *, user_id: str | None = None) -> list[InterviewQuestion]:
        assert self.questions is not None
        items = [item for item in self.questions.values() if item.question_set_id == question_set_id]
        if user_id is not None:
            items = [item for item in items if item.user_id == user_id]
        return sorted(items, key=lambda item: (item.sequence_order, item.question_id))

    async def get_question(self, question_id: str, *, user_id: str | None = None) -> InterviewQuestion | None:
        assert self.questions is not None
        item = self.questions.get(question_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return item

    async def save_question(self, question: InterviewQuestion) -> InterviewQuestion:
        assert self.questions is not None
        self.questions[question.question_id] = question
        question_set = await self.get_set(question.question_set_id, user_id=question.user_id)
        if question_set is not None:
            questions = await self.list_questions(question.question_set_id, user_id=question.user_id)
            await self.save_set(_build_question_set(question_set, questions=questions))
        return question

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewQuestionSet]:
        assert self.question_sets is not None
        deleted = await self.list_for_interview(interview_id, user_id=user_id)
        for item in deleted:
            self.question_sets.pop(item.question_set_id, None)
            assert self.questions is not None
            for question in [question for question in self.questions.values() if question.question_set_id == item.question_set_id]:
                self.questions.pop(question.question_id, None)
        return deleted


class PostgresInterviewQuestionBankStore:
    async def save_set(self, question_set: InterviewQuestionSet) -> InterviewQuestionSet:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO interview_question_sets (
                    question_set_id,
                    interview_id,
                    application_id,
                    user_id,
                    version_number,
                    status,
                    title,
                    interview_type,
                    interview_round,
                    strategy_version,
                    source_preparation_plan_id,
                    provider,
                    model_key,
                    metadata,
                    generated_at,
                    updated_at,
                    superseded_by_question_set_id
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb,
                    COALESCE($15::timestamptz, NOW()), COALESCE($16::timestamptz, NOW()), NULLIF($17, '')
                )
                ON CONFLICT (interview_id, version_number) DO UPDATE SET
                    status = EXCLUDED.status,
                    title = EXCLUDED.title,
                    interview_type = EXCLUDED.interview_type,
                    interview_round = EXCLUDED.interview_round,
                    strategy_version = EXCLUDED.strategy_version,
                    source_preparation_plan_id = EXCLUDED.source_preparation_plan_id,
                    provider = EXCLUDED.provider,
                    model_key = EXCLUDED.model_key,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW()),
                    generated_at = COALESCE(EXCLUDED.generated_at, interview_question_sets.generated_at),
                    superseded_by_question_set_id = EXCLUDED.superseded_by_question_set_id
                RETURNING *
                """,
                question_set.question_set_id,
                question_set.interview_id,
                question_set.application_id,
                question_set.user_id,
                question_set.version_number,
                question_set.status,
                question_set.title,
                question_set.interview_type,
                question_set.interview_round,
                question_set.strategy_version,
                question_set.source_preparation_plan_id,
                question_set.provider,
                question_set.model_key,
                json.dumps(question_set.metadata),
                question_set.generated_at,
                question_set.updated_at,
                question_set.superseded_by_question_set_id,
            )
        assert row is not None
        return await self.get_set(str(row["question_set_id"]), user_id=question_set.user_id) or _row_to_question_set(row, questions=[])

    async def get_set(self, question_set_id: str, *, user_id: str | None = None) -> InterviewQuestionSet | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM interview_question_sets
                WHERE question_set_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                question_set_id,
                user_id,
            )
        if row is None:
            return None
        questions = await self.list_questions(question_set_id, user_id=user_id)
        return _row_to_question_set(row, questions=questions)

    async def get_current_set(self, interview_id: str, *, user_id: str | None = None) -> InterviewQuestionSet | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM interview_question_sets
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, version_number DESC, updated_at DESC
                LIMIT 1
                """,
                interview_id,
                user_id,
            )
        if row is None:
            return None
        questions = await self.list_questions(str(row["question_set_id"]), user_id=user_id)
        return _row_to_question_set(row, questions=questions)

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewQuestionSet]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM interview_question_sets
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY version_number DESC, updated_at DESC
                """,
                interview_id,
                user_id,
            )
        items: list[InterviewQuestionSet] = []
        for row in rows:
            questions = await self.list_questions(str(row["question_set_id"]), user_id=user_id)
            items.append(_row_to_question_set(row, questions=questions))
        return items

    async def replace_questions(self, question_set_id: str, questions: list[InterviewQuestion]) -> list[InterviewQuestion]:
        async with connection() as conn:
            await conn.execute(
                """
                DELETE FROM interview_questions
                WHERE question_set_id = $1
                """,
                question_set_id,
            )
            for question in questions:
                await conn.execute(
                    """
                    INSERT INTO interview_questions (
                        question_id,
                        question_set_id,
                        interview_id,
                        application_id,
                        user_id,
                        category,
                        question,
                        rationale,
                        evaluation_dimensions,
                        related_job_requirements,
                        related_evidence,
                        follow_up_questions,
                        difficulty,
                        priority,
                        confidence,
                        expected_answer_outline,
                        risk_tags,
                        sequence_order,
                        preparation_status,
                        hidden,
                        archived,
                        user_notes,
                        metadata,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb, $11::jsonb, $12::jsonb, $13, $14, $15,
                        $16::jsonb, $17::jsonb, $18, $19, $20, $21, $22::jsonb, $23::jsonb,
                        COALESCE($24::timestamptz, NOW()), COALESCE($25::timestamptz, NOW())
                    )
                    """,
                    question.question_id,
                    question.question_set_id,
                    question.interview_id,
                    question.application_id,
                    question.user_id,
                    question.category,
                    question.question,
                    question.rationale,
                    json.dumps(question.evaluation_dimensions),
                    json.dumps(question.related_job_requirements),
                    json.dumps([item.to_dict() for item in question.related_evidence]),
                    json.dumps([item.to_dict() for item in question.follow_up_questions]),
                    question.difficulty,
                    question.priority,
                    question.confidence,
                    json.dumps(question.expected_answer_outline),
                    json.dumps(question.risk_tags),
                    question.sequence_order,
                    question.preparation_status,
                    question.hidden,
                    question.archived,
                    json.dumps([item.to_dict() for item in question.user_notes]),
                    json.dumps(question.metadata),
                    question.created_at,
                    question.updated_at,
                )
        return await self.list_questions(question_set_id)

    async def list_questions(self, question_set_id: str, *, user_id: str | None = None) -> list[InterviewQuestion]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM interview_questions
                WHERE question_set_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY sequence_order ASC, created_at ASC
                """,
                question_set_id,
                user_id,
            )
        return [_row_to_question(row) for row in rows]

    async def get_question(self, question_id: str, *, user_id: str | None = None) -> InterviewQuestion | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM interview_questions
                WHERE question_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                question_id,
                user_id,
            )
        return _row_to_question(row) if row is not None else None

    async def save_question(self, question: InterviewQuestion) -> InterviewQuestion:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO interview_questions (
                    question_id,
                    question_set_id,
                    interview_id,
                    application_id,
                    user_id,
                    category,
                    question,
                    rationale,
                    evaluation_dimensions,
                    related_job_requirements,
                    related_evidence,
                    follow_up_questions,
                    difficulty,
                    priority,
                    confidence,
                    expected_answer_outline,
                    risk_tags,
                    sequence_order,
                    preparation_status,
                    hidden,
                    archived,
                    user_notes,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10::jsonb, $11::jsonb, $12::jsonb, $13, $14, $15,
                    $16::jsonb, $17::jsonb, $18, $19, $20, $21, $22::jsonb, $23::jsonb,
                    COALESCE($24::timestamptz, NOW()), COALESCE($25::timestamptz, NOW())
                )
                ON CONFLICT (question_id) DO UPDATE SET
                    category = EXCLUDED.category,
                    question = EXCLUDED.question,
                    rationale = EXCLUDED.rationale,
                    evaluation_dimensions = EXCLUDED.evaluation_dimensions,
                    related_job_requirements = EXCLUDED.related_job_requirements,
                    related_evidence = EXCLUDED.related_evidence,
                    follow_up_questions = EXCLUDED.follow_up_questions,
                    difficulty = EXCLUDED.difficulty,
                    priority = EXCLUDED.priority,
                    confidence = EXCLUDED.confidence,
                    expected_answer_outline = EXCLUDED.expected_answer_outline,
                    risk_tags = EXCLUDED.risk_tags,
                    sequence_order = EXCLUDED.sequence_order,
                    preparation_status = EXCLUDED.preparation_status,
                    hidden = EXCLUDED.hidden,
                    archived = EXCLUDED.archived,
                    user_notes = EXCLUDED.user_notes,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                RETURNING *
                """,
                question.question_id,
                question.question_set_id,
                question.interview_id,
                question.application_id,
                question.user_id,
                question.category,
                question.question,
                question.rationale,
                json.dumps(question.evaluation_dimensions),
                json.dumps(question.related_job_requirements),
                json.dumps([item.to_dict() for item in question.related_evidence]),
                json.dumps([item.to_dict() for item in question.follow_up_questions]),
                question.difficulty,
                question.priority,
                question.confidence,
                json.dumps(question.expected_answer_outline),
                json.dumps(question.risk_tags),
                question.sequence_order,
                question.preparation_status,
                question.hidden,
                question.archived,
                json.dumps([item.to_dict() for item in question.user_notes]),
                json.dumps(question.metadata),
                question.created_at,
                question.updated_at,
            )
        assert row is not None
        return _row_to_question(row)

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewQuestionSet]:
        items = await self.list_for_interview(interview_id, user_id=user_id)
        async with connection() as conn:
            await conn.execute(
                """
                DELETE FROM interview_question_sets
                WHERE interview_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                interview_id,
                user_id,
            )
        return items


def build_interview_question_bank_store(settings: AppSettings | None = None) -> InterviewQuestionBankStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryInterviewQuestionBankStore()
    return PostgresInterviewQuestionBankStore()


def _row_to_story(row) -> InterviewStory:
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return InterviewStory(
        story_id=str(row["story_id"]),
        story_group_id=str(row["story_group_id"]),
        user_id=str(row["user_id"]),
        application_id=str(row["application_id"]) if row["application_id"] else None,
        interview_id=str(row["interview_id"]) if row["interview_id"] else None,
        linked_application_ids=_json_string_list(row["linked_application_ids"]),
        linked_interview_ids=_json_string_list(row["linked_interview_ids"]),
        title=str(row["title"] or ""),
        category=str(row["category"] or ""),
        source_evidence=_parse_evidence_references(row["source_evidence"]),
        related_projects=_json_string_list(row["related_projects"]),
        related_resume_version_id=str(row["related_resume_version_id"] or ""),
        related_question_ids=_json_string_list(row["related_question_ids"]),
        interview_types=_json_string_list(row["interview_types"]),
        tags=_json_string_list(row["tags"]),
        version_number=int(row["version_number"] or 1),
        status=str(row["status"] or "draft"),
        sections=_parse_story_sections(row["sections"]),
        technical_decisions=_json_string_list(row["technical_decisions"]),
        tradeoffs=_json_string_list(row["tradeoffs"]),
        leadership_moments=_json_string_list(row["leadership_moments"]),
        measurable_outcomes=_json_string_list(row["measurable_outcomes"]),
        lessons_learned=_json_string_list(row["lessons_learned"]),
        interviewer_follow_ups=_json_string_list(row["interviewer_follow_ups"]),
        coverage=_parse_story_coverage(row["coverage"]),
        quality=_parse_story_quality(row["quality"]),
        missing_information_prompts=_parse_story_gap_prompts(row["missing_information_prompts"]),
        superseded_by_story_id=str(row["superseded_by_story_id"] or ""),
        metadata=_json_object(row["metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


class InterviewStoryStore(Protocol):
    async def save(self, story: InterviewStory) -> InterviewStory:
        ...

    async def get(self, story_id: str, *, user_id: str | None = None) -> InterviewStory | None:
        ...

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        ...

    async def list_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_id: str | None = None,
        status: str | None = None,
    ) -> list[InterviewStory]:
        ...

    async def list_for_group(
        self,
        story_group_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        ...

    async def get_current_for_group(
        self,
        story_group_id: str,
        *,
        user_id: str | None = None,
    ) -> InterviewStory | None:
        ...

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        ...


def _story_sort_key(story: InterviewStory) -> tuple[datetime, int, str]:
    moment = _parse_datetime(story.updated_at) or _parse_datetime(story.created_at) or datetime.min.replace(tzinfo=timezone.utc)
    return moment, story.version_number, story.story_id


@dataclass
class InMemoryInterviewStoryStore:
    records: dict[str, InterviewStory] | None = None

    def __post_init__(self) -> None:
        self.records = {} if self.records is None else self.records

    async def save(self, story: InterviewStory) -> InterviewStory:
        assert self.records is not None
        self.records[story.story_id] = story
        return story

    async def get(self, story_id: str, *, user_id: str | None = None) -> InterviewStory | None:
        assert self.records is not None
        item = self.records.get(story_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return item

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        assert self.records is not None
        items = [
            item
            for item in self.records.values()
            if item.interview_id == interview_id or interview_id in item.linked_interview_ids
        ]
        if user_id is not None:
            items = [item for item in items if item.user_id == user_id]
        return sorted(items, key=_story_sort_key, reverse=True)

    async def list_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_id: str | None = None,
        status: str | None = None,
    ) -> list[InterviewStory]:
        assert self.records is not None
        items = [item for item in self.records.values() if item.user_id == user_id]
        if application_id is not None:
            items = [
                item
                for item in items
                if item.application_id == application_id or application_id in item.linked_application_ids
            ]
        if interview_id is not None:
            items = [
                item
                for item in items
                if item.interview_id == interview_id or interview_id in item.linked_interview_ids
            ]
        if status is not None:
            items = [item for item in items if item.status == status]
        return sorted(items, key=_story_sort_key, reverse=True)

    async def list_for_group(
        self,
        story_group_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        assert self.records is not None
        items = [item for item in self.records.values() if item.story_group_id == story_group_id]
        if user_id is not None:
            items = [item for item in items if item.user_id == user_id]
        return sorted(items, key=_story_sort_key, reverse=True)

    async def get_current_for_group(
        self,
        story_group_id: str,
        *,
        user_id: str | None = None,
    ) -> InterviewStory | None:
        versions = await self.list_for_group(story_group_id, user_id=user_id)
        active = [item for item in versions if item.status not in {"superseded", "archived"}]
        if active:
            return active[0]
        return versions[0] if versions else None

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        assert self.records is not None
        deleted = await self.list_for_interview(interview_id, user_id=user_id)
        for item in deleted:
            self.records.pop(item.story_id, None)
        return deleted


class PostgresInterviewStoryStore:
    async def save(self, story: InterviewStory) -> InterviewStory:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO interview_stories (
                    story_id,
                    story_group_id,
                    user_id,
                    application_id,
                    interview_id,
                    linked_application_ids,
                    linked_interview_ids,
                    title,
                    category,
                    source_evidence,
                    related_projects,
                    related_resume_version_id,
                    related_question_ids,
                    interview_types,
                    tags,
                    version_number,
                    status,
                    sections,
                    technical_decisions,
                    tradeoffs,
                    leadership_moments,
                    measurable_outcomes,
                    lessons_learned,
                    interviewer_follow_ups,
                    coverage,
                    quality,
                    missing_information_prompts,
                    superseded_by_story_id,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, NULLIF($4, ''), NULLIF($5, ''), $6::jsonb, $7::jsonb, $8, $9, $10::jsonb, $11::jsonb,
                    $12, $13::jsonb, $14::jsonb, $15::jsonb, $16, $17, $18::jsonb, $19::jsonb, $20::jsonb, $21::jsonb,
                    $22::jsonb, $23::jsonb, $24::jsonb, $25::jsonb, $26::jsonb, $27::jsonb, NULLIF($28, ''), $29::jsonb,
                    COALESCE($30::timestamptz, NOW()), COALESCE($31::timestamptz, NOW())
                )
                ON CONFLICT (story_id) DO UPDATE SET
                    application_id = EXCLUDED.application_id,
                    interview_id = EXCLUDED.interview_id,
                    linked_application_ids = EXCLUDED.linked_application_ids,
                    linked_interview_ids = EXCLUDED.linked_interview_ids,
                    title = EXCLUDED.title,
                    category = EXCLUDED.category,
                    source_evidence = EXCLUDED.source_evidence,
                    related_projects = EXCLUDED.related_projects,
                    related_resume_version_id = EXCLUDED.related_resume_version_id,
                    related_question_ids = EXCLUDED.related_question_ids,
                    interview_types = EXCLUDED.interview_types,
                    tags = EXCLUDED.tags,
                    status = EXCLUDED.status,
                    sections = EXCLUDED.sections,
                    technical_decisions = EXCLUDED.technical_decisions,
                    tradeoffs = EXCLUDED.tradeoffs,
                    leadership_moments = EXCLUDED.leadership_moments,
                    measurable_outcomes = EXCLUDED.measurable_outcomes,
                    lessons_learned = EXCLUDED.lessons_learned,
                    interviewer_follow_ups = EXCLUDED.interviewer_follow_ups,
                    coverage = EXCLUDED.coverage,
                    quality = EXCLUDED.quality,
                    missing_information_prompts = EXCLUDED.missing_information_prompts,
                    superseded_by_story_id = EXCLUDED.superseded_by_story_id,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                RETURNING *
                """,
                story.story_id,
                story.story_group_id,
                story.user_id,
                story.application_id or "",
                story.interview_id or "",
                json.dumps(story.linked_application_ids),
                json.dumps(story.linked_interview_ids),
                story.title,
                story.category,
                json.dumps([item.to_dict() for item in story.source_evidence]),
                json.dumps(story.related_projects),
                story.related_resume_version_id,
                json.dumps(story.related_question_ids),
                json.dumps(story.interview_types),
                json.dumps(story.tags),
                story.version_number,
                story.status,
                json.dumps([item.to_dict() for item in story.sections]),
                json.dumps(story.technical_decisions),
                json.dumps(story.tradeoffs),
                json.dumps(story.leadership_moments),
                json.dumps(story.measurable_outcomes),
                json.dumps(story.lessons_learned),
                json.dumps(story.interviewer_follow_ups),
                json.dumps([item.to_dict() for item in story.coverage]),
                json.dumps(story.quality.to_dict()),
                json.dumps([item.to_dict() for item in story.missing_information_prompts]),
                story.superseded_by_story_id,
                json.dumps(story.metadata),
                story.created_at,
                story.updated_at,
            )
        assert row is not None
        return _row_to_story(row)

    async def get(self, story_id: str, *, user_id: str | None = None) -> InterviewStory | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM interview_stories
                WHERE story_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                story_id,
                user_id,
            )
        return _row_to_story(row) if row is not None else None

    async def list_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM interview_stories
                WHERE ($1::text = interview_id OR linked_interview_ids ? $1)
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY updated_at DESC, version_number DESC
                """,
                interview_id,
                user_id,
            )
        return [_row_to_story(row) for row in rows]

    async def list_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_id: str | None = None,
        status: str | None = None,
    ) -> list[InterviewStory]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM interview_stories
                WHERE user_id = $1
                  AND ($2::text IS NULL OR application_id = $2 OR linked_application_ids ? $2)
                  AND ($3::text IS NULL OR interview_id = $3 OR linked_interview_ids ? $3)
                  AND ($4::text IS NULL OR status = $4)
                ORDER BY updated_at DESC, version_number DESC
                """,
                user_id,
                application_id,
                interview_id,
                status,
            )
        return [_row_to_story(row) for row in rows]

    async def list_for_group(
        self,
        story_group_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM interview_stories
                WHERE story_group_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY version_number DESC, updated_at DESC
                """,
                story_group_id,
                user_id,
            )
        return [_row_to_story(row) for row in rows]

    async def get_current_for_group(
        self,
        story_group_id: str,
        *,
        user_id: str | None = None,
    ) -> InterviewStory | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM interview_stories
                WHERE story_group_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                ORDER BY CASE WHEN status IN ('review', 'draft', 'approved') THEN 0 ELSE 1 END,
                         version_number DESC,
                         updated_at DESC
                LIMIT 1
                """,
                story_group_id,
                user_id,
            )
        return _row_to_story(row) if row is not None else None

    async def delete_for_interview(
        self,
        interview_id: str,
        *,
        user_id: str | None = None,
    ) -> list[InterviewStory]:
        items = await self.list_for_interview(interview_id, user_id=user_id)
        async with connection() as conn:
            await conn.execute(
                """
                DELETE FROM interview_stories
                WHERE ($1::text = interview_id OR linked_interview_ids ? $1)
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                interview_id,
                user_id,
            )
        return items


def build_interview_story_store(settings: AppSettings | None = None) -> InterviewStoryStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryInterviewStoryStore()
    return PostgresInterviewStoryStore()


def build_interview_store(settings: AppSettings | None = None) -> InterviewStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryInterviewStore()
    return PostgresInterviewStore()


def _section(
    *,
    section_key: str,
    title: str,
    content: list[str],
    evidence_references: list[InterviewPreparationEvidenceReference],
    confidence: float,
    generated_at: str,
) -> InterviewPreparationSection:
    return InterviewPreparationSection(
        section_key=section_key,
        title=title,
        content=_clean_lines(content),
        evidence_references=evidence_references,
        confidence=_round_confidence(confidence),
        generated_at=generated_at,
        strategy_version=_PREPARATION_STRATEGY_VERSION,
    )


def _risk(
    *,
    interview_id: str,
    title: str,
    detail: str,
    recommendation: str,
    evidence_references: list[InterviewPreparationEvidenceReference],
    confidence: float,
    generated_at: str,
    severity: str = "medium",
) -> InterviewPreparationRisk:
    return InterviewPreparationRisk(
        risk_id=_preparation_risk_id(interview_id, title),
        title=title,
        detail=detail,
        recommendation=recommendation,
        severity=severity,
        confidence=_round_confidence(confidence),
        evidence_references=evidence_references,
        generated_at=generated_at,
        strategy_version=_PREPARATION_STRATEGY_VERSION,
    )


def _job_context_from_application(application: ApplicationRecord) -> ResumeIntelligenceJobContext | None:
    payload = _json_object(application.metadata.get("job"))
    if not payload:
        return None
    return ResumeIntelligenceJobContext(
        job_id=application.job_id,
        user_id=application.user_id,
        company=str(payload.get("company") or application.company),
        title=str(payload.get("title") or application.title),
        location=str(payload.get("location") or ""),
        remote_policy=str(payload.get("remote_policy") or ""),
        apply_url=str(payload.get("apply_url") or application.apply_url),
        description_text=str(payload.get("description_text") or ""),
        connector_key=str(payload.get("connector_key") or ""),
        published_at=str(payload.get("published_at")) if payload.get("published_at") else None,
        match_score=int(payload.get("match_score")) if isinstance(payload.get("match_score"), int) else application.match_score,
        decision=str(payload.get("decision") or application.decision),
        recommended_resume=str(payload.get("recommended_resume") or ""),
        why=_json_string_list(payload.get("why")),
        gaps=_json_string_list(payload.get("gaps")),
    )


def _communication_summary_from_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    summary = _json_object(payload.get("summary"))
    if summary:
        return summary
    return _json_object(payload)


def _requirement_reference(
    requirement: JobRequirement,
    *,
    job: ResumeIntelligenceJobContext | None,
    application: ApplicationRecord,
    detail: str = "",
    confidence: float = 0.6,
) -> InterviewPreparationEvidenceReference:
    context = detail.strip() or (
        f"{application.title} at {application.company} highlights {requirement.label} for this interview."
    )
    return _reference(
        source_type="job_requirement",
        source_id=f"{application.job_id}:{_normalize_text(requirement.label)}",
        label=requirement.label,
        excerpt=context,
        confidence=confidence,
        metadata={
            "category": requirement.category,
            "keywords": list(requirement.keywords),
            "job_title": job.title if job is not None else application.title,
            "company": job.company if job is not None else application.company,
        },
    )


def _score_requirement(
    requirement: JobRequirement,
    *,
    interview: InterviewRecord,
    job: ResumeIntelligenceJobContext | None,
    communication_summary: dict[str, object],
) -> int:
    priority = _FOCUS_CATEGORY_PRIORITY.get(interview.interview_type, ("capability", "technology", "domain", "signal"))
    category_score = max(len(priority) - priority.index(requirement.category), 1) if requirement.category in priority else 0
    job_labels = {label.casefold() for label in ((job.why if job is not None else []) + (job.gaps if job is not None else []))}
    summary_text = " ".join(
        [
            str(communication_summary.get("pending_action") or ""),
            str(communication_summary.get("reason") or ""),
            str(communication_summary.get("conversation_status") or ""),
            " ".join(_json_string_list(communication_summary.get("suggested_actions"))),
            " ".join(_json_string_list(communication_summary.get("focus_labels"))),
        ]
    ).casefold()
    score = category_score * 3
    if requirement.label.casefold() in job_labels:
        score += 3
    if requirement.label.casefold() in summary_text:
        score += 2
    if interview.interview_type in {"technical", "coding", "system_design"} and requirement.category in {"technology", "capability"}:
        score += 2
    if interview.interview_type in {"behavioral", "hiring_manager", "executive"} and requirement.category in {"capability", "seniority"}:
        score += 2
    if interview.interview_type in {"recruiter_screen"} and requirement.category in {"signal", "seniority", "domain"}:
        score += 1
    return score


def _select_focus_requirements(
    requirements: list[JobRequirement],
    *,
    interview: InterviewRecord,
    job: ResumeIntelligenceJobContext | None,
    communication_summary: dict[str, object],
    limit: int = 5,
) -> list[JobRequirement]:
    ranked = sorted(
        requirements,
        key=lambda requirement: (_score_requirement(requirement, interview=interview, job=job, communication_summary=communication_summary), requirement.label),
        reverse=True,
    )
    selected = [item for item in ranked if _score_requirement(item, interview=interview, job=job, communication_summary=communication_summary) > 0]
    return (selected or ranked)[: max(1, limit)] if ranked else []


def _resume_highlights(resume_version: ResumeVersionRecord, focus_labels: list[str], *, limit: int = 4) -> list[str]:
    accepted_changes = [
        item for item in resume_version.accepted_changes
        if isinstance(item, dict) and str(item.get("final_text") or "").strip()
    ]
    if accepted_changes:
        focused = [
            str(item.get("final_text") or "").strip()
            for item in accepted_changes
            if any(label.casefold() in " ".join(_json_string_list(item.get("job_requirements"))).casefold() for label in focus_labels)
        ]
        fallback = [str(item.get("final_text") or "").strip() for item in accepted_changes]
        return _clean_lines(focused or fallback)[:limit]
    selection = _json_object(resume_version.metadata.get("selection"))
    matched = _json_string_list(selection.get("matched_requirements"))
    if matched:
        return [f"Resume version was selected because it already emphasizes {label}." for label in matched[:limit]]
    return [f"Use the submitted resume version {resume_version.file_name} as the baseline narrative for this interview."]


def _merge_checklist_progress(
    current_items: list[InterviewPreparationItem],
    generated_items: list[InterviewPreparationItem],
) -> list[InterviewPreparationItem]:
    by_label = {_normalize_text(item.label): item for item in current_items}
    merged: list[InterviewPreparationItem] = []
    for item in generated_items:
        existing = by_label.get(_normalize_text(item.label))
        if existing is None:
            merged.append(item)
            continue
        merged.append(
            InterviewPreparationItem(
                item_id=item.item_id,
                label=item.label,
                status=existing.status,
                detail=item.detail,
                reason=item.reason,
                estimated_effort=item.estimated_effort,
                priority=item.priority,
                category=item.category,
                source=item.source,
                due_at=item.due_at,
                completed_at=existing.completed_at,
                generated=item.generated,
                updated_at=existing.updated_at or item.updated_at,
                supporting_evidence=item.supporting_evidence,
            )
        )
    return merged


def _story_content_lines(content: dict[str, object], keys: tuple[str, ...], *, limit: int = 4) -> list[str]:
    lines: list[str] = []
    for key in keys:
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            lines.extend(part.strip() for part in value.replace("\n", ". ").split(".") if part.strip())
        else:
            lines.extend(_json_string_list(value))
    return _clean_lines(lines)[:limit]


def _story_category_from_entity(entity: KnowledgeEntity) -> str:
    if entity.entity_type == "leadership":
        return "leadership"
    if entity.entity_type in {"achievement", "award"}:
        return "behavioral"
    if entity.entity_type in {"technology", "skill"}:
        return "technical"
    blob = f"{entity.canonical_name} {entity_text(entity)}".casefold()
    if any(term in blob for term in ("architecture", "distributed", "platform", "scaling", "system")):
        return "architecture"
    return "project"


def _story_tags_from_entity(entity: KnowledgeEntity) -> list[str]:
    content = entity.content
    values = [entity.canonical_name, entity.entity_type]
    for key in ("technologies", "skills", "domains", "focus_areas", "keywords", "tags"):
        values.extend(_json_string_list(content.get(key)))
    for key in ("summary", "impact", "text"):
        value = str(content.get(key) or "").strip()
        if value:
            values.extend(segment for segment in value.replace("/", " ").split() if len(segment) > 3)
    return _clean_lines(values)[:12]


def _story_title_from_claim(text: str) -> str:
    cleaned = " ".join(text.replace("-", " ").replace("•", " ").split()).strip()
    if not cleaned:
        return "Resume claim"
    return _clean_excerpt(cleaned, limit=72)


def _story_version_summaries(stories: list[InterviewStory]) -> list[dict[str, object]]:
    return [
        {
            "story_id": item.story_id,
            "story_group_id": item.story_group_id,
            "title": item.title,
            "category": item.category,
            "version_number": item.version_number,
            "status": item.status,
            "quality_score": item.quality.overall_score,
            "question_count": len(item.coverage),
            "missing_prompt_count": len(item.missing_information_prompts),
            "updated_at": item.updated_at,
        }
        for item in stories
    ]


def _current_story_versions(stories: list[InterviewStory]) -> list[InterviewStory]:
    by_group: dict[str, list[InterviewStory]] = {}
    for item in stories:
        by_group.setdefault(item.story_group_id, []).append(item)
    current: list[InterviewStory] = []
    for versions in by_group.values():
        ordered = sorted(versions, key=_story_sort_key, reverse=True)
        active = [item for item in ordered if item.status not in {"superseded", "archived"}]
        current.append(active[0] if active else ordered[0])
    return sorted(current, key=_story_sort_key, reverse=True)


def _story_duplicate_groups(stories: list[InterviewStory]) -> list[str]:
    by_key: dict[str, list[str]] = {}
    for item in stories:
        key = _normalize_text(item.related_projects[0] if item.related_projects else item.title)
        if not key:
            continue
        by_key.setdefault(key, []).append(item.story_group_id)
    duplicates: list[str] = []
    for groups in by_key.values():
        if len(set(groups)) > 1:
            duplicates.extend(sorted(set(groups)))
    return sorted(set(duplicates))


def _build_record(
    *,
    record: InterviewRecord,
    interview_type: str | None = None,
    interview_round: str | None = None,
    interview_status: str | None = None,
    preparation_status: str | None = None,
    scheduled_start_at: str | None = None,
    scheduled_end_at: str | None = None,
    timezone_name: str | None = None,
    meeting_url: str | None = None,
    recruiter_name: str | None = None,
    recruiter_email: str | None = None,
    recruiter_contact_id: str | None = None,
    notes: str | None = None,
    source: str | None = None,
    interviewers: list[InterviewParticipant] | None = None,
    preparation_checklist: list[InterviewPreparationItem] | None = None,
    timeline: list[InterviewTimelineEvent] | None = None,
    audit_history: list[InterviewAuditEntry] | None = None,
    metadata: dict[str, object] | None = None,
    updated_at: str | None = None,
    completed_at: str | None = None,
) -> InterviewRecord:
    return InterviewRecord(
        interview_id=record.interview_id,
        application_id=record.application_id,
        user_id=record.user_id,
        interview_type=interview_type or record.interview_type,
        interview_round=interview_round if interview_round is not None else record.interview_round,
        interview_status=interview_status or record.interview_status,
        preparation_status=preparation_status or record.preparation_status,
        scheduled_start_at=scheduled_start_at if scheduled_start_at is not None else record.scheduled_start_at,
        scheduled_end_at=scheduled_end_at if scheduled_end_at is not None else record.scheduled_end_at,
        timezone=timezone_name if timezone_name is not None else record.timezone,
        meeting_url=meeting_url if meeting_url is not None else record.meeting_url,
        recruiter_name=recruiter_name if recruiter_name is not None else record.recruiter_name,
        recruiter_email=recruiter_email if recruiter_email is not None else record.recruiter_email,
        recruiter_contact_id=recruiter_contact_id if recruiter_contact_id is not None else record.recruiter_contact_id,
        notes=notes if notes is not None else record.notes,
        source=source if source is not None else record.source,
        interviewers=interviewers if interviewers is not None else record.interviewers,
        preparation_checklist=preparation_checklist if preparation_checklist is not None else record.preparation_checklist,
        timeline=timeline if timeline is not None else record.timeline,
        audit_history=audit_history if audit_history is not None else record.audit_history,
        metadata=metadata if metadata is not None else record.metadata,
        created_at=record.created_at,
        updated_at=updated_at or record.updated_at,
        completed_at=completed_at if completed_at is not None else record.completed_at,
    )


def _application_interview_detail(record: InterviewRecord) -> str:
    parts = [record.interview_round.strip(), record.interview_type.replace("_", " ").title()]
    detail = " · ".join(part for part in parts if part)
    if record.scheduled_start_at:
        return f"{detail or 'Interview'} at {record.scheduled_start_at}"
    return detail or "Interview workspace updated"


@dataclass
class InterviewIntelligenceService:
    settings: AppSettings | None = None
    interview_store: InterviewStore | None = None
    application_service: ApplicationIntelligenceService | None = None
    preparation_store: InterviewPreparationPlanStore | None = None
    question_store: InterviewQuestionBankStore | None = None
    story_store: InterviewStoryStore | None = None
    knowledge_client: KnowledgePlatformClient | None = None
    recruiter_service: RecruiterIntelligenceService | None = None
    resume_service: ResumeIntelligenceService | None = None
    version_store: ResumeVersionStore | None = None
    question_generator: InterviewQuestionGenerator | None = None
    story_generator: InterviewStoryGenerator | None = None

    def _store(self) -> InterviewStore:
        if self.interview_store is not None:
            return self.interview_store
        return build_interview_store(self.settings)

    def _applications(self) -> ApplicationIntelligenceService:
        if self.application_service is not None:
            return self.application_service
        return build_application_intelligence_service(self.settings)

    def _preparations(self) -> InterviewPreparationPlanStore:
        if self.preparation_store is not None:
            return self.preparation_store
        return build_interview_preparation_plan_store(self.settings)

    def _questions(self) -> InterviewQuestionBankStore:
        if self.question_store is not None:
            return self.question_store
        return build_interview_question_bank_store(self.settings)

    def _stories(self) -> InterviewStoryStore:
        if self.story_store is not None:
            return self.story_store
        return build_interview_story_store(self.settings)

    def _knowledge(self) -> KnowledgePlatformClient:
        if self.knowledge_client is not None:
            return self.knowledge_client
        return build_knowledge_platform_client(self.settings)

    def _recruiters(self) -> RecruiterIntelligenceService:
        if self.recruiter_service is not None:
            return self.recruiter_service
        return build_recruiter_intelligence_service(self.settings)

    def _resume_intelligence(self) -> ResumeIntelligenceService:
        if self.resume_service is not None:
            return self.resume_service
        return build_resume_intelligence_service(self.settings)

    def _version_store(self) -> ResumeVersionStore:
        if self.version_store is not None:
            return self.version_store
        return build_resume_version_store(self.settings)

    def _question_generator(self) -> InterviewQuestionGenerator:
        if self.question_generator is not None:
            return self.question_generator
        return DeterministicInterviewQuestionGenerator()

    def _story_generator(self) -> InterviewStoryGenerator:
        if self.story_generator is not None:
            return self.story_generator
        return DeterministicInterviewStoryGenerator()

    async def _load_resume_version(self, application: ApplicationRecord) -> ResumeVersionRecord | None:
        return await self._version_store().get(application.resume_version_id, user_id=application.user_id)

    async def _load_job_context(self, user_id: str, application: ApplicationRecord) -> ResumeIntelligenceJobContext | None:
        job = await self._resume_intelligence().load_job_context(user_id, application.job_id)
        if job is not None:
            return job
        return _job_context_from_application(application)

    async def _load_communication_summary(self, user_id: str, application: ApplicationRecord) -> dict[str, object]:
        try:
            payload = await self._recruiters().get_application_communication(user_id, application.application_id)
        except ValueError:
            payload = {}
        summary = _communication_summary_from_payload(payload)
        if summary:
            return summary
        return _json_object(application.metadata.get("communication_summary"))

    async def _knowledge_entity_reference(
        self,
        user_id: str,
        entity: KnowledgeEntity,
        *,
        default_confidence: float = 0.85,
    ) -> InterviewPreparationEvidenceReference:
        evidence = await self._knowledge().find_evidence(user_id, entity_id=entity.id, limit=1)
        if evidence:
            item = evidence[0]
            confidence = item.metadata.get("confidence")
            resolved_confidence = float(confidence) if isinstance(confidence, (int, float)) else default_confidence
            return _reference(
                source_type=item.source_type,
                source_id=item.source_id,
                label=entity.canonical_name,
                excerpt=item.excerpt or entity_text(entity),
                confidence=resolved_confidence,
                entity_type=entity.entity_type,
                entity_id=entity.id,
                metadata=item.metadata,
            )
        return _reference(
            source_type=f"knowledge_{entity.entity_type}",
            source_id=entity.id,
            label=entity.canonical_name,
            excerpt=entity_text(entity),
            confidence=default_confidence,
            entity_type=entity.entity_type,
            entity_id=entity.id,
        )

    async def _knowledge_section_payload(
        self,
        user_id: str,
        entities: list[KnowledgeEntity],
        *,
        limit: int = 3,
    ) -> tuple[list[str], list[InterviewPreparationEvidenceReference]]:
        lines: list[str] = []
        references: list[InterviewPreparationEvidenceReference] = []
        seen: set[str] = set()
        for entity in entities:
            if entity.id in seen:
                continue
            seen.add(entity.id)
            summary = entity.content.get("summary") or entity.content.get("text") or entity.content.get("impact") or entity_text(entity)
            lines.append(f"{entity.canonical_name}: {_clean_excerpt(str(summary), limit=160)}")
            references.append(await self._knowledge_entity_reference(user_id, entity))
            if len(lines) >= limit:
                break
        return _clean_lines(lines), references

    async def _build_preparation_plan(
        self,
        interview: InterviewRecord,
        application: ApplicationRecord,
        *,
        version_number: int,
    ) -> InterviewPreparationPlan:
        now = _iso_now()
        job = await self._load_job_context(interview.user_id, application)
        resume_version = await self._load_resume_version(application)
        communication_summary = await self._load_communication_summary(interview.user_id, application)
        profile = await self._knowledge().get_profile(interview.user_id)
        knowledge_entities = _flatten_profile(profile)
        requirements = extract_job_requirements(job) if job is not None else []
        focus_requirements = _select_focus_requirements(
            requirements,
            interview=interview,
            job=job,
            communication_summary=communication_summary,
            limit=5,
        )
        focus_labels = [item.label for item in focus_requirements]

        requirement_refs: dict[str, list[InterviewPreparationEvidenceReference]] = {}
        missing_proof_flags: list[str] = []
        if focus_requirements:
            evidence_result = await retrieve_requirement_evidence(
                knowledge=self._knowledge().service,
                user_id=interview.user_id,
                requirements=focus_requirements,
                knowledge_entities=knowledge_entities,
            )
            missing_proof_flags = list(evidence_result.missing_proof_flags)
            requirements_by_label = {item.label: item for item in focus_requirements}
            for item in evidence_result.items:
                requirement = requirements_by_label.get(item.requirement_label)
                if requirement is None:
                    continue
                references = [
                    _reference(
                        source_type=evidence.source_type,
                        source_id=evidence.source_id,
                        label=item.requirement_label,
                        excerpt=evidence.excerpt,
                        confidence=evidence.confidence,
                        metadata={"category": item.category, "support_level": item.support_level},
                    )
                    for evidence in item.evidence
                ]
                if not references:
                    references = [
                        _requirement_reference(
                            requirement,
                            job=job,
                            application=application,
                            detail=item.rationale,
                            confidence=0.45 if item.support_level == "missing_proof" else 0.62,
                        )
                    ]
                requirement_refs[item.requirement_label] = references[:3]
        for requirement in focus_requirements:
            requirement_refs.setdefault(requirement.label, [_requirement_reference(requirement, job=job, application=application)])

        application_reference = _reference(
            source_type="application",
            source_id=application.application_id,
            label=f"{application.company} application",
            excerpt=f"{application.title} at {application.company} is currently in {application.status.replace('_', ' ')} status.",
            confidence=0.9,
            metadata={"job_id": application.job_id, "resume_version_id": application.resume_version_id},
        )
        job_reference = _reference(
            source_type="job_context",
            source_id=application.job_id,
            label=job.title if job is not None else application.title,
            excerpt=job.description_text if job is not None and job.description_text.strip() else f"{application.title} at {application.company}.",
            confidence=0.88 if job is not None else 0.6,
            metadata={"why": list(job.why) if job is not None else [], "gaps": list(job.gaps) if job is not None else []},
        )
        recruiter_reference = None
        if communication_summary:
            recruiter_reference = _reference(
                source_type="recruiter_summary",
                source_id=application.application_id,
                label="Recruiter communication",
                excerpt=" ".join(
                    part
                    for part in [
                        str(communication_summary.get("pending_action") or "").strip(),
                        str(communication_summary.get("reason") or "").strip(),
                        str(communication_summary.get("last_message_subject") or "").strip(),
                    ]
                    if part
                )
                or "Recruiter communication is linked to this application.",
                confidence=float(communication_summary.get("confidence") or 0.72)
                if isinstance(communication_summary.get("confidence"), (int, float))
                else 0.72,
                metadata={"waiting_on": communication_summary.get("waiting_on")},
            )

        resume_highlights = _resume_highlights(resume_version, focus_labels) if resume_version is not None else []
        resume_references = [
            _reference(
                source_type="resume_version",
                source_id=resume_version.version_id,
                label=resume_version.file_name,
                excerpt=highlight,
                confidence=0.82,
                metadata={"version_signature": resume_version.version_signature},
            )
            for highlight in resume_highlights[:3]
        ] if resume_version is not None else []

        project_candidates: list[KnowledgeEntity] = []
        for requirement in focus_requirements[:3]:
            if requirement.category == "domain":
                project_candidates.extend(await self._knowledge().find_projects(interview.user_id, domain=requirement.label, limit=3))
            else:
                project_candidates.extend(await self._knowledge().find_projects(interview.user_id, skill=requirement.label, limit=3))
                project_candidates.extend(await self._knowledge().search_projects(interview.user_id, requirement.label, limit=2))
        if not project_candidates:
            project_candidates.extend(await self._knowledge().find_backend_projects(interview.user_id, limit=3))
        project_lines, project_refs = await self._knowledge_section_payload(interview.user_id, project_candidates, limit=3)

        leadership_candidates = await self._knowledge().find_best_examples(interview.user_id, topic="leadership", limit=3)
        leadership_lines, leadership_refs = await self._knowledge_section_payload(interview.user_id, leadership_candidates, limit=3)
        achievement_candidates = await self._knowledge().find_best_examples(interview.user_id, topic="achievement", limit=3)
        achievement_lines, achievement_refs = await self._knowledge_section_payload(interview.user_id, achievement_candidates, limit=2)

        architecture_candidates: list[KnowledgeEntity] = []
        if interview.interview_type in {"technical", "system_design", "coding", "panel", "final", "onsite"}:
            architecture_candidates.extend(await self._knowledge().search_projects(interview.user_id, "architecture", limit=3))
            architecture_candidates.extend(await self._knowledge().search_projects(interview.user_id, "distributed systems", limit=2))
            architecture_candidates.extend(await self._knowledge().find_cloud_experience(interview.user_id, limit=2))
        architecture_lines, architecture_refs = await self._knowledge_section_payload(interview.user_id, architecture_candidates, limit=3)

        recent_experience = await self._knowledge().find_recent_experience(interview.user_id, limit=2)
        recent_lines, recent_refs = await self._knowledge_section_payload(interview.user_id, recent_experience, limit=2)

        technical_focus = [item for item in focus_requirements if item.category in {"technology", "capability"}]
        behavioral_focus = [item for item in focus_requirements if item.category in {"capability", "seniority", "signal"}]
        technical_lines = (
            [
                f"Refresh {requirement.label} with concrete tradeoffs, production constraints, and outcomes from your real work."
                for requirement in technical_focus[:4]
            ]
            if technical_focus
            else ["Keep one concise technical walkthrough ready in case the interviewer probes implementation detail."]
        )
        derived_behavioral_lines = (
            [
                f"Prepare a real story that demonstrates {requirement.label} through ownership, communication, or decision-making."
                for requirement in behavioral_focus[:3]
            ]
            if behavioral_focus
            else ["Prepare one ownership story and one collaboration story grounded in approved experience."]
        )
        if leadership_lines:
            derived_behavioral_lines.extend([f"Use {line}" for line in leadership_lines[:2]])
        behavioral_topic_lines = _clean_lines(derived_behavioral_lines)[:4]

        focus_lines = (
            [
                f"Expect emphasis on {requirement.label} because the role context and {interview.interview_type.replace('_', ' ')} format both point there."
                for requirement in focus_requirements[:5]
            ]
            if focus_requirements
            else [f"Use the {interview.interview_type.replace('_', ' ')} format, application context, and submitted resume as the primary preparation frame."]
        )
        role_summary_lines = _clean_lines(
            [
                f"This interview is for {application.title} at {application.company}.",
                f"The submitted resume version is {resume_version.file_name}." if resume_version is not None else "",
                f"Current role signals emphasize {', '.join(job.why[:3])}." if job is not None and job.why else "",
                f"Pending recruiter action: {communication_summary.get('pending_action')}." if communication_summary.get("pending_action") else "",
                f"The application package already includes {len(application.artifacts)} artifact(s) and {len(application.answers)} answer artifact(s)." if application.artifacts or application.answers else "",
            ]
        )
        company_context_lines = _clean_lines(
            [
                f"{application.company} is evaluating you for {application.title}.",
                f"Location and work arrangement: {job.location} · {job.remote_policy}." if job is not None and (job.location or job.remote_policy) else "",
                f"Last recruiter signal: {communication_summary.get('last_message_type')}." if communication_summary.get("last_message_type") else "",
                f"Conversation status: {communication_summary.get('conversation_status')}." if communication_summary.get("conversation_status") else "",
                f"Recent approved experience to keep fresh: {recent_lines[0]}" if recent_lines else "",
            ]
        )
        questions = list(_QUESTION_TEMPLATES.get(interview.interview_type, _QUESTION_TEMPLATES["technical"]))
        if communication_summary.get("pending_action"):
            questions.insert(0, f"What does success look like after I complete the current step: {communication_summary.get('pending_action')}?")
        questions = _clean_lines(questions)[:4]

        focus_section_refs = [
            reference
            for requirement in focus_requirements
            for reference in requirement_refs.get(requirement.label, [])
        ][:6]
        technical_section_refs = [
            reference
            for requirement in technical_focus[:4]
            for reference in requirement_refs.get(requirement.label, [])
        ][:6]
        behavioral_section_refs = (leadership_refs or achievement_refs) + [
            reference
            for requirement in behavioral_focus[:2]
            for reference in requirement_refs.get(requirement.label, [])
        ][:2]

        sections = [
            _section(
                section_key="role_summary",
                title="Role Summary",
                content=role_summary_lines or [f"Prepare for {application.title} at {application.company} using the submitted application package."],
                evidence_references=[reference for reference in [application_reference, job_reference, recruiter_reference] if reference is not None] + resume_references[:1],
                confidence=0.86 if job is not None and resume_version is not None else 0.68,
                generated_at=now,
            ),
            _section(
                section_key="company_context",
                title="Company Context",
                content=company_context_lines or [f"Use the application workflow, job context, and recruiter messages as the current company context for {application.company}."],
                evidence_references=[reference for reference in [application_reference, job_reference, recruiter_reference] if reference is not None] + recent_refs[:1],
                confidence=0.82 if job is not None else 0.64,
                generated_at=now,
            ),
            _section(
                section_key="focus_areas",
                title="Interview Focus Areas",
                content=focus_lines,
                evidence_references=focus_section_refs or [job_reference],
                confidence=0.84 if focus_requirements else 0.58,
                generated_at=now,
            ),
            _section(
                section_key="resume_highlights",
                title="Relevant Resume Highlights",
                content=resume_highlights or ["Use the submitted resume version as the approved baseline narrative for this interview."],
                evidence_references=resume_references or [application_reference],
                confidence=0.83 if resume_highlights else 0.6,
                generated_at=now,
            ),
            _section(
                section_key="projects",
                title="Relevant Projects",
                content=project_lines or ["No strongly matched project evidence is currently approved, so choose the closest production example and keep the explanation concrete."],
                evidence_references=project_refs or focus_section_refs[:2] or [application_reference],
                confidence=0.8 if project_lines else 0.48,
                generated_at=now,
            ),
            _section(
                section_key="leadership",
                title="Leadership Examples",
                content=leadership_lines or achievement_lines or ["Leadership evidence is currently light. Use the strongest approved ownership example and keep the impact specific."],
                evidence_references=leadership_refs or achievement_refs or [application_reference],
                confidence=0.78 if leadership_lines or achievement_lines else 0.45,
                generated_at=now,
            ),
            _section(
                section_key="architecture",
                title="Architecture Examples",
                content=architecture_lines or ["Keep one architecture or scaling walkthrough ready, even if the round is not explicitly system design."],
                evidence_references=architecture_refs or technical_section_refs[:2] or [job_reference],
                confidence=0.79 if architecture_lines else 0.46,
                generated_at=now,
            ),
            _section(
                section_key="technical_topics",
                title="Technical Topics",
                content=technical_lines,
                evidence_references=technical_section_refs or [job_reference],
                confidence=0.81 if technical_focus else 0.56,
                generated_at=now,
            ),
            _section(
                section_key="behavioral_topics",
                title="Behavioral Topics",
                content=behavioral_topic_lines,
                evidence_references=behavioral_section_refs or [application_reference],
                confidence=0.77 if leadership_lines or achievement_lines else 0.52,
                generated_at=now,
            ),
            _section(
                section_key="questions_to_ask",
                title="Questions To Ask",
                content=questions,
                evidence_references=[reference for reference in [application_reference, recruiter_reference, job_reference] if reference is not None],
                confidence=0.74,
                generated_at=now,
            ),
        ]

        risks: list[InterviewPreparationRisk] = []
        requirement_lookup = {item.label: item for item in requirements}
        for label in missing_proof_flags[:3]:
            requirement = requirement_lookup.get(label)
            if requirement is None:
                continue
            risk_references = requirement_refs.get(label) or [_requirement_reference(requirement, job=job, application=application)]
            risks.append(
                _risk(
                    interview_id=interview.interview_id,
                    title=f"Limited approved evidence for {label}",
                    detail=f"The role context highlights {label}, but the Knowledge Platform currently has limited approved evidence tied to that requirement.",
                    recommendation="Prepare the nearest real example you can defend, then capture any missing evidence after the interview.",
                    evidence_references=risk_references,
                    confidence=0.78,
                    generated_at=now,
                    severity="high" if label in focus_labels else "medium",
                )
            )
        if interview.interview_type in {"behavioral", "hiring_manager", "executive"} and not leadership_lines:
            risks.append(
                _risk(
                    interview_id=interview.interview_id,
                    title="Leadership evidence is thin",
                    detail="This round is likely to probe ownership and influence, but approved leadership examples are limited.",
                    recommendation="Prepare one clear ownership story and one cross-functional collaboration story grounded in real work.",
                    evidence_references=[application_reference],
                    confidence=0.68,
                    generated_at=now,
                )
            )
        if interview.interview_type in {"technical", "system_design", "panel", "final", "onsite"} and not architecture_lines:
            risks.append(
                _risk(
                    interview_id=interview.interview_id,
                    title="Architecture depth may need reinforcement",
                    detail="The interview format suggests architecture or systems depth, but matching approved architecture examples are limited.",
                    recommendation="Refresh one system walkthrough with explicit tradeoffs, constraints, and outcomes before the interview.",
                    evidence_references=[job_reference],
                    confidence=0.66,
                    generated_at=now,
                )
            )

        generated_checklist = [
            InterviewPreparationItem(
                item_id=_checklist_item_id(interview.interview_id, "Review role summary and focus areas"),
                label="Review role summary and focus areas",
                status="pending",
                detail="Align on what this round is most likely to test before drilling into examples.",
                reason="Focus areas were derived from the job context, interview type, and recruiter communication.",
                estimated_effort="15m",
                priority="high",
                category="context",
                source="interview_preparation",
                due_at=interview.scheduled_start_at,
                generated=True,
                updated_at=now,
                supporting_evidence=[application_reference, job_reference] + ([recruiter_reference] if recruiter_reference is not None else []),
            ),
            InterviewPreparationItem(
                item_id=_checklist_item_id(interview.interview_id, "Rehearse submitted resume highlights"),
                label="Rehearse submitted resume highlights",
                status="pending",
                detail="Review the strongest approved bullets and be ready to expand each one into a concrete explanation.",
                reason="The submitted resume version is the exact narrative already attached to the application.",
                estimated_effort="20m",
                priority="high",
                category="resume",
                source="interview_preparation",
                due_at=interview.scheduled_start_at,
                generated=True,
                updated_at=now,
                supporting_evidence=resume_references or [application_reference],
            ),
            InterviewPreparationItem(
                item_id=_checklist_item_id(interview.interview_id, "Prepare project walkthroughs"),
                label="Prepare project walkthroughs",
                status="pending",
                detail="Choose the most relevant projects and be ready to explain scope, decisions, tradeoffs, and outcomes.",
                reason="Project evidence is the most reusable proof for role-specific depth.",
                estimated_effort="30m",
                priority="high",
                category="projects",
                source="interview_preparation",
                due_at=interview.scheduled_start_at,
                generated=True,
                updated_at=now,
                supporting_evidence=project_refs or [application_reference],
            ),
            InterviewPreparationItem(
                item_id=_checklist_item_id(interview.interview_id, "Refresh technical and architecture topics"),
                label="Refresh technical and architecture topics",
                status="pending",
                detail="Review the topics most likely to surface in this round and connect them to real implementation decisions.",
                reason="The interview format points to technical depth and architectural reasoning.",
                estimated_effort="30m",
                priority="high" if interview.interview_type in {"technical", "coding", "system_design", "panel", "final", "onsite"} else "medium",
                category="technical",
                source="interview_preparation",
                due_at=interview.scheduled_start_at,
                generated=True,
                updated_at=now,
                supporting_evidence=architecture_refs or technical_section_refs[:3] or [job_reference],
            ),
            InterviewPreparationItem(
                item_id=_checklist_item_id(interview.interview_id, "Prepare behavioral and leadership stories"),
                label="Prepare behavioral and leadership stories",
                status="pending",
                detail="Translate approved experience into concise ownership, collaboration, and decision-making stories.",
                reason="Behavioral evidence is needed even when the round is technical.",
                estimated_effort="25m",
                priority="medium",
                category="behavioral",
                source="interview_preparation",
                due_at=interview.scheduled_start_at,
                generated=True,
                updated_at=now,
                supporting_evidence=leadership_refs or achievement_refs or [application_reference],
            ),
            InterviewPreparationItem(
                item_id=_checklist_item_id(interview.interview_id, "Finalize questions for the interviewer"),
                label="Finalize questions for the interviewer",
                status="pending",
                detail="Prepare questions that show you understand the role, team constraints, and current stage of the process.",
                reason="Questions should reflect the interview round rather than a generic checklist.",
                estimated_effort="10m",
                priority="medium",
                category="questions",
                source="interview_preparation",
                due_at=interview.scheduled_start_at,
                generated=True,
                updated_at=now,
                supporting_evidence=[reference for reference in [application_reference, recruiter_reference, job_reference] if reference is not None],
            ),
            InterviewPreparationItem(
                item_id=_checklist_item_id(interview.interview_id, "Confirm logistics and timing"),
                label="Confirm logistics and timing",
                status="pending",
                detail="Double-check meeting link, timezone, start time, and any pending recruiter asks.",
                reason="Execution failures on logistics are avoidable and should not consume interview energy.",
                estimated_effort="5m",
                priority="high",
                category="logistics",
                source="interview_preparation",
                due_at=interview.scheduled_start_at,
                generated=True,
                updated_at=now,
                supporting_evidence=[reference for reference in [application_reference, recruiter_reference] if reference is not None],
            ),
        ]
        if risks:
            generated_checklist.insert(
                5,
                InterviewPreparationItem(
                    item_id=_checklist_item_id(interview.interview_id, "Address highest-risk evidence gap"),
                    label="Address highest-risk evidence gap",
                    status="pending",
                    detail=risks[0].detail,
                    reason=risks[0].recommendation,
                    estimated_effort="20m",
                    priority="high",
                    category="risk",
                    source="interview_preparation",
                    due_at=interview.scheduled_start_at,
                    generated=True,
                    updated_at=now,
                    supporting_evidence=risks[0].evidence_references,
                ),
            )

        checklist = _merge_checklist_progress(interview.preparation_checklist, generated_checklist)
        overall_confidence = _average_confidence([item.confidence for item in sections] + ([0.65] if risks else [0.75]))
        return InterviewPreparationPlan(
            plan_id=_preparation_plan_id(interview.interview_id, version_number),
            interview_id=interview.interview_id,
            application_id=application.application_id,
            user_id=interview.user_id,
            version_number=version_number,
            status="generated",
            strategy_version=_PREPARATION_STRATEGY_VERSION,
            focus_labels=focus_labels,
            overall_confidence=overall_confidence,
            sections=sections,
            checklist=checklist,
            risks=risks,
            metadata={
                "application_status": application.status,
                "job_id": application.job_id,
                "resume_version_id": application.resume_version_id,
                "interview_type": interview.interview_type,
                "interview_round": interview.interview_round,
                "communication_status": communication_summary.get("conversation_status", ""),
                "waiting_on": communication_summary.get("waiting_on", ""),
                "missing_proof_flags": missing_proof_flags,
            },
            generated_at=now,
            updated_at=now,
        )

    async def _sync_preparation_plan(
        self,
        interview: InterviewRecord,
        plan: InterviewPreparationPlan,
        *,
        event_type: str,
        label: str,
        detail: str,
        actor_user_id: str,
        occurred_at: str,
    ) -> InterviewRecord:
        versions = await self._preparations().list_for_interview(interview.interview_id, user_id=interview.user_id)
        version_summaries = [
            {
                "plan_id": item.plan_id,
                "version_number": item.version_number,
                "status": item.status,
                "generated_at": item.generated_at,
                "updated_at": item.updated_at,
                "overall_confidence": item.overall_confidence,
                "focus_labels": list(item.focus_labels),
            }
            for item in versions
        ]
        metadata = {
            **dict(interview.metadata),
            "preparation_plan_current": {
                "plan_id": plan.plan_id,
                "version_number": plan.version_number,
                "generated_at": plan.generated_at,
                "updated_at": plan.updated_at,
                "overall_confidence": plan.overall_confidence,
                "focus_labels": list(plan.focus_labels),
            },
            "preparation_plan_versions": version_summaries,
        }
        timeline = list(interview.timeline)
        timeline.append(_timeline_item(event_type=event_type, label=label, detail=detail, occurred_at=occurred_at))
        audit_history = list(interview.audit_history)
        audit_history.append(_audit_entry(event_type=event_type, actor_user_id=actor_user_id, detail=detail, created_at=occurred_at))
        updated = _build_record(
            record=interview,
            preparation_status=_derive_preparation_status(plan.checklist, current=interview.preparation_status),
            preparation_checklist=plan.checklist,
            timeline=timeline,
            audit_history=audit_history,
            metadata=metadata,
            updated_at=occurred_at,
        )
        saved = await self._store().save(updated)
        await self._applications().record_interview_activity(
            actor_user_id,
            saved.application_id,
            interview_id=saved.interview_id,
            event_type=event_type,
            label=label,
            detail=detail,
            occurred_at=occurred_at,
        )
        return saved

    def _question_examples_from_section(
        self,
        section: InterviewPreparationSection | None,
        *,
        fallback_label: str,
        risk_tags: list[str] | None = None,
    ) -> list[QuestionExample]:
        if section is None:
            return []
        examples: list[QuestionExample] = []
        seen: set[str] = set()
        for reference in section.evidence_references[:4]:
            key = f"{reference.source_type}:{reference.source_id}:{reference.label.casefold()}"
            if key in seen:
                continue
            seen.add(key)
            examples.append(
                QuestionExample(
                    label=reference.label or fallback_label,
                    detail=reference.excerpt or (section.content[0] if section.content else fallback_label),
                    evidence=[reference],
                    risk_tags=list(risk_tags or []),
                )
            )
        if not examples and section.content:
            examples.append(
                QuestionExample(
                    label=fallback_label,
                    detail=section.content[0],
                    evidence=[],
                    risk_tags=list(risk_tags or []),
                )
            )
        return examples

    def _question_requirement_references(
        self,
        focus_labels: list[str],
        plan: InterviewPreparationPlan,
        *,
        application: ApplicationRecord,
        job: ResumeIntelligenceJobContext | None,
    ) -> dict[str, list[InterviewPreparationEvidenceReference]]:
        refs: dict[str, list[InterviewPreparationEvidenceReference]] = {}
        for label in focus_labels:
            normalized = label.casefold().strip()
            matches: list[InterviewPreparationEvidenceReference] = []
            for section in plan.sections:
                for reference in section.evidence_references:
                    reference_blob = " ".join(
                        [
                            reference.label.casefold(),
                            reference.excerpt.casefold(),
                            reference.relevance_explanation.casefold(),
                        ]
                    )
                    if normalized and (reference.label.casefold() == normalized or normalized in reference_blob):
                        matches.append(reference)
            for risk in plan.risks:
                for reference in risk.evidence_references:
                    reference_blob = " ".join(
                        [
                            reference.label.casefold(),
                            reference.excerpt.casefold(),
                            reference.relevance_explanation.casefold(),
                        ]
                    )
                    if normalized and (reference.label.casefold() == normalized or normalized in reference_blob):
                        matches.append(reference)
            if not matches:
                matches.append(
                    _reference(
                        source_type="job_requirement",
                        source_id=f"{application.job_id}:{_normalize_text(label)}",
                        label=label,
                        excerpt=(
                            job.description_text
                            if job is not None and job.description_text.strip()
                            else f"The preparation plan identified {label} as a focus area for this interview."
                        ),
                        confidence=0.62,
                        relevance_explanation="Prioritized because the preparation plan identified this as a role focus area.",
                        metadata={"job_id": application.job_id},
                    )
                )
            refs[label] = matches[:3]
        return refs

    def _resume_claims_from_version(
        self,
        resume_version: ResumeVersionRecord | None,
        plan: InterviewPreparationPlan,
    ) -> list[ResumeClaim]:
        if resume_version is None:
            return []
        claims: list[ResumeClaim] = []
        for index, item in enumerate(resume_version.accepted_changes[:6], start=1):
            detail = str(item.get("final_text") or "").strip()
            if not detail:
                continue
            requirements = [str(value).strip() for value in item.get("job_requirements", []) if str(value).strip()]
            risk_tags = [
                risk.title
                for risk in plan.risks
                if any(
                    requirement.casefold() in f"{risk.title} {risk.detail}".casefold()
                    for requirement in requirements
                )
            ]
            claims.append(
                ResumeClaim(
                    label=f"Resume claim {index}",
                    detail=detail,
                    requirements=requirements,
                    evidence=[
                        _reference(
                            source_type="resume_version",
                            source_id=resume_version.version_id,
                            label=resume_version.file_name,
                            excerpt=detail,
                            confidence=0.84,
                            relevance_explanation="Submitted resume claim that may be probed directly during the interview.",
                            metadata={"version_signature": resume_version.version_signature},
                        )
                    ],
                    risk_tags=risk_tags,
                )
            )
        return claims

    async def _build_question_context(
        self,
        interview: InterviewRecord,
        application: ApplicationRecord,
        plan: InterviewPreparationPlan,
    ) -> tuple[QuestionGenerationContext, QuestionCoveragePlan]:
        job = await self._load_job_context(interview.user_id, application)
        resume_version = await self._load_resume_version(application)
        communication_summary = await self._load_communication_summary(interview.user_id, application)
        section_lookup = {section.section_key: section for section in plan.sections}
        focus_labels = list(plan.focus_labels)
        if not focus_labels and job is not None:
            focus_labels = [item.label for item in extract_job_requirements(job)[:5]]
        requirement_refs = self._question_requirement_references(
            focus_labels,
            plan,
            application=application,
            job=job,
        )
        recruiter_context = _clean_lines(
            [
                str(communication_summary.get("pending_action") or ""),
                str(communication_summary.get("reason") or ""),
                str(communication_summary.get("last_message_type") or ""),
                str(communication_summary.get("last_message_subject") or ""),
            ]
        )
        company_context = _clean_lines(
            list(section_lookup.get("company_context").content if section_lookup.get("company_context") is not None else [])
            + list(section_lookup.get("role_summary").content if section_lookup.get("role_summary") is not None else [])
        )[:6]
        candidate_question_prompts = _clean_lines(
            list(_QUESTION_TEMPLATES.get(interview.interview_type, _QUESTION_TEMPLATES["technical"]))
            + list(section_lookup.get("questions_to_ask").content if section_lookup.get("questions_to_ask") is not None else [])
        )
        project_examples = self._question_examples_from_section(section_lookup.get("projects"), fallback_label="Relevant project")
        leadership_examples = self._question_examples_from_section(section_lookup.get("leadership"), fallback_label="Leadership example")
        architecture_examples = self._question_examples_from_section(section_lookup.get("architecture"), fallback_label="Architecture example")
        risk_examples = [
            QuestionExample(
                label=risk.title,
                detail=risk.detail,
                evidence=list(risk.evidence_references),
                risk_tags=[risk.title],
            )
            for risk in plan.risks
        ]
        coverage_plan = build_question_coverage_plan(interview.interview_type)
        context = QuestionGenerationContext(
            question_set_id="",
            interview_id=interview.interview_id,
            application_id=application.application_id,
            user_id=interview.user_id,
            interview_type=interview.interview_type,
            interview_round=interview.interview_round,
            company=application.company,
            role_title=application.title,
            focus_requirements=focus_labels,
            company_context=company_context,
            recruiter_context=recruiter_context,
            candidate_question_prompts=candidate_question_prompts,
            job_requirement_evidence=requirement_refs,
            resume_claims=self._resume_claims_from_version(resume_version, plan),
            project_examples=project_examples,
            leadership_examples=leadership_examples,
            architecture_examples=architecture_examples,
            risk_examples=risk_examples,
            application_artifacts=[artifact.label for artifact in application.artifacts if artifact.label.strip()],
            application_answers=[answer.question for answer in application.answers if answer.question.strip()],
        )
        return context, coverage_plan

    def _fallback_generated_question(
        self,
        *,
        category: str,
        prompt: str,
        rationale: str,
        related_job_requirements: list[str],
        evidence: list[InterviewPreparationEvidenceReference],
        risk_tags: list[str] | None = None,
    ) -> GeneratedInterviewQuestion:
        dimensions_map = {
            "resume_deep_dive": ["accuracy", "depth", "impact"],
            "technical": ["technical depth", "tradeoff reasoning", "production judgment"],
            "candidate_questions": ["curiosity", "judgment", "process awareness"],
        }
        return GeneratedInterviewQuestion(
            category=category,
            question=prompt,
            rationale=rationale,
            evaluation_dimensions=dimensions_map.get(category, ["clarity", "evidence usage"]),
            related_job_requirements=related_job_requirements,
            related_evidence=evidence[:3],
            follow_up_questions=[],
            difficulty="intermediate",
            priority="high",
            confidence=0.62 if evidence else 0.48,
            expected_answer_outline=[
                "Anchor the answer in real context.",
                "Explain your role, decisions, and tradeoffs.",
                "Close with outcomes and reflection.",
            ],
            risk_tags=list(risk_tags or []),
        )

    def _materialize_question(
        self,
        generated: GeneratedInterviewQuestion,
        *,
        question_set_id: str,
        interview: InterviewRecord,
        application: ApplicationRecord,
        sequence_order: int,
        created_at: str,
    ) -> InterviewQuestion:
        return InterviewQuestion(
            question_id=_question_id(question_set_id, generated.category, generated.question),
            question_set_id=question_set_id,
            interview_id=interview.interview_id,
            application_id=application.application_id,
            user_id=interview.user_id,
            category=generated.category,
            question=generated.question.strip(),
            rationale=generated.rationale.strip(),
            evaluation_dimensions=_clean_lines(generated.evaluation_dimensions),
            related_job_requirements=_clean_lines(generated.related_job_requirements),
            related_evidence=list(generated.related_evidence)[:3],
            follow_up_questions=list(generated.follow_up_questions)[: QUESTION_SET_LIMITS["max_follow_ups"]],
            difficulty=generated.difficulty,
            priority=generated.priority,
            confidence=_round_confidence(generated.confidence),
            expected_answer_outline=_clean_lines(generated.expected_answer_outline),
            risk_tags=_clean_lines(generated.risk_tags),
            sequence_order=sequence_order,
            preparation_status="not_started",
            hidden=False,
            archived=False,
            user_notes=[],
            metadata=dict(generated.metadata),
            created_at=created_at,
            updated_at=created_at,
        )

    def _finalize_generated_questions(
        self,
        generated: list[GeneratedInterviewQuestion],
        *,
        context: QuestionGenerationContext,
        coverage_plan: QuestionCoveragePlan,
        question_set_id: str,
        interview: InterviewRecord,
        application: ApplicationRecord,
        created_at: str,
    ) -> list[InterviewQuestion]:
        deduped: list[GeneratedInterviewQuestion] = []
        seen_questions: set[str] = set()
        for item in generated:
            prompt = " ".join(item.question.split()).strip()
            if not prompt or not item.rationale.strip():
                continue
            key = prompt.casefold()
            if key in seen_questions:
                continue
            seen_questions.add(key)
            deduped.append(item)

        covered_requirements = {
            requirement
            for item in deduped
            for requirement in item.related_job_requirements
        }
        for requirement in context.focus_requirements[:3]:
            if requirement in covered_requirements:
                continue
            deduped.append(
                self._fallback_generated_question(
                    category="technical",
                    prompt=f"Tell me about a concrete example where you used {requirement} in production and what tradeoffs mattered most.",
                    rationale=f"Added deterministically because {requirement} is a high-priority focus area that still needed explicit coverage.",
                    related_job_requirements=[requirement],
                    evidence=context.job_requirement_evidence.get(requirement, []),
                )
            )

        covered_risks = {risk for item in deduped for risk in item.risk_tags}
        for risk in context.risk_examples[:2]:
            if risk.label in covered_risks:
                continue
            deduped.append(
                self._fallback_generated_question(
                    category="resume_deep_dive",
                    prompt=f"There may be follow-up risk around {risk.label}. How would you explain the nearest real example honestly and concretely?",
                    rationale=f"Added deterministically because the preparation plan flagged {risk.label} as a risk area.",
                    related_job_requirements=[],
                    evidence=risk.evidence,
                    risk_tags=[risk.label],
                )
            )

        if len(deduped) < QUESTION_SET_LIMITS["minimum"]:
            prompts = list(context.candidate_question_prompts) or [
                f"What should you ask the interviewer about success in the {context.role_title} role?"
            ]
            while len(deduped) < QUESTION_SET_LIMITS["minimum"]:
                prompt = prompts[len(deduped) % len(prompts)]
                deduped.append(
                    self._fallback_generated_question(
                        category="candidate_questions",
                        prompt=prompt,
                        rationale="Added deterministically to maintain minimum question-bank coverage even when evidence is sparse.",
                        related_job_requirements=context.focus_requirements[:1],
                        evidence=context.job_requirement_evidence.get(context.focus_requirements[0], []) if context.focus_requirements else [],
                    )
                )

        records = [
            self._materialize_question(
                item,
                question_set_id=question_set_id,
                interview=interview,
                application=application,
                sequence_order=index,
                created_at=created_at,
            )
            for index, item in enumerate(deduped[: QUESTION_SET_LIMITS["maximum"]], start=1)
        ]

        categories = {item.category for item in records}
        missing_categories = coverage_plan.required_categories - categories
        if missing_categories:
            raise ValueError("Deterministic interview question coverage is incomplete.")
        if any(not item.rationale or item.confidence <= 0.0 for item in records):
            raise ValueError("Interview question validation failed.")
        return records

    async def _build_interview_question_set(
        self,
        interview: InterviewRecord,
        application: ApplicationRecord,
        plan: InterviewPreparationPlan,
        *,
        version_number: int,
    ) -> InterviewQuestionSet:
        now = _iso_now()
        question_set_id = _question_set_id(interview.interview_id, version_number)
        context, coverage_plan = await self._build_question_context(interview, application, plan)
        context = QuestionGenerationContext(
            question_set_id=question_set_id,
            interview_id=context.interview_id,
            application_id=context.application_id,
            user_id=context.user_id,
            interview_type=context.interview_type,
            interview_round=context.interview_round,
            company=context.company,
            role_title=context.role_title,
            focus_requirements=list(context.focus_requirements),
            company_context=list(context.company_context),
            recruiter_context=list(context.recruiter_context),
            candidate_question_prompts=list(context.candidate_question_prompts),
            job_requirement_evidence=dict(context.job_requirement_evidence),
            resume_claims=list(context.resume_claims),
            project_examples=list(context.project_examples),
            leadership_examples=list(context.leadership_examples),
            architecture_examples=list(context.architecture_examples),
            risk_examples=list(context.risk_examples),
            application_artifacts=list(context.application_artifacts),
            application_answers=list(context.application_answers),
        )
        generated = await self._question_generator().generate(context, coverage_plan)
        questions = self._finalize_generated_questions(
            generated,
            context=context,
            coverage_plan=coverage_plan,
            question_set_id=question_set_id,
            interview=interview,
            application=application,
            created_at=now,
        )
        generation_info = generator_metadata()
        return InterviewQuestionSet(
            question_set_id=question_set_id,
            interview_id=interview.interview_id,
            application_id=application.application_id,
            user_id=interview.user_id,
            version_number=version_number,
            status="active",
            title=f"{interview.interview_round} Question Bank",
            interview_type=interview.interview_type,
            interview_round=interview.interview_round,
            strategy_version=QUESTION_STRATEGY_VERSION,
            source_preparation_plan_id=plan.plan_id,
            provider=str(generation_info.get("provider") or ""),
            model_key=str(generation_info.get("model_key") or ""),
            metadata={
                "focus_labels": list(context.focus_requirements),
                "categories": sorted({item.category for item in questions}),
                "question_count": len(questions),
                "risk_count": len(plan.risks),
                "candidate_question_count": len([item for item in questions if item.category == "candidate_questions"]),
                "generation": generation_info,
            },
            generated_at=now,
            updated_at=now,
            superseded_by_question_set_id="",
            questions=questions,
        )

    async def _sync_question_set_state(
        self,
        interview: InterviewRecord,
        question_set: InterviewQuestionSet,
        *,
        actor_user_id: str,
        occurred_at: str,
        event_type: str = "",
        label: str = "",
        detail: str = "",
        record_application_event: bool = False,
    ) -> InterviewRecord:
        versions = await self._questions().list_for_interview(interview.interview_id, user_id=interview.user_id)
        version_summaries = [
            {
                "question_set_id": item.question_set_id,
                "version_number": item.version_number,
                "status": item.status,
                "generated_at": item.generated_at,
                "updated_at": item.updated_at,
                "question_count": len(item.questions),
                "categories": sorted({question.category for question in item.questions}),
            }
            for item in versions
        ]
        metadata = {
            **dict(interview.metadata),
            "question_set_current": {
                "question_set_id": question_set.question_set_id,
                "version_number": question_set.version_number,
                "status": question_set.status,
                "generated_at": question_set.generated_at,
                "updated_at": question_set.updated_at,
                "question_count": len(question_set.questions),
                "categories": sorted({item.category for item in question_set.questions}),
            },
            "question_set_versions": version_summaries,
        }
        timeline = list(interview.timeline)
        audit_history = list(interview.audit_history)
        if event_type and label:
            timeline.append(_timeline_item(event_type=event_type, label=label, detail=detail, occurred_at=occurred_at))
            audit_history.append(_audit_entry(event_type=event_type, actor_user_id=actor_user_id, detail=detail, created_at=occurred_at))
        updated = _build_record(
            record=interview,
            timeline=timeline,
            audit_history=audit_history,
            metadata=metadata,
            updated_at=occurred_at,
        )
        saved = await self._store().save(updated)
        if event_type and label and record_application_event:
            await self._applications().record_interview_activity(
                actor_user_id,
                saved.application_id,
                interview_id=saved.interview_id,
                event_type=event_type,
                label=label,
                detail=detail,
                occurred_at=occurred_at,
            )
        return saved

    async def _story_seed_from_entity(
        self,
        user_id: str,
        entity: KnowledgeEntity,
        *,
        related_resume_version_id: str,
        interview_type: str,
    ) -> StorySeed:
        content = entity.content
        summary = str(content.get("summary") or content.get("impact") or content.get("description") or content.get("text") or entity_text(entity))
        role_text = str(content.get("role") or content.get("ownership") or content.get("challenge") or content.get("scope") or "")
        outcome_text = str(content.get("outcome") or content.get("impact") or content.get("result") or content.get("results") or "")
        reflection_text = str(content.get("reflection") or content.get("lessons_learned") or content.get("lessons") or "")
        reference = await self._knowledge_entity_reference(user_id, entity, default_confidence=max(0.55, float(entity.confidence or 0.0)))
        return StorySeed(
            story_group_id=story_group_id(user_id=user_id, seed_kind="knowledge_entity", seed_id=entity.id),
            seed_kind="knowledge_entity",
            seed_id=entity.id,
            category=_story_category_from_entity(entity),
            title=entity.canonical_name,
            summary=summary,
            role_text=role_text,
            outcome_text=outcome_text,
            reflection_text=reflection_text,
            technical_decisions=_story_content_lines(content, ("technical_decisions", "decisions", "architecture", "implementation")),
            tradeoffs=_story_content_lines(content, ("tradeoffs", "constraints", "considerations")),
            leadership_moments=_story_content_lines(content, ("leadership", "leadership_moments", "collaboration", "stakeholder_management")),
            measurable_outcomes=_story_content_lines(content, ("metrics", "measurable_outcomes", "outcomes", "results", "impact")),
            lessons_learned=_story_content_lines(content, ("lessons_learned", "lessons", "reflection")),
            related_projects=_clean_lines(
                ([entity.canonical_name] if entity.entity_type in {"project", "experience"} else [])
                + _json_string_list(content.get("related_projects"))
            )[:3],
            source_evidence=[reference],
            tags=_story_tags_from_entity(entity),
            interview_types=[interview_type],
            related_resume_version_id=related_resume_version_id,
            metadata={
                "entity_id": entity.id,
                "entity_type": entity.entity_type,
                "entity_version": entity.version,
            },
        )

    def _story_seed_from_resume_claim(
        self,
        user_id: str,
        claim: ResumeClaim,
        *,
        related_resume_version_id: str,
        interview_type: str,
        seed_id: str,
    ) -> StorySeed:
        detail = claim.detail.strip()
        return StorySeed(
            story_group_id=story_group_id(user_id=user_id, seed_kind="resume_claim", seed_id=seed_id),
            seed_kind="resume_claim",
            seed_id=seed_id,
            category="resume_claim",
            title=_story_title_from_claim(detail),
            summary=detail,
            role_text=detail,
            outcome_text=detail if any(token.isdigit() for token in detail) else "",
            reflection_text="",
            technical_decisions=[detail] if any(term in detail.casefold() for term in ("python", "kubernetes", "postgresql", "architecture", "distributed")) else [],
            tradeoffs=[],
            leadership_moments=[detail] if any(term in detail.casefold() for term in ("led", "mentored", "owned", "drove")) else [],
            measurable_outcomes=[detail] if any(token.isdigit() for token in detail) else [],
            lessons_learned=[],
            related_projects=[],
            source_evidence=list(claim.evidence),
            tags=_clean_lines([claim.label] + claim.requirements + claim.risk_tags),
            interview_types=[interview_type],
            related_resume_version_id=related_resume_version_id,
            metadata={"claim_label": claim.label, "requirements": list(claim.requirements)},
        )

    async def _build_story_context(
        self,
        interview: InterviewRecord,
        application: ApplicationRecord,
        plan: InterviewPreparationPlan,
        question_set: InterviewQuestionSet,
    ) -> StoryGenerationContext:
        resume_version = await self._load_resume_version(application)
        profile = await self._knowledge().get_profile(interview.user_id)
        entities = [entity for entity in _flatten_profile(profile) if entity.status == "approved"]
        entity_by_id = {entity.id: entity for entity in entities}
        selected_entities: dict[str, KnowledgeEntity] = {}

        def remember(entity: KnowledgeEntity) -> None:
            if entity.status != "approved":
                return
            selected_entities.setdefault(entity.id, entity)

        def capture_references(references: list[InterviewPreparationEvidenceReference]) -> None:
            for reference in references:
                if reference.entity_id and reference.entity_id in entity_by_id:
                    remember(entity_by_id[reference.entity_id])

        for section in plan.sections:
            capture_references(section.evidence_references)
        for risk in plan.risks:
            capture_references(risk.evidence_references)
        for question in question_set.questions:
            if question.archived or question.hidden:
                continue
            capture_references(question.related_evidence)

        focus_labels = list(plan.focus_labels) or _json_string_list(question_set.metadata.get("focus_labels"))
        for label in focus_labels[:3]:
            if len(selected_entities) >= 6:
                break
            for entity in await self._knowledge().search_projects(interview.user_id, label, limit=2):
                remember(entity)
            for entity in await self._knowledge().find_projects(interview.user_id, skill=label, limit=2):
                remember(entity)
        if len(selected_entities) < 6:
            for entity in await self._knowledge().find_best_examples(interview.user_id, topic="leadership", limit=2):
                remember(entity)
        if len(selected_entities) < 6:
            for entity in await self._knowledge().find_best_examples(interview.user_id, topic="achievement", limit=2):
                remember(entity)
        if len(selected_entities) < 6:
            for entity in await self._knowledge().find_backend_projects(interview.user_id, limit=2):
                remember(entity)
        if len(selected_entities) < 6:
            for entity in await self._knowledge().find_recent_experience(interview.user_id, limit=2):
                remember(entity)

        seeds: list[StorySeed] = []
        seen_groups: set[str] = set()
        for entity in selected_entities.values():
            seed = await self._story_seed_from_entity(
                interview.user_id,
                entity,
                related_resume_version_id=resume_version.version_id if resume_version is not None else "",
                interview_type=interview.interview_type,
            )
            if seed.story_group_id in seen_groups:
                continue
            seen_groups.add(seed.story_group_id)
            seeds.append(seed)

        for index, claim in enumerate(self._resume_claims_from_version(resume_version, plan), start=1):
            seed = self._story_seed_from_resume_claim(
                interview.user_id,
                claim,
                related_resume_version_id=resume_version.version_id if resume_version is not None else "",
                interview_type=interview.interview_type,
                seed_id=f"{resume_version.version_id}:{index}" if resume_version is not None else f"claim:{index}",
            )
            if seed.story_group_id in seen_groups:
                continue
            seen_groups.add(seed.story_group_id)
            seeds.append(seed)

        questions = [
            StoryQuestionContext(
                question_id=item.question_id,
                question=item.question,
                category=item.category,
                requirements=list(item.related_job_requirements),
                evidence=list(item.related_evidence),
            )
            for item in question_set.questions
            if not item.archived and not item.hidden
        ]
        return StoryGenerationContext(
            user_id=interview.user_id,
            application_id=application.application_id,
            interview_id=interview.interview_id,
            interview_type=interview.interview_type,
            interview_round=interview.interview_round,
            company=application.company,
            role_title=application.title,
            focus_requirements=focus_labels,
            question_set_id=question_set.question_set_id,
            questions=questions,
            seeds=seeds,
        )

    def _materialize_story(
        self,
        generated: GeneratedInterviewStory,
        *,
        interview: InterviewRecord,
        application: ApplicationRecord,
        question_set: InterviewQuestionSet,
        plan: InterviewPreparationPlan,
        version_number: int,
        created_at: str,
    ) -> InterviewStory:
        quality = InterviewStoryQualityAssessment(
            overall_score=generated.quality.overall_score,
            dimensions=[
                InterviewStoryQualityDimension(
                    label=item.label,
                    score=item.score,
                    rationale=item.rationale,
                )
                for item in generated.quality.dimensions
            ],
            summary=generated.quality.summary,
            generated_at=created_at,
            strategy_version=STORY_STRATEGY_VERSION,
        )
        return InterviewStory(
            story_id=_story_id(generated.story_group_id, version_number),
            story_group_id=generated.story_group_id,
            user_id=interview.user_id,
            application_id=application.application_id,
            interview_id=interview.interview_id,
            linked_application_ids=[application.application_id],
            linked_interview_ids=[interview.interview_id],
            title=generated.title,
            category=generated.category if generated.category in STORY_CATEGORIES else "project",
            source_evidence=list(generated.source_evidence),
            related_projects=list(generated.related_projects),
            related_resume_version_id=generated.related_resume_version_id,
            related_question_ids=list(generated.related_question_ids),
            interview_types=list(generated.interview_types or [interview.interview_type]),
            tags=_clean_lines(generated.tags),
            version_number=version_number,
            status="review",
            sections=[
                InterviewStorySection(
                    section_key=item.section_key,
                    title=item.title,
                    content=_clean_lines(item.content),
                    evidence_references=list(item.evidence_references),
                    missing_fields=_json_string_list(item.missing_fields),
                )
                for item in generated.sections
            ],
            technical_decisions=_clean_lines(generated.technical_decisions),
            tradeoffs=_clean_lines(generated.tradeoffs),
            leadership_moments=_clean_lines(generated.leadership_moments),
            measurable_outcomes=_clean_lines(generated.measurable_outcomes),
            lessons_learned=_clean_lines(generated.lessons_learned),
            interviewer_follow_ups=_clean_lines(generated.interviewer_follow_ups),
            coverage=[
                InterviewStoryCoverageLink(
                    question_id=item.question_id,
                    question=item.question,
                    category=item.category,
                    coverage_score=_round_confidence(item.coverage_score),
                    reason=item.reason,
                    confidence=_round_confidence(item.confidence),
                )
                for item in generated.coverage
            ],
            quality=quality,
            missing_information_prompts=[
                InterviewStoryGapPrompt(
                    prompt_id=item.prompt_id,
                    field_key=item.field_key,
                    prompt=item.prompt,
                    reason=item.reason,
                    topic=item.topic,
                    status="open",
                    related_evidence=list(item.related_evidence),
                    profile_evolution_payload={
                        **dict(item.profile_evolution_payload),
                        "story_group_id": generated.story_group_id,
                    },
                    created_at=created_at,
                    updated_at=created_at,
                )
                for item in generated.missing_information_prompts
            ],
            superseded_by_story_id="",
            metadata={
                **dict(generated.metadata),
                "question_set_id": question_set.question_set_id,
                "source_preparation_plan_id": plan.plan_id,
                "generation": {
                    "provider": "deterministic",
                    "model_key": "",
                    "strategy_version": STORY_STRATEGY_VERSION,
                },
            },
            created_at=created_at,
            updated_at=created_at,
        )

    async def _build_interview_story_records(
        self,
        interview: InterviewRecord,
        application: ApplicationRecord,
        plan: InterviewPreparationPlan,
        question_set: InterviewQuestionSet,
        *,
        target_group_ids: set[str] | None = None,
        version_overrides: dict[str, int] | None = None,
    ) -> list[InterviewStory]:
        context = await self._build_story_context(interview, application, plan, question_set)
        if target_group_ids is not None:
            filtered_seeds = [item for item in context.seeds if item.story_group_id in target_group_ids]
            context = StoryGenerationContext(
                user_id=context.user_id,
                application_id=context.application_id,
                interview_id=context.interview_id,
                interview_type=context.interview_type,
                interview_round=context.interview_round,
                company=context.company,
                role_title=context.role_title,
                focus_requirements=list(context.focus_requirements),
                question_set_id=context.question_set_id,
                questions=list(context.questions),
                seeds=filtered_seeds,
            )
        generated = await self._story_generator().generate(context)
        if target_group_ids is not None:
            generated = [item for item in generated if item.story_group_id in target_group_ids]
        if not generated:
            raise ValueError("No interview stories could be generated from the current approved evidence.")
        now = _iso_now()
        records = [
            self._materialize_story(
                item,
                interview=interview,
                application=application,
                question_set=question_set,
                plan=plan,
                version_number=(version_overrides or {}).get(item.story_group_id, 1),
                created_at=now,
            )
            for item in generated
        ]
        return sorted(records, key=_story_sort_key, reverse=True)

    async def _sync_story_library_state(
        self,
        interview: InterviewRecord,
        *,
        actor_user_id: str,
        occurred_at: str,
        event_type: str = "",
        label: str = "",
        detail: str = "",
        record_application_event: bool = False,
    ) -> InterviewRecord:
        versions = await self._stories().list_for_interview(interview.interview_id, user_id=interview.user_id)
        current = _current_story_versions(versions)
        question_set = await self._questions().get_current_set(interview.interview_id, user_id=interview.user_id)
        question_ids = [
            item.question_id
            for item in (question_set.questions if question_set is not None else [])
            if not item.archived and not item.hidden
        ]
        covered_question_ids = sorted({link.question_id for story in current for link in story.coverage})
        uncovered_question_ids = [question_id for question_id in question_ids if question_id not in covered_question_ids]
        quality_scores = [item.quality.overall_score for item in current]
        weak_story_ids = [
            item.story_id
            for item in current
            if item.quality.overall_score < 70 or bool(item.missing_information_prompts)
        ]
        overused_story_ids = [item.story_id for item in current if len(item.coverage) >= 4]
        metadata = {
            **dict(interview.metadata),
            "story_library_current": {
                "story_count": len(current),
                "approved_count": len([item for item in current if item.status == "approved"]),
                "review_count": len([item for item in current if item.status == "review"]),
                "average_quality": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0.0,
                "covered_question_ids": covered_question_ids,
                "uncovered_question_ids": uncovered_question_ids,
                "coverage_ratio": round(len(covered_question_ids) / len(question_ids), 2) if question_ids else 0.0,
                "weak_story_ids": weak_story_ids,
                "overused_story_ids": overused_story_ids,
                "duplicate_story_group_ids": _story_duplicate_groups(current),
                "updated_at": occurred_at,
            },
            "story_library_versions": _story_version_summaries(versions),
        }
        timeline = list(interview.timeline)
        audit_history = list(interview.audit_history)
        if event_type and label:
            timeline.append(_timeline_item(event_type=event_type, label=label, detail=detail, occurred_at=occurred_at))
            audit_history.append(_audit_entry(event_type=event_type, actor_user_id=actor_user_id, detail=detail, created_at=occurred_at))
        updated = _build_record(
            record=interview,
            timeline=timeline,
            audit_history=audit_history,
            metadata=metadata,
            updated_at=occurred_at,
        )
        saved = await self._store().save(updated)
        if event_type and label and record_application_event:
            await self._applications().record_interview_activity(
                actor_user_id,
                saved.application_id,
                interview_id=saved.interview_id,
                event_type=event_type,
                label=label,
                detail=detail,
                occurred_at=occurred_at,
            )
        return saved

    async def list_interview_stories(self, user_id: str, interview_id: str) -> list[InterviewStory]:
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        return await self._stories().list_for_interview(interview_id, user_id=user_id)

    async def list_stories(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_id: str | None = None,
        status: str | None = None,
    ) -> list[InterviewStory]:
        return await self._stories().list_for_user(
            user_id,
            application_id=application_id,
            interview_id=interview_id,
            status=status,
        )

    async def get_story(self, user_id: str, story_id: str) -> InterviewStory | None:
        return await self._stories().get(story_id, user_id=user_id)

    async def generate_stories(self, user_id: str, interview_id: str) -> list[InterviewStory]:
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        application = await self._applications().get_application(user_id, interview.application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        plan = await self.get_preparation(user_id, interview_id)
        if plan is None:
            raise ValueError("No preparation plan exists for this interview yet.")
        question_set = await self.get_current_question_set(user_id, interview_id)
        if question_set is None:
            raise ValueError("No question set exists for this interview yet.")
        existing_versions = await self._stories().list_for_interview(interview_id, user_id=user_id)
        current = _current_story_versions(existing_versions)
        if any(item.status in {"draft", "review", "approved"} for item in current):
            return current
        version_overrides: dict[str, int] = {}
        for item in existing_versions:
            version_overrides[item.story_group_id] = max(version_overrides.get(item.story_group_id, 0), item.version_number)
        generated = await self._build_interview_story_records(
            interview,
            application,
            plan,
            question_set,
            version_overrides={key: value + 1 for key, value in version_overrides.items()},
        )
        saved: list[InterviewStory] = []
        for item in generated:
            version = version_overrides.get(item.story_group_id, 0) + 1
            saved.append(
                await self._stories().save(
                    InterviewStory(
                        story_id=_story_id(item.story_group_id, version),
                        story_group_id=item.story_group_id,
                        user_id=item.user_id,
                        application_id=item.application_id,
                        interview_id=item.interview_id,
                        linked_application_ids=list(item.linked_application_ids),
                        linked_interview_ids=list(item.linked_interview_ids),
                        title=item.title,
                        category=item.category,
                        source_evidence=list(item.source_evidence),
                        related_projects=list(item.related_projects),
                        related_resume_version_id=item.related_resume_version_id,
                        related_question_ids=list(item.related_question_ids),
                        interview_types=list(item.interview_types),
                        tags=list(item.tags),
                        version_number=version,
                        status=item.status,
                        sections=list(item.sections),
                        technical_decisions=list(item.technical_decisions),
                        tradeoffs=list(item.tradeoffs),
                        leadership_moments=list(item.leadership_moments),
                        measurable_outcomes=list(item.measurable_outcomes),
                        lessons_learned=list(item.lessons_learned),
                        interviewer_follow_ups=list(item.interviewer_follow_ups),
                        coverage=list(item.coverage),
                        quality=item.quality,
                        missing_information_prompts=list(item.missing_information_prompts),
                        superseded_by_story_id=item.superseded_by_story_id,
                        metadata=dict(item.metadata),
                        created_at=item.created_at,
                        updated_at=item.updated_at,
                    )
                )
            )
        await self._sync_story_library_state(
            interview,
            actor_user_id=user_id,
            occurred_at=saved[0].created_at or _iso_now(),
            event_type="InterviewStoryLibraryGenerated",
            label="Interview story library generated",
            detail=f"Generated {len(saved)} evidence-backed interview stories.",
            record_application_event=True,
        )
        return _current_story_versions(saved)

    async def regenerate_story(self, user_id: str, story_id: str) -> InterviewStory:
        current = await self._stories().get(story_id, user_id=user_id)
        if current is None:
            raise ValueError("Unknown interview story.")
        if not current.interview_id:
            raise ValueError("Interview story is not linked to an interview workspace.")
        interview = await self.get_interview(user_id, current.interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        application = await self._applications().get_application(user_id, interview.application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        plan = await self.get_preparation(user_id, interview.interview_id)
        if plan is None:
            raise ValueError("No preparation plan exists for this interview yet.")
        question_set = await self.get_current_question_set(user_id, interview.interview_id)
        if question_set is None:
            raise ValueError("No question set exists for this interview yet.")
        versions = await self._stories().list_for_group(current.story_group_id, user_id=user_id)
        next_version = (versions[0].version_number + 1) if versions else (current.version_number + 1)
        generated = await self._build_interview_story_records(
            interview,
            application,
            plan,
            question_set,
            target_group_ids={current.story_group_id},
            version_overrides={current.story_group_id: next_version},
        )
        regenerated = generated[0]
        for item in versions:
            if item.story_id == regenerated.story_id or item.status in {"approved", "archived", "superseded"}:
                continue
            await self._stories().save(
                InterviewStory(
                    story_id=item.story_id,
                    story_group_id=item.story_group_id,
                    user_id=item.user_id,
                    application_id=item.application_id,
                    interview_id=item.interview_id,
                    linked_application_ids=list(item.linked_application_ids),
                    linked_interview_ids=list(item.linked_interview_ids),
                    title=item.title,
                    category=item.category,
                    source_evidence=list(item.source_evidence),
                    related_projects=list(item.related_projects),
                    related_resume_version_id=item.related_resume_version_id,
                    related_question_ids=list(item.related_question_ids),
                    interview_types=list(item.interview_types),
                    tags=list(item.tags),
                    version_number=item.version_number,
                    status="superseded",
                    sections=list(item.sections),
                    technical_decisions=list(item.technical_decisions),
                    tradeoffs=list(item.tradeoffs),
                    leadership_moments=list(item.leadership_moments),
                    measurable_outcomes=list(item.measurable_outcomes),
                    lessons_learned=list(item.lessons_learned),
                    interviewer_follow_ups=list(item.interviewer_follow_ups),
                    coverage=list(item.coverage),
                    quality=item.quality,
                    missing_information_prompts=list(item.missing_information_prompts),
                    superseded_by_story_id=regenerated.story_id,
                    metadata=dict(item.metadata),
                    created_at=item.created_at,
                    updated_at=regenerated.updated_at,
                )
            )
        saved = await self._stories().save(regenerated)
        await self._sync_story_library_state(
            interview,
            actor_user_id=user_id,
            occurred_at=saved.updated_at or _iso_now(),
            event_type="InterviewStoryRegenerated",
            label="Interview story regenerated",
            detail=f"Regenerated {saved.title} as story version {saved.version_number}.",
            record_application_event=True,
        )
        return saved

    async def update_story(
        self,
        user_id: str,
        story_id: str,
        *,
        title: str | None = None,
        category: str | None = None,
        status: str | None = None,
        sections: list[InterviewStorySection | dict[str, object]] | None = None,
        technical_decisions: list[str] | None = None,
        tradeoffs: list[str] | None = None,
        leadership_moments: list[str] | None = None,
        measurable_outcomes: list[str] | None = None,
        lessons_learned: list[str] | None = None,
        interviewer_follow_ups: list[str] | None = None,
        tags: list[str] | None = None,
        missing_information_prompts: list[InterviewStoryGapPrompt | dict[str, object]] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> InterviewStory:
        current = await self._stories().get(story_id, user_id=user_id)
        if current is None:
            raise ValueError("Unknown interview story.")
        if current.status in {"archived", "superseded"}:
            raise ValueError("Archived or superseded interview stories cannot be edited.")
        normalized_status = current.status
        if status is not None and status.strip():
            candidate = status.strip().casefold()
            if candidate not in STORY_STATUSES:
                raise ValueError("Unsupported interview story status.")
            if candidate in {"approved", "archived", "superseded"}:
                raise ValueError("Use the dedicated interview story approval or archive action.")
            normalized_status = candidate
        normalized_category = current.category
        if category is not None and category.strip():
            candidate = category.strip().casefold()
            if candidate not in STORY_CATEGORIES:
                raise ValueError("Unsupported interview story category.")
            normalized_category = candidate
        normalized_sections = (
            _parse_story_sections([item.to_dict() if isinstance(item, InterviewStorySection) else item for item in sections])
            if sections is not None
            else current.sections
        )
        normalized_prompts = (
            _parse_story_gap_prompts(
                [item.to_dict() if isinstance(item, InterviewStoryGapPrompt) else item for item in missing_information_prompts]
            )
            if missing_information_prompts is not None
            else current.missing_information_prompts
        )
        now = _iso_now()
        if current.status == "approved":
            versions = await self._stories().list_for_group(current.story_group_id, user_id=user_id)
            next_version = (versions[0].version_number + 1) if versions else (current.version_number + 1)
            updated = InterviewStory(
                story_id=_story_id(current.story_group_id, next_version),
                story_group_id=current.story_group_id,
                user_id=current.user_id,
                application_id=current.application_id,
                interview_id=current.interview_id,
                linked_application_ids=list(current.linked_application_ids),
                linked_interview_ids=list(current.linked_interview_ids),
                title=title.strip() if title is not None else current.title,
                category=normalized_category,
                source_evidence=list(current.source_evidence),
                related_projects=list(current.related_projects),
                related_resume_version_id=current.related_resume_version_id,
                related_question_ids=list(current.related_question_ids),
                interview_types=list(current.interview_types),
                tags=_clean_lines(tags) if tags is not None else list(current.tags),
                version_number=next_version,
                status=normalized_status if normalized_status in {"draft", "review"} else "review",
                sections=normalized_sections,
                technical_decisions=_clean_lines(technical_decisions) if technical_decisions is not None else list(current.technical_decisions),
                tradeoffs=_clean_lines(tradeoffs) if tradeoffs is not None else list(current.tradeoffs),
                leadership_moments=_clean_lines(leadership_moments) if leadership_moments is not None else list(current.leadership_moments),
                measurable_outcomes=_clean_lines(measurable_outcomes) if measurable_outcomes is not None else list(current.measurable_outcomes),
                lessons_learned=_clean_lines(lessons_learned) if lessons_learned is not None else list(current.lessons_learned),
                interviewer_follow_ups=_clean_lines(interviewer_follow_ups) if interviewer_follow_ups is not None else list(current.interviewer_follow_ups),
                coverage=list(current.coverage),
                quality=current.quality,
                missing_information_prompts=normalized_prompts,
                superseded_by_story_id="",
                metadata={**dict(current.metadata), **dict(metadata or {})},
                created_at=now,
                updated_at=now,
            )
        else:
            updated = InterviewStory(
                story_id=current.story_id,
                story_group_id=current.story_group_id,
                user_id=current.user_id,
                application_id=current.application_id,
                interview_id=current.interview_id,
                linked_application_ids=list(current.linked_application_ids),
                linked_interview_ids=list(current.linked_interview_ids),
                title=title.strip() if title is not None else current.title,
                category=normalized_category,
                source_evidence=list(current.source_evidence),
                related_projects=list(current.related_projects),
                related_resume_version_id=current.related_resume_version_id,
                related_question_ids=list(current.related_question_ids),
                interview_types=list(current.interview_types),
                tags=_clean_lines(tags) if tags is not None else list(current.tags),
                version_number=current.version_number,
                status=normalized_status if normalized_status in {"draft", "review"} else current.status,
                sections=normalized_sections,
                technical_decisions=_clean_lines(technical_decisions) if technical_decisions is not None else list(current.technical_decisions),
                tradeoffs=_clean_lines(tradeoffs) if tradeoffs is not None else list(current.tradeoffs),
                leadership_moments=_clean_lines(leadership_moments) if leadership_moments is not None else list(current.leadership_moments),
                measurable_outcomes=_clean_lines(measurable_outcomes) if measurable_outcomes is not None else list(current.measurable_outcomes),
                lessons_learned=_clean_lines(lessons_learned) if lessons_learned is not None else list(current.lessons_learned),
                interviewer_follow_ups=_clean_lines(interviewer_follow_ups) if interviewer_follow_ups is not None else list(current.interviewer_follow_ups),
                coverage=list(current.coverage),
                quality=current.quality,
                missing_information_prompts=normalized_prompts,
                superseded_by_story_id=current.superseded_by_story_id,
                metadata={**dict(current.metadata), **dict(metadata or {})},
                created_at=current.created_at,
                updated_at=now,
            )
        saved = await self._stories().save(updated)
        if saved.interview_id:
            interview = await self.get_interview(user_id, saved.interview_id)
            if interview is not None:
                await self._sync_story_library_state(
                    interview,
                    actor_user_id=user_id,
                    occurred_at=saved.updated_at or now,
                    event_type="InterviewStoryUpdated",
                    label="Interview story updated",
                    detail=f"Updated {saved.title}.",
                    record_application_event=False,
                )
        return saved

    async def approve_story(self, user_id: str, story_id: str) -> InterviewStory:
        current = await self._stories().get(story_id, user_id=user_id)
        if current is None:
            raise ValueError("Unknown interview story.")
        if current.status == "archived":
            raise ValueError("Archived interview stories must be regenerated before approval.")
        now = _iso_now()
        approved = InterviewStory(
            story_id=current.story_id,
            story_group_id=current.story_group_id,
            user_id=current.user_id,
            application_id=current.application_id,
            interview_id=current.interview_id,
            linked_application_ids=list(current.linked_application_ids),
            linked_interview_ids=list(current.linked_interview_ids),
            title=current.title,
            category=current.category,
            source_evidence=list(current.source_evidence),
            related_projects=list(current.related_projects),
            related_resume_version_id=current.related_resume_version_id,
            related_question_ids=list(current.related_question_ids),
            interview_types=list(current.interview_types),
            tags=list(current.tags),
            version_number=current.version_number,
            status="approved",
            sections=list(current.sections),
            technical_decisions=list(current.technical_decisions),
            tradeoffs=list(current.tradeoffs),
            leadership_moments=list(current.leadership_moments),
            measurable_outcomes=list(current.measurable_outcomes),
            lessons_learned=list(current.lessons_learned),
            interviewer_follow_ups=list(current.interviewer_follow_ups),
            coverage=list(current.coverage),
            quality=current.quality,
            missing_information_prompts=list(current.missing_information_prompts),
            superseded_by_story_id="",
            metadata=dict(current.metadata),
            created_at=current.created_at,
            updated_at=now,
        )
        saved = await self._stories().save(approved)
        for item in await self._stories().list_for_group(saved.story_group_id, user_id=user_id):
            if item.story_id == saved.story_id or item.status == "archived":
                continue
            await self._stories().save(
                InterviewStory(
                    story_id=item.story_id,
                    story_group_id=item.story_group_id,
                    user_id=item.user_id,
                    application_id=item.application_id,
                    interview_id=item.interview_id,
                    linked_application_ids=list(item.linked_application_ids),
                    linked_interview_ids=list(item.linked_interview_ids),
                    title=item.title,
                    category=item.category,
                    source_evidence=list(item.source_evidence),
                    related_projects=list(item.related_projects),
                    related_resume_version_id=item.related_resume_version_id,
                    related_question_ids=list(item.related_question_ids),
                    interview_types=list(item.interview_types),
                    tags=list(item.tags),
                    version_number=item.version_number,
                    status="superseded",
                    sections=list(item.sections),
                    technical_decisions=list(item.technical_decisions),
                    tradeoffs=list(item.tradeoffs),
                    leadership_moments=list(item.leadership_moments),
                    measurable_outcomes=list(item.measurable_outcomes),
                    lessons_learned=list(item.lessons_learned),
                    interviewer_follow_ups=list(item.interviewer_follow_ups),
                    coverage=list(item.coverage),
                    quality=item.quality,
                    missing_information_prompts=list(item.missing_information_prompts),
                    superseded_by_story_id=saved.story_id,
                    metadata=dict(item.metadata),
                    created_at=item.created_at,
                    updated_at=now,
                )
            )
        if saved.interview_id:
            interview = await self.get_interview(user_id, saved.interview_id)
            if interview is not None:
                await self._sync_story_library_state(
                    interview,
                    actor_user_id=user_id,
                    occurred_at=now,
                    event_type="InterviewStoryApproved",
                    label="Interview story approved",
                    detail=f"Approved {saved.title} for interview use.",
                    record_application_event=True,
                )
        return saved

    async def archive_story(self, user_id: str, story_id: str) -> InterviewStory:
        current = await self._stories().get(story_id, user_id=user_id)
        if current is None:
            raise ValueError("Unknown interview story.")
        if current.status == "archived":
            return current
        now = _iso_now()
        archived = InterviewStory(
            story_id=current.story_id,
            story_group_id=current.story_group_id,
            user_id=current.user_id,
            application_id=current.application_id,
            interview_id=current.interview_id,
            linked_application_ids=list(current.linked_application_ids),
            linked_interview_ids=list(current.linked_interview_ids),
            title=current.title,
            category=current.category,
            source_evidence=list(current.source_evidence),
            related_projects=list(current.related_projects),
            related_resume_version_id=current.related_resume_version_id,
            related_question_ids=list(current.related_question_ids),
            interview_types=list(current.interview_types),
            tags=list(current.tags),
            version_number=current.version_number,
            status="archived",
            sections=list(current.sections),
            technical_decisions=list(current.technical_decisions),
            tradeoffs=list(current.tradeoffs),
            leadership_moments=list(current.leadership_moments),
            measurable_outcomes=list(current.measurable_outcomes),
            lessons_learned=list(current.lessons_learned),
            interviewer_follow_ups=list(current.interviewer_follow_ups),
            coverage=list(current.coverage),
            quality=current.quality,
            missing_information_prompts=list(current.missing_information_prompts),
            superseded_by_story_id=current.superseded_by_story_id,
            metadata=dict(current.metadata),
            created_at=current.created_at,
            updated_at=now,
        )
        saved = await self._stories().save(archived)
        if saved.interview_id:
            interview = await self.get_interview(user_id, saved.interview_id)
            if interview is not None:
                await self._sync_story_library_state(
                    interview,
                    actor_user_id=user_id,
                    occurred_at=now,
                    event_type="InterviewStoryArchived",
                    label="Interview story archived",
                    detail=f"Archived {saved.title}.",
                    record_application_event=False,
                )
        return saved

    async def list_question_sets(self, user_id: str, interview_id: str) -> list[InterviewQuestionSet]:
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        return await self._questions().list_for_interview(interview_id, user_id=user_id)

    async def get_current_question_set(self, user_id: str, interview_id: str) -> InterviewQuestionSet | None:
        return await self._questions().get_current_set(interview_id, user_id=user_id)

    async def get_question_set(self, user_id: str, question_set_id: str) -> InterviewQuestionSet | None:
        return await self._questions().get_set(question_set_id, user_id=user_id)

    async def generate_question_set(self, user_id: str, interview_id: str) -> InterviewQuestionSet:
        existing = await self.get_current_question_set(user_id, interview_id)
        if existing is not None and existing.status == "active":
            return existing
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        application = await self._applications().get_application(user_id, interview.application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        plan = await self.get_preparation(user_id, interview_id)
        if plan is None:
            raise ValueError("No preparation plan exists for this interview yet.")
        version_number = 1
        latest_versions = await self._questions().list_for_interview(interview_id, user_id=user_id)
        if latest_versions:
            version_number = latest_versions[0].version_number + 1
        question_set = await self._build_interview_question_set(interview, application, plan, version_number=version_number)
        if latest_versions:
            latest = latest_versions[0]
            superseded = _build_question_set(
                latest,
                questions=list(latest.questions),
            )
            superseded = InterviewQuestionSet(
                question_set_id=superseded.question_set_id,
                interview_id=superseded.interview_id,
                application_id=superseded.application_id,
                user_id=superseded.user_id,
                version_number=superseded.version_number,
                status="superseded",
                title=superseded.title,
                interview_type=superseded.interview_type,
                interview_round=superseded.interview_round,
                strategy_version=superseded.strategy_version,
                source_preparation_plan_id=superseded.source_preparation_plan_id,
                provider=superseded.provider,
                model_key=superseded.model_key,
                metadata=dict(superseded.metadata),
                generated_at=superseded.generated_at,
                updated_at=question_set.generated_at,
                superseded_by_question_set_id=question_set.question_set_id,
                questions=list(superseded.questions),
            )
            await self._questions().save_set(superseded)
        saved_set = await self._questions().save_set(question_set)
        saved_questions = await self._questions().replace_questions(saved_set.question_set_id, question_set.questions)
        hydrated = _build_question_set(saved_set, questions=saved_questions)
        await self._sync_question_set_state(
            interview,
            hydrated,
            actor_user_id=user_id,
            occurred_at=hydrated.generated_at or _iso_now(),
            event_type="InterviewQuestionSetGenerated",
            label="Interview question bank generated",
            detail=f"Generated interview question bank v{hydrated.version_number} with {len(hydrated.questions)} questions.",
            record_application_event=True,
        )
        return hydrated

    async def regenerate_question_set(self, user_id: str, interview_id: str) -> InterviewQuestionSet:
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        application = await self._applications().get_application(user_id, interview.application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        plan = await self.get_preparation(user_id, interview_id)
        if plan is None:
            raise ValueError("No preparation plan exists for this interview yet.")
        existing_versions = await self._questions().list_for_interview(interview_id, user_id=user_id)
        version_number = (existing_versions[0].version_number + 1) if existing_versions else 1
        question_set = await self._build_interview_question_set(interview, application, plan, version_number=version_number)
        if existing_versions:
            latest = existing_versions[0]
            superseded = InterviewQuestionSet(
                question_set_id=latest.question_set_id,
                interview_id=latest.interview_id,
                application_id=latest.application_id,
                user_id=latest.user_id,
                version_number=latest.version_number,
                status="superseded",
                title=latest.title,
                interview_type=latest.interview_type,
                interview_round=latest.interview_round,
                strategy_version=latest.strategy_version,
                source_preparation_plan_id=latest.source_preparation_plan_id,
                provider=latest.provider,
                model_key=latest.model_key,
                metadata=dict(latest.metadata),
                generated_at=latest.generated_at,
                updated_at=question_set.generated_at,
                superseded_by_question_set_id=question_set.question_set_id,
                questions=list(latest.questions),
            )
            await self._questions().save_set(superseded)
        saved_set = await self._questions().save_set(question_set)
        saved_questions = await self._questions().replace_questions(saved_set.question_set_id, question_set.questions)
        hydrated = _build_question_set(saved_set, questions=saved_questions)
        await self._sync_question_set_state(
            interview,
            hydrated,
            actor_user_id=user_id,
            occurred_at=hydrated.generated_at or _iso_now(),
            event_type="InterviewQuestionSetRegenerated",
            label="Interview question bank regenerated",
            detail=f"Generated interview question bank v{hydrated.version_number} using the latest preparation plan and application context.",
            record_application_event=True,
        )
        return hydrated

    async def update_question(
        self,
        user_id: str,
        question_id: str,
        *,
        preparation_status: str | None = None,
        priority: str | None = None,
        sequence_order: int | None = None,
        hidden: bool | None = None,
        archived: bool | None = None,
        metadata: dict[str, object] | None = None,
    ) -> InterviewQuestion:
        current = await self._questions().get_question(question_id, user_id=user_id)
        if current is None:
            raise ValueError("Unknown interview question.")
        normalized_preparation_status = current.preparation_status
        if preparation_status is not None:
            candidate = preparation_status.strip().casefold()
            if candidate not in QUESTION_PREPARATION_STATUSES:
                raise ValueError("Unsupported interview question preparation status.")
            normalized_preparation_status = candidate
        normalized_priority = current.priority
        if priority is not None:
            candidate = priority.strip().casefold()
            if candidate not in QUESTION_PRIORITIES:
                raise ValueError("Unsupported interview question priority.")
            normalized_priority = candidate
        normalized_order = current.sequence_order if sequence_order is None else int(sequence_order)
        if normalized_order < 1:
            raise ValueError("Interview question sequence order must be at least 1.")
        now = _iso_now()
        updated = InterviewQuestion(
            question_id=current.question_id,
            question_set_id=current.question_set_id,
            interview_id=current.interview_id,
            application_id=current.application_id,
            user_id=current.user_id,
            category=current.category,
            question=current.question,
            rationale=current.rationale,
            evaluation_dimensions=list(current.evaluation_dimensions),
            related_job_requirements=list(current.related_job_requirements),
            related_evidence=list(current.related_evidence),
            follow_up_questions=list(current.follow_up_questions),
            difficulty=current.difficulty,
            priority=normalized_priority,
            confidence=current.confidence,
            expected_answer_outline=list(current.expected_answer_outline),
            risk_tags=list(current.risk_tags),
            sequence_order=normalized_order,
            preparation_status=normalized_preparation_status,
            hidden=current.hidden if hidden is None else bool(hidden),
            archived=current.archived if archived is None else bool(archived),
            user_notes=list(current.user_notes),
            metadata={**dict(current.metadata), **dict(metadata or {})},
            created_at=current.created_at,
            updated_at=now,
        )
        saved = await self._questions().save_question(updated)
        question_set = await self._questions().get_set(saved.question_set_id, user_id=user_id)
        if question_set is not None:
            touched_set = InterviewQuestionSet(
                question_set_id=question_set.question_set_id,
                interview_id=question_set.interview_id,
                application_id=question_set.application_id,
                user_id=question_set.user_id,
                version_number=question_set.version_number,
                status=question_set.status,
                title=question_set.title,
                interview_type=question_set.interview_type,
                interview_round=question_set.interview_round,
                strategy_version=question_set.strategy_version,
                source_preparation_plan_id=question_set.source_preparation_plan_id,
                provider=question_set.provider,
                model_key=question_set.model_key,
                metadata=dict(question_set.metadata),
                generated_at=question_set.generated_at,
                updated_at=now,
                superseded_by_question_set_id=question_set.superseded_by_question_set_id,
                questions=list(question_set.questions),
            )
            saved_set = await self._questions().save_set(touched_set)
            interview = await self.get_interview(user_id, saved.interview_id)
            if interview is not None:
                event_type = ""
                label = ""
                detail = ""
                if current.preparation_status != normalized_preparation_status and normalized_preparation_status == "prepared":
                    event_type = "InterviewQuestionPrepared"
                    label = "Interview question prepared"
                    detail = _clean_excerpt(saved.question, limit=120)
                elif current.preparation_status != normalized_preparation_status and normalized_preparation_status == "needs_practice":
                    event_type = "InterviewQuestionNeedsPractice"
                    label = "Interview question needs practice"
                    detail = _clean_excerpt(saved.question, limit=120)
                await self._sync_question_set_state(
                    interview,
                    _build_question_set(saved_set, questions=question_set.questions),
                    actor_user_id=user_id,
                    occurred_at=now,
                    event_type=event_type,
                    label=label,
                    detail=detail,
                    record_application_event=False,
                )
        return saved

    async def add_question_note(self, user_id: str, question_id: str, *, body: str) -> InterviewQuestion:
        current = await self._questions().get_question(question_id, user_id=user_id)
        if current is None:
            raise ValueError("Unknown interview question.")
        note_body = body.strip()
        if not note_body:
            raise ValueError("Interview question note cannot be empty.")
        now = _iso_now()
        notes = list(current.user_notes)
        notes.append(
            InterviewQuestionNote(
                note_id=_question_note_id(current.question_id, note_body, now),
                body=note_body,
                created_at=now,
                updated_at=now,
            )
        )
        updated = InterviewQuestion(
            question_id=current.question_id,
            question_set_id=current.question_set_id,
            interview_id=current.interview_id,
            application_id=current.application_id,
            user_id=current.user_id,
            category=current.category,
            question=current.question,
            rationale=current.rationale,
            evaluation_dimensions=list(current.evaluation_dimensions),
            related_job_requirements=list(current.related_job_requirements),
            related_evidence=list(current.related_evidence),
            follow_up_questions=list(current.follow_up_questions),
            difficulty=current.difficulty,
            priority=current.priority,
            confidence=current.confidence,
            expected_answer_outline=list(current.expected_answer_outline),
            risk_tags=list(current.risk_tags),
            sequence_order=current.sequence_order,
            preparation_status=current.preparation_status,
            hidden=current.hidden,
            archived=current.archived,
            user_notes=notes,
            metadata=dict(current.metadata),
            created_at=current.created_at,
            updated_at=now,
        )
        saved = await self._questions().save_question(updated)
        question_set = await self._questions().get_set(saved.question_set_id, user_id=user_id)
        if question_set is not None:
            touched_set = InterviewQuestionSet(
                question_set_id=question_set.question_set_id,
                interview_id=question_set.interview_id,
                application_id=question_set.application_id,
                user_id=question_set.user_id,
                version_number=question_set.version_number,
                status=question_set.status,
                title=question_set.title,
                interview_type=question_set.interview_type,
                interview_round=question_set.interview_round,
                strategy_version=question_set.strategy_version,
                source_preparation_plan_id=question_set.source_preparation_plan_id,
                provider=question_set.provider,
                model_key=question_set.model_key,
                metadata=dict(question_set.metadata),
                generated_at=question_set.generated_at,
                updated_at=now,
                superseded_by_question_set_id=question_set.superseded_by_question_set_id,
                questions=list(question_set.questions),
            )
            saved_set = await self._questions().save_set(touched_set)
            interview = await self.get_interview(user_id, saved.interview_id)
            if interview is not None:
                await self._sync_question_set_state(
                    interview,
                    _build_question_set(saved_set, questions=question_set.questions),
                    actor_user_id=user_id,
                    occurred_at=now,
                    record_application_event=False,
                )
        return saved

    async def list_interviews(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        interview_status: str | None = None,
    ) -> list[InterviewRecord]:
        return await self._store().list_for_user(user_id, application_id=application_id, interview_status=interview_status)

    async def get_interview(self, user_id: str, interview_id: str) -> InterviewRecord | None:
        return await self._store().get(interview_id, user_id=user_id)

    async def get_preparation(self, user_id: str, interview_id: str) -> InterviewPreparationPlan | None:
        return await self._preparations().get_latest(interview_id, user_id=user_id)

    async def list_upcoming(self, user_id: str, *, limit: int = 10) -> list[InterviewRecord]:
        items = await self.list_interviews(user_id)
        now = datetime.now(timezone.utc)
        upcoming = [
            item
            for item in items
            if item.interview_status in _ACTIVE_UPCOMING_STATUSES
            and (_parse_datetime(item.scheduled_start_at) or now) >= now
        ]
        return sorted(
            upcoming,
            key=lambda item: (_parse_datetime(item.scheduled_start_at) or datetime.max.replace(tzinfo=timezone.utc), item.interview_id),
        )[:limit]

    async def prepare_interview(self, user_id: str, interview_id: str) -> InterviewPreparationPlan:
        existing = await self.get_preparation(user_id, interview_id)
        if existing is not None:
            return existing
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        application = await self._applications().get_application(user_id, interview.application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        plan = await self._build_preparation_plan(interview, application, version_number=1)
        saved_plan = await self._preparations().save(plan)
        await self._sync_preparation_plan(
            interview,
            saved_plan,
            event_type="InterviewPreparationGenerated",
            label="Preparation plan generated",
            detail=f"Generated preparation plan v{saved_plan.version_number} for {interview.interview_round}.",
            actor_user_id=user_id,
            occurred_at=saved_plan.generated_at or _iso_now(),
        )
        return saved_plan

    async def regenerate_preparation(self, user_id: str, interview_id: str) -> InterviewPreparationPlan:
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        application = await self._applications().get_application(user_id, interview.application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        latest = await self.get_preparation(user_id, interview_id)
        version_number = (latest.version_number + 1) if latest is not None else 1
        plan = await self._build_preparation_plan(interview, application, version_number=version_number)
        saved_plan = await self._preparations().save(plan)
        await self._sync_preparation_plan(
            interview,
            saved_plan,
            event_type="InterviewPreparationRegenerated",
            label="Preparation plan regenerated",
            detail=f"Generated preparation plan v{saved_plan.version_number} using the latest application and recruiter context.",
            actor_user_id=user_id,
            occurred_at=saved_plan.generated_at or _iso_now(),
        )
        return saved_plan

    async def update_preparation(
        self,
        user_id: str,
        interview_id: str,
        *,
        checklist: list[InterviewPreparationItem | dict[str, object]] | None = None,
        status: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> InterviewPreparationPlan:
        interview = await self.get_interview(user_id, interview_id)
        if interview is None:
            raise ValueError("Unknown interview workspace.")
        current = await self.get_preparation(user_id, interview_id)
        if current is None:
            raise ValueError("No preparation plan exists for this interview yet.")
        normalized_status = current.status
        if status is not None and status.strip():
            normalized_status = status.strip().casefold()
            if normalized_status not in _PREPARATION_PLAN_STATUSES:
                raise ValueError("Unsupported interview preparation plan status.")
        normalized_checklist = (
            _normalize_checklist(interview.interview_id, checklist, scheduled_start_at=interview.scheduled_start_at)
            if checklist is not None
            else current.checklist
        )
        now = _iso_now()
        updated_plan = InterviewPreparationPlan(
            plan_id=current.plan_id,
            interview_id=current.interview_id,
            application_id=current.application_id,
            user_id=current.user_id,
            version_number=current.version_number,
            status="updated" if checklist is not None else normalized_status,
            strategy_version=current.strategy_version,
            focus_labels=list(current.focus_labels),
            overall_confidence=current.overall_confidence,
            sections=list(current.sections),
            checklist=normalized_checklist,
            risks=list(current.risks),
            metadata={**dict(current.metadata), **dict(metadata or {})},
            generated_at=current.generated_at,
            updated_at=now,
        )
        saved_plan = await self._preparations().save(updated_plan)
        await self._sync_preparation_plan(
            interview,
            saved_plan,
            event_type="InterviewPreparationUpdated",
            label="Preparation plan updated",
            detail=f"Updated checklist progress for preparation plan v{saved_plan.version_number}.",
            actor_user_id=user_id,
            occurred_at=now,
        )
        return saved_plan

    async def create_interview(
        self,
        user_id: str,
        application_id: str,
        *,
        interview_type: str,
        interview_round: str = "",
        interview_status: str = "planned",
        scheduled_start_at: str = "",
        scheduled_end_at: str = "",
        timezone_name: str = "UTC",
        meeting_url: str = "",
        recruiter_name: str = "",
        recruiter_email: str = "",
        recruiter_contact_id: str = "",
        notes: str = "",
        preparation_status: str = "",
        interviewers: list[InterviewParticipant | dict[str, object]] | None = None,
        preparation_checklist: list[InterviewPreparationItem | dict[str, object]] | None = None,
        source: str = "manual",
        metadata: dict[str, object] | None = None,
    ) -> InterviewRecord:
        application = await self._applications().get_application(user_id, application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        normalized_type = _normalize_interview_type(interview_type)
        normalized_status = _normalize_interview_status(interview_status)
        now = _iso_now()
        resolved_start = scheduled_start_at.strip()
        resolved_end = scheduled_end_at.strip()
        interview_id = _interview_id(user_id, application_id, normalized_type, interview_round.strip(), resolved_start or now)
        normalized_interviewers = _normalize_interviewers(interview_id, interviewers)
        checklist = _normalize_checklist(interview_id, preparation_checklist, scheduled_start_at=resolved_start or None)
        if not checklist:
            checklist = _default_checklist(interview_id, interview_type=normalized_type, scheduled_start_at=resolved_start or None)
        resolved_preparation_status = (
            _normalize_preparation_status(preparation_status)
            if preparation_status.strip()
            else _derive_preparation_status(checklist)
        )
        resolved_recruiter_name = recruiter_name.strip() or application.structured_metadata.recruiter_name
        resolved_recruiter_email = recruiter_email.strip() or application.structured_metadata.recruiter_email
        timeline = [
            _timeline_item(
                event_type="InterviewCreated",
                label="Interview created",
                detail=f"{interview_round.strip() or 'New round'} · {normalized_type.replace('_', ' ')}",
                occurred_at=now,
            )
        ]
        if normalized_status in {"scheduled", "rescheduled"} and resolved_start:
            timeline.append(
                _timeline_item(
                    event_type="InterviewScheduled",
                    label="Interview scheduled",
                    detail=resolved_start,
                    occurred_at=now,
                )
            )
        audit_history = [_audit_entry(event_type="InterviewCreated", actor_user_id=user_id, detail="Interview workspace created.", created_at=now)]
        record = InterviewRecord(
            interview_id=interview_id,
            application_id=application_id,
            user_id=user_id,
            interview_type=normalized_type,
            interview_round=interview_round.strip() or "Round 1",
            interview_status=normalized_status,
            preparation_status=resolved_preparation_status,
            scheduled_start_at=resolved_start or None,
            scheduled_end_at=resolved_end or None,
            timezone=timezone_name.strip() or "UTC",
            meeting_url=meeting_url.strip(),
            recruiter_name=resolved_recruiter_name,
            recruiter_email=resolved_recruiter_email,
            recruiter_contact_id=recruiter_contact_id.strip(),
            notes=notes.strip(),
            source=source.strip() or "manual",
            interviewers=normalized_interviewers,
            preparation_checklist=checklist,
            timeline=timeline,
            audit_history=audit_history,
            metadata={
                "application_company": application.company,
                "application_title": application.title,
                **dict(metadata or {}),
            },
            created_at=now,
            updated_at=now,
            completed_at=now if normalized_status == "completed" else None,
        )
        saved = await self._store().save(record)
        await self._applications().record_interview_activity(
            user_id,
            application_id,
            interview_id=saved.interview_id,
            event_type="InterviewCreated",
            label="Interview created",
            detail=_application_interview_detail(saved),
            occurred_at=now,
        )
        return saved

    async def update_interview(
        self,
        user_id: str,
        interview_id: str,
        *,
        interview_type: str | None = None,
        interview_round: str | None = None,
        interview_status: str | None = None,
        scheduled_start_at: str | None = None,
        scheduled_end_at: str | None = None,
        timezone_name: str | None = None,
        meeting_url: str | None = None,
        recruiter_name: str | None = None,
        recruiter_email: str | None = None,
        recruiter_contact_id: str | None = None,
        notes: str | None = None,
        preparation_status: str | None = None,
        interviewers: list[InterviewParticipant | dict[str, object]] | None = None,
        preparation_checklist: list[InterviewPreparationItem | dict[str, object]] | None = None,
        source: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> InterviewRecord:
        record = await self._store().get(interview_id, user_id=user_id)
        if record is None:
            raise ValueError("Unknown interview workspace.")
        now = _iso_now()
        resolved_type = _normalize_interview_type(interview_type) if interview_type is not None else record.interview_type
        resolved_status = (
            _normalize_interview_status(interview_status) if interview_status is not None else record.interview_status
        )
        resolved_interviewers = (
            _normalize_interviewers(record.interview_id, interviewers) if interviewers is not None else record.interviewers
        )
        resolved_start = scheduled_start_at.strip() if scheduled_start_at is not None else record.scheduled_start_at
        resolved_end = scheduled_end_at.strip() if scheduled_end_at is not None else record.scheduled_end_at
        checklist = (
            _normalize_checklist(record.interview_id, preparation_checklist, scheduled_start_at=resolved_start or None)
            if preparation_checklist is not None
            else record.preparation_checklist
        )
        resolved_preparation_status = (
            _normalize_preparation_status(preparation_status)
            if preparation_status is not None and preparation_status.strip()
            else _derive_preparation_status(checklist, current=record.preparation_status)
        )
        timeline = list(record.timeline)
        detail_for_application = ""
        event_type_for_application = ""
        label_for_application = ""

        if resolved_status != record.interview_status:
            status_labels = {
                "planned": ("InterviewPlanned", "Interview planned"),
                "scheduled": ("InterviewScheduled", "Interview scheduled"),
                "completed": ("InterviewCompleted", "Interview completed"),
                "cancelled": ("InterviewCancelled", "Interview cancelled"),
                "rescheduled": ("InterviewRescheduled", "Interview rescheduled"),
                "no_show": ("InterviewNoShow", "Interview marked no-show"),
            }
            event_type_for_application, label_for_application = status_labels[resolved_status]
            detail_for_application = notes.strip() if notes is not None else _application_interview_detail(record)
            timeline.append(
                _timeline_item(
                    event_type=event_type_for_application,
                    label=label_for_application,
                    detail=detail_for_application,
                    occurred_at=now,
                )
            )
        elif (
            resolved_start != record.scheduled_start_at
            or resolved_end != record.scheduled_end_at
            or (timezone_name is not None and timezone_name != record.timezone)
        ):
            event_type_for_application = "InterviewRescheduled" if record.scheduled_start_at else "InterviewScheduled"
            label_for_application = "Interview schedule updated"
            detail_for_application = resolved_start or _application_interview_detail(record)
            timeline.append(
                _timeline_item(
                    event_type=event_type_for_application,
                    label=label_for_application,
                    detail=detail_for_application,
                    occurred_at=now,
                )
            )
        if resolved_preparation_status != record.preparation_status:
            timeline.append(
                _timeline_item(
                    event_type="PreparationStatusUpdated",
                    label="Preparation status updated",
                    detail=resolved_preparation_status.replace("_", " ").title(),
                    occurred_at=now,
                )
            )
        audit_history = list(record.audit_history)
        audit_history.append(
            _audit_entry(
                event_type="InterviewUpdated",
                actor_user_id=user_id,
                detail="Interview workspace updated.",
                created_at=now,
            )
        )
        completed_at = now if resolved_status == "completed" else (None if record.interview_status == "completed" and resolved_status != "completed" else record.completed_at)
        updated = _build_record(
            record=record,
            interview_type=resolved_type,
            interview_round=interview_round.strip() if interview_round is not None else record.interview_round,
            interview_status=resolved_status,
            preparation_status=resolved_preparation_status,
            scheduled_start_at=resolved_start or None,
            scheduled_end_at=resolved_end or None,
            timezone_name=timezone_name.strip() if timezone_name is not None else record.timezone,
            meeting_url=meeting_url.strip() if meeting_url is not None else record.meeting_url,
            recruiter_name=recruiter_name.strip() if recruiter_name is not None else record.recruiter_name,
            recruiter_email=recruiter_email.strip() if recruiter_email is not None else record.recruiter_email,
            recruiter_contact_id=recruiter_contact_id.strip() if recruiter_contact_id is not None else record.recruiter_contact_id,
            notes=notes.strip() if notes is not None else record.notes,
            source=source.strip() if source is not None else record.source,
            interviewers=resolved_interviewers,
            preparation_checklist=checklist,
            timeline=timeline,
            audit_history=audit_history,
            metadata={**dict(record.metadata), **dict(metadata or {})},
            updated_at=now,
            completed_at=completed_at,
        )
        saved = await self._store().save(updated)
        latest_plan = await self._preparations().get_latest(saved.interview_id, user_id=user_id)
        if latest_plan is not None and preparation_checklist is not None:
            refreshed_plan = InterviewPreparationPlan(
                plan_id=latest_plan.plan_id,
                interview_id=latest_plan.interview_id,
                application_id=latest_plan.application_id,
                user_id=latest_plan.user_id,
                version_number=latest_plan.version_number,
                status="updated",
                strategy_version=latest_plan.strategy_version,
                focus_labels=list(latest_plan.focus_labels),
                overall_confidence=latest_plan.overall_confidence,
                sections=list(latest_plan.sections),
                checklist=checklist,
                risks=list(latest_plan.risks),
                metadata=dict(latest_plan.metadata),
                generated_at=latest_plan.generated_at,
                updated_at=now,
            )
            await self._preparations().save(refreshed_plan)
        if event_type_for_application and label_for_application:
            await self._applications().record_interview_activity(
                user_id,
                saved.application_id,
                interview_id=saved.interview_id,
                event_type=event_type_for_application,
                label=label_for_application,
                detail=detail_for_application or _application_interview_detail(saved),
                occurred_at=now,
            )
        return saved

    async def delete_interview(self, user_id: str, interview_id: str) -> InterviewRecord:
        deleted = await self._store().delete(interview_id, user_id=user_id)
        if deleted is None:
            raise ValueError("Unknown interview workspace.")
        await self._preparations().delete_for_interview(interview_id, user_id=user_id)
        await self._questions().delete_for_interview(interview_id, user_id=user_id)
        await self._stories().delete_for_interview(interview_id, user_id=user_id)
        await self._applications().record_interview_activity(
            user_id,
            deleted.application_id,
            interview_id=deleted.interview_id,
            event_type="InterviewDeleted",
            label="Interview removed from workspace",
            detail=_application_interview_detail(deleted),
            occurred_at=_iso_now(),
            remove=True,
        )
        return deleted


def build_interview_intelligence_service(settings: AppSettings | None = None) -> InterviewIntelligenceService:
    resolved_settings = settings or get_settings()
    return InterviewIntelligenceService(
        settings=resolved_settings,
        interview_store=build_interview_store(resolved_settings),
        application_service=build_application_intelligence_service(resolved_settings),
        preparation_store=build_interview_preparation_plan_store(resolved_settings),
        question_store=build_interview_question_bank_store(resolved_settings),
        story_store=build_interview_story_store(resolved_settings),
        knowledge_client=build_knowledge_platform_client(resolved_settings),
        recruiter_service=build_recruiter_intelligence_service(resolved_settings),
        resume_service=build_resume_intelligence_service(resolved_settings),
        version_store=build_resume_version_store(resolved_settings),
    )
