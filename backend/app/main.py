from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from asyncpg import UniqueViolationError
import jwt

from app.audit_logs import list_audit_logs, record_audit_event
from app.application_intelligence import build_application_intelligence_service
from app.catalog import (
    import_recommended_companies,
    list_companies as list_catalog_companies,
    list_watchlists as list_catalog_watchlists,
    update_preference_settings,
    upsert_company,
    upsert_watchlist,
)
from app.company_requests import (
    create_company_request,
    list_company_requests,
    list_user_company_requests,
    review_company_request,
)
from app.email_integration import build_email_integration_service
from app.auth import create_telegram_connect_token, decode_token, extract_telegram_start_token, role_allows
from app.config import get_settings as get_app_settings
from app.db.bootstrap import bootstrap_database
from app.domain import CompanyPreference, UserAccount, Watchlist, WatchlistTerm
from app.interview_intelligence import build_interview_intelligence_service
from app.logging_utils import configure_logging
from app.notifications.telegram import TelegramConfigurationError, TelegramDeliveryError, list_updates
from app.repositories.postgres import (
    get_admin_notification_insights,
    get_user_notification_insights,
    list_user_alerts,
    list_user_jobs,
    list_user_missed_jobs,
)
from app.resume_library import ResumeUploadError, delete_resume_for_user, list_user_resumes, upload_resume_for_user
from app.maintenance_service import MaintenanceService, get_maintenance_service, set_maintenance_service
from app.knowledge_platform import KnowledgeChangeConflictError, build_knowledge_platform_service
from app.profile_evolution import ProfileEvolutionQuestion, build_profile_evolution_service
from app.recruiter_intelligence import RecruiterMessageImportRecord, build_recruiter_intelligence_service
from app.resume_intelligence import ResumeChangeReviewInput, build_resume_intelligence_service
from app.scheduler_service import SchedulerBusyError, SchedulerService, get_scheduler_service, set_scheduler_service
from app.saved_jobs import list_saved_jobs, remove_saved_job_for_user, save_job_for_user
from app.services.admin_connectors import (
    build_admin_connectors_workspace,
    list_company_connector_errors,
    list_company_jobs_for_admin,
    run_connector_now,
    set_company_monitoring,
    validate_company_connector,
)
from app.services.dashboard import (
    build_dashboard_snapshot,
    build_health_snapshot,
    get_job,
    get_settings,
    list_alerts,
    list_jobs_page,
    list_sources,
)
from app.user_job_sync import sync_recent_jobs_for_user
from app.user_accounts import (
    authenticate_user,
    create_user,
    ensure_super_admin,
    get_user_by_id,
    issue_session_tokens,
    list_users,
    revoke_refresh_token,
    resolve_delivery_telegram_chat_id,
    rotate_refresh_token,
    set_user_telegram_chat,
    update_user_onboarding,
    update_user_preferences,
    update_user_profile,
)
from app.user_watchlists import create_user_watchlist, delete_user_watchlist, list_user_watchlists, update_user_watchlist


class CompanyPayload(BaseModel):
    company: str = Field(min_length=1)
    enabled: bool = True
    tier: int = Field(default=3, ge=1, le=3)
    priority: int = Field(default=999, ge=1, le=999)
    connector: str = Field(default="company-api", min_length=1)
    poll_interval_minutes: int = Field(default=5, ge=1, le=1440)
    country: str = "US"
    career_url: str = ""
    external_identifier: str = ""
    role_families: list[str] = Field(default_factory=list)


class WatchlistTermPayload(BaseModel):
    term: str = Field(min_length=1)
    company: str = ""
    enabled: bool = True


class WatchlistPayload(BaseModel):
    name: str = Field(min_length=1)
    enabled: bool = True
    terms: list[WatchlistTermPayload] = Field(default_factory=list)


class PreferencesPayload(BaseModel):
    primary_connector: str = Field(min_length=1)
    minimum_match_score: int = Field(ge=0, le=100)
    apply_now_threshold_score: int = Field(ge=0, le=100)
    review_threshold_score: int = Field(ge=0, le=100)
    polling_interval_minutes: int = Field(ge=1, le=1440)
    selected_country: str = "US"
    alert_freshness_hours: int = Field(ge=1, le=24 * 7)
    discovery_alert_freshness_hours: int = Field(default=24, ge=1, le=24 * 14)
    recovery_alert_freshness_hours: int = Field(default=24 * 7, ge=1, le=24 * 30)
    high_priority_discovery_match_score: int = Field(default=95, ge=0, le=100)
    high_priority_discovery_window_hours: int = Field(default=48, ge=1, le=24 * 14)
    dashboard_freshness_hours: int = Field(ge=1, le=24 * 30)
    roles: list[str] = Field(default_factory=list)
    role_families: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    resume_variants: list[str] = Field(default_factory=list)
    initial_alert_window_hours: int = Field(default=24, ge=1, le=24 * 14)
    initial_sync_openai_job_limit: int = Field(default=20, ge=0, le=500)
    initial_sync_max_alerts: int = Field(default=5, ge=0, le=500)


class SignUpPayload(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    full_name: str = ""


class LoginPayload(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)


class RefreshPayload(BaseModel):
    refresh_token: str = Field(min_length=20)


class LogoutPayload(BaseModel):
    refresh_token: str = Field(min_length=20)


class OnboardingPayload(BaseModel):
    full_name: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    github_url: str = ""
    years_of_experience: int | None = Field(default=None, ge=0, le=60)
    visa_status: str = ""
    work_authorization: str = ""
    resume_uploaded: bool = False
    telegram_chat_id: str | None = None
    country: str = "US"
    locations: list[str] = Field(default_factory=list)
    preferred_companies: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    watchlists: list[str] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(default_factory=list)
    freshness_hours: int = Field(default=24, ge=1, le=168)
    search_window_hours: int = Field(default=24 * 7, ge=1, le=24 * 30)
    minimum_match_score: int = Field(default=90, ge=0, le=100)
    notification_frequency: str = "instant"


class UserProfilePayload(BaseModel):
    full_name: str = ""
    linkedin_url: str = ""
    portfolio_url: str = ""
    github_url: str = ""
    years_of_experience: int | None = Field(default=None, ge=0, le=60)
    visa_status: str = ""
    work_authorization: str = ""
    resume_uploaded: bool = False


class SkillPriorityPayload(BaseModel):
    skill: str = Field(min_length=1)
    weight: int = Field(ge=1, le=5)


class UserPreferencesPayload(BaseModel):
    country: str = "US"
    locations: list[str] = Field(default_factory=list)
    preferred_companies: list[str] = Field(default_factory=list)
    company_priorities: dict[str, str] = Field(default_factory=dict)
    preferred_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skill_priorities: list[SkillPriorityPayload] = Field(default_factory=list)
    work_arrangements: list[str] = Field(default_factory=list)
    experience_levels: list[str] = Field(default_factory=list)
    job_types: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    minimum_salary: int | None = Field(default=None, ge=0)
    desired_salary: int | None = Field(default=None, ge=0)
    visa_status: str = ""
    years_of_experience: int | None = Field(default=None, ge=0, le=60)
    travel_preference: str = ""
    remote_preference: str = ""
    freshness_hours: int = Field(default=24, ge=1, le=168)
    search_window_hours: int = Field(default=24 * 7, ge=1, le=24 * 30)
    minimum_match_score: int = Field(default=90, ge=0, le=100)
    notification_frequency: str = "instant"
    notification_rules: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    resume_strategy: str = "auto"
    preferred_resume_variants: list[str] = Field(default_factory=list)


class TelegramVerifyPayload(BaseModel):
    connect_token: str = Field(min_length=20)


class CompanyRequestPayload(BaseModel):
    company_name: str = Field(min_length=1)
    career_url: str = ""
    connector_suggestion: str = ""
    external_identifier_suggestion: str = ""
    notes: str = ""


class CompanyRequestReviewPayload(BaseModel):
    status: Literal["approved", "rejected"]
    admin_notes: str = ""
    connector: str = ""
    external_identifier: str = ""
    career_url: str = ""
    tier: int = Field(default=3, ge=1, le=3)
    priority: int = Field(default=999, ge=1, le=999)
    poll_interval_minutes: int = Field(default=5, ge=1, le=1440)
    country: str = "US"
    enabled: bool = True
    role_families: list[str] = Field(default_factory=list)


class SavedJobPayload(BaseModel):
    job_id: str = Field(min_length=1)


class CompanyMonitoringPayload(BaseModel):
    enabled: bool


class KnowledgeAliasPayload(BaseModel):
    entity_type: str = Field(min_length=1)
    alias_value: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)


class ProfileEvolutionAnswerPayload(BaseModel):
    answer: str = Field(min_length=1)
    topic: str = ""
    question_id: str = ""
    question_prompt: str = ""


class ReviewDecisionPayload(BaseModel):
    review_notes: str = ""


class ResumeChangeReviewPayload(BaseModel):
    change_id: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    edited_text: str = ""


class ResumeFinalizePayload(BaseModel):
    reviews: list[ResumeChangeReviewPayload] = Field(default_factory=list)


class ApplicationPackagePayload(BaseModel):
    resume_version_id: str = Field(min_length=1)
    notes: str = ""


class ApplicationStatusPayload(BaseModel):
    status: str = Field(min_length=1)
    notes: str = ""


class ApplicationTaskPayload(BaseModel):
    status: str = Field(min_length=1)
    detail: str = ""


class ApplicationNotePayload(BaseModel):
    body: str = Field(min_length=1)
    note_type: str = "general"


