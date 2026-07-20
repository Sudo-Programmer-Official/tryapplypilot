from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.job_metadata import matches_country_preference
from app.db.client import connection
from app.runtime import get_runtime
from app.scheduler_service import SchedulerStatusSnapshot, get_scheduler_service

SOURCE_LAYER_LABELS = {
    "official_ats": "Official ATS",
    "company_careers": "Company Careers",
    "job_aggregator": "Job Aggregators",
    "discovery_agent": "Discovery Agent",
}

CONNECTOR_STATUS_LABELS = {
    "live": "Live",
    "beta": "Beta",
    "planned": "Planned",
    "disabled": "Disabled",
}


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


def _build_source_layer_summary(sources: list[Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for layer, label in SOURCE_LAYER_LABELS.items():
        layer_sources = [source for source in sources if source.layer == layer]
        if not layer_sources:
            continue
        summary.append(
            {
                "layer": layer,
                "label": label,
                "connectors_registered": len(layer_sources),
                "connectors_enabled": sum(1 for source in layer_sources if source.enabled),
                "connectors_live": sum(1 for source in layer_sources if source.admin_status == "live"),
                "connectors_beta": sum(1 for source in layer_sources if source.admin_status == "beta"),
                "connectors_planned": sum(1 for source in layer_sources if source.admin_status == "planned"),
                "companies_enabled": sum(source.companies_enabled for source in layer_sources),
                "catalog_company_count": sum(source.catalog_company_count for source in layer_sources),
                "jobs_collected_today": sum(source.jobs_collected for source in layer_sources),
            }
        )
    return summary


def _build_connector_roadmap(sources: list[Any]) -> list[dict[str, Any]]:
    roadmap: list[dict[str, Any]] = []
    for status, label in CONNECTOR_STATUS_LABELS.items():
        grouped_sources = [source for source in sources if source.admin_status == status]
        if not grouped_sources:
            continue
        roadmap.append(
            {
                "status": status,
                "label": label,
                "count": len(grouped_sources),
                "connectors": [
                    {
                        "key": source.connector_key,
                        "source": source.source,
                        "layer": source.layer,
                        "layer_label": SOURCE_LAYER_LABELS.get(source.layer, source.layer),
                        "enabled": source.enabled,
                        "state": source.state,
                        "companies_enabled": source.companies_enabled,
                        "catalog_company_count": source.catalog_company_count,
                        "last_successful_sync": source.last_successful_sync,
                    }
                    for source in grouped_sources
                ],
            }
        )
    return roadmap


async def list_jobs(
    min_score: int | None = None,
    company: str | None = None,
    status: str | None = None,
    max_age_hours: int | None = None,
    query: str | None = None,
    decision: str | None = None,
    sort_by: str = "highest_match",
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
    if decision is not None:
        decision_key = decision.casefold()
        jobs = [job for job in jobs if str(job["decision"]).casefold() == decision_key]
    if status is not None:
        status_key = status.casefold()
        jobs = [job for job in jobs if str(job["status"]).casefold() == status_key]
    if query is not None and query.strip():
        query_key = query.casefold()
        jobs = [
            job
            for job in jobs
            if query_key
            in " ".join(
                [
                    str(job.get("company") or ""),
                    str(job.get("title") or ""),
                    str(job.get("source") or ""),
                    str(job.get("location") or ""),
                    str(job.get("country_display") or ""),
                    str(job.get("remote_policy") or ""),
                    str(job.get("recommendation") or ""),
                    " ".join(str(item) for item in list(job.get("why") or [])),
                ]
            ).casefold()
        ]
    if sort_by in {"newest", "recently_updated"}:
        return sorted(jobs, key=lambda job: (int(job["posted_minutes_ago"]), -int(job["match_score"])))
    if sort_by == "company":
        return sorted(jobs, key=lambda job: (str(job["company"]).casefold(), -int(job["match_score"]), int(job["posted_minutes_ago"])))
    return sorted(jobs, key=lambda job: (-int(job["match_score"]), int(job["posted_minutes_ago"])))


async def list_jobs_page(
    min_score: int | None = None,
    company: str | None = None,
    status: str | None = None,
    max_age_hours: int | None = None,
    query: str | None = None,
    decision: str | None = None,
    sort_by: str = "highest_match",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    jobs = await list_jobs(
        min_score=min_score,
        company=company,
        status=status,
        max_age_hours=max_age_hours,
        query=query,
        decision=decision,
        sort_by=sort_by,
    )
    total = len(jobs)
    safe_offset = min(max(offset, 0), total)
    safe_limit = max(limit, 1)
    items = jobs[safe_offset : safe_offset + safe_limit]
    return {
        "items": items,
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": safe_offset + len(items) < total,
    }


async def get_job(job_id: str) -> dict[str, Any] | None:
    job = await get_runtime().repositories.jobs.get(job_id)
    if job is None:
        return None
    return job.to_dict()


async def build_dashboard_snapshot(now: datetime | None = None) -> dict[str, Any]:
    runtime = get_runtime()
    current_time = now or datetime.now(timezone.utc)
    settings = await runtime.repositories.settings.get()
    jobs = (
        await list_jobs_page(
            max_age_hours=settings.dashboard_freshness_hours,
            limit=12,
            offset=0,
        )
    )["items"]
    alerts = await runtime.repositories.alerts.list()
    alerts = [
        alert
        for alert in alerts
        if matches_country_preference(alert.country_code, settings.selected_country)
    ]
    sources = await runtime.repositories.sources.list()
    if runtime.database.connected:
        async with connection() as conn:
            inventory_row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE lifecycle_status = 'active') AS active_inventory,
                    COUNT(*) FILTER (WHERE lifecycle_status = 'stale') AS stale_inventory,
                    COUNT(*) FILTER (WHERE lifecycle_status = 'closed') AS closed_inventory,
                    COUNT(*) FILTER (WHERE lifecycle_status = 'expired') AS expired_inventory,
                    COUNT(*) FILTER (WHERE lifecycle_status = 'archived') AS archived_inventory,
                    COUNT(*) FILTER (WHERE first_seen_at >= date_trunc('day', NOW())) AS new_today_inventory,
                    COUNT(*) AS total_inventory
                FROM jobs
                """
            )
            collected_lifetime = int(await conn.fetchval("SELECT COALESCE(SUM(jobs_inserted), 0) FROM connector_runs") or 0)
            try:
                estimated_storage_bytes = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(pg_total_relation_size(oid)), 0)
                    FROM pg_class
                    WHERE relname = ANY($1::text[])
                    """,
                    ["jobs", "connector_runs", "alerts", "user_alerts", "job_matches", "saved_jobs"],
                )
            except Exception:  # noqa: BLE001
                estimated_storage_bytes = None
    else:
        inventory_row = {
            "active_inventory": 0,
            "stale_inventory": 0,
            "closed_inventory": 0,
            "expired_inventory": 0,
            "archived_inventory": 0,
            "new_today_inventory": 0,
            "total_inventory": 0,
        }
        collected_lifetime = 0
        estimated_storage_bytes = None
    apply_now_threshold = settings.apply_now_threshold_score
    review_threshold = settings.review_threshold_score
    apply_now_jobs = [job for job in jobs if str(job["decision"]) == "APPLY_NOW"]
    review_jobs = [job for job in jobs if str(job["decision"]) == "REVIEW"]
    ignore_jobs = [job for job in jobs if str(job["decision"]) == "IGNORE"]
    latest_alert = alerts[0].to_dict() if alerts else None
    enabled_companies = [company for company in settings.companies if company.enabled]
    live_sources = [source for source in sources if source.enabled and source.rollout_stage == "live"]
    next_sources = [source for source in sources if source.rollout_stage == "next"]
    source_coverage = _build_source_layer_summary(sources)
    connector_roadmap = _build_connector_roadmap(sources)
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
            "name": "TryApplyPilot",
            "phase": "Internet Job Discovery Engine",
            "goal": "If a relevant software or AI job becomes public anywhere online, detect it within minutes.",
            "focus": "Official ATS first, then company careers, then aggregators and autonomous discovery.",
            "implementation_order": "Official ATS -> Company Careers -> Job Aggregators -> Discovery Agent.",
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
            "beta_connectors": sum(1 for source in sources if source.admin_status == "beta"),
            "planned_connectors": sum(1 for source in sources if source.admin_status == "planned"),
            "polling_interval_minutes": settings.polling_interval_minutes,
            "notification_sla_minutes": 5,
            "apply_now_threshold_score": apply_now_threshold,
            "review_threshold_score": review_threshold,
            "active_inventory": int(inventory_row["active_inventory"] or 0),
            "stale_inventory": int(inventory_row["stale_inventory"] or 0),
            "closed_inventory": int(inventory_row["closed_inventory"] or 0),
            "expired_inventory": int(inventory_row["expired_inventory"] or 0),
            "archived_inventory": int(inventory_row["archived_inventory"] or 0),
            "collected_lifetime": collected_lifetime,
            "new_today_inventory": int(inventory_row["new_today_inventory"] or 0),
            "estimated_storage_bytes": int(estimated_storage_bytes) if estimated_storage_bytes is not None else None,
        },
        "notification_preview": latest_alert,
        "jobs": jobs,
        "alerts": [alert.to_dict() for alert in alerts],
        "sources": [source.to_dict() for source in sources],
        "source_coverage": source_coverage,
        "connector_roadmap": connector_roadmap,
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
            "source_coverage": source_coverage,
            "connector_roadmap": connector_roadmap,
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
    source_layers = _build_source_layer_summary(sources)
    connector_roadmap = _build_connector_roadmap(sources)

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
        "source_layers": source_layers,
        "connector_roadmap": connector_roadmap,
        "connectors": [
            {
                "connector_key": source.connector_key,
                "source": source.source,
                "layer": source.layer,
                "admin_status": source.admin_status,
                "enabled": source.enabled,
                "rollout_stage": source.rollout_stage,
                "state": source.state,
                "companies_enabled": source.companies_enabled,
                "catalog_company_count": source.catalog_company_count,
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
