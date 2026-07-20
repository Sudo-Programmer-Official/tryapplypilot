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
from app.connectors.amazon_jobs import AmazonJobsConnector, build_amazon_career_site
from app.connectors.ashby import AshbyBoard, AshbyJobConnector
from app.connectors.base import ConnectorCursor, NormalizedJobRecord
from app.connectors.comeet import ComeetJobConnector, build_comeet_site
from app.connectors.greenhouse import GreenhouseJobConnector
from app.connectors.google_careers import GoogleCareersJobConnector, build_google_career_site
from app.connectors.icims import ICIMSJobConnector, build_icims_career_site
from app.connectors.jobvite import JobviteJobConnector, build_jobvite_site
from app.connectors.lever import LeverBoard, LeverJobConnector
from app.connectors.microsoft_careers import MicrosoftCareerSite, MicrosoftCareersJobConnector
from app.connectors.oracle_recruiting_cloud import OracleRecruitingCloudConnector, build_oracle_recruiting_cloud_site
from app.connectors.smartrecruiters import SmartRecruitersJobConnector, build_smartrecruiters_site
from app.connectors.successfactors import SuccessFactorsJobConnector, build_successfactors_site
from app.connectors.workday import WorkdayJobConnector, build_workday_career_site
from app.db.client import connection
from app.domain import CompanyPreference, UserAccount
from app.job_lifecycle import content_hash_for_job, lifecycle_for_missed_syncs
from app.job_metadata import (
    country_display,
    freshness_label,
    infer_country_code,
    recommendation_label,
)
from app.logging_utils import get_logger
from app.notification_delivery import evaluate_notification_decision
from app.notifications.telegram import send_message
from app.retry import RetryPolicy, retry_sync
from app.scoring import MatchResult, heuristic_score_job, score_job
from app.user_accounts import list_users
from app.user_matching import (
    alert_freshness_hours,
    build_user_profile_text,
    build_user_matching_settings,
    filter_reason_for_user,
    minimum_match_score,
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
    requests_made: int = 0
    jobs_closed: int = 0
    jobs_archived: int = 0
    jobs_ignored: int = 0
    companies_scanned: int = 1
    retries: int = 0
    inventory_complete: bool = True
    pages_scanned: int = 1
    expected_pages: int | None = None
    partial_reason: str | None = None
    failed: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "connector_key": self.connector_key,
            "company": self.company,
            "jobs_fetched": self.jobs_fetched,
            "jobs_inserted": self.jobs_inserted,
            "jobs_updated": self.jobs_updated,
            "jobs_closed": self.jobs_closed,
            "jobs_archived": self.jobs_archived,
            "jobs_ignored": self.jobs_ignored,
            "jobs_matched": self.jobs_matched,
            "alerts_sent": self.alerts_sent,
            "alerts_failed": self.alerts_failed,
            "requests_made": self.requests_made,
            "companies_scanned": self.companies_scanned,
            "retries": self.retries,
            "inventory_complete": self.inventory_complete,
            "pages_scanned": self.pages_scanned,
            "expected_pages": self.expected_pages,
            "partial_reason": self.partial_reason,
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
    def jobs_closed(self) -> int:
        return sum(run.jobs_closed for run in self.runs)

    @property
    def jobs_archived(self) -> int:
        return sum(run.jobs_archived for run in self.runs)

    @property
    def jobs_ignored(self) -> int:
        return sum(run.jobs_ignored for run in self.runs)

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
    def requests_made(self) -> int:
        return sum(run.requests_made for run in self.runs)

    @property
    def companies_scanned(self) -> int:
        return sum(run.companies_scanned for run in self.runs)

    @property
    def retries(self) -> int:
        return sum(run.retries for run in self.runs)

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
            "jobs_closed": self.jobs_closed,
            "jobs_archived": self.jobs_archived,
            "jobs_ignored": self.jobs_ignored,
            "jobs_matched": self.jobs_matched,
            "alerts_sent": self.alerts_sent,
            "alerts_failed": self.alerts_failed,
            "requests_made": self.requests_made,
            "companies_scanned": self.companies_scanned,
            "retries": self.retries,
            "connector_failures": self.connector_failures,
        }


@dataclass(frozen=True)
class ConnectorLifecycleDelta:
    jobs_closed: int = 0
    jobs_archived: int = 0


@dataclass(frozen=True)
class UserMatchContext:
    user: UserAccount
    settings: AppSettings
    profile_text: str
    minimum_match_score: int
    freshness_hours: int


