from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from app.application_intelligence import ApplicationIntelligenceService, ApplicationRecord, build_application_intelligence_service
from app.config import AppSettings, get_settings
from app.db.client import connection

from .assistant import build_draft, build_message_summary, build_thread_summary, normalize_draft_kind, normalize_tone
from .models import (
    CommunicationEvent,
    CommunicationDraft,
    CommunicationInsightSummary,
    CommunicationHealth,
    CommunicationSummary,
    ConversationSla,
    ConversationState,
    ConversationSuggestion,
    RecruiterContact,
    RecruiterContactApplicationLink,
    RecruiterContactProfile,
    RecruiterMessage,
    RecruiterMessageImportRecord,
    RecruiterThread,
)

_ACTIONABLE_CONVERSATION_STATUSES = {"awaiting_user", "action_required", "decision_required"}
_MATCH_ATTACH_THRESHOLD = 0.75
_MATCH_AMBIGUITY_GAP = 0.15
_RECRUITER_FOLLOW_UP_DAYS = 5
_STALE_DAYS = 7
_BLOCKED_DAYS = 10
_CANDIDATE_BLOCKED_DAYS = 7
_CLOSED_APPLICATION_STATUSES = {"accepted", "rejected", "withdrawn"}
_CONVERSATION_STATE_LABELS = {
    "waiting_for_recruiter": "Waiting For Recruiter",
    "waiting_for_candidate": "Waiting For Candidate",
    "interview_scheduled": "Interview Scheduled",
    "assessment_pending": "Assessment Pending",
    "offer_pending": "Offer Pending",
    "conversation_closed": "Conversation Closed",
    "unknown": "Unknown",
}
_COMMUNICATION_HEALTH_LABELS = {
    "healthy": "Healthy",
    "needs_follow_up": "Needs Follow-up",
    "stale": "Stale",
    "blocked": "Blocked",
    "closed": "Closed",
    "unknown": "Unknown",
}
_COMMUNICATION_HEALTH_SCORES = {
    "healthy": 90,
    "needs_follow_up": 65,
    "stale": 40,
    "blocked": 20,
    "closed": 100,
    "unknown": 50,
}
_MESSAGE_TYPE_ACTIONS: dict[str, dict[str, object]] = {
    "interview_invitation": {
        "event_type": "InterviewRequested",
        "title": "Interview requested",
        "pending_action": "Reply to schedule the interview",
        "suggested_actions": ["Reply within 24 hours", "Schedule interview", "Prepare STAR stories"],
        "conversation_status": "awaiting_user",
        "response_window_hours": 24,
    },
    "assessment": {
        "event_type": "AssessmentReceived",
        "title": "Assessment received",
        "pending_action": "Complete the assessment",
        "suggested_actions": ["Confirm the deadline", "Complete assessment", "Block time for preparation"],
        "conversation_status": "action_required",
        "response_window_hours": 48,
    },
    "offer": {
        "event_type": "OfferReceived",
        "title": "Offer received",
        "pending_action": "Review the offer details",
        "suggested_actions": ["Review offer details", "Prepare questions", "Respond before the deadline"],
        "conversation_status": "decision_required",
        "response_window_hours": 48,
    },
    "rejection": {
        "event_type": "Rejected",
        "title": "Rejection received",
        "pending_action": "",
        "suggested_actions": ["Review the message and update application notes"],
        "conversation_status": "closed",
        "response_window_hours": 0,
    },
    "recruiter_outreach": {
        "event_type": "RecruiterContacted",
        "title": "Recruiter outreach received",
        "pending_action": "Reply to the recruiter",
        "suggested_actions": ["Reply within 24 hours", "Evaluate the role fit", "Share current resume if needed"],
        "conversation_status": "awaiting_user",
        "response_window_hours": 24,
    },
    "follow_up": {
        "event_type": "FollowUpReceived",
        "title": "Follow-up received",
        "pending_action": "Reply to the follow-up",
        "suggested_actions": ["Reply within 24 hours", "Confirm the current status", "Capture any new deadlines"],
        "conversation_status": "awaiting_user",
        "response_window_hours": 24,
    },
    "scheduling": {
        "event_type": "SchedulingRequested",
        "title": "Scheduling request received",
        "pending_action": "Share your availability",
        "suggested_actions": ["Reply within 24 hours", "Share interview availability", "Confirm time zone details"],
        "conversation_status": "awaiting_user",
        "response_window_hours": 24,
    },
    "general": {
        "event_type": "RecruiterMessageLogged",
        "title": "Recruiter message logged",
        "pending_action": "Review the recruiter message",
        "suggested_actions": ["Review the message", "Capture relevant notes on the application"],
        "conversation_status": "active",
        "response_window_hours": 0,
    },
    "unknown": {
        "event_type": "RecruiterMessageLogged",
        "title": "Recruiter message logged",
        "pending_action": "Review the recruiter message",
        "suggested_actions": ["Review the message manually"],
        "conversation_status": "active",
        "response_window_hours": 0,
    },
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
    normalized = "".join(character.lower() if character.isalnum() else " " for character in value)
    return " ".join(segment for segment in normalized.split() if segment)


def _normalize_subject(value: str) -> str:
    normalized = value.strip()
    while normalized[:3].lower() in {"re:", "fw:", "fwd"}:
        normalized = normalized[3:].lstrip(": ").strip()
    return normalized


def _body_preview(value: str, *, limit: int = 280) -> str:
    preview = " ".join(value.split())
    return preview[:limit]


def _round_hours(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _contains_phrase(text: str, phrase: str) -> bool:
    return _normalize_text(phrase) in text


def _token_overlap_score(left: str, right: str) -> float:
    left_tokens = {
        token
        for token in _normalize_text(left).split()
        if token not in {"and", "at", "engineer", "of", "for", "senior", "staff", "the", "to"}
    }
    right_tokens = {
        token
        for token in _normalize_text(right).split()
        if token not in {"and", "at", "engineer", "of", "for", "senior", "staff", "the", "to"}
    }
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    if not overlap:
        return 0.0
    if left_tokens == right_tokens:
        return 0.25
    coverage = len(overlap) / max(len(left_tokens), len(right_tokens))
    if coverage >= 0.66:
        return 0.18
    return 0.1


def _recruiter_contact_id(user_id: str, email: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"recruiter-contact:{user_id}:{email.strip().casefold()}"))


def _thread_id(user_id: str, item: RecruiterMessageImportRecord, recruiter_email: str, subject: str) -> str:
    if item.external_thread_id.strip():
        basis = item.external_thread_id.strip()
    else:
        parts = [
            item.source.strip() or "manual_import",
            recruiter_email.strip().casefold(),
            _normalize_text(subject),
            _normalize_text(item.company),
            _normalize_text(item.job_title),
        ]
        basis = ":".join(parts)
    return str(uuid5(NAMESPACE_URL, f"recruiter-thread:{user_id}:{basis}"))


def _message_id(user_id: str, item: RecruiterMessageImportRecord, recruiter_email: str, subject: str) -> str:
    if item.external_message_id.strip():
        basis = item.external_message_id.strip()
    else:
        parts = [
            item.source.strip() or "manual_import",
            recruiter_email.strip().casefold(),
            _normalize_text(subject),
            item.received_at or "",
            _normalize_text(item.body_reference or item.body_text[:120]),
        ]
        basis = ":".join(parts)
    return str(uuid5(NAMESPACE_URL, f"recruiter-message:{user_id}:{basis}"))


def _event_id(message_id: str, event_type: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"communication-event:{message_id}:{event_type}"))


def _draft_group_id(thread_id: str, draft_kind: str, source_message_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"communication-draft-group:{thread_id}:{draft_kind}:{source_message_id or 'latest'}"))


def _draft_id(draft_group_id: str, version_number: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"communication-draft:{draft_group_id}:{version_number}"))


def _suggestion_id(scope_id: str, action_type: str, supporting_message_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"conversation-suggestion:{scope_id}:{action_type}:{supporting_message_id}"))


def _is_recruiter_authored(message: RecruiterMessage) -> bool:
    recruiter_email = message.recruiter.email.strip().casefold()
    sender = message.sender.strip().casefold()
    if not sender:
        return True
    return sender == recruiter_email


def _is_candidate_authored(message: RecruiterMessage) -> bool:
    sender = message.sender.strip()
    if not sender:
        return False
    return not _is_recruiter_authored(message)


def _sort_messages(messages: list[RecruiterMessage]) -> list[RecruiterMessage]:
    return sorted(
        messages,
        key=lambda item: (_parse_datetime(item.received_at) or datetime.min.replace(tzinfo=timezone.utc), item.message_id),
    )


def _latest_message(messages: list[RecruiterMessage]) -> RecruiterMessage | None:
    if not messages:
        return None
    return _sort_messages(messages)[-1]


def _latest_matching_message(messages: list[RecruiterMessage], predicate) -> RecruiterMessage | None:
    for message in reversed(_sort_messages(messages)):
        if predicate(message):
            return message
    return None


def _message_received_at(message: RecruiterMessage) -> datetime | None:
    return _parse_datetime(message.received_at or message.created_at)


