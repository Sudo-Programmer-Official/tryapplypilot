from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from app.catalog import list_companies as list_catalog_companies, upsert_company
from app.config import AppSettings, get_settings
from app.connectors.registry import build_default_registry
from app.db.client import connection
from app.domain import CompanyPreference
from app.maintenance_service import get_maintenance_service
from app.market_scout import MarketScoutAgent
from app.runtime import get_runtime

ATS_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RUNTIME_SUPPORTED_CONNECTORS = frozenset({"greenhouse", "lever"})


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


def _monitoring_reason(
    company: CompanyPreference,
    *,
    validation_payload: dict[str, object] | None,
) -> tuple[str, str]:
    registry = build_default_registry()
    definition = registry.get(company.connector)
    if not company.enabled:
        return ("disabled", "Monitoring is disabled. Enable the company to resume polling.")
    if definition is None:
        return ("connector_unavailable", "No connector definition exists for this company.")
    if definition.admin_status == "planned":
        return ("planned", "This connector is still planned and cannot poll yet.")
    if company.connector not in RUNTIME_SUPPORTED_CONNECTORS:
        return ("connector_unavailable", "The connector is registered but not implemented in the live runtime yet.")
    if company.connector in {"greenhouse", "lever", "ashby"} and not company.external_identifier.strip():
        return ("missing_identifier", "The ATS board identifier is missing.")
    if company.connector in {"greenhouse", "lever", "ashby"} and not ATS_IDENTIFIER_PATTERN.match(company.external_identifier.strip()):
        return ("invalid_board", "The ATS board identifier format is invalid.")
    if validation_payload is not None and str(validation_payload.get("status")) == "failed":
        return (
            str(validation_payload.get("reason") or "validation_failed"),
            str(validation_payload.get("message") or "Latest validation failed."),
        )
    return ("monitored", "This company is eligible for live polling.")


def _recommended_action(reason: str, connector: str) -> str:
    if reason == "disabled":
        return "Enable monitoring"
    if reason == "missing_identifier":
        return "Add the external board identifier"
    if reason == "invalid_board":
        return "Correct the board identifier and re-validate"
    if reason == "validation_failed":
        return "Review the last validation error"
    if reason == "planned":
        return f"Implement the {connector} connector"
    if reason == "connector_unavailable":
        return f"Finish the {connector} runtime collector"
    return "Monitoring healthy"


