from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.application_intelligence import ApplicationRecord

from .models import (
    CommunicationDraft,
    CommunicationEvidence,
    CommunicationHealth,
    CommunicationInsightSummary,
    CommunicationSummary,
    RecruiterMessage,
    RecruiterThread,
)

_ASSISTANT_STRATEGY_VERSION = "recruiter-assistant.v1"
_ASSISTANT_MODEL_KEY = "deterministic_template"
_SUPPORTED_DRAFT_KINDS = {"reply", "follow_up", "interview_confirmation", "thank_you"}
_SUPPORTED_TONES = {"professional", "warm", "direct", "appreciative"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary_id(scope_type: str, scope_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"communication-summary:{scope_type}:{scope_id}"))


def _normalize_subject(subject: str) -> str:
    normalized = subject.strip()
    while normalized[:3].lower() in {"re:", "fw:", "fwd"}:
        normalized = normalized[3:].lstrip(": ").strip()
    return normalized


def _thread_subject(subject: str) -> str:
    base = _normalize_subject(subject)
    return base or "Recruiter conversation"


def _evidence_items(
    *,
    latest_message: RecruiterMessage,
    application: ApplicationRecord | None,
    pending_action: str = "",
) -> list[CommunicationEvidence]:
    items = [
        CommunicationEvidence(
            source_type="recruiter_message",
            source_id=latest_message.message_id,
            label=latest_message.subject or latest_message.message_type.replace("_", " ").title(),
            excerpt=latest_message.body_preview or latest_message.subject,
        )
    ]
    if application is not None:
        items.append(
            CommunicationEvidence(
                source_type="application",
                source_id=application.application_id,
                label=f"{application.company} · {application.title}",
                excerpt=f"Application status: {application.status.replace('_', ' ')}",
            )
        )
    if pending_action:
        items.append(
            CommunicationEvidence(
                source_type="workflow_suggestion",
                source_id=latest_message.message_id,
                label="Pending action",
                excerpt=pending_action,
            )
        )
    return items


def _summary_confidence(latest_message: RecruiterMessage, application: ApplicationRecord | None) -> float:
    values = [latest_message.confidence or 0.0]
    if latest_message.application_id and application is not None:
        values.append(latest_message.match_confidence or 0.0)
    return round(sum(values) / max(len(values), 1), 2)


def build_message_summary(
    *,
    message: RecruiterMessage,
    application: ApplicationRecord | None,
    communication_summary: CommunicationSummary,
    health: CommunicationHealth,
) -> CommunicationInsightSummary:
    objective = communication_summary.pending_action or "Review the recruiter message and decide the next response."
    key_points = [
        f"Latest message type: {message.message_type.replace('_', ' ')}",
        f"Waiting on: {communication_summary.waiting_on or 'none'}",
    ]
    if message.company.strip() or message.job_title.strip():
        key_points.append(f"Role context: {message.company.strip() or 'Unknown company'} · {message.job_title.strip() or 'Unknown role'}")
    risks: list[str] = []
    if health.reason.strip() and health.status not in {"healthy", "closed", "unknown"}:
        risks.append(health.reason)
    assumptions = [] if application is not None else ["This message is not yet linked to a canonical application record."]
    return CommunicationInsightSummary(
        summary_id=_summary_id("message", message.message_id),
        scope_type="message",
        scope_id=message.message_id,
        thread_id=message.thread_id,
        application_id=message.application_id,
        message_id=message.message_id,
        title=message.subject or message.message_type.replace("_", " ").title(),
        summary=(
            f"{message.recruiter.display_name or message.recruiter.email} sent a "
            f"{message.message_type.replace('_', ' ')} message about "
            f"{message.job_title or 'the role'} at {message.company or 'the company'}."
        ),
        communication_objective=objective,
        key_points=key_points,
        pending_action=communication_summary.pending_action,
        risks=risks,
        evidence=_evidence_items(latest_message=message, application=application, pending_action=communication_summary.pending_action),
        assumptions=assumptions,
        confidence=_summary_confidence(message, application),
        strategy_version=_ASSISTANT_STRATEGY_VERSION,
        generated_at=_iso_now(),
    )


