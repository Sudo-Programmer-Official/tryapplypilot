from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

from asyncpg import Record

from app.catalog import build_effective_app_settings, build_scout_settings
from app.config import AppSettings, get_settings
from app.connectors.base import ConnectorDefinition
from app.connectors.registry import ConnectorRegistry
from app.db.client import connection
from app.domain import AlertEvent, JobOpportunity, ScoutSettings, SourceStatus
from app.job_metadata import (
    country_display,
    freshness_label,
    freshness_tone_from_minutes,
    infer_country_code,
    recommendation_label,
    recommendation_tone,
)
from app.repositories.interfaces import RadarRepositories


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


def _json_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
    return []


def _minutes_ago(instant: datetime | None, *, now: datetime) -> int:
    if instant is None:
        return 0
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return max(0, int((now - instant).total_seconds() // 60))


def _connector_source_label(connector_key: str) -> str:
    connector_name = connector_key.split(":", 1)[0]
    special_labels = {
        "greenhouse": "Greenhouse",
        "google-careers": "Google Careers",
        "microsoft-careers": "Microsoft Careers",
        "smartrecruiters": "SmartRecruiters",
        "company-api": "Company APIs",
    }
    if connector_name in special_labels:
        return special_labels[connector_name]
    return connector_name.replace("-", " ").title()


def _row_value(row: Record, key: str, default: object = None) -> object:
    try:
        return row[key]
    except KeyError:
        return default


def _job_from_row(row: Record, *, now: datetime, settings: AppSettings) -> JobOpportunity:
    published_at = row["published_at"] or row["first_seen_at"]
    metadata = _json_object(row["metadata"])
    posted_minutes_ago = _minutes_ago(published_at, now=now)
    inferred_country = infer_country_code(str(row["location"]), str(row["description_text"]))
    country_code = _row_value(row, "effective_country_code", metadata.get("country_code"))
    if inferred_country is not None:
        country_code = inferred_country
    elif not isinstance(country_code, str):
        country_code = None
    decision = str(_row_value(row, "effective_decision", row["decision"]))
    return JobOpportunity(
        id=row["job_id"],
        company=row["company"],
        title=row["title"],
        source=_connector_source_label(row["connector_key"]),
        location=row["location"],
        remote_policy=row["remote_policy"],
        posted_minutes_ago=posted_minutes_ago,
        match_score=int(_row_value(row, "effective_match_score", row["match_score"]) or 0),
        decision=decision,
        why=_json_list(_row_value(row, "effective_why", metadata.get("why", []))),
        recommended_resume=str(_row_value(row, "effective_recommended_resume", row["recommended_resume"])),
        duplicate_sources=int(row["duplicate_source_count"]),
        status=str(_row_value(row, "effective_status", row["job_status"])),
        alert_sent=bool(row["alert_sent"]),
        apply_url=row["apply_url"],
        gaps=_json_list(_row_value(row, "effective_gaps", metadata.get("gaps", []))),
        country_code=country_code,
        country_display=country_display(country_code),
        freshness_label=freshness_label(
            posted_minutes_ago,
            alert_freshness_hours=settings.radar.alert_freshness_hours,
            dashboard_freshness_hours=settings.radar.dashboard_freshness_hours,
        ),
        freshness_tone=freshness_tone_from_minutes(
            posted_minutes_ago,
            alert_freshness_hours=settings.radar.alert_freshness_hours,
            dashboard_freshness_hours=settings.radar.dashboard_freshness_hours,
        ),
        recommendation=recommendation_label(decision),
        recommendation_tone=recommendation_tone(decision),
    )


def _alert_from_row(row: Record, *, now: datetime, settings: AppSettings) -> AlertEvent:
    published_at = row["published_at"] or row["first_seen_at"]
    sent_at = row["sent_at"] or row["created_at"]
    payload = _json_object(row["payload"])
    job_metadata = _json_object(row["job_metadata"])
    posted_minutes_ago = _minutes_ago(published_at, now=now)
    inferred_country = infer_country_code(str(row["location"]), "")
    country_code = _row_value(row, "effective_country_code", payload.get("country_code"))
    if inferred_country is not None:
        country_code = inferred_country
    elif not isinstance(country_code, str):
        country_code = job_metadata.get("country_code")
    if not isinstance(country_code, str):
        country_code = None
    decision = str(_row_value(row, "effective_decision", row["decision"]))
    return AlertEvent(
        id=row["alert_id"],
        channel=row["channel"],
        company=row["company"],
        title=row["title"],
        match_score=int(_row_value(row, "effective_match_score", row["match_score"]) or 0),
        decision=decision,
        posted_minutes_ago=posted_minutes_ago,
        sent_minutes_ago=_minutes_ago(sent_at, now=now),
        why=_json_list(_row_value(row, "effective_why", payload.get("why", []))),
        recommended_resume=str(_row_value(row, "effective_recommended_resume", payload.get("recommended_resume", row["recommended_resume"]))),
        apply_url=row["apply_url"],
        gaps=_json_list(_row_value(row, "effective_gaps", payload.get("gaps", []))),
        country_code=country_code,
        country_display=country_display(country_code),
        freshness_label=freshness_label(
            posted_minutes_ago,
            alert_freshness_hours=settings.radar.alert_freshness_hours,
            dashboard_freshness_hours=settings.radar.dashboard_freshness_hours,
        ),
        freshness_tone=freshness_tone_from_minutes(
            posted_minutes_ago,
            alert_freshness_hours=settings.radar.alert_freshness_hours,
            dashboard_freshness_hours=settings.radar.dashboard_freshness_hours,
        ),
        recommendation=recommendation_label(decision),
        recommendation_tone=recommendation_tone(decision),
    )


@dataclass(frozen=True)
class PostgresJobsRepository:
    settings: AppSettings

    async def list(self) -> list[JobOpportunity]:
        now = datetime.now(timezone.utc)
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    j.*,
                    COALESCE(best_match.match_score, j.match_score) AS effective_match_score,
                    COALESCE(best_match.decision, j.decision) AS effective_decision,
                    COALESCE(best_match.recommended_resume, j.recommended_resume) AS effective_recommended_resume,
                    COALESCE(best_match.why, j.metadata->'why', '[]'::jsonb) AS effective_why,
                    COALESCE(best_match.gaps, j.metadata->'gaps', '[]'::jsonb) AS effective_gaps,
                    COALESCE(best_match.country_code, j.metadata->>'country_code') AS effective_country_code,
                    (
                        EXISTS (
                            SELECT 1
                            FROM user_alerts ua
                            WHERE ua.job_id = j.job_id
                              AND ua.alert_status = 'sent'
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM alerts a
                            WHERE a.job_id = j.job_id
                              AND a.alert_status = 'sent'
                        )
                    ) AS alert_sent
                FROM jobs j
                LEFT JOIN LATERAL (
                    SELECT
                        jm.match_score,
                        jm.decision,
                        jm.recommended_resume,
                        jm.why,
                        jm.gaps,
                        jm.country_code
                    FROM job_matches jm
                    WHERE jm.job_id = j.job_id
                    ORDER BY
                        CASE jm.decision
                            WHEN 'APPLY_NOW' THEN 0
                            WHEN 'REVIEW' THEN 1
                            ELSE 2
                        END,
                        jm.match_score DESC,
                        jm.updated_at DESC
                    LIMIT 1
                ) AS best_match ON TRUE
                WHERE COALESCE(j.published_at, j.first_seen_at) >= NOW() - INTERVAL '14 days'
                ORDER BY COALESCE(j.published_at, j.first_seen_at) DESC, COALESCE(best_match.match_score, j.match_score) DESC NULLS LAST
                LIMIT 250
                """
            )
        return [_job_from_row(row, now=now, settings=self.settings) for row in rows]

    async def get(self, job_id: str) -> JobOpportunity | None:
        now = datetime.now(timezone.utc)
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    j.*,
                    COALESCE(best_match.match_score, j.match_score) AS effective_match_score,
                    COALESCE(best_match.decision, j.decision) AS effective_decision,
                    COALESCE(best_match.recommended_resume, j.recommended_resume) AS effective_recommended_resume,
                    COALESCE(best_match.why, j.metadata->'why', '[]'::jsonb) AS effective_why,
                    COALESCE(best_match.gaps, j.metadata->'gaps', '[]'::jsonb) AS effective_gaps,
                    COALESCE(best_match.country_code, j.metadata->>'country_code') AS effective_country_code,
                    (
                        EXISTS (
                            SELECT 1
                            FROM user_alerts ua
                            WHERE ua.job_id = j.job_id
                              AND ua.alert_status = 'sent'
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM alerts a
                            WHERE a.job_id = j.job_id
                              AND a.alert_status = 'sent'
                        )
                    ) AS alert_sent
                FROM jobs j
                LEFT JOIN LATERAL (
                    SELECT
                        jm.match_score,
                        jm.decision,
                        jm.recommended_resume,
                        jm.why,
                        jm.gaps,
                        jm.country_code
                    FROM job_matches jm
                    WHERE jm.job_id = j.job_id
                    ORDER BY
                        CASE jm.decision
                            WHEN 'APPLY_NOW' THEN 0
                            WHEN 'REVIEW' THEN 1
                            ELSE 2
                        END,
                        jm.match_score DESC,
                        jm.updated_at DESC
                    LIMIT 1
                ) AS best_match ON TRUE
                WHERE j.job_id = $1
                """,
                job_id,
            )
        if row is None:
            return None
        return _job_from_row(row, now=now, settings=self.settings)


@dataclass(frozen=True)
class PostgresAlertsRepository:
    settings: AppSettings

    async def list(self) -> list[AlertEvent]:
        now = datetime.now(timezone.utc)
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM (
                    SELECT
                        ua.user_alert_id AS alert_id,
                        ua.channel,
                        COALESCE(jm.decision, ua.decision) AS effective_decision,
                        COALESCE(jm.match_score, j.match_score) AS effective_match_score,
                        COALESCE(jm.why, ua.payload->'why', '[]'::jsonb) AS effective_why,
                        COALESCE(jm.gaps, ua.payload->'gaps', '[]'::jsonb) AS effective_gaps,
                        COALESCE(jm.recommended_resume, ua.payload->>'recommended_resume', j.recommended_resume) AS effective_recommended_resume,
                        COALESCE(jm.country_code, ua.payload->>'country_code', j.metadata->>'country_code') AS effective_country_code,
                        ua.decision,
                        ua.payload,
                        ua.created_at,
                        ua.sent_at,
                        j.company,
                        j.title,
                        j.apply_url,
                        j.published_at,
                        j.first_seen_at,
                        j.location,
                        j.metadata AS job_metadata,
                        j.match_score,
                        j.recommended_resume
                    FROM user_alerts ua
                    INNER JOIN jobs j ON j.job_id = ua.job_id
                    LEFT JOIN job_matches jm ON jm.job_id = ua.job_id AND jm.user_id = ua.user_id

                    UNION ALL

                    SELECT
                        a.alert_id,
                        a.channel,
                        a.decision AS effective_decision,
                        j.match_score AS effective_match_score,
                        COALESCE(a.payload->'why', j.metadata->'why', '[]'::jsonb) AS effective_why,
                        COALESCE(a.payload->'gaps', j.metadata->'gaps', '[]'::jsonb) AS effective_gaps,
                        COALESCE(a.payload->>'recommended_resume', j.recommended_resume) AS effective_recommended_resume,
                        COALESCE(a.payload->>'country_code', j.metadata->>'country_code') AS effective_country_code,
                        a.decision,
                        a.payload,
                        a.created_at,
                        a.sent_at,
                        j.company,
                        j.title,
                        j.apply_url,
                        j.published_at,
                        j.first_seen_at,
                        j.location,
                        j.metadata AS job_metadata,
                        j.match_score,
                        j.recommended_resume
                    FROM alerts a
                    INNER JOIN jobs j ON j.job_id = a.job_id
                ) AS alert_rows
                ORDER BY created_at DESC
                LIMIT 100
                """,
            )
        return [_alert_from_row(row, now=now, settings=self.settings) for row in rows]


@dataclass(frozen=True)
class AggregatedSourcesRepository:
    settings: AppSettings
    registry: ConnectorRegistry

    async def list(self) -> list[SourceStatus]:
        effective_settings = await build_effective_app_settings(self.settings)
        async with connection() as conn:
            return [
                await self._build_source_status(conn, definition, effective_settings)
                for definition in self.registry.list_definitions()
            ]

    async def _build_source_status(self, conn, definition: ConnectorDefinition, settings: AppSettings) -> SourceStatus:
        key_prefix = f"{definition.key}:%"
        aggregate = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(jobs_inserted) FILTER (WHERE started_at >= date_trunc('day', NOW())), 0) AS new_jobs_today,
                COALESCE(SUM(jobs_fetched) FILTER (WHERE started_at >= date_trunc('day', NOW())), 0) AS jobs_collected,
                COALESCE(SUM(retries) FILTER (WHERE started_at >= date_trunc('day', NOW())), 0) AS retries_today,
                AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) FILTER (
                    WHERE run_status = 'succeeded' AND finished_at IS NOT NULL
                ) AS average_runtime_seconds,
                MAX(started_at) AS last_run_at,
                MAX(finished_at) FILTER (WHERE run_status = 'succeeded') AS last_successful_sync,
                MAX(finished_at) FILTER (WHERE run_status = 'failed') AS last_failed_sync
            FROM connector_runs
            WHERE connector_key = $1 OR connector_key LIKE $2
            """,
            definition.key,
            key_prefix,
        )
        latest_run = await conn.fetchrow(
            """
            SELECT run_status, started_at, finished_at, error_message
            FROM connector_runs
            WHERE connector_key = $1 OR connector_key LIKE $2
            ORDER BY started_at DESC
            LIMIT 1
            """,
            definition.key,
            key_prefix,
        )

        connector_companies = [
            company
            for company in settings.radar.companies
            if company.connector == definition.key
        ]
        runnable_companies = [
            company
            for company in connector_companies
            if company.enabled and (definition.key != "greenhouse" or bool(company.external_identifier.strip()))
        ]
        enabled = bool(runnable_companies)
        now = datetime.now(timezone.utc)
        last_run_at = aggregate["last_run_at"] if aggregate is not None else None
        last_successful_sync = aggregate["last_successful_sync"] if aggregate is not None else None
        last_failed_sync = aggregate["last_failed_sync"] if aggregate is not None else None
        last_run_minutes_ago = _minutes_ago(last_run_at, now=now) if last_run_at is not None else None
        retries_today = int(aggregate["retries_today"] or 0) if aggregate is not None else 0
        new_jobs_today = int(aggregate["new_jobs_today"] or 0) if aggregate is not None else 0
        jobs_collected = int(aggregate["jobs_collected"] or 0) if aggregate is not None else 0
        average_runtime_seconds = (
            int(float(aggregate["average_runtime_seconds"]))
            if aggregate is not None and aggregate["average_runtime_seconds"] is not None
            else None
        )
        cadence_minutes = min(
            (company.poll_interval_minutes for company in runnable_companies),
            default=settings.radar.polling_interval_minutes,
        )
        next_scheduled_poll = (
            (last_run_at + timedelta(minutes=cadence_minutes)).isoformat()
            if enabled and last_run_at is not None
            else None
        )

        state = "healthy"
        lag_reason = None
        if enabled and last_run_minutes_ago is None:
            state = "lagging"
            lag_reason = "Collector has not run yet."
        elif enabled and last_run_minutes_ago is not None and last_run_minutes_ago > settings.radar.polling_interval_minutes * 2:
            state = "lagging"
            lag_reason = "Collector is behind the 5-minute SLA."
        if enabled and latest_run is not None and latest_run["run_status"] == "failed":
            state = "degraded"
            lag_reason = latest_run["error_message"] or "Latest collector run failed."

        return SourceStatus(
            id=f"source-{definition.key}",
            source=definition.display_name,
            connector_key=definition.key,
            layer=definition.layer,
            admin_status=definition.admin_status,
            enabled=enabled,
            rollout_stage=definition.rollout_stage,
            state=state,
            cadence_minutes=cadence_minutes,
            new_jobs_today=new_jobs_today,
            last_run_minutes_ago=last_run_minutes_ago,
            retries_today=retries_today,
            last_successful_sync=last_successful_sync.isoformat() if last_successful_sync is not None else None,
            jobs_collected=jobs_collected,
            companies_enabled=len(runnable_companies),
            catalog_company_count=len(connector_companies),
            average_runtime_seconds=average_runtime_seconds,
            last_failed_sync=last_failed_sync.isoformat() if last_failed_sync is not None else None,
            next_scheduled_poll=next_scheduled_poll,
            lag_reason=lag_reason,
        )


