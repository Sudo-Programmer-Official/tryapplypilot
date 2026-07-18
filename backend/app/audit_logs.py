from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import uuid4

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import AuditLogEntry, UserAccount


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


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


def _row_to_audit_log(row) -> AuditLogEntry:
    row_dict = dict(row)
    return AuditLogEntry(
        id=str(row_dict["audit_log_id"]),
        event_type=str(row_dict["event_type"]),
        subject_type=str(row_dict["subject_type"]),
        subject_id=str(row_dict["subject_id"]),
        message=str(row_dict["message"]),
        actor_user_id=str(row_dict["actor_user_id"]) if row_dict.get("actor_user_id") is not None else None,
        actor_email=str(row_dict["email"]) if row_dict.get("email") is not None else None,
        metadata=_json_object(row_dict["metadata"]),
        created_at=_isoformat(row_dict["created_at"]),
    )


async def record_audit_event(
    *,
    event_type: str,
    subject_type: str,
    message: str,
    subject_id: str = "",
    actor_user: UserAccount | None = None,
    actor_user_id: str | None = None,
    metadata: dict[str, object] | None = None,
    settings: AppSettings | None = None,
) -> AuditLogEntry | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None

    effective_actor_user_id = actor_user.id if actor_user is not None else actor_user_id
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO audit_logs (
                audit_log_id,
                actor_user_id,
                event_type,
                subject_type,
                subject_id,
                message,
                metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING *
            """,
            str(uuid4()),
            effective_actor_user_id,
            event_type.strip(),
            subject_type.strip(),
            subject_id.strip(),
            message.strip(),
            json.dumps(metadata or {}),
        )
    if row is None:
        return None
    enriched = {**dict(row), "email": actor_user.email if actor_user is not None else None}
    return _row_to_audit_log(enriched)


async def list_audit_logs(*, limit: int = 100, settings: AppSettings | None = None) -> list[AuditLogEntry]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return []

    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT al.*, u.email
            FROM audit_logs al
            LEFT JOIN users u ON u.user_id = al.actor_user_id
            ORDER BY al.created_at DESC
            LIMIT $1
            """,
            max(1, min(limit, 500)),
        )
    return [_row_to_audit_log(row) for row in rows]