def build_thread_summary(
    *,
    thread: RecruiterThread,
    messages: list[RecruiterMessage],
    application: ApplicationRecord | None,
    communication_summary: CommunicationSummary,
    health: CommunicationHealth,
) -> CommunicationInsightSummary:
    latest = messages[0] if messages else None
    if latest is None:
        return CommunicationInsightSummary(
            summary_id=_summary_id("thread", thread.thread_id),
            scope_type="thread",
            scope_id=thread.thread_id,
            thread_id=thread.thread_id,
            application_id=thread.application_id,
            title=thread.subject,
            summary="No recruiter messages are available in this thread yet.",
            communication_objective="Review the thread when new recruiter communication arrives.",
            confidence=0.2,
            strategy_version=_ASSISTANT_STRATEGY_VERSION,
            generated_at=_iso_now(),
        )
    key_points = [
        f"Conversation state: {communication_summary.conversation_status.replace('_', ' ')}",
        f"Waiting on: {communication_summary.waiting_on or 'none'}",
        f"Messages in thread: {thread.message_count}",
    ]
    if communication_summary.last_contact_date:
        key_points.append(f"Last contact: {communication_summary.last_contact_date}")
    risks: list[str] = []
    if health.reason.strip() and health.status not in {"healthy", "closed", "unknown"}:
        risks.append(health.reason)
    assumptions = [] if thread.application_id else ["This thread is not yet linked to a canonical application record."]
    return CommunicationInsightSummary(
        summary_id=_summary_id("thread", thread.thread_id),
        scope_type="thread",
        scope_id=thread.thread_id,
        thread_id=thread.thread_id,
        application_id=thread.application_id,
        message_id=latest.message_id,
        title=_thread_subject(thread.subject),
        summary=(
            f"The recruiter thread with {thread.recruiter.display_name or thread.recruiter.email} is currently "
            f"{communication_summary.conversation_status.replace('_', ' ')} for "
            f"{thread.job_title or 'the role'} at {thread.company or 'the company'}."
        ),
        communication_objective=communication_summary.pending_action or "Keep the recruiter conversation moving without losing application context.",
        key_points=key_points,
        pending_action=communication_summary.pending_action,
        risks=risks,
        evidence=_evidence_items(latest_message=latest, application=application, pending_action=communication_summary.pending_action),
        assumptions=assumptions,
        confidence=_summary_confidence(latest, application),
        strategy_version=_ASSISTANT_STRATEGY_VERSION,
        generated_at=_iso_now(),
    )


