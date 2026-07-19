from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.company_catalog_defaults import build_recommended_company_preferences
from app.config import DEFAULT_EXCLUDED_KEYWORDS, DEFAULT_EXPERIENCE_LEVELS, DEFAULT_ROLE_FAMILIES, DEFAULT_TARGET_ROLES, DEFAULT_WORK_ARRANGEMENTS
from app.connectors.registry import build_default_registry
from app.domain import (
    AlertEvent,
    CompanyPreference,
    JobOpportunity,
    NotificationChannel,
    RolePreference,
    ScoutSettings,
    SourceStatus,
    Watchlist,
    WatchlistTerm,
)

JOBS: list[JobOpportunity] = [
    JobOpportunity(
        id="databricks-ml-platform",
        company="Databricks",
        title="Senior Software Engineer, ML Platform",
        source="Greenhouse",
        location="San Francisco, CA",
        remote_policy="Hybrid",
        posted_minutes_ago=4,
        match_score=94,
        decision="APPLY_NOW",
        why=["Distributed Systems", "Python", "ML platform", "Backend"],
        recommended_resume="Backend_AI_v5.pdf",
        duplicate_sources=0,
        status="new",
        alert_sent=True,
        apply_url="https://boards.greenhouse.io/databricks",
    ),
    JobOpportunity(
        id="stripe-payments-platform",
        company="Stripe",
        title="Senior Backend Engineer, Payments Platform",
        source="Greenhouse",
        location="Seattle, WA",
        remote_policy="Hybrid",
        posted_minutes_ago=11,
        match_score=91,
        decision="APPLY_NOW",
        why=["Backend systems", "Python", "Distributed services", "Platform ownership"],
        recommended_resume="Backend_AI_v5.pdf",
        duplicate_sources=0,
        status="seen",
        alert_sent=True,
        apply_url="https://boards.greenhouse.io/stripe",
    ),
    JobOpportunity(
        id="scale-ai-agents-platform",
        company="Scale AI",
        title="Senior Software Engineer, Agents Platform",
        source="Greenhouse",
        location="San Francisco, CA",
        remote_policy="Hybrid",
        posted_minutes_ago=17,
        match_score=88,
        decision="REVIEW",
        why=["Agents", "Python", "Platform work", "Infrastructure"],
        recommended_resume="AI_Platform_v3.pdf",
        duplicate_sources=0,
        status="new",
        alert_sent=False,
        apply_url="https://boards.greenhouse.io/scaleai",
    ),
    JobOpportunity(
        id="figma-core-infra",
        company="Figma",
        title="Platform Engineer, Core Infrastructure",
        source="Greenhouse",
        location="Remote, US",
        remote_policy="Remote",
        posted_minutes_ago=23,
        match_score=84,
        decision="REVIEW",
        why=["Platform engineering", "Python", "Reliability"],
        recommended_resume="Platform_v4.pdf",
        duplicate_sources=0,
        status="seen",
        alert_sent=False,
        apply_url="https://boards.greenhouse.io/figma",
    ),
    JobOpportunity(
        id="reddit-ads-infra",
        company="Reddit",
        title="Senior Backend Engineer, Ads Infrastructure",
        source="Greenhouse",
        location="Remote, US",
        remote_policy="Remote",
        posted_minutes_ago=31,
        match_score=79,
        decision="REVIEW",
        why=["Backend", "Infrastructure", "Large-scale systems"],
        recommended_resume="Backend_v6.pdf",
        duplicate_sources=1,
        status="dismissed",
        alert_sent=False,
        apply_url="https://boards.greenhouse.io/reddit",
    ),
    JobOpportunity(
        id="coinbase-distributed-systems",
        company="Coinbase",
        title="Senior Software Engineer, Distributed Systems",
        source="Greenhouse",
        location="Remote, US",
        remote_policy="Remote",
        posted_minutes_ago=44,
        match_score=72,
        decision="IGNORE",
        why=["General backend overlap", "Scale signal"],
        recommended_resume="Distributed_Systems_v2.pdf",
        duplicate_sources=0,
        status="skipped",
        alert_sent=False,
        apply_url="https://boards.greenhouse.io/coinbase",
    ),
]

COMPANIES: list[CompanyPreference] = build_recommended_company_preferences()

ROLE_FAMILIES: list[RolePreference] = [RolePreference(label=label, enabled=True) for label in DEFAULT_ROLE_FAMILIES]

ROLES: list[RolePreference] = [RolePreference(label=label, enabled=True) for label in DEFAULT_TARGET_ROLES]

WORK_ARRANGEMENTS: list[RolePreference] = [RolePreference(label=label, enabled=True) for label in DEFAULT_WORK_ARRANGEMENTS]

EXPERIENCE_LEVELS: list[RolePreference] = [RolePreference(label=label, enabled=True) for label in DEFAULT_EXPERIENCE_LEVELS]

WATCHLISTS: list[Watchlist] = [
    Watchlist(
        id="priority-teams",
        name="Priority Teams",
        enabled=True,
        terms=[
            WatchlistTerm(id="azure-ai", term="Azure AI", company="Microsoft", enabled=True),
            WatchlistTerm(id="copilot", term="Copilot", company="Microsoft", enabled=True),
            WatchlistTerm(id="databricks-ai", term="Databricks AI", company="Databricks", enabled=True),
            WatchlistTerm(id="openai-platform", term="OpenAI Platform", company="OpenAI", enabled=True),
            WatchlistTerm(id="anthropic-infrastructure", term="Anthropic Infrastructure", company="Anthropic", enabled=True),
        ],
    )
]