def _company_connector_run_key(company: CompanyPreference) -> str:
    connector_key = company.connector.strip().casefold()
    if connector_key == "comeet":
        try:
            company_key = build_comeet_site(
                company=company.company,
                career_url=company.career_url,
                external_identifier=company.external_identifier.strip(),
                country=company.country,
                role_families=tuple(company.role_families),
            ).identifier
        except ValueError:
            company_key = company.company.casefold().replace(" ", "-")
    else:
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
                                companies_scanned=0,
                                jobs_fetched=0,
                                jobs_inserted=0,
                                jobs_updated=0,
                                jobs_matched=0,
                                alerts_sent=0,
                                alerts_failed=0,
                                requests_made=0,
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
                                requests_made=0,
                                retries=0,
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

    async def run_connector_now(self, connector_key: str) -> MarketScoutRunSummary:
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
        runnable_companies = [
            company
            for company in sorted(
                self.settings.radar.companies,
                key=lambda item: (item.tier, item.priority, item.company.casefold()),
            )
            if company.enabled and company.connector.strip().casefold() == connector_key.casefold()
        ]
        runner = self._connector_runner(connector_key.casefold())
        if runner is None:
            runs = [
                ConnectorRunSummary(
                    connector_key=_company_connector_run_key(company),
                    company=company.company,
                    companies_scanned=0,
                    jobs_fetched=0,
                    jobs_inserted=0,
                    jobs_updated=0,
                    jobs_matched=0,
                    alerts_sent=0,
                    alerts_failed=0,
                    requests_made=0,
                    failed=True,
                    error_message="Collector not implemented for this connector.",
                )
                for company in runnable_companies
            ]
        else:
            for company in runnable_companies:
                try:
                    runs.append(await runner(company))
                except Exception as exc:  # noqa: BLE001
                    runs.append(
                        ConnectorRunSummary(
                            connector_key=_company_connector_run_key(company),
                            company=company.company,
                            jobs_fetched=0,
                            jobs_inserted=0,
                            jobs_updated=0,
                            jobs_matched=0,
                            alerts_sent=0,
                            alerts_failed=0,
                            requests_made=0,
                            retries=0,
                            failed=True,
                            error_message=str(exc)[:1000],
                        )
                    )
        finished_at = datetime.now(timezone.utc)
        return MarketScoutRunSummary(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            runs=runs,
        )

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
            if connector_key in {
                "greenhouse",
                "lever",
                "ashby",
                "microsoft-careers",
                "google-careers",
                "oracle-recruiting-cloud",
            } and not company.external_identifier.strip():
                self.logger.warning(
                    "Skipping enabled company without external identifier",
                    extra={
                        "operation_name": "market_scout.company.invalid",
                        "connector_key": connector_key,
                        "company": company.company,
                    },
                )
                continue
            if connector_key in {
                "workday",
                "google-careers",
                "amazon-jobs",
                "oracle-recruiting-cloud",
                "successfactors",
            } and not company.career_url.strip():
                self.logger.warning(
                    "Skipping enabled company without career URL",
                    extra={
                        "operation_name": "market_scout.company.invalid",
                        "connector_key": connector_key,
                        "company": company.company,
                    },
                )
                continue
            if connector_key == "icims" and not (company.career_url.strip() or company.external_identifier.strip()):
                self.logger.warning(
                    "Skipping enabled company without iCIMS site configuration",
                    extra={
                        "operation_name": "market_scout.company.invalid",
                        "connector_key": connector_key,
                        "company": company.company,
                    },
                )
                continue
            if connector_key == "jobvite" and not (company.career_url.strip() or company.external_identifier.strip()):
                self.logger.warning(
                    "Skipping enabled company without Jobvite site configuration",
                    extra={
                        "operation_name": "market_scout.company.invalid",
                        "connector_key": connector_key,
                        "company": company.company,
                    },
                )
                continue
            if connector_key == "smartrecruiters":
                try:
                    build_smartrecruiters_site(
                        company=company.company,
                        career_url=company.career_url,
                        external_identifier=company.external_identifier.strip(),
                        country=company.country,
                        role_families=tuple(company.role_families),
                    )
                except ValueError:
                    self.logger.warning(
                        "Skipping enabled SmartRecruiters company with invalid configuration",
                        extra={
                            "operation_name": "market_scout.company.invalid",
                            "connector_key": connector_key,
                            "company": company.company,
                        },
                    )
                    continue
            if connector_key == "icims":
                try:
                    build_icims_career_site(
                        company=company.company,
                        career_url=company.career_url,
                        external_identifier=company.external_identifier.strip(),
                        country=company.country,
                        role_families=tuple(company.role_families),
                    )
                except ValueError:
                    self.logger.warning(
                        "Skipping enabled iCIMS company with invalid configuration",
                        extra={
                            "operation_name": "market_scout.company.invalid",
                            "connector_key": connector_key,
                            "company": company.company,
                        },
                    )
                    continue
            if connector_key == "jobvite":
                try:
                    build_jobvite_site(
                        company=company.company,
                        career_url=company.career_url,
                        external_identifier=company.external_identifier.strip(),
                        country=company.country,
                        role_families=tuple(company.role_families),
                    )
                except ValueError:
                    self.logger.warning(
                        "Skipping enabled Jobvite company with invalid configuration",
                        extra={
                            "operation_name": "market_scout.company.invalid",
                            "connector_key": connector_key,
                            "company": company.company,
                        },
                    )
                    continue
            if connector_key == "comeet":
                try:
                    build_comeet_site(
                        company=company.company,
                        career_url=company.career_url,
                        external_identifier=company.external_identifier.strip(),
                        country=company.country,
                        role_families=tuple(company.role_families),
                    )
                except ValueError:
                    self.logger.warning(
                        "Skipping enabled Comeet company with invalid configuration",
                        extra={
                            "operation_name": "market_scout.company.invalid",
                            "connector_key": connector_key,
                            "company": company.company,
                        },
                    )
                    continue
            if connector_key == "oracle-recruiting-cloud":
                try:
                    build_oracle_recruiting_cloud_site(
                        company=company.company,
                        career_url=company.career_url,
                        external_identifier=company.external_identifier.strip(),
                        country=company.country,
                        role_families=tuple(company.role_families),
                    )
                except ValueError:
                    self.logger.warning(
                        "Skipping enabled Oracle Recruiting Cloud company with invalid configuration",
                        extra={
                            "operation_name": "market_scout.company.invalid",
                            "connector_key": connector_key,
                            "company": company.company,
                        },
                    )
                    continue
            if connector_key == "successfactors":
                try:
                    build_successfactors_site(
                        company=company.company,
                        career_url=company.career_url,
                        external_identifier=company.external_identifier.strip(),
                        country=company.country,
                        role_families=tuple(company.role_families),
                    )
                except ValueError:
                    self.logger.warning(
                        "Skipping enabled SuccessFactors company with invalid configuration",
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
                    "companies_scanned": 0,
                    "jobs_fetched": 0,
                    "jobs_new": 0,
                    "jobs_updated": 0,
                    "jobs_closed": 0,
                    "jobs_archived": 0,
                    "jobs_ignored": 0,
                    "jobs_matched": 0,
                    "alerts_sent": 0,
                    "alerts_failed": 0,
                    "requests_made": 0,
                    "retries": 0,
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
            summary["companies_scanned"] = int(summary["companies_scanned"]) + run.companies_scanned
            summary["jobs_fetched"] = int(summary["jobs_fetched"]) + run.jobs_fetched
            summary["jobs_new"] = int(summary["jobs_new"]) + run.jobs_inserted
            summary["jobs_updated"] = int(summary["jobs_updated"]) + run.jobs_updated
            summary["jobs_closed"] = int(summary["jobs_closed"]) + run.jobs_closed
            summary["jobs_archived"] = int(summary["jobs_archived"]) + run.jobs_archived
            summary["jobs_ignored"] = int(summary["jobs_ignored"]) + run.jobs_ignored
            summary["jobs_matched"] = int(summary["jobs_matched"]) + run.jobs_matched
            summary["alerts_sent"] = int(summary["alerts_sent"]) + run.alerts_sent
            summary["alerts_failed"] = int(summary["alerts_failed"]) + run.alerts_failed
            summary["requests_made"] = int(summary["requests_made"]) + run.requests_made
            summary["retries"] = int(summary["retries"]) + run.retries
            summary["failures"] = int(summary["failures"]) + (1 if run.failed else 0)

        return [summary_by_connector[connector_key] for connector_key in connector_order]

    def _connector_runner(
        self,
        connector_key: str,
    ) -> Callable[[CompanyPreference], Awaitable[ConnectorRunSummary]] | None:
        if connector_key == "greenhouse":
            return self._run_greenhouse_company
        if connector_key == "ashby":
            return self._run_ashby_company
        if connector_key == "lever":
            return self._run_lever_company
        if connector_key == "microsoft-careers":
            return self._run_microsoft_company
        if connector_key == "workday":
            return self._run_workday_company
        if connector_key == "smartrecruiters":
            return self._run_smartrecruiters_company
        if connector_key == "icims":
            return self._run_icims_company
        if connector_key == "jobvite":
            return self._run_jobvite_company
        if connector_key == "comeet":
            return self._run_comeet_company
        if connector_key == "oracle-recruiting-cloud":
            return self._run_oracle_company
        if connector_key == "successfactors":
            return self._run_successfactors_company
        if connector_key == "google-careers":
            return self._run_google_company
        if connector_key == "amazon-jobs":
            return self._run_amazon_company
        return None

    async def _reconcile_connector_inventory(
        self,
        *,
        conn,
        company: CompanyPreference,
        connector_key: str,
        observed_external_job_ids: set[str],
        now: datetime,
    ) -> ConnectorLifecycleDelta:
        jobs_closed = 0
        jobs_archived = 0
        rows = await conn.fetch(
            """
            SELECT job_id, lifecycle_status, closed_at, archived_at, consecutive_missed_syncs
            FROM jobs
            WHERE connector_key = $1
              AND ($2::text IS NULL OR company_id = $2::text)
              AND lifecycle_status NOT IN ('archived', 'deleted')
              AND NOT (external_job_id = ANY($3::text[]))
            """,
            connector_key,
            company.id or None,
            list(observed_external_job_ids),
        )
        for row in rows:
            current_status = str(row["lifecycle_status"] or "active")
            next_missed_syncs = int(row["consecutive_missed_syncs"] or 0) + 1
            transition = lifecycle_for_missed_syncs(
                current_status=current_status,
                consecutive_missed_syncs=next_missed_syncs,
                current_closed_at=row["closed_at"],
                current_archived_at=row["archived_at"],
                settings=self.settings,
                now=now,
            )
            if transition.lifecycle_status == "closed" and current_status != "closed":
                jobs_closed += 1
            if transition.lifecycle_status == "archived" and current_status != "archived":
                jobs_archived += 1
            await conn.execute(
                """
                UPDATE jobs
                SET consecutive_missed_syncs = $2,
                    source_status = $3,
                    lifecycle_status = $4,
                    closed_at = $5,
                    archived_at = $6,
                    last_changed_at = CASE
                        WHEN lifecycle_status IS DISTINCT FROM $4
                          OR source_status IS DISTINCT FROM $3
                        THEN NOW()
                        ELSE last_changed_at
                    END
                WHERE job_id = $1
                """,
                str(row["job_id"]),
                next_missed_syncs,
                transition.source_status,
                transition.lifecycle_status,
                transition.closed_at,
                transition.archived_at,
            )
        return ConnectorLifecycleDelta(
            jobs_closed=jobs_closed,
            jobs_archived=jobs_archived,
        )

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

    async def _run_company_connector(
        self,
        *,
        company: CompanyPreference,
        connector_key: str,
        collect_operation_name: str,
        collect_fn: Callable[[ConnectorCursor], object],
    ) -> ConnectorRunSummary:
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
                    company_id,
                    run_status,
                    cursor_before
                )
                VALUES ($1, $2, $3, 'running', $4)
                """,
                run_id,
                connector_key,
                company.id or None,
                cursor_before,
            )

        connector_cursor = ConnectorCursor(cursor=cursor_before, last_published_at=last_successful_sync)
        attempts = {"count": 0}

        def _collect() -> object:
            attempts["count"] += 1
            return collect_fn(connector_cursor)

        try:
            result = await asyncio.to_thread(
                retry_sync,
                _collect,
                policy=self.retry_policy,
                logger=self.logger,
                operation_name=collect_operation_name,
            )
            retry_count = max(0, attempts["count"] - 1)
            self.logger.info(
                "Collected jobs from connector",
                extra={
                    "operation_name": "market_scout.connector.collect",
                    "connector_key": connector_key,
                    "jobs_fetched": len(result.jobs),
                    "requests_made": result.requests_made,
                    "retries": retry_count,
                    "inventory_complete": result.exhausted,
                    "pages_scanned": result.pages_scanned,
                    "expected_pages": result.expected_pages,
                    "partial_reason": result.partial_reason,
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
                retry_count=retry_count,
                requests_made=result.requests_made,
                inventory_complete=result.exhausted,
                pages_scanned=result.pages_scanned,
                expected_pages=result.expected_pages,
                partial_reason=result.partial_reason,
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
                    "jobs_closed": summary.jobs_closed,
                    "jobs_archived": summary.jobs_archived,
                    "jobs_ignored": summary.jobs_ignored,
                    "alerts_sent": summary.alerts_sent,
                    "alerts_failed": summary.alerts_failed,
                    "requests_made": summary.requests_made,
                    "retries": summary.retries,
                    "inventory_complete": summary.inventory_complete,
                    "pages_scanned": summary.pages_scanned,
                    "expected_pages": summary.expected_pages,
                    "partial_reason": summary.partial_reason,
                },
            )
            return summary
        except BaseException as exc:  # noqa: BLE001
            retry_count = max(0, attempts["count"] - 1)
            async with connection() as conn:
                await conn.execute(
                    """
                    UPDATE connector_runs
                    SET finished_at = NOW(),
                        run_status = 'failed',
                        error_message = $2,
                        retries = $3,
                        inventory_complete = FALSE,
                        partial_reason = 'run_failed'
                    WHERE run_id = $1
                    """,
                    run_id,
                    str(exc)[:1000],
                    retry_count,
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

    async def _run_greenhouse_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        board = GreenhouseBoard(company=company.company, token=company.external_identifier.strip())
        connector = GreenhouseJobConnector(board=board, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"greenhouse:{board.token}",
            collect_operation_name=f"greenhouse.collect.{board.token}",
            collect_fn=connector.collect,
        )

    async def _run_ashby_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        board = AshbyBoard(
            company=company.company,
            token=company.external_identifier.strip(),
            country=company.country,
        )
        connector = AshbyJobConnector(board=board, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"ashby:{board.token}",
            collect_operation_name=f"ashby.collect.{board.token}",
            collect_fn=connector.collect,
        )

    async def _run_lever_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        board = LeverBoard(company=company.company, token=company.external_identifier.strip())
        connector = LeverJobConnector(board=board, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"lever:{board.token}",
            collect_operation_name=f"lever.collect.{board.token}",
            collect_fn=connector.collect,
        )

    async def _run_microsoft_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = MicrosoftCareerSite(
            company=company.company,
            domain=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = MicrosoftCareersJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"microsoft-careers:{site.domain}",
            collect_operation_name=f"microsoft-careers.collect.{site.domain}",
            collect_fn=connector.collect,
        )

    async def _run_workday_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_workday_career_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = WorkdayJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"workday:{site.identifier}",
            collect_operation_name=f"workday.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_smartrecruiters_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_smartrecruiters_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = SmartRecruitersJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"smartrecruiters:{site.identifier}",
            collect_operation_name=f"smartrecruiters.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_google_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_google_career_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = GoogleCareersJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"google-careers:{site.identifier}",
            collect_operation_name=f"google-careers.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_icims_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_icims_career_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = ICIMSJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"icims:{site.identifier}",
            collect_operation_name=f"icims.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_jobvite_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_jobvite_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = JobviteJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"jobvite:{site.identifier}",
            collect_operation_name=f"jobvite.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_comeet_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_comeet_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = ComeetJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"comeet:{site.identifier}",
            collect_operation_name=f"comeet.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_oracle_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_oracle_recruiting_cloud_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = OracleRecruitingCloudConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"oracle-recruiting-cloud:{site.identifier}",
            collect_operation_name=f"oracle-recruiting-cloud.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_successfactors_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_successfactors_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = SuccessFactorsJobConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"successfactors:{site.identifier}",
            collect_operation_name=f"successfactors.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

    async def _run_amazon_company(self, company: CompanyPreference) -> ConnectorRunSummary:
        site = build_amazon_career_site(
            company=company.company,
            career_url=company.career_url,
            external_identifier=company.external_identifier.strip(),
            country=company.country,
            role_families=tuple(company.role_families),
        )
        connector = AmazonJobsConnector(site=site, connector_settings=self.settings.connectors)
        return await self._run_company_connector(
            company=company,
            connector_key=f"amazon-jobs:{site.identifier}",
            collect_operation_name=f"amazon-jobs.collect.{site.identifier}",
            collect_fn=connector.collect,
        )

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
        retry_count: int,
        requests_made: int,
        inventory_complete: bool,
        pages_scanned: int,
        expected_pages: int | None,
        partial_reason: str | None,
    ) -> ConnectorRunSummary:
        jobs_inserted = 0
        jobs_updated = 0
        jobs_closed = 0
        jobs_archived = 0
        jobs_ignored = 0
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
            existing_jobs_by_external_id: dict[str, dict[str, object]] = {}
            if jobs:
                rows = await conn.fetch(
                    """
                    SELECT external_job_id, job_id, content_hash, lifecycle_status, source_status, closed_at, archived_at
                    FROM jobs
                    WHERE connector_key = $1
                      AND external_job_id = ANY($2::text[])
                    """,
                    connector_key,
                    [job.external_job_id for job in jobs],
                )
                existing_jobs_by_external_id = {
                    str(row["external_job_id"]): {
                        "job_id": str(row["job_id"]),
                        "content_hash": str(row["content_hash"] or ""),
                        "lifecycle_status": str(row["lifecycle_status"] or "active"),
                        "source_status": str(row["source_status"] or "observed"),
                        "closed_at": row["closed_at"],
                        "archived_at": row["archived_at"],
                    }
                    for row in rows
                }

            observed_external_job_ids: set[str] = set()
            for job in jobs:
                observed_external_job_ids.add(job.external_job_id)
                job_content_hash = content_hash_for_job(job)
                existing_job = existing_jobs_by_external_id.get(job.external_job_id)
                if existing_job is not None:
                    job_id = str(existing_job["job_id"])
                    job_changed = (
                        str(existing_job["content_hash"] or "") != job_content_hash
                        or str(existing_job["lifecycle_status"] or "active") != "active"
                        or str(existing_job["source_status"] or "observed") != "observed"
                    )
                    if job_changed:
                        jobs_updated += 1
                    else:
                        jobs_ignored += 1
                    await conn.execute(
                        """
                        UPDATE jobs
                        SET last_seen_at = NOW(),
                            last_changed_at = CASE
                                WHEN content_hash IS DISTINCT FROM $3
                                  OR lifecycle_status <> 'active'
                                  OR source_status <> 'observed'
                                THEN NOW()
                                ELSE last_changed_at
                            END,
                            company_id = $4,
                            title = $5,
                            location = $6,
                            remote_policy = $7,
                            apply_url = $8,
                            published_at = $9,
                            content_hash = $3,
                            lifecycle_status = 'active',
                            source_status = 'observed',
                            consecutive_missed_syncs = 0,
                            closed_at = NULL,
                            archived_at = NULL,
                            description_text = $10,
                            metadata = $11::jsonb
                        WHERE connector_key = $1
                          AND external_job_id = $2
                        """,
                        connector_key,
                        job.external_job_id,
                        job_content_hash,
                        company.id or None,
                        job.title,
                        job.location,
                        job.remote_policy,
                        job.apply_url,
                        job.published_at,
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
                        company_id,
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
                        last_changed_at,
                        consecutive_missed_syncs,
                        lifecycle_status,
                        source_status,
                        content_hash,
                        match_score,
                        decision,
                        recommended_resume,
                        job_status,
                        duplicate_source_count,
                        metadata
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, NOW(), 0, 'active', 'observed', $13, $14, $15, $16, 'new', 0, $17::jsonb
                    )
                    """,
                    job_id,
                    company.id or None,
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
                    job_content_hash,
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
                            notification_status,
                            notification_reason,
                            notification_type,
                            notification_evaluated_at,
                            updated_at
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, 'new', $7::jsonb, $8::jsonb, $9, $10, 'pending', 'collected', 'fresh_alert', NOW(), NOW()
                        )
                        ON CONFLICT (user_id, job_id) DO UPDATE SET
                            match_score = EXCLUDED.match_score,
                            decision = EXCLUDED.decision,
                            recommended_resume = EXCLUDED.recommended_resume,
                            why = EXCLUDED.why,
                            gaps = EXCLUDED.gaps,
                            provider = EXCLUDED.provider,
                            country_code = EXCLUDED.country_code,
                            notification_status = EXCLUDED.notification_status,
                            notification_reason = EXCLUDED.notification_reason,
                            notification_type = EXCLUDED.notification_type,
                            notification_evaluated_at = EXCLUDED.notification_evaluated_at,
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
                    notification_decision = evaluate_notification_decision(
                        job=job,
                        match=match,
                        user=user_context.user,
                        settings=self.settings,
                        published_at=published_at,
                        first_seen_at=now,
                        last_changed_at=now,
                        delivery_phase="fresh",
                        initial_sync=initial_sync,
                        now=now,
                        remaining_initial_alert_budget=remaining_initial_alert_budget,
                        minimum_match_score_override=user_context.minimum_match_score,
                        freshness_hours_override=user_context.freshness_hours,
                    )
                    await self._set_job_match_notification_state(
                        conn=conn,
                        user_id=user_context.user.id,
                        job_id=job_id,
                        notification_status=notification_decision.notification_status,
                        notification_reason=notification_decision.reason_code,
                        notification_type=notification_decision.notification_type,
                    )
                    if not notification_decision.should_send:
                        continue

                    inserted_alert = await self._upsert_user_alert(
                        conn=conn,
                        job_id=job_id,
                        user_id=user_context.user.id,
                        decision=match.decision,
                        notification_type=notification_decision.notification_type,
                        reason_code=notification_decision.reason_code,
                        payload={
                            "why": match.top_strengths,
                            "gaps": match.gaps,
                            "recommended_resume": match.recommended_resume,
                            "country_code": country_code,
                        },
                    )
                    if inserted_alert is None:
                        await self._set_job_match_notification_state(
                            conn=conn,
                            user_id=user_context.user.id,
                            job_id=job_id,
                            notification_status="sent",
                            notification_reason="already_alerted",
                            notification_type=notification_decision.notification_type,
                            mark_alerted=True,
                        )
                        continue
                    if initial_sync:
                        remaining_initial_alert_budget = max(0, remaining_initial_alert_budget - 1)
                    sent, failed = await self._send_inserted_alert(
                        conn=conn,
                        alert_id=inserted_alert,
                        job_id=job_id,
                        job=job,
                        match=match,
                        user_context=user_context,
                        published_at=published_at,
                        country_code=country_code,
                        now=now,
                        notification_type=notification_decision.notification_type,
                        reason_code=notification_decision.reason_code,
                    )
                    alerts_sent += sent
                    alerts_failed += failed

            if inventory_complete:
                lifecycle_delta = await self._reconcile_connector_inventory(
                    conn=conn,
                    company=company,
                    connector_key=connector_key,
                    observed_external_job_ids=observed_external_job_ids,
                    now=now,
                )
                jobs_closed += lifecycle_delta.jobs_closed
                jobs_archived += lifecycle_delta.jobs_archived
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
                    jobs_updated = $4,
                    jobs_closed = $5,
                    jobs_archived = $6,
                    jobs_ignored = $7,
                    jobs_matched = $8,
                    alerts_sent = $9,
                    alerts_failed = $10,
                    requests_made = $11,
                    retries = $12,
                    cursor_after = $13,
                    inventory_complete = $14,
                    pages_scanned = $15,
                    expected_pages = $16,
                    partial_reason = $17
                WHERE run_id = $1
                """,
                run_id,
                len(jobs),
                jobs_inserted,
                jobs_updated,
                jobs_closed,
                jobs_archived,
                jobs_ignored,
                jobs_matched,
                alerts_sent,
                alerts_failed,
                requests_made,
                retry_count,
                next_cursor,
                inventory_complete,
                pages_scanned,
                expected_pages,
                partial_reason,
            )

            return ConnectorRunSummary(
                connector_key=connector_key,
                company=company.company,
                jobs_fetched=len(jobs),
                jobs_inserted=jobs_inserted,
                jobs_updated=jobs_updated,
                jobs_closed=jobs_closed,
                jobs_archived=jobs_archived,
                jobs_ignored=jobs_ignored,
                jobs_matched=jobs_matched,
                alerts_sent=alerts_sent,
                alerts_failed=alerts_failed,
                requests_made=requests_made,
                retries=retry_count,
                inventory_complete=inventory_complete,
                pages_scanned=pages_scanned,
                expected_pages=expected_pages,
                partial_reason=partial_reason,
            )

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
        job_timestamps = await conn.fetchrow(
            """
            SELECT first_seen_at, last_changed_at
            FROM jobs
            WHERE job_id = $1
            """,
            job_id,
        )
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
            notification_decision = evaluate_notification_decision(
                job=job,
                match=match,
                user=user_context.user,
                settings=self.settings,
                published_at=published_at,
                first_seen_at=(job_timestamps["first_seen_at"] if job_timestamps is not None else None),
                last_changed_at=(job_timestamps["last_changed_at"] if job_timestamps is not None else None),
                delivery_phase="recovery",
                initial_sync=False,
                now=now,
                remaining_initial_alert_budget=0,
                minimum_match_score_override=user_context.minimum_match_score,
                freshness_hours_override=user_context.freshness_hours,
            )
            await self._set_job_match_notification_state(
                conn=conn,
                user_id=user_id,
                job_id=job_id,
                notification_status=notification_decision.notification_status,
                notification_reason=notification_decision.reason_code,
                notification_type=notification_decision.notification_type,
            )
            if not notification_decision.should_send:
                continue

            inserted_alert = await self._upsert_user_alert(
                conn=conn,
                job_id=job_id,
                user_id=user_id,
                decision=match.decision,
                notification_type=notification_decision.notification_type,
                reason_code=notification_decision.reason_code,
                payload={
                    "why": match.top_strengths,
                    "gaps": match.gaps,
                    "recommended_resume": match.recommended_resume,
                    "country_code": country_code,
                },
            )
            if inserted_alert is None:
                await self._set_job_match_notification_state(
                    conn=conn,
                    user_id=user_id,
                    job_id=job_id,
                    notification_status="sent",
                    notification_reason="already_alerted",
                    notification_type=notification_decision.notification_type,
                    mark_alerted=True,
                )
                continue

            sent, failed = await self._send_inserted_alert(
                conn=conn,
                alert_id=inserted_alert,
                job_id=job_id,
                job=job,
                match=match,
                user_context=user_context,
                published_at=published_at,
                country_code=country_code,
                now=now,
                notification_type=notification_decision.notification_type,
                reason_code=notification_decision.reason_code,
            )
            alerts_sent += sent
            alerts_failed += failed

        return alerts_sent, alerts_failed

    async def _upsert_user_alert(
        self,
        *,
        conn,
        job_id: str,
        user_id: str,
        decision: str,
        notification_type: str,
        reason_code: str,
        payload: dict[str, object],
    ) -> str | None:
        alert_id = str(uuid5(NAMESPACE_URL, f"{job_id}:{user_id}:telegram:{decision}"))
        return await conn.fetchval(
            """
            INSERT INTO user_alerts (
                user_alert_id,
                job_id,
                user_id,
                channel,
                decision,
                alert_status,
                notification_type,
                reason_code,
                evaluated_at,
                payload
            )
            VALUES ($1, $2, $3, 'telegram', $4, 'pending', $5, $6, NOW(), $7::jsonb)
            ON CONFLICT (user_id, job_id, channel, decision)
            DO UPDATE SET
                alert_status = 'pending',
                notification_type = EXCLUDED.notification_type,
                reason_code = EXCLUDED.reason_code,
                evaluated_at = NOW(),
                payload = EXCLUDED.payload,
                sent_at = CASE WHEN user_alerts.alert_status = 'sent' THEN user_alerts.sent_at ELSE NULL END,
                failure_reason = CASE WHEN user_alerts.alert_status = 'sent' THEN user_alerts.failure_reason ELSE NULL END
            WHERE user_alerts.alert_status <> 'sent'
            RETURNING user_alert_id
            """,
            alert_id,
            job_id,
            user_id,
            decision,
            notification_type,
            reason_code,
            json.dumps(payload),
        )

    async def _set_job_match_notification_state(
        self,
        *,
        conn,
        user_id: str,
        job_id: str,
        notification_status: str,
        notification_reason: str,
        notification_type: str,
        mark_alerted: bool = False,
        increment_attempts: bool = False,
    ) -> None:
        await conn.execute(
            """
            UPDATE job_matches
            SET notification_status = $3,
                notification_reason = $4,
                notification_type = $5,
                notification_evaluated_at = NOW(),
                notification_attempts = CASE
                    WHEN $6 THEN COALESCE(notification_attempts, 0) + 1
                    ELSE COALESCE(notification_attempts, 0)
                END,
                alerted_at = CASE
                    WHEN $7 THEN COALESCE(alerted_at, NOW())
                    ELSE alerted_at
                END,
                updated_at = NOW()
            WHERE user_id = $1
              AND job_id = $2
            """,
            user_id,
            job_id,
            notification_status,
            notification_reason,
            notification_type,
            increment_attempts,
            mark_alerted,
        )

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
        notification_type: str,
        reason_code: str,
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
                    sent_at = NOW(),
                    reason_code = $2
                WHERE user_alert_id = $1
                """,
                alert_id,
                reason_code,
            )
            await self._set_job_match_notification_state(
                conn=conn,
                user_id=user_context.user.id,
                job_id=job_id,
                notification_status="sent",
                notification_reason=reason_code,
                notification_type=notification_type,
                mark_alerted=True,
                increment_attempts=True,
            )
            return 1, 0
        except Exception as exc:  # noqa: BLE001
            await conn.execute(
                """
                UPDATE user_alerts
                SET alert_status = 'failed',
                    failure_reason = $2,
                    reason_code = 'telegram_delivery_failed'
                WHERE user_alert_id = $1
                """,
                alert_id,
                str(exc)[:1000],
            )
            await self._set_job_match_notification_state(
                conn=conn,
                user_id=user_context.user.id,
                job_id=job_id,
                notification_status="failed",
                notification_reason="telegram_delivery_failed",
                notification_type=notification_type,
                increment_attempts=True,
            )
            return 0, 1