def normalize_draft_kind(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized in _SUPPORTED_DRAFT_KINDS else "reply"


def normalize_tone(value: str) -> str:
    normalized = value.strip().casefold()
    return normalized if normalized in _SUPPORTED_TONES else "professional"


def _salutation(recipient_name: str, tone: str) -> str:
    name = recipient_name.strip() or "there"
    if tone == "direct":
        return f"Hi {name},"
    return f"Hi {name},"


def _closing(tone: str) -> str:
    if tone == "warm":
        return "Best regards,"
    if tone == "appreciative":
        return "Thanks again,"
    if tone == "direct":
        return "Best,"
    return "Best,"


def _body_for_kind(
    *,
    draft_kind: str,
    tone: str,
    recruiter_name: str,
    company: str,
    title: str,
    thread_subject: str,
    message_preview: str,
    pending_action: str,
) -> tuple[str, str, str, list[str]]:
    role_context = f"{title} role at {company}".strip() if company or title else "opportunity"
    assumptions: list[str] = []
    if draft_kind == "follow_up":
        subject = f"Follow-up on {_thread_subject(thread_subject)}"
        objective = "Follow up with the recruiter while keeping the conversation active."
        body = (
            f"{_salutation(recruiter_name, tone)}\n\n"
            f"I wanted to follow up on our conversation about the {role_context}. "
            "I remain interested and wanted to check whether there are any updates on timing or next steps.\n\n"
            f"{_closing(tone)}"
        )
        return subject, body, objective, assumptions
    if draft_kind == "interview_confirmation":
        subject = f"Re: {_thread_subject(thread_subject)}"
        objective = "Confirm interest and keep interview scheduling moving."
        body = (
            f"{_salutation(recruiter_name, tone)}\n\n"
            f"Thank you for reaching out about the {role_context}. "
            "I would be glad to move forward and coordinate the next interview step.\n\n"
            "Please let me know the preferred scheduling process, or I can share availability if that is helpful.\n\n"
            f"{_closing(tone)}"
        )
        return subject, body, objective, assumptions
    if draft_kind == "thank_you":
        subject = f"Thank you - {_thread_subject(thread_subject)}"
        objective = "Send a post-conversation thank-you note without inventing new details."
        assumptions.append("This draft assumes an interview or live conversation has already happened.")
        body = (
            f"{_salutation(recruiter_name, tone)}\n\n"
            f"Thank you for the conversation about the {role_context}. "
            "I appreciated the opportunity to learn more about the team and the work.\n\n"
            "I remain excited about the opportunity and would be glad to continue with the process.\n\n"
            f"{_closing(tone)}"
        )
        return subject, body, objective, assumptions
    subject = f"Re: {_thread_subject(thread_subject)}"
    objective = pending_action or "Reply to the recruiter and keep the workflow moving."
    preview_sentence = message_preview.strip()
    if preview_sentence:
        preview_sentence = preview_sentence.rstrip(".")
    body = (
        f"{_salutation(recruiter_name, tone)}\n\n"
        f"Thank you for your message about the {role_context}. "
        f"{'I reviewed your note about ' + preview_sentence + '. ' if preview_sentence else ''}"
        "I would be glad to keep moving forward and can provide whatever is most helpful for the next step.\n\n"
        f"{_closing(tone)}"
    )
    return subject, body, objective, assumptions


def build_draft(
    *,
    base: CommunicationDraft,
    latest_message: RecruiterMessage,
    application: ApplicationRecord | None,
    communication_summary: CommunicationSummary,
) -> CommunicationDraft:
    draft_kind = normalize_draft_kind(base.draft_kind)
    tone = normalize_tone(base.tone)
    subject, body, objective, assumptions = _body_for_kind(
        draft_kind=draft_kind,
        tone=tone,
        recruiter_name=latest_message.recruiter.display_name or latest_message.recruiter.email,
        company=latest_message.company or (application.company if application is not None else ""),
        title=latest_message.job_title or (application.title if application is not None else ""),
        thread_subject=latest_message.subject,
        message_preview=latest_message.body_preview,
        pending_action=communication_summary.pending_action,
    )
    evidence = _evidence_items(
        latest_message=latest_message,
        application=application,
        pending_action=communication_summary.pending_action,
    )
    explanation = (
        f"This {draft_kind.replace('_', ' ')} draft is grounded in the latest recruiter message, "
        f"the linked application context, and the current workflow suggestion."
    )
    return CommunicationDraft(
        draft_id=base.draft_id,
        draft_group_id=base.draft_group_id,
        version_number=base.version_number,
        user_id=base.user_id,
        thread_id=base.thread_id,
        draft_kind=draft_kind,
        tone=tone,
        status=base.status,
        intended_recipient=latest_message.recruiter.display_name or latest_message.recruiter.email,
        intended_recipient_email=latest_message.recruiter.email,
        communication_objective=objective,
        subject=subject,
        body=body,
        confidence=round(min(max((latest_message.confidence + (latest_message.match_confidence or 0.55)) / 2, 0.4), 0.98), 2),
        explanation=explanation,
        strategy_version=_ASSISTANT_STRATEGY_VERSION,
        model_key=_ASSISTANT_MODEL_KEY,
        application_id=base.application_id,
        source_message_id=base.source_message_id,
        parent_draft_id=base.parent_draft_id,
        evidence=evidence,
        assumptions=assumptions,
        user_edited=base.user_edited,
        generated_at=base.generated_at or _iso_now(),
        created_at=base.created_at,
        updated_at=base.updated_at,
    )