class ApplicationArtifactPayload(BaseModel):
    kind: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = ""
    status: str = "ready"
    url: str = ""
    file_name: str = ""
    mime_type: str = ""
    detail: str = ""
    source_id: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class ApplicationAnswerPayload(BaseModel):
    question: str = Field(min_length=1)
    question_key: str = ""
    answer: str = Field(min_length=1)
    source: str = ""
    reusable: bool = False
    sensitive_data: bool = False
    user_approved: bool = True


class ApplicationMetadataPayload(BaseModel):
    recruiter_name: str = ""
    recruiter_email: str = ""
    hiring_manager: str = ""
    application_portal: str = ""
    external_application_id: str = ""
    confirmation_number: str = ""
    submitted_url: str = ""
    submission_timestamp: str = ""
    deadline: str = ""
    assessment_deadline: str = ""
    follow_up_date: str = ""
    referral_source: str = ""
    referral_contact: str = ""
    salary_range: str = ""
    location: str = ""
    work_arrangement: str = ""
    sponsorship_status: str = ""
    application_source: str = ""


class ApplicationSubmitPayload(BaseModel):
    submitted_at: str = ""
    portal: str = ""
    confirmation_number: str = ""
    external_application_id: str = ""
    submitted_url: str = ""
    answer_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    notes: str = ""


class RecruiterMessageImportItemPayload(BaseModel):
    external_message_id: str = ""
    external_thread_id: str = ""
    application_id: str = ""
    recruiter_name: str = ""
    recruiter_email: str = ""
    sender_email: str = ""
    sender_name: str = ""
    recipients: list[str] = Field(default_factory=list)
    subject: str = ""
    body_text: str = ""
    body_reference: str = ""
    company: str = ""
    job_title: str = ""
    received_at: str = ""
    source: str = "manual_import"
    metadata: dict[str, object] = Field(default_factory=dict)


class RecruiterMessageImportPayload(BaseModel):
    items: list[RecruiterMessageImportItemPayload] = Field(default_factory=list)


class RecruiterProviderConnectPayload(BaseModel):
    account_email: str = Field(min_length=3)
    scopes: list[str] = Field(default_factory=list)
    token_reference: str = Field(min_length=3)
    token_metadata: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)


