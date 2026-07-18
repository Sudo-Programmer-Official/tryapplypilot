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
from app.auth import create_telegram_connect_token, decode_token, extract_telegram_start_token, role_allows
from app.config import get_settings as get_app_settings
from app.db.bootstrap import bootstrap_database
from app.domain import CompanyPreference, UserAccount, Watchlist, WatchlistTerm
from app.logging_utils import configure_logging
from app.notifications.telegram import TelegramConfigurationError, TelegramDeliveryError, list_updates
from app.repositories.postgres import list_user_alerts, list_user_jobs
from app.resume_library import ResumeUploadError, list_user_resumes, upload_resume_for_user
from app.scheduler_service import SchedulerBusyError, SchedulerService, get_scheduler_service, set_scheduler_service
from app.saved_jobs import list_saved_jobs, remove_saved_job_for_user, save_job_for_user
from app.services.dashboard import (
    build_dashboard_snapshot,
    build_health_snapshot,
    get_job,
    get_settings,
    list_alerts,
    list_jobs,
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
    freshness_hours: int = Field(default=6, ge=1, le=168)
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
    freshness_hours: int = Field(default=6, ge=1, le=168)
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


security = HTTPBearer(auto_error=False)

configure_logging(get_app_settings().log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_app_settings()
    scheduler = SchedulerService(settings)
    set_scheduler_service(scheduler)
    app.state.scheduler_service = scheduler
    try:
        if settings.radar.mode != "seed":
            await bootstrap_database()
            await ensure_super_admin(settings)
        await scheduler.start()
        yield
    finally:
        await scheduler.stop()
        set_scheduler_service(None)

app = FastAPI(
    title="AI Job Radar API",
    version="0.1.0",
    description="Phase 1 backend for the Market Scout Agent MVP.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/api/auth/me/jobs")
async def current_user_jobs(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [job.to_dict() for job in await list_user_jobs(user.id)]}


@app.get("/api/auth/me/alerts")
async def current_user_alerts(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [alert.to_dict() for alert in await list_user_alerts(user.id)]}


@app.get("/api/auth/me/resumes")
async def current_user_resumes(user: UserAccount = Depends(_current_user)) -> dict[str, object]:
    return {"items": [resume.to_dict() for resume in await list_user_resumes(user.id)]}


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


@app.get("/api/dashboard")
async def dashboard(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return await build_dashboard_snapshot()


@app.get("/api/jobs")
async def jobs(
    min_score: int | None = Query(default=None, ge=0, le=100),
    company: str | None = Query(default=None),
    status: str | None = Query(default=None),
    max_age_hours: int | None = Query(default=None, ge=1, le=24 * 30),
    _: UserAccount = Depends(require_admin),
) -> dict[str, object]:
    return {
        "items": await list_jobs(
            min_score=min_score,
            company=company,
            status=status,
            max_age_hours=max_age_hours,
        )
    }


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


@app.get("/api/sources")
async def sources(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": await list_sources()}


@app.get("/api/audit-logs")
async def audit_logs(_: UserAccount = Depends(require_admin)) -> dict[str, object]:
    return {"items": [item.to_dict() for item in await list_audit_logs(settings=get_app_settings())]}
