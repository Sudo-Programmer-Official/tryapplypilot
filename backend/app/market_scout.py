from __future__ import annotations

import asyncio
from dataclasses import replace
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
import json
from typing import Awaitable, Callable
from uuid import uuid4, uuid5, NAMESPACE_URL

from app.audit_logs import record_audit_event
from app.catalog import build_effective_app_settings
from app.config import AppSettings, GreenhouseBoard, get_settings
from app.connectors.base import ConnectorCursor, NormalizedJobRecord
from app.connectors.greenhouse import GreenhouseJobConnector
from app.connectors.lever import LeverBoard, LeverJobConnector
from app.db.client import connection
from app.domain import CompanyPreference, UserAccount
from app.job_metadata import (
    country_display,
    freshness_label,
    infer_country_code,
    recommendation_label,
)
from app.logging_utils import get_logger
from app.notifications.telegram import send_message
from app.retry import RetryPolicy, retry_sync
from app.scoring import MatchResult, heuristic_score_job, score_job
from app.user_accounts import list_users
from app.user_matching import (
    alert_freshness_hours,
    alert_rule_allows_job,
    build_user_profile_text,
    build_user_matching_settings,
    filter_reason_for_user,
    minimum_match_score,
    telegram_connected,
)


@dataclass(frozen=True)
class ConnectorRunSummary:
    connector_key: str
    company: str
    jobs_fetched: int
    jobs_inserted: int
    jobs_updated: int
    jobs_matched: int
    alerts_sent: int
    alerts_failed: int
    failed: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "connector_key": self.connector_key,
            "company": self.company,
            "jobs_fetched": self.jobs_fetched,
            "jobs_inserted": self.jobs_inserted,
            "jobs_updated": self.jobs_updated,
            "jobs_matched": self.jobs_matched,
            "alerts_sent": self.alerts_sent,
            "alerts_failed": self.alerts_failed,
            "failed": self.failed,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class MarketScoutRunSummary:
    started_at: str
    finished_at: str
    runs: list[ConnectorRunSummary]

    @property
    def jobs_collected(self) -> int:
        return sum(run.jobs_fetched for run in self.runs)

    @property
    def jobs_inserted(self) -> int:
        return sum(run.jobs_inserted for run in self.runs)

    @property
    def jobs_updated(self) -> int:
        return sum(run.jobs_updated for run in self.runs)

    @property
    def jobs_matched(self) -> int:
        return sum(run.jobs_matched for run in self.runs)

    @property
    def alerts_sent(self) -> int:
        return sum(run.alerts_sent for run in self.runs)

    @property
    def alerts_failed(self) -> int:
        return sum(run.alerts_failed for run in self.runs)

    @property
    def connector_failures(self) -> int:
        return sum(1 for run in self.runs if run.failed)

    def to_dict(self) -> dict[str, object]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "runs": [run.to_dict() for run in self.runs],
            "jobs_collected": self.jobs_collected,
            "jobs_inserted": self.jobs_inserted,
            "jobs_updated": self.jobs_updated,
            "jobs_matched": self.jobs_matched,
            "alerts_sent": self.alerts_sent,
            "alerts_failed": self.alerts_failed,
            "connector_failures": self.connector_failures,
        }


@dataclass(frozen=True)
class UserMatchContext:
    user: UserAccount
    settings: AppSettings
    profile_text: str
    minimum_match_score: int
    freshness_hours: int


def _company_connector_run_key(company: CompanyPreference) -> str:
    connector_key = company.connector.strip().casefold()
    company_key = company.external_identifier.strip() or company.company.casefold().replace(" ", "-")
    return f"{connector_key}:{company_key}"


def _decision_rank(decision: str) -> int:
    if decision == "APPLY_NOW":
        return 0
    if decision == "REVIEW":
        return 1
    return 2


def _format_alert_message(
    job: NormalizedJobRecord,
    match: MatchResult,
    posted_minutes_ago: int,
    *,
    country_code: str | None,
    settings: AppSettings,
) -> str:
    strengths = "\n".join(f"• {escape(reason)}" for reason in match.top_strengths[:4])
    missing = "\n".join(f"⚠ {escape(reason)}" for reason in match.gaps[:3])
    apply_link = f'<a href="{escape(job.apply_url, quote=True)}">Apply Now</a>'
    return "\n".join(
        [
            "🚨 <b>High-Match Job</b>",
            "<b>Company</b>",
            escape(job.company),
            "<b>Role</b>",
            escape(job.title),
            escape(country_display(country_code)),
            "<b>🟢 Match</b>",
            f"{match.score}%",
            "<b>🕒 Freshness</b>",
            escape(
                freshness_label(
                    posted_minutes_ago,
                    alert_freshness_hours=settings.radar.alert_freshness_hours,
                    dashboard_freshness_hours=settings.radar.dashboard_freshness_hours,
                )
            ),
            "<b>🟢 Recommendation</b>",
            escape(recommendation_label(match.decision)),
            "<b>Why it matched</b>",
            strengths or "• General overlap",
            "<b>Missing</b>",
            missing or "• No critical gaps detected",
            "<b>Recommended Resume</b>",
            escape(match.recommended_resume),
            f"🔗 {apply_link}",
        ]
    )


