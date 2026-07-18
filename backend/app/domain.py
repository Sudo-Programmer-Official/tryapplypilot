from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

CollectorState = Literal["healthy", "lagging", "degraded"]
ConnectorRolloutStage = Literal["live", "next", "later"]
JobState = Literal["new", "seen", "dismissed", "skipped"]
MatchDecision = Literal["APPLY_NOW", "REVIEW", "IGNORE"]
NotificationChannelName = Literal["telegram", "email", "slack", "desktop"]
UserRole = Literal["super_admin", "admin", "user"]
CompanyRequestStatus = Literal["pending", "approved", "rejected"]


@dataclass(frozen=True)
class JobOpportunity:
    id: str
    company: str
    title: str
    source: str
    location: str
    remote_policy: str
    posted_minutes_ago: int
    match_score: int
    decision: MatchDecision
    why: list[str]
    recommended_resume: str
    duplicate_sources: int
    status: JobState
    alert_sent: bool
    apply_url: str
    gaps: list[str] = field(default_factory=list)
    country_code: str | None = None
    country_display: str = "🌍 Any"
    freshness_label: str = ""
    freshness_tone: str = "fresh"
    recommendation: str = "Review Before Applying"
    recommendation_tone: str = "review"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CompanyPreference:
    company: str
    enabled: bool
    id: str = ""
    tier: int = 3
    priority: int = 999
    connector: str = "company-api"
    poll_interval_minutes: int = 5
    country: str = "US"
    career_url: str = ""
    external_identifier: str = ""
    role_families: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class RolePreference:
    label: str
    enabled: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class NotificationChannel:
    channel: NotificationChannelName
    enabled: bool
    destination: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class WatchlistTerm:
    term: str
    id: str = ""
    company: str = ""
    enabled: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Watchlist:
    name: str
    id: str = ""
    enabled: bool = True
    terms: list[WatchlistTerm] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SavedJobRecord:
    id: str
    user_id: str
    job_id: str
    saved_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OnboardingStep:
    id: str
    label: str
    completed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OnboardingStatus:
    progress_percent: int
    steps: list[OnboardingStep]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class UserAccount:
    id: str
    email: str
    role: UserRole
    full_name: str = ""
    telegram_chat_id: str | None = None
    country: str = "US"
    profile: dict[str, object] = field(default_factory=dict)
    preferences: dict[str, object] = field(default_factory=dict)
    onboarding: OnboardingStatus = field(default_factory=lambda: OnboardingStatus(progress_percent=0, steps=[]))
    created_at: str | None = None
    last_login_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in_seconds: int
    refresh_expires_in_seconds: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResumeAsset:
    id: str
    user_id: str
    display_name: str
    original_filename: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    extracted_text_preview: str
    extracted_skills: list[str]
    role_focus: str
    created_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CompanyRequest:
    id: str
    user_id: str
    requester_email: str
    company_name: str
    career_url: str
    connector_suggestion: str
    external_identifier_suggestion: str
    notes: str
    status: CompanyRequestStatus
    admin_notes: str = ""
    reviewed_at: str | None = None
    reviewed_by_user_id: str | None = None
    approved_company_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SourceStatus:
    id: str
    source: str
    enabled: bool
    rollout_stage: ConnectorRolloutStage
    state: CollectorState
    cadence_minutes: int
    new_jobs_today: int
    last_run_minutes_ago: int | None
    retries_today: int
    last_successful_sync: str | None
    jobs_collected: int = 0
    average_runtime_seconds: int | None = None
    last_failed_sync: str | None = None
    next_scheduled_poll: str | None = None
    lag_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AuditLogEntry:
    id: str
    event_type: str
    subject_type: str
    message: str
    subject_id: str = ""
    actor_user_id: str | None = None
    actor_email: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AlertEvent:
    id: str
    channel: NotificationChannelName
    company: str
    title: str
    match_score: int
    decision: MatchDecision
    posted_minutes_ago: int
    sent_minutes_ago: int
    why: list[str]
    recommended_resume: str
    apply_url: str
    gaps: list[str] = field(default_factory=list)
    country_code: str | None = None
    country_display: str = "🌍 Any"
    freshness_label: str = ""
    freshness_tone: str = "fresh"
    recommendation: str = "Review Before Applying"
    recommendation_tone: str = "review"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ScoutSettings:
    primary_connector: str
    apply_now_threshold_score: int
    review_threshold_score: int
    polling_interval_minutes: int
    companies: list[CompanyPreference]
    roles: list[RolePreference]
    notifications: list[NotificationChannel]
    role_families: list[RolePreference] = field(default_factory=list)
    work_arrangements: list[RolePreference] = field(default_factory=list)
    experience_levels: list[RolePreference] = field(default_factory=list)
    excluded_keywords: list[str] = field(default_factory=list)
    watchlists: list[Watchlist] = field(default_factory=list)
    minimum_match_score: int = 90
    selected_country: str = "US"
    alert_freshness_hours: int = 6
    dashboard_freshness_hours: int = 24
    profile_text: str = ""
    resume_variants: list[str] = field(default_factory=list)
    initial_alert_window_hours: int = 24
    initial_sync_openai_job_limit: int = 20
    initial_sync_max_alerts: int = 5

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
