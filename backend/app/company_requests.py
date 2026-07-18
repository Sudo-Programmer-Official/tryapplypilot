from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import NAMESPACE_URL, uuid5

from app.catalog import upsert_company
from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import CompanyPreference, CompanyRequest, UserAccount
from app.job_metadata import normalize_supported_country


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _request_id(user_id: str, company_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"company-request:{user_id}:{company_name.strip().casefold()}"))


def _row_to_company_request(row) -> CompanyRequest:
    return CompanyRequest(
        id=str(row["company_request_id"]),
        user_id=str(row["user_id"]),
        requester_email=str(row["email"]),
        company_name=str(row["company_name"]),
        career_url=str(row["career_url"]),
        connector_suggestion=str(row["connector_suggestion"]),
        external_identifier_suggestion=str(row["external_identifier_suggestion"]),
        notes=str(row["notes"]),
        status=str(row["status"]),  # type: ignore[arg-type]
        admin_notes=str(row["admin_notes"]),
        reviewed_at=_isoformat(row["reviewed_at"]),
        reviewed_by_user_id=str(row["reviewed_by_user_id"]) if row["reviewed_by_user_id"] is not None else None,
        approved_company_id=str(row["approved_company_id"]) if row["approved_company_id"] is not None else None,
        created_at=_isoformat(row["created_at"]),
        updated_at=_isoformat(row["updated_at"]),
    )


async def list_user_company_requests(user_id: str, settings: AppSettings | None = None) -> list[CompanyRequest]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return []
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT cr.*, u.email
            FROM company_requests cr
            INNER JOIN users u ON u.user_id = cr.user_id
            WHERE cr.user_id = $1
            ORDER BY cr.created_at DESC
            """,
            user_id,
        )
    return [_row_to_company_request(row) for row in rows]


async def list_company_requests(settings: AppSettings | None = None) -> list[CompanyRequest]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return []
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT cr.*, u.email
            FROM company_requests cr
            INNER JOIN users u ON u.user_id = cr.user_id
            ORDER BY
                CASE cr.status
                    WHEN 'pending' THEN 0
                    WHEN 'approved' THEN 1
                    ELSE 2
                END,
                cr.created_at DESC
            """
        )
    return [_row_to_company_request(row) for row in rows]


async def create_company_request(
    user: UserAccount,
    *,
    company_name: str,
    career_url: str,
    connector_suggestion: str,
    external_identifier_suggestion: str,
    notes: str,
    settings: AppSettings | None = None,
) -> CompanyRequest:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        raise ValueError("Company requests are unavailable in seed mode.")

    normalized_name = company_name.strip()
    if not normalized_name:
        raise ValueError("Company name is required.")

    async with connection() as conn:
        existing_company = await conn.fetchval(
            "SELECT company_id FROM companies WHERE lower(name) = lower($1)",
            normalized_name,
        )
        if existing_company is not None:
            raise ValueError("That company is already in the catalog.")

        row = await conn.fetchrow(
            """
            INSERT INTO company_requests (
                company_request_id,
                user_id,
                company_name,
                career_url,
                connector_suggestion,
                external_identifier_suggestion,
                notes,
                status,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', NOW())
            ON CONFLICT (company_request_id) DO UPDATE SET
                career_url = EXCLUDED.career_url,
                connector_suggestion = EXCLUDED.connector_suggestion,
                external_identifier_suggestion = EXCLUDED.external_identifier_suggestion,
                notes = EXCLUDED.notes,
                status = 'pending',
                admin_notes = '',
                reviewed_at = NULL,
                reviewed_by_user_id = NULL,
                approved_company_id = NULL,
                updated_at = NOW()
            RETURNING *
            """,
            _request_id(user.id, normalized_name),
            user.id,
            normalized_name,
            career_url.strip(),
            connector_suggestion.strip(),
            external_identifier_suggestion.strip(),
            notes.strip(),
        )
    assert row is not None
    enriched = {**dict(row), "email": user.email}
    return _row_to_company_request(enriched)


async def review_company_request(
    request_id: str,
    *,
    reviewer: UserAccount,
    status: str,
    admin_notes: str,
    connector: str,
    external_identifier: str,
    career_url: str,
    tier: int,
    priority: int,
    poll_interval_minutes: int,
    country: str,
    enabled: bool,
    role_families: list[str],
    settings: AppSettings | None = None,
) -> CompanyRequest:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        raise ValueError("Company request review is unavailable in seed mode.")

    approved_company_id: str | None = None
    async with connection() as conn:
        request_row = await conn.fetchrow(
            """
            SELECT cr.*, u.email
            FROM company_requests cr
            INNER JOIN users u ON u.user_id = cr.user_id
            WHERE cr.company_request_id = $1
            """,
            request_id,
        )
    if request_row is None:
        raise ValueError("Unknown company request.")

    if status == "approved":
        company = await upsert_company(
            CompanyPreference(
                company=str(request_row["company_name"]),
                enabled=enabled,
                tier=tier,
                priority=priority,
                connector=connector.strip() or str(request_row["connector_suggestion"] or "company-api"),
                poll_interval_minutes=poll_interval_minutes,
                country=normalize_supported_country(country),
                career_url=career_url.strip() or str(request_row["career_url"]),
                external_identifier=external_identifier.strip() or str(request_row["external_identifier_suggestion"]),
                role_families=role_families,
            ),
            settings=resolved_settings,
        )
        approved_company_id = company.id

    async with connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE company_requests
            SET status = $2,
                admin_notes = $3,
                reviewed_at = NOW(),
                reviewed_by_user_id = $4,
                approved_company_id = $5,
                updated_at = NOW()
            WHERE company_request_id = $1
            RETURNING *
            """,
            request_id,
            status,
            admin_notes.strip(),
            reviewer.id,
            approved_company_id,
        )
    assert row is not None
    enriched = {**dict(row), "email": str(request_row["email"])}
    return _row_to_company_request(enriched)
