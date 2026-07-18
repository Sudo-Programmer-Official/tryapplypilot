from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.job_metadata import matches_country_preference
from app.runtime import get_runtime
from app.scheduler_service import SchedulerStatusSnapshot, get_scheduler_service


def _component_detail(status: str, healthy: str, lagging: str, degraded: str) -> str:
    if status == "healthy":
        return healthy
    if status == "lagging":
        return lagging
    return degraded


def _build_scheduler_status(
    *,
    current_time: datetime,
    polling_interval_minutes: int,
    active_source: dict[str, Any] | None,
) -> tuple[str, str, str | None, str | None]:
    if active_source is None:
        return ("lagging", "No live source has reported a scheduler heartbeat yet.", None, None)

    last_poll = active_source.get("last_successful_sync")
    next_poll = None
    if last_poll is not None:
        last_poll_at = datetime.fromisoformat(str(last_poll))
        next_poll = (last_poll_at + timedelta(minutes=polling_interval_minutes)).isoformat()
    last_run_minutes_ago = active_source.get("last_run_minutes_ago")
    if last_run_minutes_ago is None:
        return ("lagging", "Scheduler has not completed its first sync yet.", last_poll, next_poll)
    if int(last_run_minutes_ago) > polling_interval_minutes * 2:
        return ("lagging", "Scheduler is behind the 5-minute polling target.", last_poll, next_poll)
    return ("healthy", f"Next poll due within {polling_interval_minutes} minutes.", last_poll, next_poll)