def _days_since(value: str | None) -> int | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    delta = datetime.now(timezone.utc) - parsed
    return max(int(delta.total_seconds() // 86400), 0)


def _hours_between(start: str | None, end: str | None) -> float | None:
    start_dt = _parse_datetime(start)
    end_dt = _parse_datetime(end)
    if start_dt is None or end_dt is None or end_dt < start_dt:
        return None
    return _round_hours((end_dt - start_dt).total_seconds() / 3600)


def _response_latency_pairs(messages: list[RecruiterMessage]) -> list[tuple[RecruiterMessage, RecruiterMessage, float]]:
    pending_recruiter: RecruiterMessage | None = None
    pairs: list[tuple[RecruiterMessage, RecruiterMessage, float]] = []
    for message in _sort_messages(messages):
        if _is_recruiter_authored(message):
            pending_recruiter = message
            continue
        if not _is_candidate_authored(message) or pending_recruiter is None:
            continue
        latency = _hours_between(pending_recruiter.received_at, message.received_at)
        if latency is None:
            continue
        pairs.append((pending_recruiter, message, latency))
        pending_recruiter = None
    return pairs


def _average_response_latency_hours(messages: list[RecruiterMessage]) -> float | None:
    pairs = _response_latency_pairs(messages)
    if not pairs:
        return None
    return _round_hours(sum(latency for _, _, latency in pairs) / len(pairs))


def _latest_response_latency_hours(messages: list[RecruiterMessage]) -> float | None:
    pairs = _response_latency_pairs(messages)
    if not pairs:
        return None
    return pairs[-1][2]


def _waiting_on_for_latest_message(message: RecruiterMessage | None) -> str:
    if message is None:
        return "none"
    if _is_recruiter_authored(message):
        return "candidate"
    if _is_candidate_authored(message):
        return "recruiter"
    return "none"


def _interview_scheduled_signal(messages: list[RecruiterMessage]) -> RecruiterMessage | None:
    scheduling_signals = ("calendar invite", "scheduled for", "confirmed", "booked", "see you on")
    for message in reversed(_sort_messages(messages)):
        if message.message_type not in {"interview_invitation", "scheduling"}:
            continue
        text = _normalize_text(" ".join([message.subject, message.body_preview]))
        if any(signal in text for signal in scheduling_signals):
            return message
    return None


def _candidate_response_threshold_hours(last_message_type: str) -> int:
    guidance = _message_guidance(last_message_type)
    threshold = int(guidance.get("response_window_hours", 0) or 0)
    if threshold > 0:
        return threshold
    return 24 if last_message_type in {"follow_up", "general", "unknown"} else 48


def _waiting_threshold_hours(waiting_on: str, last_message_type: str) -> int:
    if waiting_on == "candidate":
        return _candidate_response_threshold_hours(last_message_type)
    if waiting_on == "recruiter":
        return _RECRUITER_FOLLOW_UP_DAYS * 24
    return 0


def _overdue_for_waiting_side(last_contact_at: str | None, waiting_on: str, last_message_type: str) -> bool:
    threshold_hours = _waiting_threshold_hours(waiting_on, last_message_type)
    if threshold_hours <= 0:
        return False
    due_at = _communication_due_at(last_contact_at, threshold_hours)
    due_at_dt = _parse_datetime(due_at)
    if due_at_dt is None:
        return False
    return due_at_dt < datetime.now(timezone.utc)


def _classification(text: str) -> tuple[str, float, str]:
    rules: list[tuple[str, float, str, tuple[str, ...]]] = [
        (
            "rejection",
            0.98,
            "rejection phrasing detected",
            (
                "unfortunately",
                "regret to inform",
                "not moving forward",
                "move forward with other candidates",
                "decided to pursue other candidates",
                "position has been filled",
            ),
        ),
        (
            "offer",
            0.98,
            "offer language detected",
            ("extend an offer", "offer letter", "written offer", "compensation package", "congratulations"),
        ),
        (
            "assessment",
            0.95,
            "assessment keywords detected",
            ("assessment", "take home", "take-home", "hackerrank", "codility", "online test"),
        ),
        (
            "follow_up",
            0.9,
            "follow-up phrasing detected",
            ("following up", "follow up", "checking in", "circling back", "just wanted to bump"),
        ),
        (
            "scheduling",
            0.92,
            "scheduling language detected",
            ("availability", "schedule", "reschedule", "time slots", "calendar invite", "timezone"),
        ),
        (
            "interview_invitation",
            0.94,
            "interview invitation language detected",
            ("interview", "phone screen", "technical screen", "onsite", "final round", "meet with the team"),
        ),
        (
            "recruiter_outreach",
            0.88,
            "outreach language detected",
            ("came across your profile", "came across your background", "might be a fit", "would love to connect", "open role"),
        ),
    ]
    for message_type, confidence, reason, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return message_type, confidence, reason
    if text.strip():
        return "general", 0.55, "message contains recruiter content but no stronger rule matched"
    return "unknown", 0.0, "message does not contain enough content to classify"


def _message_guidance(message_type: str) -> dict[str, object]:
    return dict(_MESSAGE_TYPE_ACTIONS.get(message_type, _MESSAGE_TYPE_ACTIONS["unknown"]))


def _timeline_detail(subject: str, recruiter_name: str, company: str) -> str:
    if subject.strip():
        return subject.strip()
    if recruiter_name.strip() and company.strip():
        return f"{recruiter_name.strip()} from {company.strip()}"
    return recruiter_name.strip() or company.strip()


def _communication_due_at(received_at: str | None, response_window_hours: int) -> str | None:
    if response_window_hours <= 0:
        return None
    received = _parse_datetime(received_at)
    if received is None:
        return None
    return (received + timedelta(hours=response_window_hours)).isoformat()


def _response_overdue(received_at: str | None, conversation_status: str, response_window_hours: int) -> bool:
    if conversation_status not in _ACTIONABLE_CONVERSATION_STATUSES or response_window_hours <= 0:
        return False
    due_at = _parse_datetime(_communication_due_at(received_at, response_window_hours))
    if due_at is None:
        return False
    return due_at < datetime.now(timezone.utc)


def _build_sla(messages: list[RecruiterMessage]) -> ConversationSla:
    latest = _latest_message(messages)
    last_recruiter = _latest_matching_message(messages, _is_recruiter_authored)
    last_candidate = _latest_matching_message(messages, _is_candidate_authored)
    waiting_on = _waiting_on_for_latest_message(latest)
    last_contact_at = latest.received_at if latest is not None else None
    last_message_type = latest.message_type if latest is not None else "unknown"
    return ConversationSla(
        waiting_on=waiting_on,
        last_recruiter_message_at=last_recruiter.received_at if last_recruiter is not None else None,
        last_candidate_response_at=last_candidate.received_at if last_candidate is not None else None,
        last_contact_at=last_contact_at,
        response_latency_hours=_latest_response_latency_hours(messages),
        average_response_latency_hours=_average_response_latency_hours(messages),
        days_since_last_contact=_days_since(last_contact_at),
        overdue_threshold_hours=_waiting_threshold_hours(waiting_on, last_message_type),
        overdue=_overdue_for_waiting_side(last_contact_at, waiting_on, last_message_type),
    )


def _build_conversation_state(
    messages: list[RecruiterMessage],
    *,
    application: ApplicationRecord | None = None,
) -> ConversationState:
    latest = _latest_message(messages)
    if latest is None:
        if application is not None and (application.status in _CLOSED_APPLICATION_STATUSES or application.status == "accepted"):
            return ConversationState(
                application_id=application.application_id,
                state="conversation_closed",
                label=_CONVERSATION_STATE_LABELS["conversation_closed"],
                reason=f"Application status is already {application.status}.",
            )
        return ConversationState(application_id=application.application_id if application is not None else None)

    sla = _build_sla(messages)
    state = "unknown"
    reason = "Conversation history does not yet establish a stable waiting state."
    application_status = application.status if application is not None else ""
    scheduled_message = _interview_scheduled_signal(messages)

    if application_status in _CLOSED_APPLICATION_STATUSES or application_status == "accepted":
        state = "conversation_closed"
        reason = f"Application status is already {application_status}."
    elif latest.message_type == "rejection":
        state = "conversation_closed"
        reason = "The latest recruiter message is a rejection."
    elif latest.message_type == "offer" and sla.waiting_on == "candidate":
        state = "offer_pending"
        reason = "The latest recruiter message contains an offer that still needs a candidate response."
    elif latest.message_type == "assessment" and sla.waiting_on == "candidate":
        state = "assessment_pending"
        reason = "The latest recruiter message requests an assessment that still needs a candidate response."
    elif scheduled_message is not None:
        state = "interview_scheduled"
        reason = "Scheduling language indicates the interview time has likely been confirmed."
    elif sla.waiting_on == "recruiter":
        state = "waiting_for_recruiter"
        reason = "The candidate replied last, so the next move belongs to the recruiter."
    elif sla.waiting_on == "candidate":
        state = "waiting_for_candidate"
        reason = "The recruiter replied last, so the candidate still owes the next action."

    return ConversationState(
        application_id=application.application_id if application is not None else latest.application_id,
        thread_id=latest.thread_id,
        state=state,
        label=_CONVERSATION_STATE_LABELS.get(state, state.replace("_", " ").title()),
        waiting_on=sla.waiting_on,
        derived_from_message_id=latest.message_id,
        last_message_type=latest.message_type,
        last_message_at=latest.received_at,
        reason=reason,
        sla=sla,
    )


def _build_communication_health(
    state: ConversationState,
    *,
    application: ApplicationRecord | None = None,
) -> CommunicationHealth:
    days_since_last_contact = state.sla.days_since_last_contact
    status = "healthy"
    reason = "Conversation is current and does not need intervention yet."
    needs_follow_up = False

    if state.state == "conversation_closed" or (application is not None and application.status == "accepted"):
        status = "closed"
        reason = state.reason
    elif days_since_last_contact is None:
        status = "unknown"
        reason = "No conversation timestamps are available yet."
    elif state.waiting_on == "recruiter":
        if days_since_last_contact >= _BLOCKED_DAYS:
            status = "blocked"
            reason = f"The recruiter has not replied for {days_since_last_contact} days."
            needs_follow_up = True
        elif days_since_last_contact >= _STALE_DAYS:
            status = "stale"
            reason = f"The recruiter conversation has been quiet for {days_since_last_contact} days."
            needs_follow_up = True
        elif days_since_last_contact >= _RECRUITER_FOLLOW_UP_DAYS:
            status = "needs_follow_up"
            reason = f"The recruiter has not replied for {days_since_last_contact} days, so a follow-up is appropriate."
            needs_follow_up = True
    elif state.waiting_on == "candidate" or state.state in {"assessment_pending", "offer_pending"}:
        if state.sla.overdue and days_since_last_contact >= _CANDIDATE_BLOCKED_DAYS:
            status = "blocked"
            reason = "The candidate response window has passed long enough that the application is at risk."
            needs_follow_up = True
        elif state.sla.overdue:
            status = "needs_follow_up"
            reason = "The candidate response window is overdue."
            needs_follow_up = True

    return CommunicationHealth(
        application_id=state.application_id,
        status=status,
        label=_COMMUNICATION_HEALTH_LABELS.get(status, status.replace("_", " ").title()),
        score=_COMMUNICATION_HEALTH_SCORES.get(status, 50),
        waiting_on=state.waiting_on,
        last_message_at=state.last_message_at,
        needs_follow_up=needs_follow_up,
        reason=reason,
    )


def _suggestion_due_at(message_at: str | None, hours: int) -> str | None:
    if hours <= 0:
        return None
    return _communication_due_at(message_at, hours)


def _build_suggestions(
    messages: list[RecruiterMessage],
    *,
    state: ConversationState,
    health: CommunicationHealth,
    application_id: str | None,
) -> list[ConversationSuggestion]:
    latest = _latest_message(messages)
    if latest is None:
        return []

    suggestions: list[ConversationSuggestion] = []
    seen_action_types: set[str] = set()
    last_recruiter = _latest_matching_message(messages, _is_recruiter_authored)
    last_candidate = _latest_matching_message(messages, _is_candidate_authored)
    scope_id = application_id or latest.thread_id or latest.message_id

    def add(
        *,
        action_type: str,
        label: str,
        reason: str,
        confidence: float,
        supporting_message: RecruiterMessage | None,
        due_at: str | None = None,
    ) -> None:
        if action_type in seen_action_types:
            return
        seen_action_types.add(action_type)
        supporting = supporting_message or latest
        suggestions.append(
            ConversationSuggestion(
                suggestion_id=_suggestion_id(scope_id, action_type, supporting.message_id),
                action_type=action_type,
                label=label,
                reason=reason,
                confidence=confidence,
                supporting_message_id=supporting.message_id,
                supporting_message_subject=supporting.subject,
                related_application_id=application_id,
                due_at=due_at,
                waiting_on=state.waiting_on,
            )
        )

    if state.state == "conversation_closed":
        add(
            action_type="review_conversation_outcome",
            label="Review conversation outcome",
            reason="The conversation is closed, so the remaining work is documenting the outcome on the application.",
            confidence=0.62,
            supporting_message=latest,
        )
        return suggestions

    if state.state == "offer_pending":
        due_at = _suggestion_due_at(latest.received_at, state.sla.overdue_threshold_hours)
        add(
            action_type="review_offer",
            label="Review offer details",
            reason="An offer message arrived and still needs a candidate decision or response.",
            confidence=0.96,
            supporting_message=latest,
            due_at=due_at,
        )
        add(
            action_type="prepare_offer_questions",
            label="Prepare offer questions",
            reason="Use the recruiter thread to confirm compensation, timing, and other offer details before responding.",
            confidence=0.78,
            supporting_message=latest,
            due_at=due_at,
        )
        return suggestions

    if state.state == "assessment_pending":
        due_at = _suggestion_due_at(latest.received_at, state.sla.overdue_threshold_hours)
        add(
            action_type="complete_assessment",
            label="Complete assessment",
            reason="The latest recruiter message requests an assessment and the candidate still owes the next action.",
            confidence=0.97,
            supporting_message=latest,
            due_at=due_at,
        )
        add(
            action_type="confirm_assessment_deadline",
            label="Confirm assessment deadline",
            reason="Record or verify the assessment timing while the request is still active.",
            confidence=0.75,
            supporting_message=latest,
            due_at=due_at,
        )
        return suggestions

    scheduled_message = _interview_scheduled_signal(messages)
    if state.state == "interview_scheduled":
        add(
            action_type="prepare_interview",
            label="Prepare interview",
            reason="The conversation suggests the interview time is already scheduled, so preparation is the highest-value next step.",
            confidence=0.91,
            supporting_message=scheduled_message or latest,
        )
        add(
            action_type="confirm_interview_time",
            label="Confirm interview time",
            reason="Make sure the final interview time, date, and time zone are captured on the application.",
            confidence=0.77,
            supporting_message=scheduled_message or latest,
        )
        return suggestions

    if state.waiting_on == "candidate":
        due_at = _suggestion_due_at(
            last_recruiter.received_at if last_recruiter is not None else latest.received_at,
            state.sla.overdue_threshold_hours,
        )
        if latest.message_type == "interview_invitation":
            add(
                action_type="reply_to_recruiter",
                label="Reply to schedule the interview",
                reason="The recruiter is waiting for a scheduling response before the interview can progress.",
                confidence=0.95,
                supporting_message=last_recruiter or latest,
                due_at=due_at,
            )
            add(
                action_type="prepare_interview",
                label="Prepare interview",
                reason="Interview-related recruiter communication is already active, so preparation can start now.",
                confidence=0.8,
                supporting_message=last_recruiter or latest,
            )
            return suggestions
        if latest.message_type == "scheduling":
            add(
                action_type="confirm_interview_time",
                label="Confirm interview time",
                reason="The recruiter is waiting for scheduling details before the interview can progress.",
                confidence=0.93,
                supporting_message=last_recruiter or latest,
                due_at=due_at,
            )
            add(
                action_type="prepare_interview",
                label="Prepare interview",
                reason="Interview-related conversation is already active, so preparation can start now.",
                confidence=0.8,
                supporting_message=last_recruiter or latest,
            )
            return suggestions
        if latest.message_type == "follow_up":
            add(
                action_type="reply_to_recruiter",
                label="Reply to recruiter",
                reason="The recruiter followed up and still needs a direct response.",
                confidence=0.93,
                supporting_message=last_recruiter or latest,
                due_at=due_at,
            )
            return suggestions
        add(
            action_type="reply_to_recruiter",
            label="Reply to recruiter",
            reason="The recruiter sent the latest message, so the candidate still owes the next response.",
            confidence=0.9,
            supporting_message=last_recruiter or latest,
            due_at=due_at,
        )
        return suggestions

    if state.waiting_on == "recruiter":
        follow_up_due_at = _suggestion_due_at(
            last_candidate.received_at if last_candidate is not None else latest.received_at,
            _RECRUITER_FOLLOW_UP_DAYS * 24,
        )
        if health.status in {"needs_follow_up", "stale", "blocked"}:
            add(
                action_type="follow_up_with_recruiter",
                label="Follow up with recruiter",
                reason=health.reason,
                confidence=0.87,
                supporting_message=last_candidate or latest,
                due_at=follow_up_due_at,
            )
        else:
            add(
                action_type="wait_for_recruiter_response",
                label="Wait for recruiter response",
                reason="The candidate replied last, so the recruiter currently owns the next move.",
                confidence=0.74,
                supporting_message=last_candidate or latest,
                due_at=follow_up_due_at,
            )
        if any(message.message_type in {"interview_invitation", "scheduling"} for message in messages):
            add(
                action_type="prepare_interview",
                label="Prepare interview",
                reason="Interview-related conversation is active, so preparation can continue while waiting for recruiter confirmation.",
                confidence=0.79,
                supporting_message=last_candidate or latest,
            )
        return suggestions

    add(
        action_type="review_communication",
        label="Review communication",
        reason="The conversation history does not yet produce a stronger workflow recommendation.",
        confidence=0.55,
        supporting_message=latest,
    )
    return suggestions


def _build_summary(
    messages: list[RecruiterMessage],
    *,
    application: ApplicationRecord | None = None,
    reason: str = "",
) -> CommunicationSummary:
    latest = _latest_message(messages)
    if latest is None:
        state = _build_conversation_state(messages, application=application)
        health = _build_communication_health(state, application=application)
        return CommunicationSummary(
            application_id=application.application_id if application is not None else None,
            recruiter_name=application.structured_metadata.recruiter_name if application is not None else "",
            recruiter_email=application.structured_metadata.recruiter_email if application is not None else "",
            waiting_on=state.waiting_on,
            conversation_state=state,
            health=health,
            sla=state.sla,
        )

    state = _build_conversation_state(messages, application=application)
    health = _build_communication_health(state, application=application)
    suggestions = _build_suggestions(
        messages,
        state=state,
        health=health,
        application_id=application.application_id if application is not None else latest.application_id,
    )
    return CommunicationSummary(
        application_id=application.application_id if application is not None else latest.application_id,
        last_message_id=latest.message_id,
        last_thread_id=latest.thread_id,
        last_message_type=latest.message_type,
        last_message_subject=latest.subject,
        last_contact_date=latest.received_at,
        pending_action=suggestions[0].label if suggestions else "",
        conversation_status=state.state,
        response_overdue=state.sla.overdue,
        suggested_actions=[item.label for item in suggestions],
        recruiter_name=latest.recruiter.display_name,
        recruiter_email=latest.recruiter.email,
        confidence=latest.match_confidence or latest.confidence,
        reason=reason or state.reason or latest.classification_reason,
        waiting_on=state.waiting_on,
        conversation_state=state,
        health=health,
        sla=state.sla,
        suggestions=suggestions,
    )


def _build_event(message: RecruiterMessage) -> CommunicationEvent:
    if _is_candidate_authored(message):
        title = "Candidate replied"
        if message.message_type == "scheduling":
            title = "Candidate shared availability"
        elif message.message_type == "assessment":
            title = "Candidate replied about the assessment"
        elif message.message_type == "offer":
            title = "Candidate replied about the offer"
        return CommunicationEvent(
            event_id=_event_id(message.message_id, "CandidateReplied"),
            user_id=message.user_id,
            application_id=message.application_id,
            thread_id=message.thread_id,
            message_id=message.message_id,
            event_type="CandidateReplied",
            title=title,
            detail=_timeline_detail(message.subject, message.recruiter.display_name, message.company),
            occurred_at=message.received_at,
            source=message.source,
            metadata={
                "message_type": message.message_type,
                "match_confidence": message.match_confidence,
                "match_reason": message.match_reason,
                "suggested_actions": list(message.suggested_actions),
            },
        )
    guidance = _message_guidance(message.message_type)
    event_type = str(guidance.get("event_type", "RecruiterMessageLogged"))
    title = str(guidance.get("title", "Recruiter message logged"))
    return CommunicationEvent(
        event_id=_event_id(message.message_id, event_type),
        user_id=message.user_id,
        application_id=message.application_id,
        thread_id=message.thread_id,
        message_id=message.message_id,
        event_type=event_type,
        title=title,
        detail=_timeline_detail(message.subject, message.recruiter.display_name, message.company),
        occurred_at=message.received_at,
        source=message.source,
        metadata={
            "message_type": message.message_type,
            "match_confidence": message.match_confidence,
            "match_reason": message.match_reason,
            "suggested_actions": list(message.suggested_actions),
        },
    )


def _build_thread(contact: RecruiterContact, messages: list[RecruiterMessage]) -> RecruiterThread:
    ordered = _sort_messages(messages)
    latest = ordered[-1]
    summary = _build_summary(ordered, reason=latest.match_reason or latest.classification_reason)
    return RecruiterThread(
        thread_id=latest.thread_id,
        user_id=latest.user_id,
        application_id=latest.application_id,
        recruiter=contact,
        subject=_normalize_subject(latest.subject),
        company=latest.company,
        job_title=latest.job_title,
        last_message_id=latest.message_id,
        last_message_at=latest.received_at,
        message_count=len(ordered),
        source=latest.source,
        confidence=latest.match_confidence or latest.confidence,
        conversation_status=summary.conversation_state.state,
        pending_action=summary.pending_action,
        response_overdue=summary.response_overdue,
        created_at=ordered[0].created_at,
        updated_at=latest.updated_at or latest.received_at,
        metadata={
            "waiting_on": summary.waiting_on,
            "suggested_actions": summary.suggested_actions,
            "reason": summary.reason,
            "conversation_state": summary.conversation_state.to_dict(),
            "health": summary.health.to_dict(),
            "sla": summary.sla.to_dict(),
        },
    )


def _row_to_contact(row) -> RecruiterContact:
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return RecruiterContact(
        contact_id=str(row["contact_id"]),
        user_id=str(row["user_id"]),
        display_name=str(row["display_name"]),
        email=str(row["email"]),
        company=str(row["company"] or ""),
        title=str(row["title"] or ""),
        metadata=_json_object(row["metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


def _row_to_contact_from_join(row, *, prefix: str = "recruiter_") -> RecruiterContact:
    created_at = row[f"{prefix}created_at"]
    updated_at = row[f"{prefix}updated_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return RecruiterContact(
        contact_id=str(row[f"{prefix}contact_id"]),
        user_id=str(row[f"{prefix}user_id"]),
        display_name=str(row[f"{prefix}display_name"]),
        email=str(row[f"{prefix}email"]),
        company=str(row[f"{prefix}company"] or ""),
        title=str(row[f"{prefix}title"] or ""),
        metadata=_json_object(row[f"{prefix}metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


def _row_to_message(row) -> RecruiterMessage:
    received_at = row["received_at"]
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if received_at is not None and received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return RecruiterMessage(
        message_id=str(row["message_id"]),
        thread_id=str(row["thread_id"]),
        user_id=str(row["user_id"]),
        application_id=str(row["application_id"]) if row["application_id"] is not None else None,
        recruiter=_row_to_contact_from_join(row),
        sender=str(row["sender"]),
        recipients=[str(item) for item in _json_list(row["recipients"])],
        subject=str(row["subject"] or ""),
        body_reference=str(row["body_reference"] or ""),
        body_preview=str(row["body_preview"] or ""),
        received_at=received_at.isoformat() if received_at is not None else None,
        message_type=str(row["message_type"] or "unknown"),
        confidence=float(row["confidence"] or 0.0),
        source=str(row["source"] or "manual_import"),
        timeline_id=str(row["timeline_id"] or ""),
        company=str(row["company"] or ""),
        job_title=str(row["job_title"] or ""),
        matched=bool(row["application_id"]),
        match_confidence=float(row["match_confidence"] or 0.0),
        match_reason=str(row["match_reason"] or ""),
        classification_reason=str(row["classification_reason"] or ""),
        suggested_actions=[str(item) for item in _json_list(row["suggested_actions"])],
        metadata=_json_object(row["metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


def _row_to_thread(row) -> RecruiterThread:
    last_message_at = row["last_message_at"]
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if last_message_at is not None and last_message_at.tzinfo is None:
        last_message_at = last_message_at.replace(tzinfo=timezone.utc)
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return RecruiterThread(
        thread_id=str(row["thread_id"]),
        user_id=str(row["user_id"]),
        application_id=str(row["application_id"]) if row["application_id"] is not None else None,
        recruiter=_row_to_contact_from_join(row),
        subject=str(row["subject"] or ""),
        company=str(row["company"] or ""),
        job_title=str(row["job_title"] or ""),
        last_message_id=str(row["last_message_id"] or ""),
        last_message_at=last_message_at.isoformat() if last_message_at is not None else None,
        message_count=int(row["message_count"] or 0),
        source=str(row["source"] or "manual_import"),
        confidence=float(row["confidence"] or 0.0),
        conversation_status=str(row["conversation_status"] or "idle"),
        pending_action=str(row["pending_action"] or ""),
        response_overdue=bool(row["response_overdue"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
        metadata=_json_object(row["metadata"]),
    )


def _row_to_event(row) -> CommunicationEvent:
    occurred_at = row["occurred_at"]
    created_at = row["created_at"]
    if occurred_at is not None and occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return CommunicationEvent(
        event_id=str(row["event_id"]),
        user_id=str(row["user_id"]),
        application_id=str(row["application_id"]) if row["application_id"] is not None else None,
        thread_id=str(row["thread_id"]),
        message_id=str(row["message_id"]),
        event_type=str(row["event_type"]),
        title=str(row["title"]),
        detail=str(row["detail"] or ""),
        occurred_at=occurred_at.isoformat() if occurred_at is not None else None,
        source=str(row["source"] or "manual_import"),
        metadata=_json_object(row["metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
    )


def _row_to_draft(row) -> CommunicationDraft:
    generated_at = row["generated_at"]
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if generated_at is not None and generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    from .models import CommunicationEvidence

    evidence = [
        CommunicationEvidence(**item)
        for item in _json_list(row["evidence"])
        if isinstance(item, dict)
    ]
    return CommunicationDraft(
        draft_id=str(row["draft_id"]),
        draft_group_id=str(row["draft_group_id"]),
        version_number=int(row["version_number"] or 1),
        user_id=str(row["user_id"]),
        thread_id=str(row["thread_id"]),
        draft_kind=str(row["draft_kind"] or "reply"),
        tone=str(row["tone"] or "professional"),
        status=str(row["status"] or "generated"),
        intended_recipient=str(row["intended_recipient"] or ""),
        intended_recipient_email=str(row["intended_recipient_email"] or ""),
        communication_objective=str(row["communication_objective"] or ""),
        subject=str(row["subject"] or ""),
        body=str(row["body"] or ""),
        confidence=float(row["confidence"] or 0.0),
        explanation=str(row["explanation"] or ""),
        strategy_version=str(row["strategy_version"] or ""),
        model_key=str(row["model_key"] or ""),
        application_id=str(row["application_id"]) if row["application_id"] is not None else None,
        source_message_id=str(row["source_message_id"] or ""),
        parent_draft_id=str(row["parent_draft_id"] or ""),
        evidence=evidence,
        assumptions=[str(item) for item in _json_list(row["assumptions"])],
        user_edited=bool(row["user_edited"]),
        generated_at=generated_at.isoformat() if generated_at is not None else None,
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


class RecruiterStore(Protocol):
    async def save_contact(self, contact: RecruiterContact) -> RecruiterContact:
        ...

    async def save_thread(self, thread: RecruiterThread) -> RecruiterThread:
        ...

    async def save_message(self, message: RecruiterMessage) -> RecruiterMessage:
        ...

    async def save_event(self, event: CommunicationEvent) -> CommunicationEvent:
        ...

    async def get_contact(self, contact_id: str, *, user_id: str | None = None) -> RecruiterContact | None:
        ...

    async def get_thread(self, thread_id: str, *, user_id: str | None = None) -> RecruiterThread | None:
        ...

    async def list_contacts_for_user(self, user_id: str) -> list[RecruiterContact]:
        ...

    async def get_message(self, message_id: str, *, user_id: str | None = None) -> RecruiterMessage | None:
        ...

    async def list_messages_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        message_type: str | None = None,
        thread_id: str | None = None,
    ) -> list[RecruiterMessage]:
        ...

    async def list_threads_for_user(self, user_id: str, *, application_id: str | None = None) -> list[RecruiterThread]:
        ...

    async def list_events_for_application(self, user_id: str, application_id: str) -> list[CommunicationEvent]:
        ...

    async def save_draft(self, draft: CommunicationDraft) -> CommunicationDraft:
        ...

    async def get_draft(self, draft_id: str, *, user_id: str | None = None) -> CommunicationDraft | None:
        ...

    async def list_drafts_for_user(
        self,
        user_id: str,
        *,
        thread_id: str | None = None,
        application_id: str | None = None,
    ) -> list[CommunicationDraft]:
        ...


@dataclass
class InMemoryRecruiterStore:
    contacts: dict[str, RecruiterContact] | None = None
    threads: dict[str, RecruiterThread] | None = None
    messages: dict[str, RecruiterMessage] | None = None
    events: dict[str, CommunicationEvent] | None = None
    drafts: dict[str, CommunicationDraft] | None = None

    def __post_init__(self) -> None:
        self.contacts = {} if self.contacts is None else self.contacts
        self.threads = {} if self.threads is None else self.threads
        self.messages = {} if self.messages is None else self.messages
        self.events = {} if self.events is None else self.events
        self.drafts = {} if self.drafts is None else self.drafts

    async def save_contact(self, contact: RecruiterContact) -> RecruiterContact:
        assert self.contacts is not None
        self.contacts[contact.contact_id] = contact
        return contact

    async def save_thread(self, thread: RecruiterThread) -> RecruiterThread:
        assert self.threads is not None
        self.threads[thread.thread_id] = thread
        return thread

    async def save_message(self, message: RecruiterMessage) -> RecruiterMessage:
        assert self.messages is not None
        self.messages[message.message_id] = message
        return message

    async def save_event(self, event: CommunicationEvent) -> CommunicationEvent:
        assert self.events is not None
        self.events[event.event_id] = event
        return event

    async def get_contact(self, contact_id: str, *, user_id: str | None = None) -> RecruiterContact | None:
        assert self.contacts is not None
        item = self.contacts.get(contact_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return item

    async def get_thread(self, thread_id: str, *, user_id: str | None = None) -> RecruiterThread | None:
        assert self.threads is not None
        item = self.threads.get(thread_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return item

    async def list_contacts_for_user(self, user_id: str) -> list[RecruiterContact]:
        assert self.contacts is not None
        items = [item for item in self.contacts.values() if item.user_id == user_id]
        return sorted(
            items,
            key=lambda item: (_parse_datetime(item.updated_at) or datetime.min.replace(tzinfo=timezone.utc), item.contact_id),
            reverse=True,
        )

    async def get_message(self, message_id: str, *, user_id: str | None = None) -> RecruiterMessage | None:
        assert self.messages is not None
        item = self.messages.get(message_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return item

    async def list_messages_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        message_type: str | None = None,
        thread_id: str | None = None,
    ) -> list[RecruiterMessage]:
        assert self.messages is not None
        items = [item for item in self.messages.values() if item.user_id == user_id]
        if application_id is not None:
            items = [item for item in items if item.application_id == application_id]
        if message_type is not None:
            items = [item for item in items if item.message_type == message_type]
        if thread_id is not None:
            items = [item for item in items if item.thread_id == thread_id]
        return sorted(
            items,
            key=lambda item: (_parse_datetime(item.received_at) or datetime.min.replace(tzinfo=timezone.utc), item.message_id),
            reverse=True,
        )

    async def list_threads_for_user(self, user_id: str, *, application_id: str | None = None) -> list[RecruiterThread]:
        assert self.threads is not None
        items = [item for item in self.threads.values() if item.user_id == user_id]
        if application_id is not None:
            items = [item for item in items if item.application_id == application_id]
        return sorted(
            items,
            key=lambda item: (_parse_datetime(item.last_message_at) or datetime.min.replace(tzinfo=timezone.utc), item.thread_id),
            reverse=True,
        )

    async def list_events_for_application(self, user_id: str, application_id: str) -> list[CommunicationEvent]:
        assert self.events is not None
        items = [event for event in self.events.values() if event.user_id == user_id and event.application_id == application_id]
        return sorted(
            items,
            key=lambda item: (_parse_datetime(item.occurred_at) or datetime.min.replace(tzinfo=timezone.utc), item.event_id),
            reverse=True,
        )

    async def save_draft(self, draft: CommunicationDraft) -> CommunicationDraft:
        assert self.drafts is not None
        self.drafts[draft.draft_id] = draft
        return draft

    async def get_draft(self, draft_id: str, *, user_id: str | None = None) -> CommunicationDraft | None:
        assert self.drafts is not None
        item = self.drafts.get(draft_id)
        if item is None:
            return None
        if user_id is not None and item.user_id != user_id:
            return None
        return item

    async def list_drafts_for_user(
        self,
        user_id: str,
        *,
        thread_id: str | None = None,
        application_id: str | None = None,
    ) -> list[CommunicationDraft]:
        assert self.drafts is not None
        items = [item for item in self.drafts.values() if item.user_id == user_id]
        if thread_id is not None:
            items = [item for item in items if item.thread_id == thread_id]
        if application_id is not None:
            items = [item for item in items if item.application_id == application_id]
        return sorted(
            items,
            key=lambda item: (_parse_datetime(item.updated_at or item.created_at) or datetime.min.replace(tzinfo=timezone.utc), item.version_number, item.draft_id),
            reverse=True,
        )


class PostgresRecruiterStore:
    async def save_contact(self, contact: RecruiterContact) -> RecruiterContact:
        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO recruiter_contacts (
                    contact_id,
                    user_id,
                    display_name,
                    email,
                    company,
                    title,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, COALESCE($8::timestamptz, NOW()), COALESCE($9::timestamptz, NOW()))
                ON CONFLICT (user_id, email) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    company = EXCLUDED.company,
                    title = EXCLUDED.title,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                """,
                contact.contact_id,
                contact.user_id,
                contact.display_name,
                contact.email,
                contact.company,
                contact.title,
                json.dumps(contact.metadata),
                contact.created_at,
                contact.updated_at,
            )
        return contact

    async def save_thread(self, thread: RecruiterThread) -> RecruiterThread:
        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO recruiter_threads (
                    thread_id,
                    user_id,
                    application_id,
                    contact_id,
                    subject,
                    company,
                    job_title,
                    last_message_id,
                    last_message_at,
                    message_count,
                    source,
                    confidence,
                    conversation_status,
                    pending_action,
                    response_overdue,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9::timestamptz, $10, $11, $12, $13, $14, $15, $16::jsonb,
                    COALESCE($17::timestamptz, NOW()),
                    COALESCE($18::timestamptz, NOW())
                )
                ON CONFLICT (thread_id) DO UPDATE SET
                    application_id = EXCLUDED.application_id,
                    contact_id = EXCLUDED.contact_id,
                    subject = EXCLUDED.subject,
                    company = EXCLUDED.company,
                    job_title = EXCLUDED.job_title,
                    last_message_id = EXCLUDED.last_message_id,
                    last_message_at = EXCLUDED.last_message_at,
                    message_count = EXCLUDED.message_count,
                    source = EXCLUDED.source,
                    confidence = EXCLUDED.confidence,
                    conversation_status = EXCLUDED.conversation_status,
                    pending_action = EXCLUDED.pending_action,
                    response_overdue = EXCLUDED.response_overdue,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                """,
                thread.thread_id,
                thread.user_id,
                thread.application_id,
                thread.recruiter.contact_id,
                thread.subject,
                thread.company,
                thread.job_title,
                thread.last_message_id,
                thread.last_message_at,
                thread.message_count,
                thread.source,
                thread.confidence,
                thread.conversation_status,
                thread.pending_action,
                thread.response_overdue,
                json.dumps(thread.metadata),
                thread.created_at,
                thread.updated_at,
            )
        return thread

    async def save_message(self, message: RecruiterMessage) -> RecruiterMessage:
        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO recruiter_messages (
                    message_id,
                    thread_id,
                    user_id,
                    application_id,
                    contact_id,
                    sender,
                    recipients,
                    subject,
                    body_reference,
                    body_preview,
                    received_at,
                    message_type,
                    confidence,
                    source,
                    timeline_id,
                    company,
                    job_title,
                    classification_reason,
                    match_confidence,
                    match_reason,
                    suggested_actions,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11::timestamptz, $12, $13, $14, $15, $16, $17,
                    $18, $19, $20, $21::jsonb, $22::jsonb, COALESCE($23::timestamptz, NOW()), COALESCE($24::timestamptz, NOW())
                )
                ON CONFLICT (message_id) DO UPDATE SET
                    thread_id = EXCLUDED.thread_id,
                    application_id = EXCLUDED.application_id,
                    contact_id = EXCLUDED.contact_id,
                    sender = EXCLUDED.sender,
                    recipients = EXCLUDED.recipients,
                    subject = EXCLUDED.subject,
                    body_reference = EXCLUDED.body_reference,
                    body_preview = EXCLUDED.body_preview,
                    received_at = EXCLUDED.received_at,
                    message_type = EXCLUDED.message_type,
                    confidence = EXCLUDED.confidence,
                    source = EXCLUDED.source,
                    timeline_id = EXCLUDED.timeline_id,
                    company = EXCLUDED.company,
                    job_title = EXCLUDED.job_title,
                    classification_reason = EXCLUDED.classification_reason,
                    match_confidence = EXCLUDED.match_confidence,
                    match_reason = EXCLUDED.match_reason,
                    suggested_actions = EXCLUDED.suggested_actions,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                """,
                message.message_id,
                message.thread_id,
                message.user_id,
                message.application_id,
                message.recruiter.contact_id,
                message.sender,
                json.dumps(message.recipients),
                message.subject,
                message.body_reference,
                message.body_preview,
                message.received_at,
                message.message_type,
                message.confidence,
                message.source,
                message.timeline_id,
                message.company,
                message.job_title,
                message.classification_reason,
                message.match_confidence,
                message.match_reason,
                json.dumps(message.suggested_actions),
                json.dumps(message.metadata),
                message.created_at,
                message.updated_at,
            )
        return message

    async def save_event(self, event: CommunicationEvent) -> CommunicationEvent:
        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO communication_events (
                    event_id,
                    user_id,
                    application_id,
                    thread_id,
                    message_id,
                    event_type,
                    title,
                    detail,
                    occurred_at,
                    source,
                    metadata,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::timestamptz, $10, $11::jsonb, COALESCE($12::timestamptz, NOW()))
                ON CONFLICT (event_id) DO UPDATE SET
                    application_id = EXCLUDED.application_id,
                    thread_id = EXCLUDED.thread_id,
                    message_id = EXCLUDED.message_id,
                    event_type = EXCLUDED.event_type,
                    title = EXCLUDED.title,
                    detail = EXCLUDED.detail,
                    occurred_at = EXCLUDED.occurred_at,
                    source = EXCLUDED.source,
                    metadata = EXCLUDED.metadata
                """,
                event.event_id,
                event.user_id,
                event.application_id,
                event.thread_id,
                event.message_id,
                event.event_type,
                event.title,
                event.detail,
                event.occurred_at,
                event.source,
                json.dumps(event.metadata),
                event.created_at,
            )
        return event

    async def get_contact(self, contact_id: str, *, user_id: str | None = None) -> RecruiterContact | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM recruiter_contacts
                WHERE contact_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                contact_id,
                user_id,
            )
        return _row_to_contact(row) if row is not None else None

    async def get_thread(self, thread_id: str, *, user_id: str | None = None) -> RecruiterThread | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    t.*,
                    c.contact_id AS recruiter_contact_id,
                    c.user_id AS recruiter_user_id,
                    c.display_name AS recruiter_display_name,
                    c.email AS recruiter_email,
                    c.company AS recruiter_company,
                    c.title AS recruiter_title,
                    c.metadata AS recruiter_metadata,
                    c.created_at AS recruiter_created_at,
                    c.updated_at AS recruiter_updated_at
                FROM recruiter_threads t
                JOIN recruiter_contacts c
                  ON c.contact_id = t.contact_id
                WHERE t.thread_id = $1
                  AND ($2::text IS NULL OR t.user_id = $2)
                """,
                thread_id,
                user_id,
            )
        return _row_to_thread(row) if row is not None else None

    async def list_contacts_for_user(self, user_id: str) -> list[RecruiterContact]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM recruiter_contacts
                WHERE user_id = $1
                ORDER BY updated_at DESC, created_at DESC
                """,
                user_id,
            )
        return [_row_to_contact(row) for row in rows]

    async def get_message(self, message_id: str, *, user_id: str | None = None) -> RecruiterMessage | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    m.*,
                    c.contact_id AS recruiter_contact_id,
                    c.user_id AS recruiter_user_id,
                    c.display_name AS recruiter_display_name,
                    c.email AS recruiter_email,
                    c.company AS recruiter_company,
                    c.title AS recruiter_title,
                    c.metadata AS recruiter_metadata,
                    c.created_at AS recruiter_created_at,
                    c.updated_at AS recruiter_updated_at
                FROM recruiter_messages m
                JOIN recruiter_contacts c
                  ON c.contact_id = m.contact_id
                WHERE m.message_id = $1
                  AND ($2::text IS NULL OR m.user_id = $2)
                """,
                message_id,
                user_id,
            )
        return _row_to_message(row) if row is not None else None

    async def list_messages_for_user(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        message_type: str | None = None,
        thread_id: str | None = None,
    ) -> list[RecruiterMessage]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    m.*,
                    c.contact_id AS recruiter_contact_id,
                    c.user_id AS recruiter_user_id,
                    c.display_name AS recruiter_display_name,
                    c.email AS recruiter_email,
                    c.company AS recruiter_company,
                    c.title AS recruiter_title,
                    c.metadata AS recruiter_metadata,
                    c.created_at AS recruiter_created_at,
                    c.updated_at AS recruiter_updated_at
                FROM recruiter_messages m
                JOIN recruiter_contacts c
                  ON c.contact_id = m.contact_id
                WHERE m.user_id = $1
                  AND ($2::text IS NULL OR m.application_id = $2)
                  AND ($3::text IS NULL OR m.message_type = $3)
                  AND ($4::text IS NULL OR m.thread_id = $4)
                ORDER BY m.received_at DESC NULLS LAST, m.created_at DESC
                """,
                user_id,
                application_id,
                message_type,
                thread_id,
            )
        return [_row_to_message(row) for row in rows]

    async def list_threads_for_user(self, user_id: str, *, application_id: str | None = None) -> list[RecruiterThread]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    t.*,
                    c.contact_id AS recruiter_contact_id,
                    c.user_id AS recruiter_user_id,
                    c.display_name AS recruiter_display_name,
                    c.email AS recruiter_email,
                    c.company AS recruiter_company,
                    c.title AS recruiter_title,
                    c.metadata AS recruiter_metadata,
                    c.created_at AS recruiter_created_at,
                    c.updated_at AS recruiter_updated_at
                FROM recruiter_threads t
                JOIN recruiter_contacts c
                  ON c.contact_id = t.contact_id
                WHERE t.user_id = $1
                  AND ($2::text IS NULL OR t.application_id = $2)
                ORDER BY t.last_message_at DESC NULLS LAST, t.updated_at DESC
                """,
                user_id,
                application_id,
            )
        return [_row_to_thread(row) for row in rows]

    async def list_events_for_application(self, user_id: str, application_id: str) -> list[CommunicationEvent]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM communication_events
                WHERE user_id = $1
                  AND application_id = $2
                ORDER BY occurred_at DESC NULLS LAST, created_at DESC
                """,
                user_id,
                application_id,
            )
        return [_row_to_event(row) for row in rows]

    async def save_draft(self, draft: CommunicationDraft) -> CommunicationDraft:
        async with connection() as conn:
            await conn.execute(
                """
                INSERT INTO recruiter_message_drafts (
                    draft_id,
                    draft_group_id,
                    version_number,
                    user_id,
                    application_id,
                    thread_id,
                    source_message_id,
                    parent_draft_id,
                    draft_kind,
                    tone,
                    status,
                    intended_recipient,
                    intended_recipient_email,
                    communication_objective,
                    subject,
                    body,
                    evidence,
                    assumptions,
                    confidence,
                    explanation,
                    strategy_version,
                    model_key,
                    user_edited,
                    generated_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17::jsonb, $18::jsonb,
                    $19, $20, $21, $22, $23, COALESCE($24::timestamptz, NOW()), COALESCE($25::timestamptz, NOW()), COALESCE($26::timestamptz, NOW())
                )
                ON CONFLICT (draft_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    intended_recipient = EXCLUDED.intended_recipient,
                    intended_recipient_email = EXCLUDED.intended_recipient_email,
                    communication_objective = EXCLUDED.communication_objective,
                    subject = EXCLUDED.subject,
                    body = EXCLUDED.body,
                    evidence = EXCLUDED.evidence,
                    assumptions = EXCLUDED.assumptions,
                    confidence = EXCLUDED.confidence,
                    explanation = EXCLUDED.explanation,
                    strategy_version = EXCLUDED.strategy_version,
                    model_key = EXCLUDED.model_key,
                    user_edited = EXCLUDED.user_edited,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                """,
                draft.draft_id,
                draft.draft_group_id,
                draft.version_number,
                draft.user_id,
                draft.application_id,
                draft.thread_id,
                draft.source_message_id,
                draft.parent_draft_id or None,
                draft.draft_kind,
                draft.tone,
                draft.status,
                draft.intended_recipient,
                draft.intended_recipient_email,
                draft.communication_objective,
                draft.subject,
                draft.body,
                json.dumps([item.to_dict() for item in draft.evidence]),
                json.dumps(draft.assumptions),
                draft.confidence,
                draft.explanation,
                draft.strategy_version,
                draft.model_key,
                draft.user_edited,
                draft.generated_at,
                draft.created_at,
                draft.updated_at,
            )
        return draft

    async def get_draft(self, draft_id: str, *, user_id: str | None = None) -> CommunicationDraft | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM recruiter_message_drafts
                WHERE draft_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                draft_id,
                user_id,
            )
        return _row_to_draft(row) if row is not None else None

    async def list_drafts_for_user(
        self,
        user_id: str,
        *,
        thread_id: str | None = None,
        application_id: str | None = None,
    ) -> list[CommunicationDraft]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM recruiter_message_drafts
                WHERE user_id = $1
                  AND ($2::text IS NULL OR thread_id = $2)
                  AND ($3::text IS NULL OR application_id = $3)
                ORDER BY updated_at DESC NULLS LAST, version_number DESC, created_at DESC
                """,
                user_id,
                thread_id,
                application_id,
            )
        return [_row_to_draft(row) for row in rows]


def build_recruiter_store(settings: AppSettings | None = None) -> RecruiterStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryRecruiterStore()
    return PostgresRecruiterStore()


def _match_application(
    applications: list[ApplicationRecord],
    item: RecruiterMessageImportRecord,
    *,
    classification_reason: str,
) -> tuple[ApplicationRecord | None, float, str]:
    if item.application_id.strip():
        explicit = next((application for application in applications if application.application_id == item.application_id.strip()), None)
        if explicit is None:
            raise ValueError("Unknown application override for imported recruiter message.")
        return explicit, 1.0, "message import explicitly provided the application_id"

    combined_text = _normalize_text(" ".join([item.subject, item.body_text, item.company, item.job_title]))
    recruiter_email = item.recruiter_email.strip().casefold()
    recruiter_name = item.recruiter_name.strip().casefold()
    scored: list[tuple[float, ApplicationRecord, str]] = []

    for application in applications:
        score = 0.0
        reasons: list[str] = []
        if recruiter_email and application.structured_metadata.recruiter_email.strip().casefold() == recruiter_email:
            score += 0.75
            reasons.append("recruiter email matched structured recruiter email")
        if recruiter_name and application.structured_metadata.recruiter_name.strip().casefold() == recruiter_name:
            score += 0.2
            reasons.append("recruiter name matched structured recruiter name")
        company_score = 0.0
        if item.company.strip() and _normalize_text(item.company) == _normalize_text(application.company):
            company_score = 0.35
            reasons.append("imported company matched the application company")
        elif _contains_phrase(combined_text, application.company):
            company_score = 0.3
            reasons.append("message content referenced the application company")
        score += company_score

        title_score = 0.0
        if item.job_title.strip() and _normalize_text(item.job_title) == _normalize_text(application.title):
            title_score = 0.3
            reasons.append("imported job title matched the application title")
        else:
            title_score = _token_overlap_score(item.job_title or item.subject or item.body_text, application.title)
            if title_score > 0:
                reasons.append("message content overlapped the application title")
        score += title_score

        if application.status not in {"accepted", "rejected", "withdrawn"}:
            score += 0.05
            reasons.append("application is still active")
        if score > 0:
            scored.append((min(score, 0.99), application, "; ".join(reasons)))

    if not scored:
        return None, 0.0, f"no application signals matched; {classification_reason}"

    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top_application, top_reason = scored[0]
    if top_score < _MATCH_ATTACH_THRESHOLD:
        return None, top_score, f"best match was below the attachment threshold: {top_reason}"
    if len(scored) > 1 and top_score < 0.95 and top_score - scored[1][0] < _MATCH_AMBIGUITY_GAP:
        return None, top_score, "multiple applications matched with similar confidence; manual review required"
    return top_application, top_score, top_reason


def _build_contact_profile(
    contact: RecruiterContact,
    *,
    messages: list[RecruiterMessage],
    applications_by_id: dict[str, ApplicationRecord],
) -> RecruiterContactProfile:
    ordered = _sort_messages(messages)
    latest = ordered[-1] if ordered else None
    related_application = applications_by_id.get(latest.application_id) if latest is not None and latest.application_id else None
    summary = _build_summary(ordered, application=related_application, reason="contact profile aggregated from recruiter history")
    application_links_by_id: dict[str, RecruiterContactApplicationLink] = {}
    for message in ordered:
        if not message.application_id:
            continue
        application = applications_by_id.get(message.application_id)
        previous = application_links_by_id.get(message.application_id)
        last_contact_at = message.received_at
        if previous is not None and previous.last_contact_at is not None:
            previous_at = _parse_datetime(previous.last_contact_at)
            current_at = _parse_datetime(last_contact_at)
            if previous_at is not None and current_at is not None and previous_at >= current_at:
                last_contact_at = previous.last_contact_at
        application_links_by_id[message.application_id] = RecruiterContactApplicationLink(
            application_id=message.application_id,
            company=application.company if application is not None else message.company,
            title=application.title if application is not None else message.job_title,
            status=application.status if application is not None else "",
            last_contact_at=last_contact_at,
        )
    return RecruiterContactProfile(
        contact=contact,
        applications_connected=sorted(
            application_links_by_id.values(),
            key=lambda item: (_parse_datetime(item.last_contact_at) or datetime.min.replace(tzinfo=timezone.utc), item.application_id),
            reverse=True,
        ),
        last_contact_at=latest.received_at if latest is not None else None,
        total_conversations=len({message.thread_id for message in ordered}),
        total_messages=len(ordered),
        average_response_time_hours=_average_response_latency_hours(ordered),
        waiting_on=summary.waiting_on,
        latest_conversation_state=summary.conversation_state.state,
        latest_health_status=summary.health.status,
    )


@dataclass
class RecruiterIntelligenceService:
    settings: AppSettings | None = None
    recruiter_store: RecruiterStore | None = None
    application_service: ApplicationIntelligenceService | None = None

    def _store(self) -> RecruiterStore:
        if self.recruiter_store is not None:
            return self.recruiter_store
        return build_recruiter_store(self.settings)

    def _applications(self) -> ApplicationIntelligenceService:
        if self.application_service is not None:
            return self.application_service
        return build_application_intelligence_service(self.settings)

    async def list_messages(
        self,
        user_id: str,
        *,
        application_id: str | None = None,
        message_type: str | None = None,
        thread_id: str | None = None,
        matched_only: bool = False,
    ) -> list[RecruiterMessage]:
        items = await self._store().list_messages_for_user(
            user_id,
            application_id=application_id,
            message_type=message_type,
            thread_id=thread_id,
        )
        if matched_only:
            items = [item for item in items if item.application_id]
        return items

    async def list_threads(self, user_id: str, *, application_id: str | None = None) -> list[RecruiterThread]:
        return await self._store().list_threads_for_user(user_id, application_id=application_id)

    async def get_thread(self, user_id: str, thread_id: str) -> RecruiterThread | None:
        return await self._store().get_thread(thread_id, user_id=user_id)

    async def list_contacts(self, user_id: str) -> list[RecruiterContactProfile]:
        contacts = await self._store().list_contacts_for_user(user_id)
        messages = await self.list_messages(user_id)
        applications = await self._applications().list_applications(user_id)
        applications_by_id = {application.application_id: application for application in applications}
        grouped_messages: dict[str, list[RecruiterMessage]] = {contact.contact_id: [] for contact in contacts}
        for message in messages:
            grouped_messages.setdefault(message.recruiter.contact_id, []).append(message)
        profiles = [
            _build_contact_profile(
                contact,
                messages=grouped_messages.get(contact.contact_id, []),
                applications_by_id=applications_by_id,
            )
            for contact in contacts
        ]
        return sorted(
            profiles,
            key=lambda item: (_parse_datetime(item.last_contact_at) or datetime.min.replace(tzinfo=timezone.utc), item.contact.contact_id),
            reverse=True,
        )

    async def get_contact(self, user_id: str, contact_id: str) -> RecruiterContactProfile | None:
        contact = await self._store().get_contact(contact_id, user_id=user_id)
        if contact is None:
            return None
        messages = await self.list_messages(user_id)
        applications = await self._applications().list_applications(user_id)
        applications_by_id = {application.application_id: application for application in applications}
        contact_messages = [message for message in messages if message.recruiter.contact_id == contact_id]
        return _build_contact_profile(contact, messages=contact_messages, applications_by_id=applications_by_id)

    async def get_message(self, user_id: str, message_id: str) -> RecruiterMessage | None:
        return await self._store().get_message(message_id, user_id=user_id)

    async def get_message_summary(self, user_id: str, message_id: str) -> CommunicationInsightSummary:
        message = await self.get_message(user_id, message_id)
        if message is None:
            raise ValueError("Unknown recruiter message.")
        application = await self._applications().get_application(user_id, message.application_id) if message.application_id else None
        context_messages = await self.list_messages(
            user_id,
            application_id=message.application_id,
            thread_id=message.thread_id,
        )
        summary = _build_summary(context_messages or [message], application=application, reason=message.match_reason or message.classification_reason)
        return build_message_summary(
            message=message,
            application=application,
            communication_summary=summary,
            health=summary.health,
        )

    async def get_thread_summary(self, user_id: str, thread_id: str) -> CommunicationInsightSummary:
        thread = await self.get_thread(user_id, thread_id)
        if thread is None:
            raise ValueError("Unknown recruiter thread.")
        application = await self._applications().get_application(user_id, thread.application_id) if thread.application_id else None
        messages = await self.list_messages(user_id, application_id=thread.application_id, thread_id=thread.thread_id)
        summary = _build_summary(messages, application=application, reason=thread.pending_action or thread.subject)
        return build_thread_summary(
            thread=thread,
            messages=messages,
            application=application,
            communication_summary=summary,
            health=summary.health,
        )

    async def get_message_suggestions(self, user_id: str, message_id: str) -> list[ConversationSuggestion]:
        message = await self.get_message(user_id, message_id)
        if message is None:
            raise ValueError("Unknown recruiter message.")
        application = (
            await self._applications().get_application(user_id, message.application_id) if message.application_id else None
        )
        context_messages = await self.list_messages(
            user_id,
            application_id=message.application_id,
            thread_id=None if message.application_id else message.thread_id,
        )
        if not context_messages:
            context_messages = [message]
        summary = _build_summary(context_messages, application=application, reason=message.match_reason or message.classification_reason)
        suggestions = [item for item in summary.suggestions if item.supporting_message_id == message_id]
        if suggestions:
            return suggestions
        return _build_summary([message], application=application, reason=message.classification_reason).suggestions

    async def get_application_conversation_state(self, user_id: str, application_id: str) -> ConversationState:
        application = await self._applications().get_application(user_id, application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        messages = await self.list_messages(user_id, application_id=application_id)
        return _build_conversation_state(messages, application=application)

    async def get_application_communication_health(self, user_id: str, application_id: str) -> CommunicationHealth:
        application = await self._applications().get_application(user_id, application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        messages = await self.list_messages(user_id, application_id=application_id)
        state = _build_conversation_state(messages, application=application)
        return _build_communication_health(state, application=application)

    async def list_drafts(
        self,
        user_id: str,
        *,
        thread_id: str | None = None,
        application_id: str | None = None,
        latest_only: bool = True,
    ) -> list[CommunicationDraft]:
        items = await self._store().list_drafts_for_user(user_id, thread_id=thread_id, application_id=application_id)
        if not latest_only:
            return items
        latest_by_group: dict[str, CommunicationDraft] = {}
        for item in items:
            existing = latest_by_group.get(item.draft_group_id)
            if existing is None or item.version_number > existing.version_number:
                latest_by_group[item.draft_group_id] = item
        return sorted(
            latest_by_group.values(),
            key=lambda item: (_parse_datetime(item.updated_at or item.created_at) or datetime.min.replace(tzinfo=timezone.utc), item.version_number, item.draft_id),
            reverse=True,
        )

    async def generate_draft(
        self,
        user_id: str,
        *,
        thread_id: str,
        draft_kind: str,
        tone: str,
        source_message_id: str = "",
    ) -> CommunicationDraft:
        thread = await self.get_thread(user_id, thread_id)
        if thread is None:
            raise ValueError("Unknown recruiter thread.")
        messages = await self.list_messages(user_id, application_id=thread.application_id, thread_id=thread.thread_id)
        if not messages:
            raise ValueError("Cannot generate a draft for a thread with no recruiter messages.")
        source_message = None
        if source_message_id.strip():
            source_message = next((item for item in messages if item.message_id == source_message_id.strip()), None)
            if source_message is None:
                raise ValueError("Unknown source message for draft generation.")
        else:
            source_message = messages[0]
        application = await self._applications().get_application(user_id, thread.application_id) if thread.application_id else None
        communication_summary = _build_summary(messages, application=application, reason=thread.pending_action or source_message.classification_reason)
        normalized_kind = normalize_draft_kind(draft_kind)
        normalized_tone = normalize_tone(tone)
        draft_group_id = _draft_group_id(thread.thread_id, normalized_kind, source_message.message_id)
        existing_versions = [
            item
            for item in await self.list_drafts(user_id, thread_id=thread.thread_id, latest_only=False)
            if item.draft_group_id == draft_group_id
        ]
        version_number = max((item.version_number for item in existing_versions), default=0) + 1
        parent_draft_id = max(existing_versions, key=lambda item: item.version_number).draft_id if existing_versions else ""
        now = _iso_now()
        draft = build_draft(
            base=CommunicationDraft(
                draft_id=_draft_id(draft_group_id, version_number),
                draft_group_id=draft_group_id,
                version_number=version_number,
                user_id=user_id,
                application_id=thread.application_id,
                thread_id=thread.thread_id,
                source_message_id=source_message.message_id,
                parent_draft_id=parent_draft_id,
                draft_kind=normalized_kind,
                tone=normalized_tone,
                status="generated",
                intended_recipient="",
                intended_recipient_email="",
                communication_objective="",
                subject="",
                body="",
                confidence=0.0,
                explanation="",
                strategy_version="",
                model_key="",
                evidence=[],
                assumptions=[],
                user_edited=False,
                generated_at=now,
                created_at=now,
                updated_at=now,
            ),
            latest_message=source_message,
            application=application,
            communication_summary=communication_summary,
        )
        return await self._store().save_draft(draft)

    async def update_draft(
        self,
        user_id: str,
        draft_id: str,
        *,
        subject: str | None = None,
        body: str | None = None,
        status: str | None = None,
    ) -> CommunicationDraft:
        existing = await self._store().get_draft(draft_id, user_id=user_id)
        if existing is None:
            raise ValueError("Unknown recruiter communication draft.")
        next_status = (status or existing.status).strip().casefold() or existing.status
        if next_status not in {"generated", "edited", "approved", "rejected"}:
            raise ValueError("Unsupported recruiter draft status.")
        now = _iso_now()
        edited_subject = subject if subject is not None else existing.subject
        edited_body = body if body is not None else existing.body
        user_edited = edited_subject != existing.subject or edited_body != existing.body or existing.user_edited
        updated = CommunicationDraft(
            draft_id=_draft_id(existing.draft_group_id, existing.version_number + 1),
            draft_group_id=existing.draft_group_id,
            version_number=existing.version_number + 1,
            user_id=existing.user_id,
            application_id=existing.application_id,
            thread_id=existing.thread_id,
            source_message_id=existing.source_message_id,
            parent_draft_id=existing.draft_id,
            draft_kind=existing.draft_kind,
            tone=existing.tone,
            status=next_status,
            intended_recipient=existing.intended_recipient,
            intended_recipient_email=existing.intended_recipient_email,
            communication_objective=existing.communication_objective,
            subject=edited_subject,
            body=edited_body,
            confidence=existing.confidence,
            explanation=existing.explanation,
            strategy_version=existing.strategy_version,
            model_key=existing.model_key,
            evidence=list(existing.evidence),
            assumptions=list(existing.assumptions),
            user_edited=user_edited,
            generated_at=now,
            created_at=now,
            updated_at=now,
        )
        return await self._store().save_draft(updated)

    async def import_messages(self, user_id: str, items: list[RecruiterMessageImportRecord]) -> list[RecruiterMessage]:
        applications = await self._applications().list_applications(user_id)
        imported: list[RecruiterMessage] = []

        for item in items:
            subject = _normalize_subject(item.subject)
            recruiter_email = item.recruiter_email.strip().casefold() or item.sender_email.strip().casefold()
            if not recruiter_email:
                raise ValueError("Imported recruiter messages require recruiter_email or sender_email.")
            recruiter_name = item.recruiter_name.strip() or item.sender_name.strip() or recruiter_email
            received_at = item.received_at or _iso_now()
            combined_text = _normalize_text(" ".join([subject, item.body_text]))
            message_type, confidence, classification_reason = _classification(combined_text)
            matched_application, match_confidence, match_reason = _match_application(
                applications,
                item,
                classification_reason=classification_reason,
            )
            contact = RecruiterContact(
                contact_id=_recruiter_contact_id(user_id, recruiter_email),
                user_id=user_id,
                display_name=recruiter_name,
                email=recruiter_email,
                company=item.company.strip() or (matched_application.company if matched_application is not None else ""),
                title=item.job_title.strip() or (matched_application.title if matched_application is not None else ""),
                metadata={"source": item.source},
                created_at=received_at,
                updated_at=_iso_now(),
            )
            await self._store().save_contact(contact)

            resolved_thread_id = _thread_id(user_id, item, recruiter_email, subject)
            resolved_message_id = _message_id(user_id, item, recruiter_email, subject)
            guidance = _message_guidance(message_type)
            message = RecruiterMessage(
                message_id=resolved_message_id,
                thread_id=resolved_thread_id,
                user_id=user_id,
                application_id=matched_application.application_id if matched_application is not None else None,
                recruiter=contact,
                sender=item.sender_email.strip() or recruiter_email,
                recipients=[recipient.strip() for recipient in item.recipients if recipient.strip()],
                subject=subject,
                body_reference=item.body_reference.strip() or f"import://{resolved_message_id}",
                body_preview=_body_preview(item.body_text),
                received_at=received_at,
                message_type=message_type,
                confidence=confidence,
                source=item.source.strip() or "manual_import",
                timeline_id=_event_id(resolved_message_id, str(guidance.get("event_type", "RecruiterMessageLogged"))),
                company=item.company.strip() or (matched_application.company if matched_application is not None else ""),
                job_title=item.job_title.strip() or (matched_application.title if matched_application is not None else ""),
                matched=matched_application is not None,
                match_confidence=match_confidence if matched_application is not None else 0.0,
                match_reason=match_reason,
                classification_reason=classification_reason,
                suggested_actions=[str(action) for action in guidance.get("suggested_actions", []) if str(action).strip()],
                metadata=dict(item.metadata),
                created_at=received_at,
                updated_at=_iso_now(),
            )
            await self._store().save_thread(_build_thread(contact, [message]))
            await self._store().save_message(message)

            event = _build_event(message)
            await self._store().save_event(event)

            thread_messages = await self._store().list_messages_for_user(user_id, thread_id=resolved_thread_id)
            if not thread_messages:
                thread_messages = [message]
            thread = _build_thread(contact, list(reversed(thread_messages)))
            await self._store().save_thread(thread)

            if matched_application is not None:
                application_messages = await self.list_messages(user_id, application_id=matched_application.application_id)
                summary = _build_summary(
                    application_messages,
                    application=matched_application,
                    reason=match_reason or classification_reason,
                )
                updated_application = await self._applications().record_recruiter_communication(
                    user_id,
                    matched_application.application_id,
                    message_id=message.message_id,
                    thread_id=message.thread_id,
                    recruiter_name=message.recruiter.display_name,
                    recruiter_email=message.recruiter.email,
                    occurred_at=message.received_at or _iso_now(),
                    event_type=event.event_type,
                    label=event.title,
                    detail=event.detail,
                    summary=summary.to_dict(),
                    pending_action=summary.pending_action,
                    suggested_actions=[item.label for item in summary.suggestions],
                    due_at=summary.suggestions[0].due_at if summary.suggestions else None,
                )
                applications = [
                    updated_application if application.application_id == updated_application.application_id else application
                    for application in applications
                ]

            imported.append(message)

        return imported

    async def get_application_communication(self, user_id: str, application_id: str) -> dict[str, object]:
        application = await self._applications().get_application(user_id, application_id)
        if application is None:
            raise ValueError("Unknown application package.")
        messages = await self.list_messages(user_id, application_id=application_id)
        threads = await self.list_threads(user_id, application_id=application_id)
        events = await self._store().list_events_for_application(user_id, application_id)
        summary_reason = str(_json_object(application.metadata.get("communication_summary")).get("reason") or "")
        summary = _build_summary(messages, application=application, reason=summary_reason)
        contact_ids = {message.recruiter.contact_id for message in messages}
        all_contacts = await self.list_contacts(user_id)
        contact_profiles = [profile for profile in all_contacts if profile.contact.contact_id in contact_ids]
        return {
            "application_id": application_id,
            "summary": summary.to_dict(),
            "conversation_state": summary.conversation_state.to_dict(),
            "health": summary.health.to_dict(),
            "suggestions": [item.to_dict() for item in summary.suggestions],
            "messages": [item.to_dict() for item in messages],
            "threads": [item.to_dict() for item in threads],
            "events": [item.to_dict() for item in events],
            "contacts": [item.to_dict() for item in contact_profiles],
            "activity_timeline": [item.to_dict() for item in application.timeline],
        }


def build_recruiter_intelligence_service(settings: AppSettings | None = None) -> RecruiterIntelligenceService:
    resolved_settings = settings or get_settings()
    return RecruiterIntelligenceService(
        settings=resolved_settings,
        recruiter_store=build_recruiter_store(resolved_settings),
        application_service=build_application_intelligence_service(resolved_settings),
    )