async def build_admin_connectors_workspace(settings: AppSettings | None = None) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    runtime = get_runtime()
    sources = await runtime.repositories.sources.list()
    companies = await list_catalog_companies(resolved_settings)
    maintenance = get_maintenance_service()
    maintenance_status = maintenance.status().to_dict() if maintenance is not None else None
    source_by_key = {source.connector_key: source.to_dict() for source in sources}

    async with connection() as conn:
        inventory_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE lifecycle_status = 'active') AS active,
                COUNT(*) FILTER (WHERE lifecycle_status = 'stale') AS stale,
                COUNT(*) FILTER (WHERE lifecycle_status = 'closed') AS closed,
                COUNT(*) FILTER (WHERE lifecycle_status = 'expired') AS expired,
                COUNT(*) FILTER (WHERE lifecycle_status = 'archived') AS archived,
                COUNT(*) FILTER (WHERE lifecycle_status = 'deleted') AS deleted,
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (WHERE first_seen_at >= date_trunc('day', NOW())) AS new_today
            FROM jobs
            """
        )
        collected_lifetime = int(await conn.fetchval("SELECT COALESCE(SUM(jobs_inserted), 0) FROM connector_runs") or 0)
        job_stats_rows = await conn.fetch(
            """
            SELECT
                company_id,
                split_part(connector_key, ':', 1) AS connector_group,
                COUNT(*) FILTER (WHERE lifecycle_status = 'active') AS active_jobs,
                COUNT(*) FILTER (WHERE lifecycle_status = 'stale') AS stale_jobs,
                COUNT(*) FILTER (WHERE lifecycle_status = 'closed') AS closed_jobs,
                COUNT(*) FILTER (WHERE lifecycle_status = 'expired') AS expired_jobs,
                COUNT(*) FILTER (WHERE lifecycle_status = 'archived') AS archived_jobs
            FROM jobs
            GROUP BY company_id, split_part(connector_key, ':', 1)
            """
        )
        run_stats_rows = await conn.fetch(
            """
            SELECT
                company_id,
                split_part(connector_key, ':', 1) AS connector_group,
                MAX(finished_at) FILTER (WHERE run_status = 'succeeded') AS last_successful_sync,
                MAX(finished_at) FILTER (WHERE run_status = 'failed') AS last_failed_sync,
                COUNT(*) FILTER (
                    WHERE run_status = 'failed'
                      AND started_at >= NOW() - INTERVAL '7 days'
                ) AS recent_failures
            FROM connector_runs
            GROUP BY company_id, split_part(connector_key, ':', 1)
            """
        )
        run_history_rows = await conn.fetch(
            """
            SELECT
                cr.run_id,
                cr.connector_key,
                split_part(cr.connector_key, ':', 1) AS connector_group,
                cr.company_id,
                c.name AS company_name,
                cr.started_at,
                cr.finished_at,
                cr.run_status,
                cr.jobs_fetched,
                cr.jobs_inserted,
                cr.jobs_updated,
                cr.jobs_matched,
                cr.alerts_sent,
                cr.alerts_failed,
                cr.trigger,
                cr.error_message
            FROM connector_runs cr
            LEFT JOIN companies c ON c.company_id = cr.company_id
            ORDER BY cr.started_at DESC
            LIMIT 80
            """
        )
        table_counts = await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM jobs) AS jobs,
                (SELECT COUNT(*) FROM connector_runs) AS connector_runs,
                (SELECT COUNT(*) FROM user_alerts) AS user_alerts,
                (SELECT COUNT(*) FROM alerts) AS alerts,
                (SELECT COUNT(*) FROM job_matches) AS job_matches,
                (SELECT COUNT(*) FROM saved_jobs) AS saved_jobs
            """
        )
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
        company_rows = await conn.fetch(
            """
            SELECT company_id, metadata
            FROM companies
            """
        )

    company_job_stats: dict[str, dict[str, int]] = {}
    connector_job_stats: dict[str, dict[str, int]] = {}
    for row in job_stats_rows:
        company_id = str(row["company_id"]) if row["company_id"] is not None else ""
        connector_group = str(row["connector_group"] or "")
        stats = {
            "active_jobs": int(row["active_jobs"] or 0),
            "stale_jobs": int(row["stale_jobs"] or 0),
            "closed_jobs": int(row["closed_jobs"] or 0),
            "expired_jobs": int(row["expired_jobs"] or 0),
            "archived_jobs": int(row["archived_jobs"] or 0),
        }
        if company_id:
            company_job_stats[company_id] = stats
        connector_stats = connector_job_stats.setdefault(
            connector_group,
            {"active_jobs": 0, "stale_jobs": 0, "closed_jobs": 0, "expired_jobs": 0, "archived_jobs": 0},
        )
        for key, value in stats.items():
            connector_stats[key] += value

    company_run_stats: dict[str, dict[str, object]] = {}
    for row in run_stats_rows:
        company_id = str(row["company_id"]) if row["company_id"] is not None else ""
        if not company_id:
            continue
        company_run_stats[company_id] = {
            "last_successful_sync": row["last_successful_sync"].isoformat() if row["last_successful_sync"] is not None else None,
            "last_failed_sync": row["last_failed_sync"].isoformat() if row["last_failed_sync"] is not None else None,
            "recent_failures": int(row["recent_failures"] or 0),
        }

    company_metadata = {
        str(row["company_id"]): _json_object(row["metadata"])
        for row in company_rows
    }

    company_workspace_rows: list[dict[str, object]] = []
    coverage_gaps: list[dict[str, object]] = []
    monitored_company_count = 0
    enabled_connector_keys = {company.connector for company in companies if company.enabled}

    for company in companies:
        metadata = company_metadata.get(company.id, {})
        validation_payload = _json_object(metadata.get("connector_validation"))
        reason, reason_detail = _monitoring_reason(company, validation_payload=validation_payload)
        run_stats = company_run_stats.get(company.id, {})
        job_stats = company_job_stats.get(
            company.id,
            {"active_jobs": 0, "stale_jobs": 0, "closed_jobs": 0, "expired_jobs": 0, "archived_jobs": 0},
        )
        source = source_by_key.get(company.connector)
        monitoring_state = "monitored" if reason == "monitored" else "catalog_only"
        if not company.enabled:
            monitoring_state = "disabled"
        elif source is not None and str(source["admin_status"]) == "planned":
            monitoring_state = "planned"
        if reason == "monitored":
            monitored_company_count += 1
        row = {
            "id": company.id,
            "company": company.company,
            "connector": company.connector,
            "connector_label": source["source"] if source is not None else company.connector,
            "layer": source["layer"] if source is not None else "official_ats",
            "roadmap_status": source["admin_status"] if source is not None else "planned",
            "priority": company.priority,
            "tier": company.tier,
            "enabled": company.enabled,
            "poll_interval_minutes": company.poll_interval_minutes,
            "country": company.country,
            "external_identifier": company.external_identifier,
            "career_url": company.career_url,
            "role_families": company.role_families,
            "monitoring_state": monitoring_state,
            "monitoring_reason": reason,
            "monitoring_detail": reason_detail,
            "validation_status": str(validation_payload.get("status") or "pending"),
            "validation_reason": str(validation_payload.get("reason") or reason),
            "validation_message": str(validation_payload.get("message") or reason_detail),
            "validated_at": validation_payload.get("validated_at"),
            "active_jobs": job_stats["active_jobs"],
            "stale_jobs": job_stats["stale_jobs"],
            "closed_jobs": job_stats["closed_jobs"],
            "expired_jobs": job_stats["expired_jobs"],
            "archived_jobs": job_stats["archived_jobs"],
            "last_successful_sync": run_stats.get("last_successful_sync"),
            "last_failed_sync": run_stats.get("last_failed_sync"),
            "recent_failures": int(run_stats.get("recent_failures", 0) or 0),
        }
        company_workspace_rows.append(row)
        if reason != "monitored":
            coverage_gaps.append(
                {
                    "company_id": company.id,
                    "company": company.company,
                    "connector": company.connector,
                    "priority": company.priority,
                    "tier": company.tier,
                    "roadmap_status": row["roadmap_status"],
                    "missing_capability": reason,
                    "recommended_action": _recommended_action(reason, company.connector),
                    "detail": reason_detail,
                }
            )

    connector_workspace_rows: list[dict[str, object]] = []
    for source in sources:
        connector_stats = connector_job_stats.get(
            source.connector_key,
            {"active_jobs": 0, "stale_jobs": 0, "closed_jobs": 0, "expired_jobs": 0, "archived_jobs": 0},
        )
        connector_workspace_rows.append(
            {
                **source.to_dict(),
                "coverage_percent": round(
                    (source.companies_enabled / source.catalog_company_count) * 100, 1
                )
                if source.catalog_company_count > 0
                else 0.0,
                **connector_stats,
            }
        )

    inventory = {
        "active": int(inventory_row["active"] or 0),
        "stale": int(inventory_row["stale"] or 0),
        "closed": int(inventory_row["closed"] or 0),
        "expired": int(inventory_row["expired"] or 0),
        "archived": int(inventory_row["archived"] or 0),
        "deleted": int(inventory_row["deleted"] or 0),
        "collected_lifetime": collected_lifetime,
        "new_today": int(inventory_row["new_today"] or 0),
        "estimated_storage_bytes": int(estimated_storage_bytes) if estimated_storage_bytes is not None else None,
        "total_rows": int(inventory_row["total_rows"] or 0),
    }

    roadmap = [
        {
            "connector_key": source.connector_key,
            "source": source.source,
            "layer": source.layer,
            "roadmap_status": source.admin_status,
            "companies_enabled": source.companies_enabled,
            "catalog_company_count": source.catalog_company_count,
            "coverage_percent": round((source.companies_enabled / source.catalog_company_count) * 100, 1)
            if source.catalog_company_count > 0
            else 0.0,
        }
        for source in sources
    ]

    run_history = [
        {
            "run_id": str(row["run_id"]),
            "connector_key": str(row["connector_key"]),
            "connector_group": str(row["connector_group"] or ""),
            "company_id": str(row["company_id"]) if row["company_id"] is not None else None,
            "company_name": str(row["company_name"]) if row["company_name"] is not None else None,
            "started_at": row["started_at"].isoformat() if row["started_at"] is not None else None,
            "finished_at": row["finished_at"].isoformat() if row["finished_at"] is not None else None,
            "run_status": str(row["run_status"]),
            "jobs_fetched": int(row["jobs_fetched"] or 0),
            "jobs_inserted": int(row["jobs_inserted"] or 0),
            "jobs_updated": int(row["jobs_updated"] or 0),
            "jobs_matched": int(row["jobs_matched"] or 0),
            "alerts_sent": int(row["alerts_sent"] or 0),
            "alerts_failed": int(row["alerts_failed"] or 0),
            "trigger": str(row["trigger"] or "scheduled"),
            "error_message": str(row["error_message"]) if row["error_message"] is not None else None,
            "duration_seconds": (
                max(0.0, float((row["finished_at"] - row["started_at"]).total_seconds()))
                if row["finished_at"] is not None and row["started_at"] is not None
                else None
            ),
        }
        for row in run_history_rows
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overview": {
            "inventory": inventory,
            "connectors_total": len(sources),
            "connectors_live": sum(1 for source in sources if source.admin_status == "live"),
            "connectors_beta": sum(1 for source in sources if source.admin_status == "beta"),
            "connectors_planned": sum(1 for source in sources if source.admin_status == "planned"),
            "catalog_companies": len(companies),
            "monitored_companies": monitored_company_count,
            "coverage_gaps": len(coverage_gaps),
            "enabled_connectors": len(enabled_connector_keys),
        },
        "connectors": connector_workspace_rows,
        "companies": company_workspace_rows,
        "coverage_gaps": sorted(coverage_gaps, key=lambda item: (int(item["tier"]), int(item["priority"]), str(item["company"]))),
        "lifecycle": {
            "settings": {
                "stale_after_missed_syncs": resolved_settings.lifecycle.stale_after_missed_syncs,
                "closed_after_missed_syncs": resolved_settings.lifecycle.closed_after_missed_syncs,
                "archive_after_days": resolved_settings.lifecycle.archive_after_days,
                "delete_after_days": resolved_settings.lifecycle.delete_after_days,
                "cleanup_batch_size": resolved_settings.maintenance.cleanup_batch_size,
                "maintenance_interval_minutes": resolved_settings.maintenance.interval_minutes,
            },
            "inventory": inventory,
            "maintenance": maintenance_status,
        },
        "database": {
            "estimated_storage_bytes": inventory["estimated_storage_bytes"],
            "jobs_rows": int(table_counts["jobs"] or 0),
            "connector_runs_rows": int(table_counts["connector_runs"] or 0),
            "alerts_rows": int(table_counts["alerts"] or 0),
            "user_alerts_rows": int(table_counts["user_alerts"] or 0),
            "job_matches_rows": int(table_counts["job_matches"] or 0),
            "saved_jobs_rows": int(table_counts["saved_jobs"] or 0),
            "active_inventory": inventory["active"],
            "archived_inventory": inventory["archived"],
            "collected_lifetime": collected_lifetime,
        },
        "roadmap": roadmap,
        "run_history": run_history,
    }