NOTIFICATIONS: list[NotificationChannel] = [
    NotificationChannel(channel="telegram", enabled=True, destination="@abhishek_job_radar"),
    NotificationChannel(channel="email", enabled=False, destination="Primary inbox"),
    NotificationChannel(channel="slack", enabled=False, destination="#job-radar"),
    NotificationChannel(channel="desktop", enabled=False, destination="Local desktop notifications"),
]

_SOURCE_STATUS_OVERRIDES: dict[str, dict[str, object]] = {
    "greenhouse": {
        "state": "healthy",
        "new_jobs_today": 12,
        "jobs_collected": 48,
        "last_run_minutes_ago": 1,
        "retries_today": 1,
        "average_runtime_seconds": 3,
        "last_successful_sync": "2026-07-18T08:24:00+00:00",
    },
    "lever": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "ashby": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "workday": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "smartrecruiters": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "icims": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "jobvite": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "oracle-recruiting-cloud": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "successfactors": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "google-careers": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
    "amazon-jobs": {
        "state": "healthy",
        "new_jobs_today": 0,
        "jobs_collected": 0,
        "last_run_minutes_ago": None,
        "retries_today": 0,
        "average_runtime_seconds": None,
        "last_successful_sync": None,
    },
}


def _seed_source_status(connector_key: str) -> SourceStatus:
    definition = next(
        connector
        for connector in build_default_registry().list_definitions()
        if connector.key == connector_key
    )
    catalog_companies = [company for company in COMPANIES if company.connector == definition.key]
    enabled_companies = [
        company
        for company in catalog_companies
        if company.enabled and (definition.key != "greenhouse" or bool(company.external_identifier.strip()))
    ]
    cadence_minutes = min((company.poll_interval_minutes for company in enabled_companies), default=5)
    overrides = _SOURCE_STATUS_OVERRIDES.get(definition.key, {})
    last_successful_sync = overrides.get("last_successful_sync")
    next_scheduled_poll = None
    if isinstance(last_successful_sync, str):
        last_sync_at = datetime.fromisoformat(last_successful_sync.replace("Z", "+00:00"))
        if last_sync_at.tzinfo is None:
            last_sync_at = last_sync_at.replace(tzinfo=timezone.utc)
        next_scheduled_poll = (last_sync_at + timedelta(minutes=cadence_minutes)).isoformat()
    return SourceStatus(
        id=f"source-{definition.key}",
        source=definition.display_name,
        connector_key=definition.key,
        layer=definition.layer,
        admin_status=definition.admin_status,
        enabled=bool(enabled_companies),
        rollout_stage=definition.rollout_stage,
        state=str(overrides.get("state", "healthy")),  # type: ignore[arg-type]
        cadence_minutes=cadence_minutes,
        new_jobs_today=int(overrides.get("new_jobs_today", 0)),
        last_run_minutes_ago=overrides.get("last_run_minutes_ago"),  # type: ignore[arg-type]
        retries_today=int(overrides.get("retries_today", 0)),
        last_successful_sync=last_successful_sync if isinstance(last_successful_sync, str) else None,
        jobs_collected=int(overrides.get("jobs_collected", 0)),
        companies_enabled=len(enabled_companies),
        catalog_company_count=len(catalog_companies),
        average_runtime_seconds=overrides.get("average_runtime_seconds"),  # type: ignore[arg-type]
        last_failed_sync=None,
        next_scheduled_poll=next_scheduled_poll,
        lag_reason=None,
    )


SOURCES: list[SourceStatus] = [
    _seed_source_status(definition.key) for definition in build_default_registry().list_definitions()
]

ALERTS: list[AlertEvent] = [
    AlertEvent(
        id="alert-databricks-telegram",
        channel="telegram",
        company="Databricks",
        title="Senior Software Engineer, ML Platform",
        match_score=94,
        decision="APPLY_NOW",
        posted_minutes_ago=4,
        sent_minutes_ago=1,
        why=["Distributed Systems", "Python", "ML platform", "Backend"],
        recommended_resume="Backend_AI_v5.pdf",
        apply_url="https://boards.greenhouse.io/databricks",
    ),
    AlertEvent(
        id="alert-stripe-telegram",
        channel="telegram",
        company="Stripe",
        title="Senior Backend Engineer, Payments Platform",
        match_score=91,
        decision="APPLY_NOW",
        posted_minutes_ago=11,
        sent_minutes_ago=6,
        why=["Backend systems", "Python", "Distributed services", "Platform ownership"],
        recommended_resume="Backend_AI_v5.pdf",
        apply_url="https://boards.greenhouse.io/stripe",
    ),
]

SETTINGS = ScoutSettings(
    primary_connector="Greenhouse",
    apply_now_threshold_score=90,
    review_threshold_score=75,
    polling_interval_minutes=5,
    companies=COMPANIES,
    roles=ROLES,
    notifications=NOTIFICATIONS,
    role_families=ROLE_FAMILIES,
    work_arrangements=WORK_ARRANGEMENTS,
    experience_levels=EXPERIENCE_LEVELS,
    excluded_keywords=list(DEFAULT_EXCLUDED_KEYWORDS),
    watchlists=WATCHLISTS,
    minimum_match_score=90,
    selected_country="US",
    alert_freshness_hours=6,
    recovery_alert_freshness_hours=24 * 7,
    dashboard_freshness_hours=24,
    resume_variants=["Backend_AI_v5.pdf", "Platform_v4.pdf", "Distributed_Systems_v2.pdf"],
    initial_alert_window_hours=24,
    initial_sync_openai_job_limit=20,
    initial_sync_max_alerts=5,
)