def _minutes_until(instant: str | None, *, current_time: datetime) -> int | None:
    if instant is None:
        return None
    try:
        date_value = datetime.fromisoformat(instant)
    except ValueError:
        return None
    if date_value.tzinfo is None:
        date_value = date_value.replace(tzinfo=timezone.utc)
    delta_seconds = (date_value - current_time).total_seconds()
    return max(0, int(delta_seconds // 60))


def _build_scheduler_snapshot(
    *,
    current_time: datetime,
    polling_interval_minutes: int,
    active_source: dict[str, Any] | None,
) -> SchedulerStatusSnapshot:
    service = get_scheduler_service()
    if service is not None:
        return service.status()

    _, _, last_poll_at, next_poll_at = _build_scheduler_status(
        current_time=current_time,
        polling_interval_minutes=polling_interval_minutes,
        active_source=active_source,
    )
    return SchedulerStatusSnapshot(
        running=False,
        cycle_state="stopped",
        polling_interval_minutes=polling_interval_minutes,
        started_at=None,
        last_run_started_at=last_poll_at,
        last_run=last_poll_at,
        next_run=next_poll_at,
        last_duration_seconds=None,
        jobs_collected=int(active_source.get("jobs_collected", 0)) if active_source is not None else 0,
        jobs_inserted=int(active_source.get("new_jobs_today", 0)) if active_source is not None else 0,
        jobs_matched=0,
        notifications_sent=0,
        errors=0,
        current_connector=active_source.get("source") if active_source is not None else None,
        last_error=None,
    )


def _scheduler_component(
    scheduler: SchedulerStatusSnapshot,
    *,
    current_time: datetime,
) -> tuple[str, str]:
    if not scheduler.running:
        return ("degraded", "Scheduler service is not running.")
    if scheduler.cycle_state == "running":
        return ("healthy", "A poll cycle is running now.")
    if scheduler.last_run is None:
        return ("lagging", "Scheduler started and is waiting for the first completed poll.")
    next_run_minutes = _minutes_until(scheduler.next_run, current_time=current_time)
    if next_run_minutes is not None and next_run_minutes == 0:
        return ("healthy", "Next poll is due now.")
    if next_run_minutes is not None:
        return ("healthy", f"Next poll due within {next_run_minutes} minutes.")
    return ("healthy", "Scheduler is running on the configured cadence.")


async def list_jobs(
    min_score: int | None = None,
    company: str | None = None,
    status: str | None = None,
    max_age_hours: int | None = None,
) -> list[dict[str, Any]]:
    runtime = get_runtime()
    settings = await runtime.repositories.settings.get()
    jobs = [job.to_dict() for job in await runtime.repositories.jobs.list()]
    jobs = [
        job
        for job in jobs
        if matches_country_preference(str(job.get("country_code")) if job.get("country_code") is not None else None, settings.selected_country)
    ]
    if max_age_hours is not None:
        jobs = [job for job in jobs if int(job["posted_minutes_ago"]) <= max_age_hours * 60]
    if min_score is not None:
        jobs = [job for job in jobs if int(job["match_score"]) >= min_score]
    if company is not None:
        company_key = company.casefold()
        jobs = [job for job in jobs if str(job["company"]).casefold() == company_key]
    if status is not None:
        status_key = status.casefold()
        jobs = [job for job in jobs if str(job["status"]).casefold() == status_key]
    return sorted(jobs, key=lambda job: (-int(job["match_score"]), int(job["posted_minutes_ago"])))


async def get_job(job_id: str) -> dict[str, Any] | None:
    job = await get_runtime().repositories.jobs.get(job_id)
    if job is None:
        return None
    return job.to_dict()


async def build_dashboard_snapshot(now: datetime | None = None) -> dict[str, Any]:
    runtime = get_runtime()
    current_time = now or datetime.now(timezone.utc)
    settings = await runtime.repositories.settings.get()
    jobs = await list_jobs(max_age_hours=settings.dashboard_freshness_hours)
    alerts = await runtime.repositories.alerts.list()
    alerts = [
        alert
        for alert in alerts
        if matches_country_preference(alert.country_code, settings.selected_country)
    ]
    sources = await runtime.repositories.sources.list()
    apply_now_threshold = settings.apply_now_threshold_score
    review_threshold = settings.review_threshold_score
    apply_now_jobs = [job for job in jobs if str(job["decision"]) == "APPLY_NOW"]
    review_jobs = [job for job in jobs if str(job["decision"]) == "REVIEW"]
    ignore_jobs = [job for job in jobs if str(job["decision"]) == "IGNORE"]
    latest_alert = alerts[0].to_dict() if alerts else None
    enabled_companies = [company for company in settings.companies if company.enabled]
    live_sources = [source for source in sources if source.enabled and source.rollout_stage == "live"]
    next_sources = [source for source in sources if source.rollout_stage == "next"]
    active_source = live_sources[0] if live_sources else None
    scheduler = _build_scheduler_snapshot(
        current_time=current_time,
        polling_interval_minutes=settings.polling_interval_minutes,
        active_source=active_source.to_dict() if active_source is not None else None,
    )
    scheduler_state, scheduler_detail = _scheduler_component(scheduler, current_time=current_time)
    agent_state = "healthy"
    if scheduler_state == "degraded":
        agent_state = "degraded"
    elif scheduler_state == "lagging":
        agent_state = "lagging"
    elif any(source.state == "degraded" for source in live_sources):
        agent_state = "degraded"
    elif any(source.state == "lagging" for source in live_sources):
        agent_state = "lagging"
    last_poll_at = scheduler.last_run
    next_poll_at = scheduler.next_run
    total_new_today = sum(source.new_jobs_today for source in live_sources)
    last_run_minutes_ago = (
        max(0, int((current_time - datetime.fromisoformat(scheduler.last_run)).total_seconds() // 60))
        if scheduler.last_run is not None
        else (active_source.last_run_minutes_ago if active_source is not None else settings.polling_interval_minutes)
    )
    next_run_minutes = _minutes_until(scheduler.next_run, current_time=current_time)

    return {
        "generated_at": current_time.isoformat(),
        "product": {
            "name": "AI Job Radar",
            "phase": "Phase 1 MVP",
            "goal": "Never miss a high-quality job again.",
            "focus": "One real source end-to-end before expanding connector coverage.",
            "implementation_order": "Postgres -> Greenhouse -> Score -> Telegram -> Dashboard.",
        },
        "agent": {
            "name": "Market Scout Agent",
            "state": agent_state,
            "current_connector": scheduler.current_connector or settings.primary_connector,
            "polling_interval_minutes": settings.polling_interval_minutes,
            "apply_now_threshold_score": apply_now_threshold,
            "review_threshold_score": review_threshold,
            "last_run_minutes_ago": last_run_minutes_ago,
            "next_run_minutes": next_run_minutes if next_run_minutes is not None else settings.polling_interval_minutes,
            "workflow": ["Collect", "Normalize", "Deduplicate", "Score", "Notify", "Sleep"],
        },
        "summary": {
            "todays_jobs": len(jobs),
            "apply_now_queue": len(apply_now_jobs),
            "review_queue": len(review_jobs),
            "ignore_queue": len(ignore_jobs),
            "already_seen": sum(1 for job in jobs if str(job["status"]) == "seen"),
            "dismissed": sum(1 for job in jobs if str(job["status"]) == "dismissed"),
            "skipped": sum(1 for job in jobs if str(job["status"]) == "skipped"),
            "alerts_sent": sum(1 for job in jobs if bool(job["alert_sent"])),
            "configured_companies": len(enabled_companies),
            "live_connectors": len(live_sources),
            "next_connectors": len(next_sources),
            "polling_interval_minutes": settings.polling_interval_minutes,
            "notification_sla_minutes": 5,
            "apply_now_threshold_score": apply_now_threshold,
            "review_threshold_score": review_threshold,
        },
        "notification_preview": latest_alert,
        "jobs": jobs,
        "alerts": [alert.to_dict() for alert in alerts],
        "sources": [source.to_dict() for source in sources],
        "settings": settings.to_dict(),
        "scheduler": scheduler.to_dict(),
        "system_status": {
            "components": [
                {
                    "key": "backend",
                    "label": "Backend",
                    "status": "healthy",
                    "detail": "FastAPI dashboard and API are responding locally.",
                },
                {
                    "key": "database",
                    "label": "Database",
                    "status": "healthy" if runtime.database.connected else "degraded",
                    "detail": (
                        f"Connected to {runtime.settings.database.name}."
                        if runtime.database.connected
                        else "Database connection is not available."
                    ),
                },
                {
                    "key": "scheduler",
                    "label": "Scheduler",
                    "status": scheduler_state,
                    "detail": scheduler_detail,
                },
                {
                    "key": "connector",
                    "label": settings.primary_connector,
                    "status": active_source.state if active_source is not None else "lagging",
                    "detail": (
                        f"Last sync {active_source.last_run_minutes_ago} minutes ago."
                        if active_source is not None and active_source.last_run_minutes_ago is not None
                        else "Waiting on the first live sync."
                    ),
                },
                {
                    "key": "openai",
                    "label": "OpenAI",
                    "status": "healthy" if runtime.settings.openai.enabled else "lagging",
                    "detail": (
                        f"{runtime.settings.openai.model} configured for match scoring."
                        if runtime.settings.openai.enabled
                        else "OpenAI is not configured."
                    ),
                },
                {
                    "key": "telegram",
                    "label": "Telegram",
                    "status": "healthy" if runtime.settings.telegram.delivery_configured else "lagging",
                    "detail": (
                        "Bot is configured for user-linked Telegram delivery."
                        if runtime.settings.telegram.delivery_configured
                        else "Telegram bot credentials are missing."
                    ),
                },
            ],
            "stats": {
                "running": scheduler.running,
                "jobs_collected": scheduler.jobs_collected,
                "jobs_matched": scheduler.jobs_matched,
                "new_today": total_new_today,
                "notifications_sent": scheduler.notifications_sent,
                "errors": scheduler.errors,
                "last_poll_at": last_poll_at,
                "next_poll_at": next_poll_at,
            },
        },
        "infrastructure": {
            "database_backend": runtime.database.backend,
            "database_mode": runtime.database.mode,
            "schema_tables": list(runtime.database.schema_tables),
            "connectors_registered": [connector.to_dict() for connector in runtime.connectors.list_definitions()],
            "notifications": {
                "telegram_bot_configured": runtime.settings.telegram.bot_configured,
                "telegram_chat_configured": bool(runtime.settings.telegram.chat_id),
                "telegram_delivery_configured": runtime.settings.telegram.delivery_configured,
            },
            "openai": {
                "configured": runtime.settings.openai.enabled,
                "model": runtime.settings.openai.model,
            },
        },
    }


async def build_health_snapshot(now: datetime | None = None) -> dict[str, Any]:
    runtime = get_runtime()
    current_time = now or datetime.now(timezone.utc)
    settings = await runtime.repositories.settings.get()
    sources = await runtime.repositories.sources.list()
    live_sources = [source for source in sources if source.enabled]
    active_source = live_sources[0] if live_sources else None
    scheduler = _build_scheduler_snapshot(
        current_time=current_time,
        polling_interval_minutes=settings.polling_interval_minutes,
        active_source=active_source.to_dict() if active_source is not None else None,
    )
    scheduler_state, scheduler_detail = _scheduler_component(scheduler, current_time=current_time)
    last_poll_at = scheduler.last_run
    next_poll_at = scheduler.next_run
    health_state = "ok"
    if scheduler_state == "degraded":
        health_state = "degraded"
    elif scheduler_state == "lagging":
        health_state = "lagging"
    elif any(source.state == "degraded" for source in live_sources):
        health_state = "degraded"
    elif any(source.state == "lagging" for source in live_sources):
        health_state = "lagging"

    return {
        "status": health_state,
        "service": "ai-job-radar-api",
        "generated_at": current_time.isoformat(),
        "agent": {
            "name": "Market Scout Agent",
            "current_connector": settings.primary_connector,
            "polling_interval_minutes": settings.polling_interval_minutes,
        },
        "scheduler": {
            "running": scheduler.running,
            "cycle_state": scheduler.cycle_state,
            "status": scheduler_state,
            "detail": scheduler_detail,
            "last_poll_at": last_poll_at,
            "next_poll_at": next_poll_at,
            "jobs_collected": scheduler.jobs_collected,
            "jobs_matched": scheduler.jobs_matched,
            "notifications_sent": scheduler.notifications_sent,
            "errors": scheduler.errors,
            "current_connector": scheduler.current_connector,
            "last_error": scheduler.last_error,
        },
        "database": {
            "backend": runtime.database.backend,
            "target": runtime.database.target,
            "name": runtime.settings.database.name,
            "connected": runtime.database.connected,
            "mode": runtime.database.mode,
            "schema_tables": list(runtime.database.schema_tables),
        },
        "notifications": {
            "telegram_bot_configured": runtime.settings.telegram.bot_configured,
            "telegram_chat_configured": bool(runtime.settings.telegram.chat_id),
            "telegram_delivery_configured": runtime.settings.telegram.delivery_configured,
        },
        "openai": {
            "configured": runtime.settings.openai.enabled,
            "model": runtime.settings.openai.model,
        },
        "connectors": [
            {
                "source": source.source,
                "enabled": source.enabled,
                "rollout_stage": source.rollout_stage,
                "state": source.state,
                "last_run_minutes_ago": source.last_run_minutes_ago,
                "last_successful_sync": source.last_successful_sync,
            }
            for source in sources
        ],
    }


async def get_settings() -> dict[str, Any]:
    return (await get_runtime().repositories.settings.get()).to_dict()


async def list_alerts() -> list[dict[str, Any]]:
    runtime = get_runtime()
    settings = await runtime.repositories.settings.get()
    alerts = await runtime.repositories.alerts.list()
    return [
        alert.to_dict()
        for alert in alerts
        if matches_country_preference(alert.country_code, settings.selected_country)
    ]


async def list_sources() -> list[dict[str, Any]]:
    return [source.to_dict() for source in await get_runtime().repositories.sources.list()]