class RecruiterProviderOAuthCompletePayload(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


class RecruiterProviderOAuthStartPayload(BaseModel):
    scopes: list[str] = Field(default_factory=list)
    login_hint: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class RecruiterSyncPayload(BaseModel):
    provider: str = ""


class RecruiterDraftGeneratePayload(BaseModel):
    thread_id: str = Field(min_length=1)
    draft_kind: str = "reply"
    tone: str = "professional"
    source_message_id: str = ""


class RecruiterDraftUpdatePayload(BaseModel):
    subject: str | None = None
    body: str | None = None
    status: str | None = None


class InterviewParticipantPayload(BaseModel):
    participant_id: str = ""
    name: str = ""
    email: str = ""
    title: str = ""
    role: str = "interviewer"
    source_contact_id: str = ""


class InterviewPreparationEvidencePayload(BaseModel):
    reference_id: str = ""
    source_type: str = ""
    source_id: str = ""
    label: str = ""
    excerpt: str = ""
    confidence: float = 0.0
    entity_type: str = ""
    entity_id: str = ""
    metadata: dict[str, object] = Field(default_factory=dict)


class InterviewPreparationItemPayload(BaseModel):
    item_id: str = ""
    label: str = ""
    status: str = "pending"
    detail: str = ""
    reason: str = ""
    estimated_effort: str = ""
    priority: str = "normal"
    category: str = "preparation"
    source: str = "manual"
    due_at: str = ""
    completed_at: str = ""
    generated: bool = False
    updated_at: str = ""
    supporting_evidence: list[InterviewPreparationEvidencePayload] = Field(default_factory=list)


class InterviewCreatePayload(BaseModel):
    interview_type: str = Field(min_length=1)
    interview_round: str = ""
    interview_status: str = "planned"
    scheduled_start_at: str = ""
    scheduled_end_at: str = ""
    timezone: str = "UTC"
    meeting_url: str = ""
    recruiter_name: str = ""
    recruiter_email: str = ""
    recruiter_contact_id: str = ""
    notes: str = ""
    preparation_status: str = ""
    interviewers: list[InterviewParticipantPayload] = Field(default_factory=list)
    preparation_checklist: list[InterviewPreparationItemPayload] = Field(default_factory=list)
    source: str = "manual"
    metadata: dict[str, object] = Field(default_factory=dict)


class InterviewUpdatePayload(BaseModel):
    interview_type: str | None = None
    interview_round: str | None = None
    interview_status: str | None = None
    scheduled_start_at: str | None = None
    scheduled_end_at: str | None = None
    timezone: str | None = None
    meeting_url: str | None = None
    recruiter_name: str | None = None
    recruiter_email: str | None = None
    recruiter_contact_id: str | None = None
    notes: str | None = None
    preparation_status: str | None = None
    interviewers: list[InterviewParticipantPayload] | None = None
    preparation_checklist: list[InterviewPreparationItemPayload] | None = None
    source: str | None = None
    metadata: dict[str, object] | None = None


class InterviewPreparationUpdatePayload(BaseModel):
    checklist: list[InterviewPreparationItemPayload] | None = None
    status: str | None = None
    metadata: dict[str, object] | None = None


class InterviewQuestionUpdatePayload(BaseModel):
    preparation_status: str | None = None
    priority: str | None = None
    sequence_order: int | None = Field(default=None, ge=1)
    hidden: bool | None = None
    archived: bool | None = None
    metadata: dict[str, object] | None = None


class InterviewQuestionNotePayload(BaseModel):
    body: str = Field(min_length=1)


class InterviewStorySectionPayload(BaseModel):
    section_key: str = ""
    title: str = ""
    content: list[str] = Field(default_factory=list)
    evidence_references: list[InterviewPreparationEvidencePayload] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class InterviewStoryGapPromptPayload(BaseModel):
    prompt_id: str = ""
    field_key: str = ""
    prompt: str = ""
    reason: str = ""
    topic: str = ""
    status: str = "open"
    related_evidence: list[InterviewPreparationEvidencePayload] = Field(default_factory=list)
    profile_evolution_payload: dict[str, object] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class InterviewStoryUpdatePayload(BaseModel):
    title: str | None = None
    category: str | None = None
    status: str | None = None
    sections: list[InterviewStorySectionPayload] | None = None
    technical_decisions: list[str] | None = None
    tradeoffs: list[str] | None = None
    leadership_moments: list[str] | None = None
    measurable_outcomes: list[str] | None = None
    lessons_learned: list[str] | None = None
    interviewer_follow_ups: list[str] | None = None
    tags: list[str] | None = None
    missing_information_prompts: list[InterviewStoryGapPromptPayload] | None = None
    metadata: dict[str, object] | None = None


security = HTTPBearer(auto_error=False)

configure_logging(get_app_settings().log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_app_settings()
    scheduler = SchedulerService(settings)
    maintenance = MaintenanceService(settings)
    set_scheduler_service(scheduler)
    set_maintenance_service(maintenance)
    app.state.scheduler_service = scheduler
    app.state.maintenance_service = maintenance
    try:
        if settings.radar.mode != "seed":
            await bootstrap_database()
            await ensure_super_admin(settings)
        await scheduler.start()
        await maintenance.start()
        yield
    finally:
        await maintenance.stop()
        await scheduler.stop()
        set_maintenance_service(None)
        set_scheduler_service(None)

app_settings = get_app_settings()

app = FastAPI(
    title="AI Job Radar API",
    version="0.1.0",
    description="Phase 1 backend for the Market Scout Agent MVP.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(app_settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> UserAccount:
    await ensure_super_admin()
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token.") from exc
    user = await get_user_by_id(str(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user.")
    return user


def _require_role(required_role: str):
    async def dependency(user: UserAccount = Depends(_current_user)) -> UserAccount:
        if not role_allows(user.role, required_role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role for this operation.")
        return user

    return dependency


require_admin = _require_role("admin")


def _auth_response(user: UserAccount, tokens: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"user": user.to_dict()}
    if tokens is not None:
        payload["tokens"] = tokens
    return payload


def _request_context(request: Request) -> tuple[str, str]:
    user_agent = request.headers.get("user-agent", "")
    client_ip = request.client.host if request.client is not None and request.client.host is not None else ""
    return user_agent, client_ip


def _scheduler_or_503() -> SchedulerService:
    scheduler = get_scheduler_service()
    if scheduler is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduler service is not initialized.")
    return scheduler


def _maintenance_or_503() -> MaintenanceService:
    maintenance = get_maintenance_service()
    if maintenance is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Maintenance service is not initialized.")
    return maintenance


def _knowledge_service():
    return build_knowledge_platform_service(get_app_settings())


def _profile_evolution_service():
    return build_profile_evolution_service(get_app_settings())


def _resume_intelligence_service():
    return build_resume_intelligence_service(get_app_settings())


def _application_intelligence_service():
    return build_application_intelligence_service(get_app_settings())


def _interview_intelligence_service():
    return build_interview_intelligence_service(get_app_settings())


def _recruiter_intelligence_service():
    return build_recruiter_intelligence_service(get_app_settings())


def _email_integration_service():
    return build_email_integration_service(get_app_settings())


def _model_payload(value: object) -> dict[str, object]:
    if hasattr(value, "model_dump"):
        return getattr(value, "model_dump")()
    if hasattr(value, "dict"):
        return getattr(value, "dict")()
    if hasattr(value, "__dict__"):
        return dict(getattr(value, "__dict__"))
    return {}


def _serialize_profile_evolution_question(question) -> dict[str, object] | None:
    if question is None:
        return None
    return {
        "id": question.id,
        "topic": question.topic,
        "prompt": question.prompt,
        "rationale": question.rationale,
        "missing_fields": list(question.missing_fields),
        "confidence": question.confidence,
    }


def _serialize_profile_evolution_session(session) -> dict[str, object]:
    return {
        "id": session.id,
        "user_id": session.user_id,
        "current_topic": session.current_topic,
        "completed_topics": list(session.completed_topics),
        "pending_topics": list(session.pending_topics),
        "skipped_topics": list(session.skipped_topics),
        "confidence": session.confidence,
        "extracted_entities": list(session.extracted_entities),
        "topic_progress": {
            topic: {
                "topic": progress.topic,
                "answers": list(progress.answers),
                "extracted_fields": dict(progress.extracted_fields),
                "asked_follow_ups": list(progress.asked_follow_ups),
                "staged_version_ids": list(progress.staged_version_ids),
                "status": progress.status,
                "confidence": progress.confidence,
            }
            for topic, progress in session.topic_progress.items()
        },
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _serialize_profile_evolution_result(result) -> dict[str, object]:
    return {
        "session": _serialize_profile_evolution_session(result.session),
        "extracted_facts": [
            {
                "topic": fact.topic,
                "entity_type": fact.entity_type,
                "canonical_name": fact.canonical_name,
                "content": dict(fact.content),
                "reason": fact.reason,
                "confidence": fact.confidence,
                "extracted_fields": dict(fact.extracted_fields),
            }
            for fact in result.extracted_facts
        ],
        "staged_version_ids": list(result.staged_version_ids),
        "knowledge_gain": dict(result.knowledge_gain),
        "next_question": _serialize_profile_evolution_question(result.next_question),
    }


def _serialize_profile_evolution_change(version, entity, evidence) -> dict[str, object]:
    return {
        "version": version.to_dict(),
        "entity": entity.to_dict() if entity is not None else None,
        "evidence": [item.to_dict() for item in evidence],
    }


@app.post("/api/auth/signup")
async def signup(payload: SignUpPayload, request: Request) -> dict[str, object]:
    try:
        user = await create_user(email=payload.email, password=payload.password, full_name=payload.full_name)
    except UniqueViolationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.") from exc
    user_agent, client_ip = _request_context(request)
    tokens = await issue_session_tokens(user, user_agent=user_agent, ip_address=client_ip)
    return _auth_response(user, tokens.to_dict())


@app.post("/api/auth/login")
async def login(payload: LoginPayload, request: Request) -> dict[str, object]:
    user = await authenticate_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    user_agent, client_ip = _request_context(request)
    tokens = await issue_session_tokens(user, user_agent=user_agent, ip_address=client_ip)
    return _auth_response(user, tokens.to_dict())


@app.post("/api/auth/refresh")
async def refresh_session(payload: RefreshPayload, request: Request) -> dict[str, object]:
    user_agent, client_ip = _request_context(request)
    user, tokens = await rotate_refresh_token(
        payload.refresh_token,
        user_agent=user_agent,
        ip_address=client_ip,
    )
    if user is None or tokens is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
    return _auth_response(user, tokens.to_dict())


@app.post("/api/auth/logout")
async def logout(payload: LogoutPayload) -> dict[str, object]:
    await revoke_refresh_token(payload.refresh_token)
    return {"ok": True}


@app.get("/api/auth/me")
async def current_user(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return _auth_response(user)


@app.get("/api/auth/me/knowledge/profile")
async def current_user_knowledge_profile(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    service = _knowledge_service()
    profile = await service.get_user_profile(user.id)
    return {"items": {entity_type: [entity.to_dict() for entity in entities] for entity_type, entities in profile.items()}}


@app.get("/api/auth/me/knowledge/aliases")
async def current_user_knowledge_aliases(
    entity_type: str | None = Query(default=None),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    service = _knowledge_service()
    aliases = await service.list_aliases(user.id, entity_type=entity_type)
    return {"items": [alias.to_dict() for alias in aliases]}


@app.get("/api/auth/me/knowledge/timeline")
async def current_user_knowledge_timeline(
    limit: int = Query(default=50, ge=1, le=500),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    service = _knowledge_service()
    return {"items": [event.to_dict() for event in await service.get_timeline(user.id, limit=limit)]}


@app.get("/api/auth/me/knowledge/metrics")
async def current_user_knowledge_metrics(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return await _knowledge_service().get_metrics(user.id)


@app.get("/api/auth/me/knowledge/health")
async def current_user_knowledge_health(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return await _knowledge_service().run_health_checks(user.id)


@app.get("/api/auth/me/knowledge/schema")
async def current_user_knowledge_schema(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    _ = user
    return await _knowledge_service().get_schema_info()


@app.get("/api/auth/me/profile-evolution/state")
async def current_user_profile_evolution_state(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    service = _profile_evolution_service()
    session = await service.get_state(user.id)
    remaining_topics = await service.get_remaining_topics(user.id)
    return {
        "session": _serialize_profile_evolution_session(session),
        "remaining_topics": remaining_topics,
    }


@app.get("/api/auth/me/profile-evolution/next-question")
async def current_user_profile_evolution_next_question(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    question = await _profile_evolution_service().get_next_question(user.id)
    return {"item": _serialize_profile_evolution_question(question)}


@app.post("/api/auth/me/profile-evolution/answers")
async def submit_current_user_profile_evolution_answer(
    payload: ProfileEvolutionAnswerPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    question = None
    if payload.question_id or payload.question_prompt or payload.topic:
        question = ProfileEvolutionQuestion(
            id=payload.question_id or "",
            topic=payload.topic or "",
            prompt=payload.question_prompt or "",
            rationale="",
            missing_fields=[],
            confidence=0.0,
        )
    result = await _profile_evolution_service().submit_answer(
        user.id,
        answer=payload.answer,
        actor_user_id=user.id,
        topic=payload.topic or None,
        question=question,
    )
    return _serialize_profile_evolution_result(result)


@app.get("/api/auth/me/profile-evolution/changes")
async def current_user_profile_evolution_changes(
    limit: int = Query(default=50, ge=1, le=200),
    session_id: str = Query(default=""),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    knowledge = _knowledge_service()
    versions = await knowledge.list_suggested_changes(
        user.id,
        source="profile_evolution",
        agent_name="profile_evolution",
        limit=limit,
    )
    items: list[dict[str, object]] = []
    for version in versions:
        if session_id and str(version.new_content.get("profile_evolution_session_id", "")) != session_id:
            continue
        entity = await knowledge.get_entity(version.entity_id)
        evidence = await knowledge.rank_evidence(user.id, version.evidence_ids)
        items.append(_serialize_profile_evolution_change(version, entity, evidence))
    return {"items": items}


@app.post("/api/auth/me/profile-evolution/changes/{version_id}/approve")
async def approve_current_user_profile_evolution_change(
    version_id: str,
    payload: ReviewDecisionPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    knowledge = _knowledge_service()
    version = await knowledge.get_change(version_id, user_id=user.id)
    if version is None or version.source != "profile_evolution" or version.agent_name != "profile_evolution":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown profile evolution change.")
    try:
        entity = await knowledge.approve_change(
            version_id,
            reviewed_by_user_id=user.id,
            review_notes=payload.review_notes,
        )
    except KnowledgeChangeConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {
        "item": {
            "version_id": version_id,
            "status": "approved",
            "entity": entity.to_dict(),
            "review_notes": payload.review_notes,
        }
    }


@app.post("/api/auth/me/profile-evolution/changes/{version_id}/reject")
async def reject_current_user_profile_evolution_change(
    version_id: str,
    payload: ReviewDecisionPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    knowledge = _knowledge_service()
    version = await knowledge.get_change(version_id, user_id=user.id)
    if version is None or version.source != "profile_evolution" or version.agent_name != "profile_evolution":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown profile evolution change.")
    try:
        rejected = await knowledge.reject_change(
            version_id,
            reviewed_by_user_id=user.id,
            review_notes=payload.review_notes,
        )
    except KnowledgeChangeConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"item": rejected.to_dict()}


@app.get("/api/auth/me/jobs")
async def current_user_jobs(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [job.to_dict() for job in await list_user_jobs(user.id)]}


@app.get("/api/auth/me/alerts")
async def current_user_alerts(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [alert.to_dict() for alert in await list_user_alerts(user.id)]}


@app.get("/api/auth/me/missed-opportunities")
async def current_user_missed_opportunities(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [job.to_dict() for job in await list_user_missed_jobs(user.id)]}


@app.get("/api/auth/me/notification-insights")
async def current_user_notification_insights(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return await get_user_notification_insights(user.id)


@app.get("/api/auth/me/resumes")
async def current_user_resumes(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [resume.to_dict() for resume in await list_user_resumes(user.id)]}


@app.get("/api/auth/me/resume-intelligence/jobs/{job_id}/analysis")
async def current_user_resume_intelligence_analysis(
    job_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    analysis = await _resume_intelligence_service().analyze_job(user.id, job_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown job for resume analysis.")
    return {"item": analysis.to_dict()}


@app.post("/api/auth/me/resume-intelligence/jobs/{job_id}/finalize")
async def finalize_current_user_resume_intelligence_review(
    job_id: str,
    payload: ResumeFinalizePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _resume_intelligence_service().finalize_review(
            user.id,
            job_id,
            reviews=[
                ResumeChangeReviewInput(
                    change_id=item.change_id,
                    decision=item.decision,
                    edited_text=item.edited_text,
                )
                for item in payload.reviews
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"item": record.to_dict()}


@app.get("/api/auth/me/resume-intelligence/versions/{version_id}/content")
async def current_user_resume_intelligence_version_content(
    version_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    payload = await _resume_intelligence_service().get_version_content(version_id, user_id=user.id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown resume version.")
    return {"item": payload}


@app.get("/api/auth/me/applications")
async def current_user_applications(
    status: str | None = Query(default=None),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _application_intelligence_service().list_applications(user.id, status=status)
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/applications/{application_id}")
async def current_user_application(
    application_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _application_intelligence_service().get_application(user.id, application_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown application package.")
    return {"item": item.to_dict()}


@app.get("/api/auth/me/interviews")
async def current_user_interviews(
    application_id: str | None = Query(default=None),
    interview_status: str | None = Query(default=None),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _interview_intelligence_service().list_interviews(
        user.id,
        application_id=application_id,
        interview_status=interview_status,
    )
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/interviews/upcoming")
async def current_user_upcoming_interviews(
    limit: int = Query(default=10, ge=1, le=100),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _interview_intelligence_service().list_upcoming(user.id, limit=limit)
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/interviews/{interview_id}")
async def current_user_interview(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _interview_intelligence_service().get_interview(user.id, interview_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown interview workspace.")
    return {"item": item.to_dict()}


@app.get("/api/auth/me/interviews/{interview_id}/preparation")
async def current_user_interview_preparation(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _interview_intelligence_service().get_preparation(user.id, interview_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No preparation plan exists for this interview yet.")
    return {"item": item.to_dict()}


@app.post("/api/auth/me/interviews/{interview_id}/prepare")
async def prepare_current_user_interview(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().prepare_interview(user.id, interview_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.preparation.generated",
        subject_type="interview_preparation",
        subject_id=item.plan_id,
        message=f"Generated interview preparation plan v{item.version_number}.",
        metadata={
            "interview_id": item.interview_id,
            "application_id": item.application_id,
            "version_number": item.version_number,
            "focus_labels": item.focus_labels,
            "overall_confidence": item.overall_confidence,
        },
    )
    return {"item": item.to_dict()}


@app.patch("/api/auth/me/interviews/{interview_id}/preparation")
async def update_current_user_interview_preparation(
    interview_id: str,
    payload: InterviewPreparationUpdatePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().update_preparation(
            user.id,
            interview_id,
            checklist=None if payload.checklist is None else [
                {
                    **entry.__dict__,
                    "supporting_evidence": [reference.__dict__ for reference in (getattr(entry, "supporting_evidence", None) or [])],
                }
                for entry in payload.checklist
            ],
            status=payload.status,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") or detail.startswith("No preparation plan") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.preparation.updated",
        subject_type="interview_preparation",
        subject_id=item.plan_id,
        message=f"Updated interview preparation plan v{item.version_number}.",
        metadata={
            "interview_id": item.interview_id,
            "application_id": item.application_id,
            "version_number": item.version_number,
            "status": item.status,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/interviews/{interview_id}/preparation/regenerate")
async def regenerate_current_user_interview_preparation(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().regenerate_preparation(user.id, interview_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.preparation.regenerated",
        subject_type="interview_preparation",
        subject_id=item.plan_id,
        message=f"Regenerated interview preparation plan v{item.version_number}.",
        metadata={
            "interview_id": item.interview_id,
            "application_id": item.application_id,
            "version_number": item.version_number,
            "focus_labels": item.focus_labels,
            "overall_confidence": item.overall_confidence,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/interviews/{interview_id}/questions/generate")
async def generate_current_user_interview_questions(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().generate_question_set(user.id, interview_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") or detail.startswith("No preparation plan") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.questions.generated",
        subject_type="interview_question_set",
        subject_id=item.question_set_id,
        message=f"Generated interview question bank v{item.version_number}.",
        metadata={
            "interview_id": item.interview_id,
            "application_id": item.application_id,
            "version_number": item.version_number,
            "question_count": len(item.questions),
            "categories": item.metadata.get("categories", []),
        },
    )
    return {"item": item.to_dict()}


@app.get("/api/auth/me/interviews/{interview_id}/question-sets")
async def current_user_interview_question_sets(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _interview_intelligence_service().list_question_sets(user.id, interview_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/interviews/{interview_id}/question-sets/current")
async def current_user_interview_current_question_set(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _interview_intelligence_service().get_current_question_set(user.id, interview_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No question set exists for this interview yet.")
    return {"item": item.to_dict()}


@app.get("/api/auth/me/interview-question-sets/{question_set_id}")
async def current_user_interview_question_set(
    question_set_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _interview_intelligence_service().get_question_set(user.id, question_set_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown interview question set.")
    return {"item": item.to_dict()}


@app.post("/api/auth/me/interviews/{interview_id}/questions/regenerate")
async def regenerate_current_user_interview_questions(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().regenerate_question_set(user.id, interview_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") or detail.startswith("No preparation plan") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.questions.regenerated",
        subject_type="interview_question_set",
        subject_id=item.question_set_id,
        message=f"Regenerated interview question bank v{item.version_number}.",
        metadata={
            "interview_id": item.interview_id,
            "application_id": item.application_id,
            "version_number": item.version_number,
            "question_count": len(item.questions),
            "categories": item.metadata.get("categories", []),
        },
    )
    return {"item": item.to_dict()}


@app.patch("/api/auth/me/interview-questions/{question_id}")
async def update_current_user_interview_question(
    question_id: str,
    payload: InterviewQuestionUpdatePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().update_question(
            user.id,
            question_id,
            preparation_status=payload.preparation_status,
            priority=payload.priority,
            sequence_order=payload.sequence_order,
            hidden=payload.hidden,
            archived=payload.archived,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.question.updated",
        subject_type="interview_question",
        subject_id=item.question_id,
        message="Updated interview question state.",
        metadata={
            "question_set_id": item.question_set_id,
            "interview_id": item.interview_id,
            "priority": item.priority,
            "preparation_status": item.preparation_status,
            "sequence_order": item.sequence_order,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/interview-questions/{question_id}/notes")
async def add_current_user_interview_question_note(
    question_id: str,
    payload: InterviewQuestionNotePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().add_question_note(
            user.id,
            question_id,
            body=payload.body,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.question.note_added",
        subject_type="interview_question",
        subject_id=item.question_id,
        message="Added interview question note.",
        metadata={
            "question_set_id": item.question_set_id,
            "interview_id": item.interview_id,
            "note_count": len(item.user_notes),
        },
    )
    return {"item": item.to_dict()}


@app.get("/api/auth/me/interviews/{interview_id}/stories")
async def current_user_interview_stories(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _interview_intelligence_service().list_interview_stories(user.id, interview_id)
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
    return {"items": [item.to_dict() for item in items]}


@app.post("/api/auth/me/interviews/{interview_id}/stories/generate")
async def generate_current_user_interview_stories(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _interview_intelligence_service().generate_stories(user.id, interview_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail.startswith("Unknown") or detail.startswith("No preparation plan") or detail.startswith("No question set")
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.stories.generated",
        subject_type="interview_story_library",
        subject_id=interview_id,
        message=f"Generated {len(items)} evidence-backed interview stories.",
        metadata={
            "interview_id": interview_id,
            "story_count": len(items),
            "story_ids": [item.story_id for item in items],
        },
    )
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/stories")
async def current_user_stories(
    application_id: str | None = Query(default=None),
    interview_id: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _interview_intelligence_service().list_stories(
        user.id,
        application_id=application_id,
        interview_id=interview_id,
        status=status_value,
    )
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/stories/{story_id}")
async def current_user_story(
    story_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _interview_intelligence_service().get_story(user.id, story_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown interview story.")
    return {"item": item.to_dict()}


@app.patch("/api/auth/me/stories/{story_id}")
async def update_current_user_story(
    story_id: str,
    payload: InterviewStoryUpdatePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().update_story(
            user.id,
            story_id,
            title=payload.title,
            category=payload.category,
            status=payload.status,
            sections=[_model_payload(section) for section in payload.sections] if payload.sections is not None else None,
            technical_decisions=payload.technical_decisions,
            tradeoffs=payload.tradeoffs,
            leadership_moments=payload.leadership_moments,
            measurable_outcomes=payload.measurable_outcomes,
            lessons_learned=payload.lessons_learned,
            interviewer_follow_ups=payload.interviewer_follow_ups,
            tags=payload.tags,
            missing_information_prompts=(
                [_model_payload(prompt) for prompt in payload.missing_information_prompts]
                if payload.missing_information_prompts is not None
                else None
            ),
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.story.updated",
        subject_type="interview_story",
        subject_id=item.story_id,
        message="Updated interview story draft.",
        metadata={
            "story_group_id": item.story_group_id,
            "interview_id": item.interview_id,
            "status": item.status,
            "version_number": item.version_number,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/stories/{story_id}/approve")
async def approve_current_user_story(
    story_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().approve_story(user.id, story_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.story.approved",
        subject_type="interview_story",
        subject_id=item.story_id,
        message="Approved interview story.",
        metadata={
            "story_group_id": item.story_group_id,
            "interview_id": item.interview_id,
            "version_number": item.version_number,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/stories/{story_id}/archive")
async def archive_current_user_story(
    story_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().archive_story(user.id, story_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.story.archived",
        subject_type="interview_story",
        subject_id=item.story_id,
        message="Archived interview story.",
        metadata={
            "story_group_id": item.story_group_id,
            "interview_id": item.interview_id,
            "version_number": item.version_number,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/stories/{story_id}/regenerate")
async def regenerate_current_user_story(
    story_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().regenerate_story(user.id, story_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail.startswith("Unknown") or detail.startswith("No preparation plan") or detail.startswith("No question set")
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.story.regenerated",
        subject_type="interview_story",
        subject_id=item.story_id,
        message=f"Regenerated interview story v{item.version_number}.",
        metadata={
            "story_group_id": item.story_group_id,
            "interview_id": item.interview_id,
            "version_number": item.version_number,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/applications/{application_id}/interviews")
async def create_current_user_interview(
    application_id: str,
    payload: InterviewCreatePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().create_interview(
            user.id,
            application_id,
            interview_type=payload.interview_type,
            interview_round=payload.interview_round,
            interview_status=payload.interview_status,
            scheduled_start_at=payload.scheduled_start_at,
            scheduled_end_at=payload.scheduled_end_at,
            timezone_name=payload.timezone,
            meeting_url=payload.meeting_url,
            recruiter_name=payload.recruiter_name,
            recruiter_email=payload.recruiter_email,
            recruiter_contact_id=payload.recruiter_contact_id,
            notes=payload.notes,
            preparation_status=payload.preparation_status,
            interviewers=[entry.__dict__ for entry in payload.interviewers],
            preparation_checklist=[
                {
                    **entry.__dict__,
                    "supporting_evidence": [reference.__dict__ for reference in (getattr(entry, "supporting_evidence", None) or [])],
                }
                for entry in payload.preparation_checklist
            ],
            source=payload.source,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.created",
        subject_type="interview",
        subject_id=item.interview_id,
        message=f"Created interview workspace for {item.interview_round} {item.interview_type.replace('_', ' ')}.",
        metadata={
            "application_id": item.application_id,
            "interview_type": item.interview_type,
            "interview_round": item.interview_round,
            "interview_status": item.interview_status,
            "scheduled_start_at": item.scheduled_start_at,
        },
    )
    return {"item": item.to_dict()}


@app.patch("/api/auth/me/interviews/{interview_id}")
async def update_current_user_interview(
    interview_id: str,
    payload: InterviewUpdatePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().update_interview(
            user.id,
            interview_id,
            interview_type=payload.interview_type,
            interview_round=payload.interview_round,
            interview_status=payload.interview_status,
            scheduled_start_at=payload.scheduled_start_at,
            scheduled_end_at=payload.scheduled_end_at,
            timezone_name=payload.timezone,
            meeting_url=payload.meeting_url,
            recruiter_name=payload.recruiter_name,
            recruiter_email=payload.recruiter_email,
            recruiter_contact_id=payload.recruiter_contact_id,
            notes=payload.notes,
            preparation_status=payload.preparation_status,
            interviewers=None if payload.interviewers is None else [entry.__dict__ for entry in payload.interviewers],
            preparation_checklist=None if payload.preparation_checklist is None else [
                {
                    **entry.__dict__,
                    "supporting_evidence": [reference.__dict__ for reference in (getattr(entry, "supporting_evidence", None) or [])],
                }
                for entry in payload.preparation_checklist
            ],
            source=payload.source,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.updated",
        subject_type="interview",
        subject_id=item.interview_id,
        message=f"Updated interview workspace {item.interview_id}.",
        metadata={
            "application_id": item.application_id,
            "interview_type": item.interview_type,
            "interview_round": item.interview_round,
            "interview_status": item.interview_status,
            "preparation_status": item.preparation_status,
        },
    )
    return {"item": item.to_dict()}


@app.delete("/api/auth/me/interviews/{interview_id}")
async def delete_current_user_interview(
    interview_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _interview_intelligence_service().delete_interview(user.id, interview_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=user,
        event_type="interview.deleted",
        subject_type="interview",
        subject_id=item.interview_id,
        message=f"Deleted interview workspace {item.interview_id}.",
        metadata={
            "application_id": item.application_id,
            "interview_type": item.interview_type,
            "interview_round": item.interview_round,
        },
    )
    return {"item": item.to_dict()}


@app.get("/api/auth/me/applications/{application_id}/artifacts")
async def current_user_application_artifacts(
    application_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _application_intelligence_service().list_application_artifacts(user.id, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"items": [item.to_dict() for item in items]}


@app.post("/api/auth/me/applications/{application_id}/artifacts")
async def add_current_user_application_artifact(
    application_id: str,
    payload: ApplicationArtifactPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _application_intelligence_service().add_application_artifact(
            user.id,
            application_id,
            kind=payload.kind,
            title=payload.title,
            source=payload.source,
            status=payload.status,
            url=payload.url,
            file_name=payload.file_name,
            mime_type=payload.mime_type,
            detail=payload.detail,
            source_id=payload.source_id,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.artifact_added",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Added application artifact for {record.company} - {record.title}.",
        metadata={"job_id": record.job_id, "kind": payload.kind, "title": payload.title},
    )
    return {"item": record.to_dict()}


@app.get("/api/auth/me/applications/{application_id}/answers")
async def current_user_application_answers(
    application_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _application_intelligence_service().list_application_answers(user.id, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"items": [item.to_dict() for item in items]}


@app.post("/api/auth/me/applications/{application_id}/answers")
async def add_current_user_application_answer(
    application_id: str,
    payload: ApplicationAnswerPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _application_intelligence_service().add_application_answer(
            user.id,
            application_id,
            question=payload.question,
            question_key=payload.question_key,
            answer=payload.answer,
            source=payload.source,
            reusable=payload.reusable,
            sensitive_data=payload.sensitive_data,
            user_approved=payload.user_approved,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.answer_added",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Added structured application answer for {record.company} - {record.title}.",
        metadata={
            "job_id": record.job_id,
            "question": payload.question,
            "reusable": payload.reusable,
            "sensitive_data": payload.sensitive_data,
        },
    )
    return {"item": record.to_dict()}


@app.patch("/api/auth/me/applications/{application_id}/metadata")
async def update_current_user_application_metadata(
    application_id: str,
    payload: ApplicationMetadataPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    updates = {
        "recruiter_name": payload.recruiter_name,
        "recruiter_email": payload.recruiter_email,
        "hiring_manager": payload.hiring_manager,
        "application_portal": payload.application_portal,
        "external_application_id": payload.external_application_id,
        "confirmation_number": payload.confirmation_number,
        "submitted_url": payload.submitted_url,
        "submission_timestamp": payload.submission_timestamp or None,
        "deadline": payload.deadline or None,
        "assessment_deadline": payload.assessment_deadline or None,
        "follow_up_date": payload.follow_up_date or None,
        "referral_source": payload.referral_source,
        "referral_contact": payload.referral_contact,
        "salary_range": payload.salary_range,
        "location": payload.location,
        "work_arrangement": payload.work_arrangement,
        "sponsorship_status": payload.sponsorship_status,
        "application_source": payload.application_source,
    }
    try:
        record = await _application_intelligence_service().update_application_metadata(
            user.id,
            application_id,
            updates=updates,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.metadata_updated",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Updated structured application metadata for {record.company} - {record.title}.",
        metadata={"job_id": record.job_id, "fields": [key for key, value in updates.items() if value not in {"", None}]},
    )
    return {"item": record.to_dict()}


@app.post("/api/auth/me/applications/jobs/{job_id}/package")
async def build_current_user_application_package(
    job_id: str,
    payload: ApplicationPackagePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _application_intelligence_service().build_application_package(
            user.id,
            job_id,
            resume_version_id=payload.resume_version_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.package_built",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Built application package for {record.company} - {record.title}.",
        metadata={
            "job_id": record.job_id,
            "resume_version_id": record.resume_version_id,
            "status": record.status,
        },
    )
    return {"item": record.to_dict()}


@app.post("/api/auth/me/applications/jobs/{job_id}/track")
async def track_current_user_job_application(
    job_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    async def current_resume_version():
        # No reviewed changes: package the user's best-matching resume as-is.
        return await _resume_intelligence_service().finalize_review(user.id, job_id, reviews=[])

    try:
        record, created = await _application_intelligence_service().track_job_application(
            user.id,
            job_id,
            resume_version_factory=current_resume_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if created:
        await record_audit_event(
            actor_user=user,
            event_type="application.tracked_from_apply",
            subject_type="application",
            subject_id=record.application_id,
            message=f"Tracked application for {record.company} - {record.title}.",
            metadata={"job_id": record.job_id, "resume_version_id": record.resume_version_id},
        )
    return {"item": record.to_dict(), "created": created}


@app.post("/api/auth/me/applications/{application_id}/submit")
async def submit_current_user_application(
    application_id: str,
    payload: ApplicationSubmitPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _application_intelligence_service().submit_application(
            user.id,
            application_id,
            submitted_at=payload.submitted_at or None,
            portal=payload.portal,
            confirmation_number=payload.confirmation_number,
            external_application_id=payload.external_application_id,
            submitted_url=payload.submitted_url,
            answer_ids=payload.answer_ids,
            artifact_ids=payload.artifact_ids,
            notes=payload.notes,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.submitted",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Recorded application submission for {record.company} - {record.title}.",
        metadata={
            "job_id": record.job_id,
            "resume_version_id": record.resume_version_id,
            "status": record.status,
            "submitted_at": payload.submitted_at,
        },
    )
    return {"item": record.to_dict()}


@app.patch("/api/auth/me/applications/{application_id}/status")
async def update_current_user_application_status(
    application_id: str,
    payload: ApplicationStatusPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _application_intelligence_service().update_application_status(
            user.id,
            application_id,
            status=payload.status,
            notes=payload.notes,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application package" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.status_updated",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Updated application status to {record.status} for {record.company} - {record.title}.",
        metadata={
            "job_id": record.job_id,
            "resume_version_id": record.resume_version_id,
            "status": record.status,
            "notes": payload.notes,
        },
    )
    return {"item": record.to_dict()}


@app.get("/api/auth/me/application-answers")
async def current_user_reusable_application_answers(
    include_sensitive: bool = Query(default=False),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _application_intelligence_service().list_reusable_answers(
        user.id,
        include_sensitive=include_sensitive,
    )
    return {"items": [item.to_dict() for item in items]}


@app.patch("/api/auth/me/applications/{application_id}/tasks/{task_id}")
async def update_current_user_application_task(
    application_id: str,
    task_id: str,
    payload: ApplicationTaskPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _application_intelligence_service().update_application_task(
            user.id,
            application_id,
            task_id=task_id,
            status=payload.status,
            detail=payload.detail,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.task_updated",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Updated application task {task_id} for {record.company} - {record.title}.",
        metadata={
            "job_id": record.job_id,
            "resume_version_id": record.resume_version_id,
            "task_id": task_id,
            "task_status": payload.status,
            "detail": payload.detail,
        },
    )
    return {"item": record.to_dict()}


@app.post("/api/auth/me/applications/{application_id}/notes")
async def add_current_user_application_note(
    application_id: str,
    payload: ApplicationNotePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        record = await _application_intelligence_service().add_application_note(
            user.id,
            application_id,
            body=payload.body,
            note_type=payload.note_type,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "Unknown application" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="application.note_added",
        subject_type="application",
        subject_id=record.application_id,
        message=f"Added application note for {record.company} - {record.title}.",
        metadata={
            "job_id": record.job_id,
            "resume_version_id": record.resume_version_id,
            "note_type": payload.note_type,
        },
    )
    return {"item": record.to_dict()}


@app.get("/api/auth/me/recruiter/messages")
async def current_user_recruiter_messages(
    application_id: str | None = Query(default=None),
    message_type: str | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    matched_only: bool = Query(default=False),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _recruiter_intelligence_service().list_messages(
        user.id,
        application_id=application_id,
        message_type=message_type,
        thread_id=thread_id,
        matched_only=matched_only,
    )
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/recruiter/threads")
async def current_user_recruiter_threads(
    application_id: str | None = Query(default=None),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _recruiter_intelligence_service().list_threads(user.id, application_id=application_id)
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/recruiter/threads/{thread_id}")
async def current_user_recruiter_thread(
    thread_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _recruiter_intelligence_service().get_thread(user.id, thread_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown recruiter thread.")
    return {"item": item.to_dict()}


@app.get("/api/auth/me/recruiter/threads/{thread_id}/summary")
async def current_user_recruiter_thread_summary(
    thread_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _recruiter_intelligence_service().get_thread_summary(user.id, thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"item": item.to_dict()}


@app.get("/api/auth/me/recruiter/contacts")
async def current_user_recruiter_contacts(
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _recruiter_intelligence_service().list_contacts(user.id)
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/recruiter/contacts/{contact_id}")
async def current_user_recruiter_contact(
    contact_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _recruiter_intelligence_service().get_contact(user.id, contact_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown recruiter contact.")
    return {"item": item.to_dict()}


@app.post("/api/auth/me/recruiter/connect/gmail")
async def connect_current_user_gmail(
    payload: RecruiterProviderConnectPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _email_integration_service().connect_provider(
            user.id,
            "gmail",
            account_email=payload.account_email,
            scopes=payload.scopes,
            token_reference=payload.token_reference,
            token_metadata=payload.token_metadata,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=user,
        event_type="recruiter.provider_connected",
        subject_type="email_provider",
        subject_id=item.connection_id,
        message=f"Connected Gmail provider for {item.account_email}.",
        metadata={"provider": item.provider, "account_email": item.account_email, "scopes": item.scopes},
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/recruiter/connect/gmail/start")
async def start_connect_current_user_gmail(
    payload: RecruiterProviderOAuthStartPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _email_integration_service().begin_provider_oauth(
            user,
            "gmail",
            scopes=payload.scopes,
            login_hint=payload.login_hint,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"item": item.to_dict()}


@app.post("/api/auth/me/recruiter/connect/gmail/complete")
async def complete_connect_current_user_gmail(
    payload: RecruiterProviderOAuthCompletePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _email_integration_service().complete_provider_oauth(
            "gmail",
            user_id=user.id,
            state_token=payload.state,
            code=payload.code,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired Gmail OAuth state token.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=user,
        event_type="recruiter.provider_connected",
        subject_type="email_provider",
        subject_id=item.connection_id,
        message=f"Connected Gmail provider for {item.account_email}.",
        metadata={"provider": item.provider, "account_email": item.account_email, "scopes": item.scopes},
    )
    return {"item": item.to_dict()}


@app.delete("/api/auth/me/recruiter/connect/gmail")
async def disconnect_current_user_gmail(
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _email_integration_service().disconnect_provider(user.id, "gmail")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=user,
        event_type="recruiter.provider_disconnected",
        subject_type="email_provider",
        subject_id=item.connection_id,
        message=f"Disconnected Gmail provider for {item.account_email}.",
        metadata={"provider": item.provider, "account_email": item.account_email},
    )
    return {"item": item.to_dict()}


@app.get("/api/auth/me/recruiter/providers")
async def current_user_recruiter_providers(
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _email_integration_service().list_connections(user.id)
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/recruiter/providers/status")
async def current_user_recruiter_provider_status(
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _email_integration_service().list_provider_statuses(user.id)
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/recruiter/messages/{message_id}")
async def current_user_recruiter_message(
    message_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    item = await _recruiter_intelligence_service().get_message(user.id, message_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown recruiter message.")
    return {"item": item.to_dict()}


@app.get("/api/auth/me/recruiter/messages/{message_id}/summary")
async def current_user_recruiter_message_summary(
    message_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _recruiter_intelligence_service().get_message_summary(user.id, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"item": item.to_dict()}


@app.get("/api/auth/me/recruiter/messages/{message_id}/suggestions")
async def current_user_recruiter_message_suggestions(
    message_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _recruiter_intelligence_service().get_message_suggestions(user.id, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"items": [item.to_dict() for item in items]}


@app.post("/api/auth/me/recruiter/messages/import")
async def import_current_user_recruiter_messages(
    payload: RecruiterMessageImportPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _recruiter_intelligence_service().import_messages(
            user.id,
            [
                RecruiterMessageImportRecord(
                    external_message_id=item.external_message_id,
                    external_thread_id=item.external_thread_id,
                    application_id=item.application_id,
                    recruiter_name=item.recruiter_name,
                    recruiter_email=item.recruiter_email,
                    sender_email=item.sender_email,
                    sender_name=item.sender_name,
                    recipients=item.recipients,
                    subject=item.subject,
                    body_text=item.body_text,
                    body_reference=item.body_reference,
                    company=item.company,
                    job_title=item.job_title,
                    received_at=item.received_at or None,
                    source=item.source,
                    metadata=item.metadata,
                )
                for item in payload.items
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=user,
        event_type="recruiter.messages_imported",
        subject_type="recruiter_message",
        subject_id=items[0].message_id if items else "",
        message=f"Imported {len(items)} recruiter messages.",
        metadata={
            "message_count": len(items),
            "matched_count": len([item for item in items if item.application_id]),
            "sources": sorted({item.source for item in items}),
        },
    )
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/recruiter/drafts")
async def current_user_recruiter_drafts(
    thread_id: str | None = Query(default=None),
    application_id: str | None = Query(default=None),
    latest_only: bool = Query(default=True),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _recruiter_intelligence_service().list_drafts(
        user.id,
        thread_id=thread_id,
        application_id=application_id,
        latest_only=latest_only,
    )
    return {"items": [item.to_dict() for item in items]}


@app.post("/api/auth/me/recruiter/drafts")
async def generate_current_user_recruiter_draft(
    payload: RecruiterDraftGeneratePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _recruiter_intelligence_service().generate_draft(
            user.id,
            thread_id=payload.thread_id,
            draft_kind=payload.draft_kind,
            tone=payload.tone,
            source_message_id=payload.source_message_id,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="recruiter.draft_generated",
        subject_type="recruiter_draft",
        subject_id=item.draft_id,
        message=f"Generated a recruiter {item.draft_kind.replace('_', ' ')} draft for thread {item.thread_id}.",
        metadata={
            "thread_id": item.thread_id,
            "application_id": item.application_id,
            "draft_kind": item.draft_kind,
            "tone": item.tone,
            "source_message_id": item.source_message_id,
            "version_number": item.version_number,
        },
    )
    return {"item": item.to_dict()}


@app.patch("/api/auth/me/recruiter/drafts/{draft_id}")
async def update_current_user_recruiter_draft(
    draft_id: str,
    payload: RecruiterDraftUpdatePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _recruiter_intelligence_service().update_draft(
            user.id,
            draft_id,
            subject=payload.subject,
            body=payload.body,
            status=payload.status,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail.startswith("Unknown") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="recruiter.draft_updated",
        subject_type="recruiter_draft",
        subject_id=item.draft_id,
        message=f"Updated recruiter draft {item.draft_id} to version {item.version_number}.",
        metadata={
            "thread_id": item.thread_id,
            "application_id": item.application_id,
            "draft_group_id": item.draft_group_id,
            "draft_kind": item.draft_kind,
            "status": item.status,
            "parent_draft_id": item.parent_draft_id,
            "version_number": item.version_number,
            "user_edited": item.user_edited,
        },
    )
    return {"item": item.to_dict()}


@app.post("/api/auth/me/recruiter/sync")
async def sync_current_user_recruiter_provider(
    payload: RecruiterSyncPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        items = await _email_integration_service().sync(user.id, provider=payload.provider or None)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "No connected email providers" in detail else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    await record_audit_event(
        actor_user=user,
        event_type="recruiter.provider_sync_requested",
        subject_type="email_provider",
        subject_id=items[0].connection_id if items else "",
        message=f"Ran recruiter provider sync across {len(items)} connection(s).",
        metadata={
            "providers": [item.provider for item in items],
            "imported_count": sum(item.imported_count for item in items),
            "duplicate_count": sum(item.duplicate_count for item in items),
            "error_count": sum(item.error_count for item in items),
        },
    )
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/recruiter/sync/history")
async def current_user_recruiter_sync_history(
    provider: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    items = await _email_integration_service().list_sync_history(user.id, provider=provider, limit=limit)
    return {"items": [item.to_dict() for item in items]}


@app.get("/api/auth/me/applications/{application_id}/communication")
async def current_user_application_communication(
    application_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        return await _recruiter_intelligence_service().get_application_communication(user.id, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.get("/api/auth/me/applications/{application_id}/conversation-state")
async def current_user_application_conversation_state(
    application_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _recruiter_intelligence_service().get_application_conversation_state(user.id, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"item": item.to_dict()}


@app.get("/api/auth/me/applications/{application_id}/communication-health")
async def current_user_application_communication_health(
    application_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await _recruiter_intelligence_service().get_application_communication_health(user.id, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"item": item.to_dict()}


@app.delete("/api/auth/me/resumes/{resume_id}")
async def delete_current_user_resume(
    resume_id: str,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        updated_user = await delete_resume_for_user(user.id, resume_id, settings=get_app_settings())
    except ResumeUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown resume.")
    await record_audit_event(
        actor_user=updated_user,
        event_type="resume.deleted",
        subject_type="resume",
        subject_id=resume_id,
        message=f"{updated_user.email} deleted a resume.",
        metadata={"resume_id": resume_id},
        settings=get_app_settings(),
    )
    return {"user": updated_user.to_dict()}


@app.post("/api/auth/me/resumes")
async def upload_current_user_resume(
    file: UploadFile = File(...),
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        resume, updated_user = await upload_resume_for_user(user.id, file, settings=get_app_settings())
    except ResumeUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=updated_user,
        event_type="resume.uploaded",
        subject_type="resume",
        subject_id=resume.id,
        message=f"{updated_user.email} uploaded resume {resume.display_name}.",
        metadata={"resume_id": resume.id, "role_focus": resume.role_focus},
        settings=get_app_settings(),
    )
    await sync_recent_jobs_for_user(updated_user, get_app_settings())
    return {
        "item": resume.to_dict(),
        "user": updated_user.to_dict(),
    }


@app.get("/api/auth/me/company-requests")
async def current_user_company_requests(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [item.to_dict() for item in await list_user_company_requests(user.id)]}


@app.post("/api/auth/me/company-requests")
async def create_current_user_company_request(
    payload: CompanyRequestPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await create_company_request(
            user,
            company_name=payload.company_name,
            career_url=payload.career_url,
            connector_suggestion=payload.connector_suggestion,
            external_identifier_suggestion=payload.external_identifier_suggestion,
            notes=payload.notes,
            settings=get_app_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=user,
        event_type="company.requested",
        subject_type="company_request",
        subject_id=item.id,
        message=f"{user.email} requested company coverage for {item.company_name}.",
        metadata={"company_name": item.company_name, "status": item.status},
        settings=get_app_settings(),
    )
    return {"item": item.to_dict()}


@app.get("/api/auth/me/saved-jobs")
async def current_user_saved_jobs(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [item.to_dict() for item in await list_saved_jobs(user.id)]}


@app.post("/api/auth/me/saved-jobs")
async def save_current_user_job(payload: SavedJobPayload, user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    try:
        item = await save_job_for_user(user.id, payload.job_id, settings=get_app_settings())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"item": item.to_dict()}


@app.delete("/api/auth/me/saved-jobs/{job_id}")
async def delete_current_user_saved_job(job_id: str, user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    deleted = await remove_saved_job_for_user(user.id, job_id, settings=get_app_settings())
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved job not found.")
    return {"ok": True}


@app.get("/api/auth/me/watchlists")
async def current_user_watchlists(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [item.to_dict() for item in await list_user_watchlists(user.id, settings=get_app_settings())]}


@app.post("/api/auth/me/watchlists")
async def create_current_user_watchlist(
    payload: WatchlistPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await create_user_watchlist(
            user.id,
            name=payload.name,
            enabled=payload.enabled,
            terms=[
                WatchlistTerm(
                    term=term.term.strip(),
                    company=term.company.strip(),
                    enabled=term.enabled,
                )
                for term in payload.terms
            ],
            settings=get_app_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"item": item.to_dict()}


@app.patch("/api/auth/me/watchlists/{watchlist_id}")
async def patch_current_user_watchlist(
    watchlist_id: str,
    payload: WatchlistPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    try:
        item = await update_user_watchlist(
            user.id,
            watchlist_id,
            name=payload.name,
            enabled=payload.enabled,
            terms=[
                WatchlistTerm(
                    term=term.term.strip(),
                    company=term.company.strip(),
                    enabled=term.enabled,
                )
                for term in payload.terms
            ],
            settings=get_app_settings(),
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail == "Unknown watchlist." else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"item": item.to_dict()}


@app.delete("/api/auth/me/watchlists/{watchlist_id}")
async def delete_current_user_watchlist(watchlist_id: str, user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    deleted = await delete_user_watchlist(user.id, watchlist_id, settings=get_app_settings())
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found.")
    return {"ok": True}


@app.get("/api/auth/users")
async def users_admin(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": [user.to_dict() for user in await list_users()]}


@app.put("/api/auth/me/onboarding")
async def update_onboarding(payload: OnboardingPayload, user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    updated = await update_user_onboarding(user.id, payload.model_dump())
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    await sync_recent_jobs_for_user(updated, get_app_settings())
    return _auth_response(updated)


@app.get("/api/auth/me/preferences")
async def current_user_preferences(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"item": user.preferences}


@app.get("/api/auth/me/companies")
async def current_user_companies(_: UserAccount = Depends(_current_user)) -> dict[str, object]:
    companies = [company for company in await list_catalog_companies() if company.enabled]
    return {"items": [company.to_dict() for company in companies]}


@app.put("/api/auth/me/preferences")
async def update_preferences_for_current_user(
    payload: UserPreferencesPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    updated = await update_user_preferences(user.id, payload.model_dump(), settings=get_app_settings())
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    await sync_recent_jobs_for_user(updated, get_app_settings())
    return _auth_response(updated)


@app.put("/api/auth/me/profile")
async def update_profile_for_current_user(
    payload: UserProfilePayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    updated = await update_user_profile(user.id, payload.model_dump(), settings=get_app_settings())
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    await sync_recent_jobs_for_user(updated, get_app_settings())
    return _auth_response(updated)


@app.post("/api/auth/me/telegram/connect")
async def create_telegram_connect_session(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    settings = get_app_settings()
    if not settings.telegram.bot_token or not settings.telegram.bot_username:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not configured.",
        )
    connect_token, expires_in_seconds = create_telegram_connect_token(user, settings)
    return {
        "connect_token": connect_token,
        "connect_url": f"https://t.me/{settings.telegram.bot_username}?start={connect_token}",
        "connect_command": f"/start {connect_token}",
        "bot_username": settings.telegram.bot_username,
        "expires_in_seconds": expires_in_seconds,
        "already_connected": bool(user.telegram_chat_id),
        "delivery_chat_id": await resolve_delivery_telegram_chat_id(settings),
    }


@app.post("/api/auth/me/telegram/verify")
async def verify_telegram_connect_session(
    payload: TelegramVerifyPayload,
    user: UserAccount = Depends(_current_user),
) -> dict[str, object]:
    settings = get_app_settings()
    if not settings.telegram.bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not configured.",
        )
    try:
        token_payload = decode_token(payload.connect_token, expected_type="telegram_link", settings=settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Telegram connect token.") from exc
    if str(token_payload.get("sub")) != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Telegram connect token does not belong to this user.")

    try:
        updates = await asyncio.to_thread(list_updates, settings)
    except TelegramConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except TelegramDeliveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    for update in reversed(updates):
        start_token = extract_telegram_start_token(update.text)
        if start_token != payload.connect_token or update.chat_type != "private":
            continue
        updated_user = await set_user_telegram_chat(
            user.id,
            chat_id=update.chat_id,
            username=update.username,
            first_name=update.first_name,
            settings=settings,
        )
        if updated_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        await sync_recent_jobs_for_user(updated_user, settings)
        return {
            "connected": True,
            "chat_id": update.chat_id,
            "delivery_chat_id": await resolve_delivery_telegram_chat_id(settings),
            "user": updated_user.to_dict(),
        }

    return {
        "connected": False,
        "chat_id": user.telegram_chat_id,
        "delivery_chat_id": await resolve_delivery_telegram_chat_id(settings),
        "message": (
            "Telegram bot has not received the /start connect command yet. "
            "Open the exact bot link from this page and press Start in Telegram. "
            "If you already had a chat open with the bot, paste the manual command from this page. "
            "Sending a normal message like 'hi' will not connect the chat."
        ),
        "user": user.to_dict(),
    }


@app.get("/health")
async def healthcheck() -> dict[str, object]:
    return await build_health_snapshot()


@app.get("/api/admin/scheduler/status")
async def scheduler_status(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return _scheduler_or_503().status().to_dict()


@app.post("/api/admin/scheduler/run-now")
async def scheduler_run_now(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    scheduler = _scheduler_or_503()
    try:
        snapshot = await scheduler.run_poll_cycle(trigger="manual")
    except SchedulerBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return snapshot.to_dict()


@app.get("/api/admin/maintenance/status")
async def maintenance_status(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return _maintenance_or_503().status().to_dict()


@app.post("/api/admin/maintenance/run-now")
async def maintenance_run_now(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    snapshot = await _maintenance_or_503().run_cycle(trigger="manual")
    return snapshot.to_dict()


@app.get("/api/admin/connectors/workspace")
async def admin_connectors_workspace(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await build_admin_connectors_workspace()


@app.get("/api/admin/knowledge/schema")
async def admin_knowledge_schema(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await _knowledge_service().get_schema_info()


@app.get("/api/admin/knowledge/users/{user_id}/profile")
async def admin_knowledge_profile(user_id: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    service = _knowledge_service()
    profile = await service.get_user_profile(user_id)
    return {"items": {entity_type: [entity.to_dict() for entity in entities] for entity_type, entities in profile.items()}}


@app.get("/api/admin/knowledge/users/{user_id}/aliases")
async def admin_knowledge_aliases(
    user_id: str,
    entity_type: str | None = Query(default=None),
    _: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    service = _knowledge_service()
    aliases = await service.list_aliases(user_id, entity_type=entity_type)
    return {"items": [alias.to_dict() for alias in aliases]}


@app.post("/api/admin/knowledge/users/{user_id}/aliases")
async def admin_register_knowledge_alias(
    user_id: str,
    payload: KnowledgeAliasPayload,
    _: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    alias = await _knowledge_service().register_manual_alias(
        user_id,
        entity_type=payload.entity_type,
        alias_value=payload.alias_value,
        canonical_name=payload.canonical_name,
    )
    return {"item": alias.to_dict()}


@app.get("/api/admin/knowledge/users/{user_id}/timeline")
async def admin_knowledge_timeline(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    _: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    return {"items": [event.to_dict() for event in await _knowledge_service().get_timeline(user_id, limit=limit)]}


@app.get("/api/admin/knowledge/users/{user_id}/metrics")
async def admin_knowledge_metrics(user_id: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await _knowledge_service().get_metrics(user_id)


@app.get("/api/admin/knowledge/users/{user_id}/health")
async def admin_knowledge_health(user_id: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await _knowledge_service().run_health_checks(user_id)


@app.post("/api/admin/connectors/{connector_key}/run-now")
async def admin_connector_run_now(connector_key: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await run_connector_now(connector_key)


@app.post("/api/admin/connectors/companies/{company_id}/validate")
async def admin_validate_company(company_id: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    try:
        payload = await validate_company_connector(company_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"item": payload}


@app.post("/api/admin/connectors/companies/{company_id}/monitoring")
async def admin_set_company_monitoring(
    company_id: str,
    payload: CompanyMonitoringPayload,
    _: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    try:
        company = await set_company_monitoring(company_id, payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"item": company.to_dict()}


@app.get("/api/admin/connectors/companies/{company_id}/jobs")
async def admin_company_jobs(company_id: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": await list_company_jobs_for_admin(company_id)}


@app.get("/api/admin/connectors/companies/{company_id}/errors")
async def admin_company_errors(company_id: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": await list_company_connector_errors(company_id)}


@app.get("/api/dashboard")
async def dashboard(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await build_dashboard_snapshot()


@app.get("/api/jobs")
async def jobs(
    min_score: int | None = Query(default=None, ge=0, le=100),
    company: str | None = Query(default=None),
    status: str | None = Query(default=None),
    max_age_hours: int | None = Query(default=None, ge=1, le=24 * 30),
    query: str | None = Query(default=None),
    decision: Literal["APPLY_NOW", "REVIEW", "IGNORE"] | None = Query(default=None),
    sort_by: Literal["highest_match", "newest", "company", "recently_updated"] = Query(default="highest_match"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    return await list_jobs_page(
        min_score=min_score,
        company=company,
        status=status,
        max_age_hours=max_age_hours,
        query=query,
        decision=decision,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )


@app.get("/api/jobs/{job_id}")
async def job_detail(job_id: str, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job id: {job_id}")
    return {"item": job}


@app.get("/api/settings")
async def settings(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await get_settings()


@app.get("/api/catalog/companies")
async def companies_catalog(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    companies = await list_catalog_companies()
    return {"items": [company.to_dict() for company in companies]}


@app.post("/api/catalog/companies/import-defaults")
async def import_default_companies(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    items = await import_recommended_companies()
    enabled_count = sum(1 for company in items if company.enabled)
    return {
        "items": [company.to_dict() for company in items],
        "summary": {
            "count": len(items),
            "enabled_count": enabled_count,
        },
    }


@app.post("/api/catalog/companies")
async def create_company(payload: CompanyPayload, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    company = await upsert_company(
        CompanyPreference(
            company=payload.company.strip(),
            enabled=payload.enabled,
            tier=payload.tier,
            priority=payload.priority,
            connector=payload.connector.strip(),
            poll_interval_minutes=payload.poll_interval_minutes,
            country=payload.country,
            career_url=payload.career_url.strip(),
            external_identifier=payload.external_identifier.strip(),
            role_families=payload.role_families,
        )
    )
    return {"item": company.to_dict()}


@app.put("/api/catalog/companies/{company_id}")
async def update_company(company_id: str, payload: CompanyPayload, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    company = await upsert_company(
        CompanyPreference(
            id=company_id,
            company=payload.company.strip(),
            enabled=payload.enabled,
            tier=payload.tier,
            priority=payload.priority,
            connector=payload.connector.strip(),
            poll_interval_minutes=payload.poll_interval_minutes,
            country=payload.country,
            career_url=payload.career_url.strip(),
            external_identifier=payload.external_identifier.strip(),
            role_families=payload.role_families,
        )
    )
    return {"item": company.to_dict()}


@app.get("/api/catalog/watchlists")
async def watchlists_catalog(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": [watchlist.to_dict() for watchlist in await list_catalog_watchlists()]}


@app.post("/api/catalog/watchlists")
async def create_watchlist(payload: WatchlistPayload, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    watchlist = await upsert_watchlist(
        Watchlist(
            name=payload.name.strip(),
            enabled=payload.enabled,
            terms=[
                WatchlistTerm(
                    term=term.term.strip(),
                    company=term.company.strip(),
                    enabled=term.enabled,
                )
                for term in payload.terms
            ],
        )
    )
    return {"item": watchlist.to_dict()}


@app.put("/api/catalog/watchlists/{watchlist_id}")
async def update_watchlist(
    watchlist_id: str,
    payload: WatchlistPayload,
    _: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    watchlist = await upsert_watchlist(
        Watchlist(
            id=watchlist_id,
            name=payload.name.strip(),
            enabled=payload.enabled,
            terms=[
                WatchlistTerm(
                    term=term.term.strip(),
                    company=term.company.strip(),
                    enabled=term.enabled,
                )
                for term in payload.terms
            ],
        )
    )
    return {"item": watchlist.to_dict()}


@app.put("/api/catalog/preferences")
async def update_preferences(payload: PreferencesPayload, _: UserAccount = Depends(require_admin)) -> dict[str, object]:
    settings = await update_preference_settings(payload.model_dump())
    return {"item": settings.to_dict()}


@app.get("/api/catalog/company-requests")
async def company_requests_catalog(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": [item.to_dict() for item in await list_company_requests()]}


@app.put("/api/catalog/company-requests/{request_id}")
async def review_catalog_company_request(
    request_id: str,
    payload: CompanyRequestReviewPayload,
    reviewer: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    try:
        item = await review_company_request(
            request_id,
            reviewer=reviewer,
            status=payload.status,
            admin_notes=payload.admin_notes,
            connector=payload.connector,
            external_identifier=payload.external_identifier,
            career_url=payload.career_url,
            tier=payload.tier,
            priority=payload.priority,
            poll_interval_minutes=payload.poll_interval_minutes,
            country=payload.country,
            enabled=payload.enabled,
            role_families=payload.role_families,
            settings=get_app_settings(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_audit_event(
        actor_user=reviewer,
        event_type=f"company.{payload.status}",
        subject_type="company_request",
        subject_id=item.id,
        message=f"{reviewer.email} {payload.status} company request for {item.company_name}.",
        metadata={
            "company_name": item.company_name,
            "status": item.status,
            "approved_company_id": item.approved_company_id or "",
        },
        settings=get_app_settings(),
    )
    return {"item": item.to_dict()}


@app.get("/api/alerts")
async def alerts(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": await list_alerts()}


@app.get("/api/admin/notification-insights")
async def admin_notification_insights(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await get_admin_notification_insights()


@app.get("/api/sources")
async def sources(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": await list_sources()}


@app.get("/api/audit-logs")
async def audit_logs(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": [item.to_dict() for item in await list_audit_logs(settings=get_app_settings())]}
