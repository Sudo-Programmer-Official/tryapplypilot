from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import SavedJobRecord


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _saved_job_id(user_id: str, job_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"saved-job:{user_id}:{job_id}"))


def _row_to_saved_job(row) -> SavedJobRecord:
    return SavedJobRecord(
        id=str(row["saved_job_id"]),
        user_id=str(row["user_id"]),
        job_id=str(row["job_id"]),
        saved_at=_isoformat(row["saved_at"]),
    )


async def list_saved_jobs(user_id: str, settings: AppSettings | None = None) -> list[SavedJobRecord]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return []

    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM saved_jobs
            WHERE user_id = $1
            ORDER BY saved_at DESC
            """,
            user_id,
        )
    return [_row_to_saved_job(row) for row in rows]


async def save_job_for_user(user_id: str, job_id: str, settings: AppSettings | None = None) -> SavedJobRecord:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        raise ValueError("Saved jobs are unavailable in seed mode.")

    async with connection() as conn:
        existing_job = await conn.fetchval(
            "SELECT 1 FROM jobs WHERE job_id = $1",
            job_id,
        )
        if existing_job is None:
            raise ValueError("Unknown job id.")

        row = await conn.fetchrow(
            """
            INSERT INTO saved_jobs (
                saved_job_id,
                user_id,
                job_id,
                saved_at
            )
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (user_id, job_id) DO UPDATE SET
                saved_at = EXCLUDED.saved_at
            RETURNING *
            """,
            _saved_job_id(user_id, job_id),
            user_id,
            job_id,
        )
    assert row is not None
    return _row_to_saved_job(row)


async def remove_saved_job_for_user(user_id: str, job_id: str, settings: AppSettings | None = None) -> bool:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return False

    async with connection() as conn:
        deleted = await conn.fetchval(
            """
            DELETE FROM saved_jobs
            WHERE user_id = $1
              AND job_id = $2
            RETURNING saved_job_id
            """,
            user_id,
            job_id,
        )
    return deleted is not None