@dataclass(frozen=True)
class StaticSettingsRepository:
    settings: AppSettings

    async def get(self) -> ScoutSettings:
        return await build_scout_settings(self.settings)


async def list_user_jobs(user_id: str, settings: AppSettings | None = None) -> list[JobOpportunity]:
    resolved_settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                j.*,
                jm.match_score AS effective_match_score,
                jm.decision AS effective_decision,
                jm.recommended_resume AS effective_recommended_resume,
                jm.why AS effective_why,
                jm.gaps AS effective_gaps,
                jm.country_code AS effective_country_code,
                jm.match_status AS effective_status,
                EXISTS (
                    SELECT 1
                    FROM user_alerts ua
                    WHERE ua.job_id = j.job_id
                      AND ua.user_id = jm.user_id
                      AND ua.alert_status = 'sent'
                ) AS alert_sent
            FROM job_matches jm
            INNER JOIN jobs j ON j.job_id = jm.job_id
            WHERE jm.user_id = $1
              AND COALESCE(j.published_at, j.first_seen_at) >= NOW() - INTERVAL '14 days'
            ORDER BY COALESCE(j.published_at, j.first_seen_at) DESC, jm.match_score DESC
            LIMIT 100
            """,
            user_id,
        )
    return [_job_from_row(row, now=now, settings=resolved_settings) for row in rows]


async def list_user_alerts(user_id: str, settings: AppSettings | None = None) -> list[AlertEvent]:
    resolved_settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ua.user_alert_id AS alert_id,
                ua.channel,
                COALESCE(jm.decision, ua.decision) AS effective_decision,
                COALESCE(jm.match_score, j.match_score) AS effective_match_score,
                COALESCE(jm.why, ua.payload->'why', '[]'::jsonb) AS effective_why,
                COALESCE(jm.gaps, ua.payload->'gaps', '[]'::jsonb) AS effective_gaps,
                COALESCE(jm.recommended_resume, ua.payload->>'recommended_resume', j.recommended_resume) AS effective_recommended_resume,
                COALESCE(jm.country_code, ua.payload->>'country_code', j.metadata->>'country_code') AS effective_country_code,
                ua.decision,
                ua.payload,
                ua.created_at,
                ua.sent_at,
                j.company,
                j.title,
                j.apply_url,
                j.published_at,
                j.first_seen_at,
                j.location,
                j.metadata AS job_metadata,
                j.match_score,
                j.recommended_resume
            FROM user_alerts ua
            INNER JOIN jobs j ON j.job_id = ua.job_id
            LEFT JOIN job_matches jm ON jm.job_id = ua.job_id AND jm.user_id = ua.user_id
            WHERE ua.user_id = $1
            ORDER BY ua.created_at DESC
            LIMIT 50
            """,
            user_id,
        )
    return [_alert_from_row(row, now=now, settings=resolved_settings) for row in rows]


def build_postgres_repositories(registry: ConnectorRegistry | None = None) -> RadarRepositories:
    settings = get_settings()
    resolved_registry = registry or ConnectorRegistry(connectors=())
    return RadarRepositories(
        jobs=PostgresJobsRepository(settings=settings),
        alerts=PostgresAlertsRepository(settings=settings),
        sources=AggregatedSourcesRepository(settings=settings, registry=resolved_registry),
        settings=StaticSettingsRepository(settings=settings),
    )