async def validate_company_connector(company_id: str, settings: AppSettings | None = None) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    companies = {company.id: company for company in await list_catalog_companies(resolved_settings)}
    company = companies.get(company_id)
    if company is None:
        raise ValueError("Unknown company.")
    reason, message = _monitoring_reason(company, validation_payload=None)
    status = "passed" if reason == "monitored" else "failed"
    payload = {
        "status": status,
        "reason": reason,
        "message": message,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    async with connection() as conn:
        await conn.execute(
            """
            UPDATE companies
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{connector_validation}',
                $2::jsonb,
                true
            ),
                updated_at = NOW()
            WHERE company_id = $1
            """,
            company_id,
            json.dumps(payload),
        )
    return payload


async def set_company_monitoring(company_id: str, enabled: bool, settings: AppSettings | None = None) -> CompanyPreference:
    resolved_settings = settings or get_settings()
    companies = {company.id: company for company in await list_catalog_companies(resolved_settings)}
    company = companies.get(company_id)
    if company is None:
        raise ValueError("Unknown company.")
    return await upsert_company(
        CompanyPreference(
            id=company.id,
            company=company.company,
            enabled=enabled,
            tier=company.tier,
            priority=company.priority,
            connector=company.connector,
            poll_interval_minutes=company.poll_interval_minutes,
            country=company.country,
            career_url=company.career_url,
            external_identifier=company.external_identifier,
            role_families=company.role_families,
        ),
        resolved_settings,
    )


async def list_company_jobs_for_admin(company_id: str) -> list[dict[str, object]]:
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                job_id,
                title,
                location,
                apply_url,
                lifecycle_status,
                source_status,
                published_at,
                first_seen_at,
                last_seen_at,
                closed_at,
                archived_at
            FROM jobs
            WHERE company_id = $1
            ORDER BY COALESCE(published_at, first_seen_at) DESC
            LIMIT 50
            """,
            company_id,
        )
    return [
        {
            "job_id": str(row["job_id"]),
            "title": str(row["title"]),
            "location": str(row["location"]),
            "apply_url": str(row["apply_url"]),
            "lifecycle_status": str(row["lifecycle_status"]),
            "source_status": str(row["source_status"]),
            "published_at": row["published_at"].isoformat() if row["published_at"] is not None else None,
            "first_seen_at": row["first_seen_at"].isoformat() if row["first_seen_at"] is not None else None,
            "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] is not None else None,
            "closed_at": row["closed_at"].isoformat() if row["closed_at"] is not None else None,
            "archived_at": row["archived_at"].isoformat() if row["archived_at"] is not None else None,
        }
        for row in rows
    ]


async def list_company_connector_errors(company_id: str) -> list[dict[str, object]]:
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT run_id, connector_key, started_at, finished_at, error_message
            FROM connector_runs
            WHERE company_id = $1
              AND run_status = 'failed'
            ORDER BY started_at DESC
            LIMIT 20
            """,
            company_id,
        )
    return [
        {
            "run_id": str(row["run_id"]),
            "connector_key": str(row["connector_key"]),
            "started_at": row["started_at"].isoformat() if row["started_at"] is not None else None,
            "finished_at": row["finished_at"].isoformat() if row["finished_at"] is not None else None,
            "error_message": str(row["error_message"]) if row["error_message"] is not None else None,
        }
        for row in rows
    ]


async def run_connector_now(connector_key: str, settings: AppSettings | None = None) -> dict[str, object]:
    resolved_settings = settings or get_settings()
    summary = await MarketScoutAgent(resolved_settings).run_connector_now(connector_key)
    return summary.to_dict()