def _json_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


class MarketScoutAgent:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.base_settings = settings or get_settings()
        self.settings = self.base_settings
        self.logger = get_logger("app.market_scout")
        self.retry_policy = RetryPolicy(
            max_attempts=self.settings.connectors.retry_attempts,
            base_delay_seconds=self.settings.connectors.base_retry_delay_seconds,
            max_delay_seconds=self.settings.connectors.max_retry_delay_seconds,
            backoff_multiplier=self.settings.connectors.backoff_multiplier,
        )

    async def run_once(self) -> MarketScoutRunSummary:
        self.settings = await build_effective_app_settings(self.base_settings)
        self.retry_policy = replace(
            self.retry_policy,
            max_attempts=self.settings.connectors.retry_attempts,
            base_delay_seconds=self.settings.connectors.base_retry_delay_seconds,
            max_delay_seconds=self.settings.connectors.max_retry_delay_seconds,
            backoff_multiplier=self.settings.connectors.backoff_multiplier,
        )
        started_at = datetime.now(timezone.utc)
        runs: list[ConnectorRunSummary] = []
        connector_groups, enabled_company_counts, skipped_company_counts = await self._due_companies_by_connector()
        connector_summary = self._connector_cycle_summary(
            runs,
            enabled_company_counts=enabled_company_counts,
            skipped_company_counts=skipped_company_counts,
        )
        await record_audit_event(
            event_type="scheduler.started",
            subject_type="scheduler",
            subject_id="market-scout",
            message="Market Scout scheduler cycle started.",
            metadata={
                "enabled_connectors": list(connector_groups),
                "connector_summary": connector_summary,
            },
            settings=self.settings,
        )
        self.logger.info(
            "Starting market scout cycle",
            extra={
                "operation_name": "market_scout.run.start",
                "connector_key": ",".join(connector_groups) or "none",
                "connector_summary": connector_summary,
            },
        )
        try:
            for connector_key, companies in connector_groups.items():
                runner = self._connector_runner(connector_key)
                if runner is None:
                    self.logger.warning(
                        "Skipping configured connector because no collector implementation exists yet",
                        extra={
                            "operation_name": "market_scout.connector.not_implemented",
                            "connector_key": connector_key,
                            "company_count": len(companies),
                        },
                    )
                    runs.extend(
                        [
                            ConnectorRunSummary(
                                connector_key=f"{connector_key}:{company.external_identifier or company.company.casefold().replace(' ', '-')}",
                                company=company.company,
                                jobs_fetched=0,
                                jobs_inserted=0,
                                jobs_updated=0,
                                jobs_matched=0,
                                alerts_sent=0,
                                alerts_failed=0,
                                error_message="Collector not implemented for this connector.",
                            )
                            for company in companies
                        ]
                    )
                    continue

                for company in companies:
                    connector_run_key = f"{connector_key}:{company.external_identifier or company.company.casefold().replace(' ', '-')}"
                    try:
                        runs.append(await runner(company))
                    except Exception as exc:  # noqa: BLE001
                        self.logger.exception(
                            "Connector sync failed; scheduler will continue with the next connector",
                            extra={
                                "operation_name": "market_scout.connector.failure_continued",
                                "connector_key": connector_run_key,
                            },
                        )
                        runs.append(
                            ConnectorRunSummary(
                                connector_key=connector_run_key,
                                company=company.company,
                                jobs_fetched=0,
                                jobs_inserted=0,
                                jobs_updated=0,
                                jobs_matched=0,
                                alerts_sent=0,
                                alerts_failed=0,
                                failed=True,
                                error_message=str(exc)[:1000],
                            )
                        )
            finished_at = datetime.now(timezone.utc)
            connector_summary = self._connector_cycle_summary(
                runs,
                enabled_company_counts=enabled_company_counts,
                skipped_company_counts=skipped_company_counts,
            )
            self.logger.info(
                "Finished market scout cycle",
                extra={
                    "operation_name": "market_scout.run.finish",
                    "connector_key": ",".join(connector_groups) or "none",
                    "runs": [run.to_dict() for run in runs],
                    "connector_summary": connector_summary,
                    "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
                },
            )
            await record_audit_event(
                event_type="scheduler.completed",
                subject_type="scheduler",
                subject_id="market-scout",
                message="Market Scout scheduler cycle completed.",
                metadata={
                    "runs": [run.to_dict() for run in runs],
                    "connector_summary": connector_summary,
                },
                settings=self.settings,
            )
            return MarketScoutRunSummary(
                started_at=started_at.isoformat(),
                finished_at=finished_at.isoformat(),
                runs=runs,
            )
        except BaseException as exc:  # noqa: BLE001
            await record_audit_event(
                event_type="scheduler.failed",
                subject_type="scheduler",
                subject_id="market-scout",
                message=f"Market Scout scheduler cycle failed: {str(exc)[:200]}",
                metadata={"error": str(exc)[:1000]},
                settings=self.settings,
            )
            raise

    async def run_loop(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(self.settings.radar.polling_interval_minutes * 60)

    async def _due_companies_by_connector(
        self,
    ) -> tuple[dict[str, list[CompanyPreference]], dict[str, int], dict[str, int]]:
        groups: dict[str, list[CompanyPreference]] = {}
        enabled_company_counts: dict[str, int] = {}
        skipped_company_counts: dict[str, int] = {}
        candidates: list[tuple[str, str, CompanyPreference]] = []
        for company in sorted(
            self.settings.radar.companies,
            key=lambda item: (item.tier, item.priority, item.company.casefold()),
        ):
            connector_key = company.connector.strip().casefold()
            if not company.enabled or not connector_key:
                continue
            if connector_key == "greenhouse" and not company.external_identifier.strip():
                self.logger.warning(
                    "Skipping enabled greenhouse company without external identifier",
                    extra={
                        "operation_name": "market_scout.company.invalid",
                        "connector_key": connector_key,
                        "company": company.company,
                    },
                )
                continue
            if connector_key == "lever" and not company.external_identifier.strip():
                self.logger.warning(
                    "Skipping enabled lever company without external identifier",
                    extra={
                        "operation_name": "market_scout.company.invalid",
                        "connector_key": connector_key,
                        "company": company.company,
                    },
                )
                continue
            run_key = _company_connector_run_key(company)
            enabled_company_counts[connector_key] = enabled_company_counts.get(connector_key, 0) + 1
            candidates.append((connector_key, run_key, company))

        if not candidates:
            return groups, enabled_company_counts, skipped_company_counts

        cursor_keys = [run_key for _, run_key, _ in candidates]
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT connector_key, last_successful_sync
                FROM connector_cursors
                WHERE connector_key = ANY($1::text[])
                """,
                cursor_keys,
            )
        last_sync_by_run_key = {
            str(row["connector_key"]): row["last_successful_sync"]
            for row in rows
            if row["last_successful_sync"] is not None
        }
        current_time = datetime.now(timezone.utc)
        for connector_key, run_key, company in candidates:
            last_successful_sync = last_sync_by_run_key.get(run_key)
            if last_successful_sync is not None:
                if last_successful_sync.tzinfo is None:
                    last_successful_sync = last_successful_sync.replace(tzinfo=timezone.utc)
                next_due_at = last_successful_sync + timedelta(minutes=company.poll_interval_minutes)
                if current_time < next_due_at:
                    skipped_company_counts[connector_key] = skipped_company_counts.get(connector_key, 0) + 1
                    continue
            groups.setdefault(connector_key, []).append(company)
        return groups, enabled_company_counts, skipped_company_counts

    def _connector_cycle_summary(
        self,
        runs: list[ConnectorRunSummary],
        *,
        enabled_company_counts: dict[str, int],
        skipped_company_counts: dict[str, int],
    ) -> list[dict[str, object]]:
        summary_by_connector: dict[str, dict[str, object]] = {}
        connector_order: list[str] = []

        def ensure_summary(connector_key: str) -> dict[str, object]:
            if connector_key not in summary_by_connector:
                summary_by_connector[connector_key] = {
                    "connector": connector_key,
                    "companies_enabled": enabled_company_counts.get(connector_key, 0),
                    "companies_polled": 0,
                    "companies_skipped_interval": skipped_company_counts.get(connector_key, 0),
                    "jobs_fetched": 0,
                    "jobs_new": 0,
                    "jobs_updated": 0,
                    "jobs_matched": 0,
                    "alerts_sent": 0,
                    "alerts_failed": 0,
                    "failures": 0,
                }
                connector_order.append(connector_key)
            return summary_by_connector[connector_key]

        for connector_key in sorted(set(enabled_company_counts) | set(skipped_company_counts)):
            ensure_summary(connector_key)

        for run in runs:
            connector_key = run.connector_key.split(":", 1)[0]
            summary = ensure_summary(connector_key)
            summary["companies_polled"] = int(summary["companies_polled"]) + 1
            summary["jobs_fetched"] = int(summary["jobs_fetched"]) + run.jobs_fetched
            summary["jobs_new"] = int(summary["jobs_new"]) + run.jobs_inserted
            summary["jobs_updated"] = int(summary["jobs_updated"]) + run.jobs_updated
            summary["jobs_matched"] = int(summary["jobs_matched"]) + run.jobs_matched
            summary["alerts_sent"] = int(summary["alerts_sent"]) + run.alerts_sent
            summary["alerts_failed"] = int(summary["alerts_failed"]) + run.alerts_failed
            summary["failures"] = int(summary["failures"]) + (1 if run.failed else 0)

        return [summary_by_connector[connector_key] for connector_key in connector_order]

    def _connector_runner(
        self,
        connector_key: str,
    ) -> Callable[[CompanyPreference], Awaitable[ConnectorRunSummary]] | None:
        if connector_key == "greenhouse":
            return self._run_greenhouse_company
        if connector_key == "lever":
            return self._run_lever_company
        return None

    async def _active_user_contexts(self) -> list[UserMatchContext]:
        return [
            UserMatchContext(
                user=user,
                settings=build_user_matching_settings(self.settings, user),
                profile_text=build_user_profile_text(user, self.settings),
                minimum_match_score=minimum_match_score(user, self.settings),
                freshness_hours=alert_freshness_hours(user, self.settings),
            )
            for user in await list_users(self.settings)
        ]

    async def _run_greenhouse_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        board = GreenhouseBoard(company=company.company, token=company.external_identifier.strip())
        connector_key = f"greenhouse:{board.token}"
        run_id = str(uuid4())
        cursor_before: str | None = None
        last_successful_sync: datetime | None = None
        self.logger.info(
            "Starting connector sync",
            extra={
                "operation_name": "market_scout.connector.start",
                "connector_key": connector_key,
            },
        )

        async with connection() as conn:
            cursor_row = await conn.fetchrow(
                """
                SELECT cursor_value, last_successful_sync, last_published_at
                FROM connector_cursors
                WHERE connector_key = $1
                """,
                connector_key,
            )
            if cursor_row is not None:
                cursor_before = cursor_row["cursor_value"]
                last_successful_sync = cursor_row["last_successful_sync"]

            await conn.execute(
                """
                INSERT INTO connector_runs (
                    run_id,
                    connector_key,
                    run_status,
                    cursor_before
                )
                VALUES ($1, $2, 'running', $3)
                """,
                run_id,
                connector_key,
                cursor_before,
            )

        connector = GreenhouseJobConnector(board=board, connector_settings=self.settings.connectors)
        connector_cursor = ConnectorCursor(cursor=cursor_before, last_published_at=last_successful_sync)
        try:
            result = await asyncio.to_thread(
                retry_sync,
                connector.collect,
                connector_cursor,
                policy=self.retry_policy,
                logger=self.logger,
                operation_name=f"greenhouse.collect.{board.token}",
            )
            self.logger.info(
                "Collected jobs from connector",
                extra={
                    "operation_name": "market_scout.connector.collect",
                    "connector_key": connector_key,
                    "jobs_fetched": len(result.jobs),
                },
            )
            summary = await self._persist_connector_result(
                company=company,
                connector_key=connector_key,
                run_id=run_id,
                last_successful_sync=last_successful_sync,
                jobs=result.jobs,
                next_cursor=result.next_cursor.cursor,
                next_published_at=result.next_cursor.last_published_at,
            )
            self.logger.info(
                "Finished connector sync",
                extra={
                    "operation_name": "market_scout.connector.finish",
                    "connector_key": connector_key,
                    "summary": summary.to_dict(),
                    "jobs_fetched": summary.jobs_fetched,
                    "jobs_new": summary.jobs_inserted,
                    "jobs_updated": summary.jobs_updated,
                    "alerts_sent": summary.alerts_sent,
                    "alerts_failed": summary.alerts_failed,
                },
            )
            return summary
        except BaseException as exc:  # noqa: BLE001
            async with connection() as conn:
                await conn.execute(
                    """
                    UPDATE connector_runs
                    SET finished_at = NOW(),
                        run_status = 'failed',
                        error_message = $2
                    WHERE run_id = $1
                    """,
                    run_id,
                    str(exc)[:1000],
                )
            await record_audit_event(
                event_type="connector.failed",
                subject_type="connector",
                subject_id=connector_key,
                message=f"{connector_key} failed during sync.",
                metadata={"run_id": run_id, "error": str(exc)[:1000]},
                settings=self.settings,
            )
            raise

    async def _run_lever_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        board = LeverBoard(company=company.company, token=company.external_identifier.strip())
        connector_key = f"lever:{board.token}"
        run_id = str(uuid4())
        cursor_before: str | None = None
        last_successful_sync: datetime | None = None
        self.logger.info(
            "Starting connector sync",
            extra={
                "operation_name": "market_scout.connector.start",
                "connector_key": connector_key,
            },
        )

        async with connection() as conn:
            cursor_row = await conn.fetchrow(
                """
                SELECT cursor_value, last_successful_sync, last_published_at
                FROM connector_cursors
                WHERE connector_key = $1
                """,
                connector_key,
            )
            if cursor_row is not None:
                cursor_before = cursor_row["cursor_value"]
                last_successful_sync = cursor_row["last_successful_sync"]

            await conn.execute(
                """
                INSERT INTO connector_runs (
                    run_id,
                    connector_key,
                    run_status,
                    cursor_before
                )
                VALUES ($1, $2, 'running', $3)
                """,
                run_id,
                connector_key,
                cursor_before,
            )

        connector = LeverJobConnector(board=board, connector_settings=self.settings.connectors)
        connector_cursor = ConnectorCursor(cursor=cursor_before, last_published_at=last_successful_sync)
        try:
            result = await asyncio.to_thread(
                retry_sync,
                connector.collect,
                connector_cursor,
                policy=self.retry_policy,
                logger=self.logger,
                operation_name=f"lever.collect.{board.token}",
            )
            self.logger.info(
                "Collected jobs from connector",
                extra={
                    "operation_name": "market_scout.connector.collect",
                    "connector_key": connector_key,
                    "jobs_fetched": len(result.jobs),
                },
            )
            summary = await self._persist_connector_result(
                company=company,
                connector_key=connector_key,
                run_id=run_id,
                last_successful_sync=last_successful_sync,
                jobs=result.jobs,
                next_cursor=result.next_cursor.cursor,
                next_published_at=result.next_cursor.last_published_at,
            )
            self.logger.info(
                "Finished connector sync",
                extra={
                    "operation_name": "market_scout.connector.finish",
                    "connector_key": connector_key,
                    "summary": summary.to_dict(),
                    "jobs_fetched": summary.jobs_fetched,
                    "jobs_new": summary.jobs_inserted,
                    "jobs_updated": summary.jobs_updated,
                    "alerts_sent": summary.alerts_sent,
                    "alerts_failed": summary.alerts_failed,
                },
            )
            return summary
        except BaseException as exc:  # noqa: BLE001
            async with connection() as conn:
                await conn.execute(
                    """
                    UPDATE connector_runs
                    SET finished_at = NOW(),
                        run_status = 'failed',
                        error_message = $2
                    WHERE run_id = $1
                    """,
                    run_id,
                    str(exc)[:1000],
                )
            await record_audit_event(
                event_type="connector.failed",
                subject_type="connector",
                subject_id=connector_key,
                message=f"{connector_key} failed during sync.",
                metadata={"run_id": run_id, "error": str(exc)[:1000]},
                settings=self.settings,
            )
            raise

    async def _persist_connector_result(
        self,
        *,
        company: CompanyPreference,
        connector_key: str,
        run_id: str,
        last_successful_sync: datetime | None,
        jobs: list[NormalizedJobRecord],
        next_cursor: str | None,
        next_published_at: datetime | None,
    ) -> ConnectorRunSummary:
        jobs_inserted = 0
        jobs_updated = 0
        jobs_matched = 0
        alerts_sent = 0
        alerts_failed = 0
        now = datetime.now(timezone.utc)
        initial_sync = last_successful_sync is None
        initial_sync_window_start = now - timedelta(hours=self.settings.radar.initial_alert_window_hours)
        remaining_initial_openai_budget = self.settings.radar.initial_sync_openai_job_limit
        remaining_initial_alert_budget = self.settings.radar.initial_sync_max_alerts
        user_contexts = await self._active_user_contexts()

        async with connection() as conn:
            existing_jobs_by_external_id: dict[str, str] = {}
            if jobs:
                rows = await conn.fetch(
                    """
                    SELECT external_job_id, job_id
                    FROM jobs
                    WHERE connector_key = $1
                      AND external_job_id = ANY($2::text[])
                    """,
                    connector_key,
                    [job.external_job_id for job in jobs],
                )
                existing_jobs_by_external_id = {
                    str(row["external_job_id"]): str(row["job_id"])
                    for row in rows
                }

            for job in jobs:
                if job.external_job_id in existing_jobs_by_external_id:
                    job_id = existing_jobs_by_external_id[job.external_job_id]
                    jobs_updated += 1
                    await conn.execute(
                        """
                        UPDATE jobs
                        SET last_seen_at = NOW(),
                            description_text = $3,
                            metadata = $4::jsonb
                        WHERE connector_key = $1
                          AND external_job_id = $2
                        """,
                        connector_key,
                        job.external_job_id,
                        job.description_text,
                        json.dumps({"raw_payload": job.raw_payload}),
                    )
                    country_code = infer_country_code(job.location, job.description_text)
                    published_at = job.published_at or now
                    pending_alerts_sent, pending_alerts_failed = await self._deliver_pending_alerts_for_existing_job(
                        conn=conn,
                        job_id=job_id,
                        job=job,
                        user_contexts=user_contexts,
                        published_at=published_at,
                        country_code=country_code,
                        now=now,
                    )
                    alerts_sent += pending_alerts_sent
                    alerts_failed += pending_alerts_failed
                    continue

                country_code = infer_country_code(job.location, job.description_text)
                job_id = str(uuid5(NAMESPACE_URL, f"{connector_key}:{job.external_job_id}"))
                published_at = job.published_at or now
                best_match: MatchResult | None = None
                best_context: UserMatchContext | None = None
                user_matches: list[tuple[UserMatchContext, MatchResult]] = []

                for user_context in user_contexts:
                    skip_reason = filter_reason_for_user(
                        job,
                        user_context.user,
                        self.settings,
                        matching_settings=user_context.settings,
                    )
                    if skip_reason is not None:
                        self.logger.info(
                            "Skipping job for user outside target preferences",
                            extra={
                                "operation_name": "market_scout.user_preference_filter.skip",
                                "connector_key": connector_key,
                                "job_id": job.external_job_id,
                                "user_id": user_context.user.id,
                                "filter_reason": skip_reason,
                            },
                        )
                        continue

                    allow_openai = True
                    if initial_sync:
                        allow_openai = (
                            remaining_initial_openai_budget > 0
                            and published_at >= initial_sync_window_start
                        )
                    match = await score_job(
                        job,
                        user_context.settings,
                        prefer_openai=allow_openai,
                        profile_text=user_context.profile_text,
                    )
                    if initial_sync and allow_openai and match.provider == "openai":
                        remaining_initial_openai_budget -= 1
                    user_matches.append((user_context, match))
                    jobs_matched += 1

                    if (
                        best_match is None
                        or match.score > best_match.score
                        or (
                            match.score == best_match.score
                            and _decision_rank(match.decision) < _decision_rank(best_match.decision)
                        )
                    ):
                        best_match = match
                        best_context = user_context

                if best_match is None:
                    best_match = heuristic_score_job(job, self.settings)

                await conn.execute(
                    """
                    INSERT INTO jobs (
                        job_id,
                        connector_key,
                        external_job_id,
                        company,
                        title,
                        location,
                        remote_policy,
                        apply_url,
                        description_text,
                        job_fingerprint,
                        published_at,
                        match_score,
                        decision,
                        recommended_resume,
                        job_status,
                        duplicate_source_count,
                        metadata
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, 'new', 0, $15::jsonb
                    )
                    """,
                    job_id,
                    connector_key,
                    job.external_job_id,
                    job.company,
                    job.title,
                    job.location,
                    job.remote_policy,
                    job.apply_url,
                    job.description_text,
                    job.job_fingerprint,
                    published_at,
                    best_match.score,
                    best_match.decision,
                    best_match.recommended_resume,
                    json.dumps(
                        {
                            "why": best_match.top_strengths,
                            "gaps": best_match.gaps,
                            "match_provider": best_match.provider,
                            "country_code": country_code,
                            "best_match_user_id": best_context.user.id if best_context is not None else None,
                            "raw_payload": job.raw_payload,
                        }
                    ),
                )
                await conn.execute(
                    """
                    INSERT INTO seen_jobs (job_fingerprint, job_id, connector_key, source_cursor)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (job_fingerprint)
                    DO UPDATE SET
                        seen_at = NOW(),
                        source_cursor = EXCLUDED.source_cursor
                    """,
                    job.job_fingerprint,
                    job_id,
                    connector_key,
                    next_cursor,
                )
                jobs_inserted += 1

                for user_context, match in user_matches:
                    match_id = str(uuid5(NAMESPACE_URL, f"{job_id}:{user_context.user.id}"))
                    await conn.execute(
                        """
                        INSERT INTO job_matches (
                            match_id,
                            job_id,
                            user_id,
                            match_score,
                            decision,
                            recommended_resume,
                            match_status,
                            why,
                            gaps,
                            provider,
                            country_code,
                            updated_at
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, 'new', $7::jsonb, $8::jsonb, $9, $10, NOW()
                        )
                        ON CONFLICT (user_id, job_id) DO UPDATE SET
                            match_score = EXCLUDED.match_score,
                            decision = EXCLUDED.decision,
                            recommended_resume = EXCLUDED.recommended_resume,
                            why = EXCLUDED.why,
                            gaps = EXCLUDED.gaps,
                            provider = EXCLUDED.provider,
                            country_code = EXCLUDED.country_code,
                            updated_at = NOW()
                        """,
                        match_id,
                        job_id,
                        user_context.user.id,
                        match.score,
                        match.decision,
                        match.recommended_resume,
                        json.dumps(match.top_strengths),
                        json.dumps(match.gaps),
                        match.provider,
                        country_code,
                    )

                    if not self._should_alert_for_user(
                        job=job,
                        match=match,
                        user_context=user_context,
                        published_at=published_at,
                        initial_sync=initial_sync,
                        now=now,
                        remaining_initial_alert_budget=remaining_initial_alert_budget,
                    ):
                        continue

                    alert_id = str(uuid5(NAMESPACE_URL, f"{job_id}:{user_context.user.id}:telegram:{match.decision}"))
                    inserted_alert = await conn.fetchval(
                        """
                        INSERT INTO user_alerts (
                            user_alert_id,
                            job_id,
                            user_id,
                            channel,
                            decision,
                            alert_status,
                            payload
                        )
                        VALUES ($1, $2, $3, 'telegram', $4, 'pending', $5::jsonb)
                        ON CONFLICT DO NOTHING
                        RETURNING user_alert_id
                        """,
                        alert_id,
                        job_id,
                        user_context.user.id,
                        match.decision,
                        json.dumps(
                            {
                                "why": match.top_strengths,
                                "gaps": match.gaps,
                                "recommended_resume": match.recommended_resume,
                                "country_code": country_code,
                            }
                        ),
                    )
                    if inserted_alert is None:
                        continue
                    if initial_sync:
                        remaining_initial_alert_budget = max(0, remaining_initial_alert_budget - 1)
                    sent, failed = await self._send_inserted_alert(
                        conn=conn,
                        alert_id=alert_id,
                        job_id=job_id,
                        job=job,
                        match=match,
                        user_context=user_context,
                        published_at=published_at,
                        country_code=country_code,
                        now=now,
                    )
                    alerts_sent += sent
                    alerts_failed += failed

            await conn.execute(
                """
                INSERT INTO connector_cursors (
                    connector_key,
                    cursor_value,
                    last_published_at,
                    last_successful_sync,
                    updated_at
                )
                VALUES ($1, $2, $3, NOW(), NOW())
                ON CONFLICT (connector_key)
                DO UPDATE SET
                    cursor_value = EXCLUDED.cursor_value,
                    last_published_at = EXCLUDED.last_published_at,
                    last_successful_sync = EXCLUDED.last_successful_sync,
                    updated_at = NOW()
                """,
                connector_key,
                next_cursor,
                next_published_at,
            )
            await conn.execute(
                """
                UPDATE connector_runs
                SET finished_at = NOW(),
                    run_status = 'succeeded',
                    jobs_fetched = $2,
                    jobs_inserted = $3,
                    retries = 0,
                    cursor_after = $4
                WHERE run_id = $1
                """,
                run_id,
                len(jobs),
                jobs_inserted,
                next_cursor,
            )

            return ConnectorRunSummary(
                connector_key=connector_key,
                company=company.company,
                jobs_fetched=len(jobs),
                jobs_inserted=jobs_inserted,
                jobs_updated=jobs_updated,
                jobs_matched=jobs_matched,
                alerts_sent=alerts_sent,
                alerts_failed=alerts_failed,
        )

    def _should_alert_for_user(
        self,
        *,
        job: NormalizedJobRecord,
        match: MatchResult,
        user_context: UserMatchContext,
        published_at: datetime,
        initial_sync: bool,
        now: datetime,
        remaining_initial_alert_budget: int,
    ) -> bool:
        if not telegram_connected(user_context.user):
            return False
        if match.score < user_context.minimum_match_score:
            return False
        if published_at < now - timedelta(hours=user_context.freshness_hours):
            return False
        if not alert_rule_allows_job(job, user_context.user):
            return False
        if not initial_sync:
            return True
        if remaining_initial_alert_budget <= 0:
            return False
        return published_at >= now - timedelta(hours=self.settings.radar.initial_alert_window_hours)

    async def _deliver_pending_alerts_for_existing_job(
        self,
        *,
        conn,
        job_id: str,
        job: NormalizedJobRecord,
        user_contexts: list[UserMatchContext],
        published_at: datetime,
        country_code: str | None,
        now: datetime,
    ) -> tuple[int, int]:
        pending_matches = await conn.fetch(
            """
            SELECT user_id, match_score, decision, recommended_resume, why, gaps, provider
            FROM job_matches
            WHERE job_id = $1
              AND alerted_at IS NULL
            """,
            job_id,
        )
        if not pending_matches:
            return 0, 0

        user_context_by_id = {context.user.id: context for context in user_contexts}
        alerts_sent = 0
        alerts_failed = 0
        for row in pending_matches:
            user_id = str(row["user_id"])
            user_context = user_context_by_id.get(user_id)
            if user_context is None:
                continue

            match = MatchResult(
                score=int(row["match_score"]),
                decision=str(row["decision"]),
                top_strengths=_json_string_list(row["why"]),
                gaps=_json_string_list(row["gaps"]),
                recommended_resume=str(row["recommended_resume"]),
                provider=str(row["provider"]),
            )
            if not self._should_alert_for_user(
                job=job,
                match=match,
                user_context=user_context,
                published_at=published_at,
                initial_sync=False,
                now=now,
                remaining_initial_alert_budget=0,
            ):
                continue

            alert_id = str(uuid5(NAMESPACE_URL, f"{job_id}:{user_id}:telegram:{match.decision}"))
            inserted_alert = await conn.fetchval(
                """
                INSERT INTO user_alerts (
                    user_alert_id,
                    job_id,
                    user_id,
                    channel,
                    decision,
                    alert_status,
                    payload
                )
                VALUES ($1, $2, $3, 'telegram', $4, 'pending', $5::jsonb)
                ON CONFLICT DO NOTHING
                RETURNING user_alert_id
                """,
                alert_id,
                job_id,
                user_id,
                match.decision,
                json.dumps(
                    {
                        "why": match.top_strengths,
                        "gaps": match.gaps,
                        "recommended_resume": match.recommended_resume,
                        "country_code": country_code,
                    }
                ),
            )
            if inserted_alert is None:
                continue

            sent, failed = await self._send_inserted_alert(
                conn=conn,
                alert_id=alert_id,
                job_id=job_id,
                job=job,
                match=match,
                user_context=user_context,
                published_at=published_at,
                country_code=country_code,
                now=now,
            )
            alerts_sent += sent
            alerts_failed += failed

        return alerts_sent, alerts_failed

    async def _send_inserted_alert(
        self,
        *,
        conn,
        alert_id: str,
        job_id: str,
        job: NormalizedJobRecord,
        match: MatchResult,
        user_context: UserMatchContext,
        published_at: datetime,
        country_code: str | None,
        now: datetime,
    ) -> tuple[int, int]:
        posted_minutes_ago = max(0, int((now - published_at).total_seconds() // 60))
        try:
            await asyncio.to_thread(
                retry_sync,
                send_message,
                self.settings,
                _format_alert_message(
                    job,
                    match,
                    posted_minutes_ago,
                    country_code=country_code,
                    settings=user_context.settings,
                ),
                chat_id=user_context.user.telegram_chat_id,
                policy=self.retry_policy,
                logger=self.logger,
                operation_name=f"telegram.send.{job.company}.{user_context.user.id}",
                parse_mode="HTML",
            )
            await conn.execute(
                """
                UPDATE user_alerts
                SET alert_status = 'sent',
                    sent_at = NOW()
                WHERE user_alert_id = $1
                """,
                alert_id,
            )
            await conn.execute(
                """
                UPDATE job_matches
                SET alerted_at = NOW(),
                    updated_at = NOW()
                WHERE user_id = $1
                  AND job_id = $2
                """,
                user_context.user.id,
                job_id,
            )
            return 1, 0
        except Exception as exc:  # noqa: BLE001
            await conn.execute(
                """
                UPDATE user_alerts
                SET alert_status = 'failed',
                    failure_reason = $2
                WHERE user_alert_id = $1
                """,
                alert_id,
                str(exc)[:1000],
            )
            return 0, 1
