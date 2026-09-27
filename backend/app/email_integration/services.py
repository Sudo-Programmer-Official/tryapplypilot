from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from app.auth import create_email_provider_state_token, decode_token
from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import UserAccount
from app.recruiter_intelligence import RecruiterIntelligenceService, RecruiterMessageImportRecord, build_recruiter_intelligence_service

from .models import (
    EmailProviderConnection,
    EmailProviderStatus,
    EmailSyncRun,
    EmailSyncedMessage,
    EmailSyncedThread,
    ProviderAuthorizationRequest,
    ProviderMessage,
)
from .providers import EmailProviderRegistry, build_email_provider_registry


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return decoded
    return []


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


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _connection_id(user_id: str, provider: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"email-provider-connection:{user_id}:{provider.strip().casefold()}"))


def _sync_run_id(connection_id: str, started_at: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"email-sync-run:{connection_id}:{started_at}"))


def _synced_message_id(connection_id: str, provider_message_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"email-sync-message:{connection_id}:{provider_message_id}"))


def _synced_thread_id(connection_id: str, provider_thread_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"email-sync-thread:{connection_id}:{provider_thread_id}"))


def _provider_external_message_id(connection: EmailProviderConnection, item: ProviderMessage) -> str:
    return f"{connection.provider}:{connection.account_email}:{item.provider_message_id}"


def _provider_external_thread_id(connection: EmailProviderConnection, item: ProviderMessage) -> str:
    return f"{connection.provider}:{connection.account_email}:{item.provider_thread_id}"


def _attachment_payload(item: ProviderMessage) -> list[dict[str, object]]:
    return [attachment.to_dict() for attachment in item.attachments]


def _sync_message_metadata(connection: EmailProviderConnection, item: ProviderMessage) -> dict[str, object]:
    return {
        "provider": connection.provider,
        "provider_message_id": item.provider_message_id,
        "provider_thread_id": item.provider_thread_id,
        "provider_history_id": item.provider_history_id,
        "provider_account_email": connection.account_email,
        "attachments": _attachment_payload(item),
        **dict(item.metadata),
    }


def _row_to_connection(row) -> EmailProviderConnection:
    connected_at = row["connected_at"]
    disconnected_at = row["disconnected_at"]
    last_sync_at = row["last_sync_at"]
    for value_name in ("connected_at", "disconnected_at", "last_sync_at"):
        value = locals()[value_name]
        if value is not None and value.tzinfo is None:
            locals()[value_name] = value.replace(tzinfo=timezone.utc)
    if connected_at is not None and connected_at.tzinfo is None:
        connected_at = connected_at.replace(tzinfo=timezone.utc)
    if disconnected_at is not None and disconnected_at.tzinfo is None:
        disconnected_at = disconnected_at.replace(tzinfo=timezone.utc)
    if last_sync_at is not None and last_sync_at.tzinfo is None:
        last_sync_at = last_sync_at.replace(tzinfo=timezone.utc)
    return EmailProviderConnection(
        connection_id=str(row["connection_id"]),
        user_id=str(row["user_id"]),
        provider=str(row["provider"]),
        account_email=str(row["account_email"]),
        status=str(row["status"]),
        scopes=[str(item) for item in _json_list(row["scopes"])],
        connected_at=connected_at.isoformat() if connected_at is not None else None,
        disconnected_at=disconnected_at.isoformat() if disconnected_at is not None else None,
        last_sync_at=last_sync_at.isoformat() if last_sync_at is not None else None,
        sync_cursor=str(row["sync_cursor"] or ""),
        token_reference=str(row["token_reference"] or ""),
        token_metadata=_json_object(row["token_metadata"]),
        metadata=_json_object(row["metadata"]),
    )


def _row_to_sync_run(row) -> EmailSyncRun:
    started_at = row["started_at"]
    completed_at = row["completed_at"]
    failed_at = row["failed_at"]
    if started_at is not None and started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if completed_at is not None and completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    if failed_at is not None and failed_at.tzinfo is None:
        failed_at = failed_at.replace(tzinfo=timezone.utc)
    return EmailSyncRun(
        sync_run_id=str(row["sync_run_id"]),
        connection_id=str(row["connection_id"]),
        user_id=str(row["user_id"]),
        provider=str(row["provider"]),
        account_email=str(row["account_email"]),
        run_status=str(row["run_status"]),
        started_at=started_at.isoformat() if started_at is not None else None,
        completed_at=completed_at.isoformat() if completed_at is not None else None,
        failed_at=failed_at.isoformat() if failed_at is not None else None,
        imported_count=int(row["imported_count"] or 0),
        skipped_count=int(row["skipped_count"] or 0),
        duplicate_count=int(row["duplicate_count"] or 0),
        error_count=int(row["error_count"] or 0),
        metadata=_json_object(row["metadata"]),
    )


def _row_to_synced_message(row) -> EmailSyncedMessage:
    first_synced_at = row["first_synced_at"]
    last_synced_at = row["last_synced_at"]
    if first_synced_at is not None and first_synced_at.tzinfo is None:
        first_synced_at = first_synced_at.replace(tzinfo=timezone.utc)
    if last_synced_at is not None and last_synced_at.tzinfo is None:
        last_synced_at = last_synced_at.replace(tzinfo=timezone.utc)
    from .models import EmailAttachmentReference

    attachments = [
        EmailAttachmentReference(**item)
        for item in _json_list(row["attachment_refs"])
        if isinstance(item, dict)
    ]
    return EmailSyncedMessage(
        sync_message_id=str(row["sync_message_id"]),
        connection_id=str(row["connection_id"]),
        user_id=str(row["user_id"]),
        provider=str(row["provider"]),
        account_email=str(row["account_email"]),
        provider_message_id=str(row["provider_message_id"]),
        provider_thread_id=str(row["provider_thread_id"]),
        canonical_message_id=str(row["canonical_message_id"] or ""),
        canonical_thread_id=str(row["canonical_thread_id"] or ""),
        provider_history_id=str(row["provider_history_id"] or ""),
        attachment_refs=attachments,
        metadata=_json_object(row["metadata"]),
        first_synced_at=first_synced_at.isoformat() if first_synced_at is not None else None,
        last_synced_at=last_synced_at.isoformat() if last_synced_at is not None else None,
    )


def _row_to_synced_thread(row) -> EmailSyncedThread:
    first_synced_at = row["first_synced_at"]
    last_synced_at = row["last_synced_at"]
    if first_synced_at is not None and first_synced_at.tzinfo is None:
        first_synced_at = first_synced_at.replace(tzinfo=timezone.utc)
    if last_synced_at is not None and last_synced_at.tzinfo is None:
        last_synced_at = last_synced_at.replace(tzinfo=timezone.utc)
    return EmailSyncedThread(
        sync_thread_id=str(row["sync_thread_id"]),
        connection_id=str(row["connection_id"]),
        user_id=str(row["user_id"]),
        provider=str(row["provider"]),
        account_email=str(row["account_email"]),
        provider_thread_id=str(row["provider_thread_id"]),
        canonical_thread_id=str(row["canonical_thread_id"] or ""),
        subject=str(row["subject"] or ""),
        metadata=_json_object(row["metadata"]),
        first_synced_at=first_synced_at.isoformat() if first_synced_at is not None else None,
        last_synced_at=last_synced_at.isoformat() if last_synced_at is not None else None,
    )


class EmailIntegrationStore(Protocol):
    async def save_connection(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        ...

    async def get_connection(self, user_id: str, provider: str) -> EmailProviderConnection | None:
        ...

    async def list_connections_for_user(self, user_id: str) -> list[EmailProviderConnection]:
        ...

    async def save_sync_run(self, run: EmailSyncRun) -> EmailSyncRun:
        ...

    async def list_sync_runs_for_user(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        limit: int = 50,
    ) -> list[EmailSyncRun]:
        ...

    async def get_synced_message(
        self,
        connection_id: str,
        provider_message_id: str,
    ) -> EmailSyncedMessage | None:
        ...

    async def save_synced_message(self, item: EmailSyncedMessage) -> EmailSyncedMessage:
        ...

    async def get_synced_thread(
        self,
        connection_id: str,
        provider_thread_id: str,
    ) -> EmailSyncedThread | None:
        ...

    async def save_synced_thread(self, item: EmailSyncedThread) -> EmailSyncedThread:
        ...


@dataclass
class InMemoryEmailIntegrationStore:
    connections: dict[str, EmailProviderConnection] | None = None
    sync_runs: dict[str, EmailSyncRun] | None = None
    synced_messages: dict[str, EmailSyncedMessage] | None = None
    synced_threads: dict[str, EmailSyncedThread] | None = None

    def __post_init__(self) -> None:
        self.connections = {} if self.connections is None else self.connections
        self.sync_runs = {} if self.sync_runs is None else self.sync_runs
        self.synced_messages = {} if self.synced_messages is None else self.synced_messages
        self.synced_threads = {} if self.synced_threads is None else self.synced_threads

    async def save_connection(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        assert self.connections is not None
        self.connections[connection.connection_id] = connection
        return connection

    async def get_connection(self, user_id: str, provider: str) -> EmailProviderConnection | None:
        assert self.connections is not None
        key = _connection_id(user_id, provider)
        item = self.connections.get(key)
        if item is None or item.user_id != user_id or item.provider != provider.strip().casefold():
            return None
        return item

    async def list_connections_for_user(self, user_id: str) -> list[EmailProviderConnection]:
        assert self.connections is not None
        items = [item for item in self.connections.values() if item.user_id == user_id]
        return sorted(
            items,
            key=lambda item: (_parse_datetime(item.connected_at or item.last_sync_at or "") or datetime.min.replace(tzinfo=timezone.utc), item.provider),
            reverse=True,
        )

    async def save_sync_run(self, run: EmailSyncRun) -> EmailSyncRun:
        assert self.sync_runs is not None
        self.sync_runs[run.sync_run_id] = run
        return run

    async def list_sync_runs_for_user(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        limit: int = 50,
    ) -> list[EmailSyncRun]:
        assert self.sync_runs is not None
        items = [item for item in self.sync_runs.values() if item.user_id == user_id]
        if provider is not None:
            items = [item for item in items if item.provider == provider.strip().casefold()]
        items = sorted(
            items,
            key=lambda item: (_parse_datetime(item.started_at or "") or datetime.min.replace(tzinfo=timezone.utc), item.sync_run_id),
            reverse=True,
        )
        return items[:limit]

    async def get_synced_message(self, connection_id: str, provider_message_id: str) -> EmailSyncedMessage | None:
        assert self.synced_messages is not None
        key = _synced_message_id(connection_id, provider_message_id)
        return self.synced_messages.get(key)

    async def save_synced_message(self, item: EmailSyncedMessage) -> EmailSyncedMessage:
        assert self.synced_messages is not None
        self.synced_messages[item.sync_message_id] = item
        return item

    async def get_synced_thread(self, connection_id: str, provider_thread_id: str) -> EmailSyncedThread | None:
        assert self.synced_threads is not None
        key = _synced_thread_id(connection_id, provider_thread_id)
        return self.synced_threads.get(key)

    async def save_synced_thread(self, item: EmailSyncedThread) -> EmailSyncedThread:
        assert self.synced_threads is not None
        self.synced_threads[item.sync_thread_id] = item
        return item


class PostgresEmailIntegrationStore:
    async def save_connection(self, item: EmailProviderConnection) -> EmailProviderConnection:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_provider_connections (
                    connection_id,
                    user_id,
                    provider,
                    account_email,
                    status,
                    scopes,
                    connected_at,
                    disconnected_at,
                    last_sync_at,
                    sync_cursor,
                    token_reference,
                    token_metadata,
                    metadata
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6::jsonb, COALESCE($7::timestamptz, NOW()), $8::timestamptz, $9::timestamptz,
                    $10, $11, $12::jsonb, $13::jsonb
                )
                ON CONFLICT (user_id, provider) DO UPDATE SET
                    account_email = EXCLUDED.account_email,
                    status = EXCLUDED.status,
                    scopes = EXCLUDED.scopes,
                    connected_at = EXCLUDED.connected_at,
                    disconnected_at = EXCLUDED.disconnected_at,
                    last_sync_at = EXCLUDED.last_sync_at,
                    sync_cursor = EXCLUDED.sync_cursor,
                    token_reference = EXCLUDED.token_reference,
                    token_metadata = EXCLUDED.token_metadata,
                    metadata = EXCLUDED.metadata
                RETURNING *
                """,
                item.connection_id,
                item.user_id,
                item.provider,
                item.account_email,
                item.status,
                json.dumps(item.scopes),
                item.connected_at,
                item.disconnected_at,
                item.last_sync_at,
                item.sync_cursor,
                item.token_reference,
                json.dumps(item.token_metadata),
                json.dumps(item.metadata),
            )
        assert row is not None
        return _row_to_connection(row)

    async def get_connection(self, user_id: str, provider: str) -> EmailProviderConnection | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM email_provider_connections
                WHERE user_id = $1
                  AND provider = $2
                """,
                user_id,
                provider.strip().casefold(),
            )
        return _row_to_connection(row) if row is not None else None

    async def list_connections_for_user(self, user_id: str) -> list[EmailProviderConnection]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM email_provider_connections
                WHERE user_id = $1
                ORDER BY connected_at DESC, provider ASC
                """,
                user_id,
            )
        return [_row_to_connection(row) for row in rows]

    async def save_sync_run(self, item: EmailSyncRun) -> EmailSyncRun:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_sync_runs (
                    sync_run_id,
                    connection_id,
                    user_id,
                    provider,
                    account_email,
                    run_status,
                    started_at,
                    completed_at,
                    failed_at,
                    imported_count,
                    skipped_count,
                    duplicate_count,
                    error_count,
                    metadata
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, COALESCE($7::timestamptz, NOW()), $8::timestamptz, $9::timestamptz,
                    $10, $11, $12, $13, $14::jsonb
                )
                ON CONFLICT (sync_run_id) DO UPDATE SET
                    run_status = EXCLUDED.run_status,
                    completed_at = EXCLUDED.completed_at,
                    failed_at = EXCLUDED.failed_at,
                    imported_count = EXCLUDED.imported_count,
                    skipped_count = EXCLUDED.skipped_count,
                    duplicate_count = EXCLUDED.duplicate_count,
                    error_count = EXCLUDED.error_count,
                    metadata = EXCLUDED.metadata
                RETURNING *
                """,
                item.sync_run_id,
                item.connection_id,
                item.user_id,
                item.provider,
                item.account_email,
                item.run_status,
                item.started_at,
                item.completed_at,
                item.failed_at,
                item.imported_count,
                item.skipped_count,
                item.duplicate_count,
                item.error_count,
                json.dumps(item.metadata),
            )
        assert row is not None
        return _row_to_sync_run(row)

    async def list_sync_runs_for_user(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        limit: int = 50,
    ) -> list[EmailSyncRun]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM email_sync_runs
                WHERE user_id = $1
                  AND ($2::text IS NULL OR provider = $2)
                ORDER BY started_at DESC, sync_run_id DESC
                LIMIT $3
                """,
                user_id,
                provider.strip().casefold() if provider is not None else None,
                limit,
            )
        return [_row_to_sync_run(row) for row in rows]

    async def get_synced_message(self, connection_id: str, provider_message_id: str) -> EmailSyncedMessage | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM email_synced_messages
                WHERE connection_id = $1
                  AND provider_message_id = $2
                """,
                connection_id,
                provider_message_id,
            )
        return _row_to_synced_message(row) if row is not None else None

    async def save_synced_message(self, item: EmailSyncedMessage) -> EmailSyncedMessage:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_synced_messages (
                    sync_message_id,
                    connection_id,
                    user_id,
                    provider,
                    account_email,
                    provider_message_id,
                    provider_thread_id,
                    canonical_message_id,
                    canonical_thread_id,
                    provider_history_id,
                    attachment_refs,
                    metadata,
                    first_synced_at,
                    last_synced_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12::jsonb,
                    COALESCE($13::timestamptz, NOW()),
                    COALESCE($14::timestamptz, NOW())
                )
                ON CONFLICT (connection_id, provider_message_id) DO UPDATE SET
                    provider_thread_id = EXCLUDED.provider_thread_id,
                    canonical_message_id = EXCLUDED.canonical_message_id,
                    canonical_thread_id = EXCLUDED.canonical_thread_id,
                    provider_history_id = EXCLUDED.provider_history_id,
                    attachment_refs = EXCLUDED.attachment_refs,
                    metadata = EXCLUDED.metadata,
                    last_synced_at = COALESCE(EXCLUDED.last_synced_at, NOW())
                RETURNING *
                """,
                item.sync_message_id,
                item.connection_id,
                item.user_id,
                item.provider,
                item.account_email,
                item.provider_message_id,
                item.provider_thread_id,
                item.canonical_message_id,
                item.canonical_thread_id,
                item.provider_history_id,
                json.dumps([attachment.to_dict() for attachment in item.attachment_refs]),
                json.dumps(item.metadata),
                item.first_synced_at,
                item.last_synced_at,
            )
        assert row is not None
        return _row_to_synced_message(row)

    async def get_synced_thread(self, connection_id: str, provider_thread_id: str) -> EmailSyncedThread | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM email_synced_threads
                WHERE connection_id = $1
                  AND provider_thread_id = $2
                """,
                connection_id,
                provider_thread_id,
            )
        return _row_to_synced_thread(row) if row is not None else None

    async def save_synced_thread(self, item: EmailSyncedThread) -> EmailSyncedThread:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_synced_threads (
                    sync_thread_id,
                    connection_id,
                    user_id,
                    provider,
                    account_email,
                    provider_thread_id,
                    canonical_thread_id,
                    subject,
                    metadata,
                    first_synced_at,
                    last_synced_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, COALESCE($10::timestamptz, NOW()), COALESCE($11::timestamptz, NOW())
                )
                ON CONFLICT (connection_id, provider_thread_id) DO UPDATE SET
                    canonical_thread_id = EXCLUDED.canonical_thread_id,
                    subject = EXCLUDED.subject,
                    metadata = EXCLUDED.metadata,
                    last_synced_at = COALESCE(EXCLUDED.last_synced_at, NOW())
                RETURNING *
                """,
                item.sync_thread_id,
                item.connection_id,
                item.user_id,
                item.provider,
                item.account_email,
                item.provider_thread_id,
                item.canonical_thread_id,
                item.subject,
                json.dumps(item.metadata),
                item.first_synced_at,
                item.last_synced_at,
            )
        assert row is not None
        return _row_to_synced_thread(row)


def build_email_integration_store(settings: AppSettings | None = None) -> EmailIntegrationStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryEmailIntegrationStore()
    return PostgresEmailIntegrationStore()


@dataclass
class EmailIntegrationService:
    settings: AppSettings | None = None
    store: EmailIntegrationStore | None = None
    provider_registry: EmailProviderRegistry | None = None
    recruiter_service: RecruiterIntelligenceService | None = None

    def _settings(self) -> AppSettings:
        return self.settings or get_settings()

    def _store(self) -> EmailIntegrationStore:
        if self.store is not None:
            return self.store
        return build_email_integration_store(self.settings)

    def _providers(self) -> EmailProviderRegistry:
        if self.provider_registry is not None:
            return self.provider_registry
        return build_email_provider_registry(self.settings)

    def _recruiter(self) -> RecruiterIntelligenceService:
        if self.recruiter_service is not None:
            return self.recruiter_service
        return build_recruiter_intelligence_service(self.settings)

    async def begin_provider_oauth(
        self,
        user: UserAccount,
        provider: str,
        *,
        scopes: list[str] | None = None,
        login_hint: str = "",
        metadata: dict[str, object] | None = None,
    ) -> ProviderAuthorizationRequest:
        normalized_provider = provider.strip().casefold()
        requested_scopes = [item.strip() for item in (scopes or []) if item.strip()]
        state_token, expires_in_seconds = create_email_provider_state_token(
            user,
            provider=normalized_provider,
            scopes=requested_scopes,
            metadata=dict(metadata or {}),
            settings=self._settings(),
        )
        authorization_url = await self._providers().get(normalized_provider).build_authorization_url(
            state=state_token,
            scopes=requested_scopes or None,
            login_hint=login_hint.strip() or user.email,
        )
        return ProviderAuthorizationRequest(
            provider=normalized_provider,
            authorization_url=authorization_url,
            expires_in_seconds=expires_in_seconds,
            scopes=requested_scopes,
            metadata={"login_hint": login_hint.strip() or user.email},
        )

    async def complete_provider_oauth(
        self,
        provider: str,
        *,
        state_token: str,
        code: str,
    ) -> EmailProviderConnection:
        normalized_provider = provider.strip().casefold()
        payload = decode_token(state_token, expected_type="email_provider_state", settings=self._settings())
        state_provider = str(payload.get("provider") or "").strip().casefold()
        if state_provider != normalized_provider:
            raise ValueError("OAuth callback provider does not match the signed state token.")
        raw_scopes = payload.get("scopes")
        scopes = [str(item).strip() for item in raw_scopes if str(item).strip()] if isinstance(raw_scopes, list) else []
        state_metadata = payload.get("metadata")
        metadata = dict(state_metadata) if isinstance(state_metadata, dict) else {}
        result = await self._providers().get(normalized_provider).complete_authorization(
            str(payload.get("sub") or "").strip(),
            code=code,
            scopes=scopes or None,
            metadata=metadata,
        )
        return await self.connect_provider(
            str(payload.get("sub") or "").strip(),
            normalized_provider,
            account_email=result.account_email,
            scopes=result.scopes,
            token_reference=result.token_reference,
            token_metadata=result.token_metadata,
            metadata=result.metadata,
        )

    async def connect_provider(
        self,
        user_id: str,
        provider: str,
        *,
        account_email: str,
        scopes: list[str] | None = None,
        token_reference: str,
        token_metadata: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> EmailProviderConnection:
        normalized_provider = provider.strip().casefold()
        existing = await self._store().get_connection(user_id, normalized_provider)
        base = EmailProviderConnection(
            connection_id=_connection_id(user_id, normalized_provider),
            user_id=user_id,
            provider=normalized_provider,
            account_email=account_email.strip().casefold(),
            status="pending",
            scopes=list(scopes or []),
            connected_at=existing.connected_at if existing is not None else _iso_now(),
            disconnected_at=None,
            last_sync_at=existing.last_sync_at if existing is not None else None,
            sync_cursor=existing.sync_cursor if existing is not None else "",
            token_reference=token_reference.strip(),
            token_metadata=dict(token_metadata or (existing.token_metadata if existing is not None else {})),
            metadata=dict(metadata or (existing.metadata if existing is not None else {})),
        )
        resolved = await self._providers().get(normalized_provider).connect(base)
        return await self._store().save_connection(resolved)

    async def disconnect_provider(self, user_id: str, provider: str) -> EmailProviderConnection:
        normalized_provider = provider.strip().casefold()
        existing = await self._store().get_connection(user_id, normalized_provider)
        if existing is None:
            raise ValueError("Unknown email provider connection.")
        resolved = await self._providers().get(normalized_provider).disconnect(existing)
        return await self._store().save_connection(resolved)

    async def list_connections(self, user_id: str) -> list[EmailProviderConnection]:
        return await self._store().list_connections_for_user(user_id)

    async def list_provider_statuses(self, user_id: str) -> list[EmailProviderStatus]:
        connections = await self.list_connections(user_id)
        runs = await self._store().list_sync_runs_for_user(user_id, limit=200)
        latest_by_provider: dict[str, EmailSyncRun] = {}
        for run in runs:
            existing = latest_by_provider.get(run.provider)
            if existing is None or (_parse_datetime(run.started_at or "") or datetime.min.replace(tzinfo=timezone.utc)) > (
                _parse_datetime(existing.started_at or "") or datetime.min.replace(tzinfo=timezone.utc)
            ):
                latest_by_provider[run.provider] = run
        return [
            EmailProviderStatus(
                provider=connection.provider,
                account_email=connection.account_email,
                status=connection.status,
                connected_at=connection.connected_at,
                disconnected_at=connection.disconnected_at,
                last_sync_at=connection.last_sync_at,
                sync_cursor=connection.sync_cursor,
                token_configured=bool(connection.token_reference),
                last_run_status=latest_by_provider.get(connection.provider).run_status if connection.provider in latest_by_provider else "idle",
                last_run_started_at=latest_by_provider.get(connection.provider).started_at if connection.provider in latest_by_provider else None,
                last_run_completed_at=latest_by_provider.get(connection.provider).completed_at if connection.provider in latest_by_provider else None,
                last_imported_count=latest_by_provider.get(connection.provider).imported_count if connection.provider in latest_by_provider else 0,
                last_skipped_count=latest_by_provider.get(connection.provider).skipped_count if connection.provider in latest_by_provider else 0,
                last_duplicate_count=latest_by_provider.get(connection.provider).duplicate_count if connection.provider in latest_by_provider else 0,
                last_error_count=latest_by_provider.get(connection.provider).error_count if connection.provider in latest_by_provider else 0,
            )
            for connection in connections
        ]

    async def list_sync_history(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        limit: int = 50,
    ) -> list[EmailSyncRun]:
        normalized_provider = provider.strip().casefold() if provider is not None and provider.strip() else None
        return await self._store().list_sync_runs_for_user(user_id, provider=normalized_provider, limit=limit)

    async def sync(
        self,
        user_id: str,
        *,
        provider: str | None = None,
    ) -> list[EmailSyncRun]:
        connections = await self.list_connections(user_id)
        if provider is not None and provider.strip():
            normalized_provider = provider.strip().casefold()
            connections = [item for item in connections if item.provider == normalized_provider]
        if not connections:
            raise ValueError("No connected email providers are available to sync.")
        runs: list[EmailSyncRun] = []
        for connection_item in connections:
            if connection_item.status == "disconnected":
                continue
            runs.append(await self._sync_connection(connection_item))
        if not runs:
            raise ValueError("No connected email providers are available to sync.")
        return runs

    async def _sync_connection(self, connection_item: EmailProviderConnection) -> EmailSyncRun:
        provider = self._providers().get(connection_item.provider)
        refreshed = await provider.refresh_state(connection_item)
        refreshed = await self._store().save_connection(refreshed)
        if refreshed.status != "connected":
            raise ValueError(f"{refreshed.provider} provider is not ready to sync.")

        started_at = _iso_now()
        run = EmailSyncRun(
            sync_run_id=_sync_run_id(refreshed.connection_id, started_at),
            connection_id=refreshed.connection_id,
            user_id=refreshed.user_id,
            provider=refreshed.provider,
            account_email=refreshed.account_email,
            run_status="running",
            started_at=started_at,
            metadata={"sync_cursor_before": refreshed.sync_cursor},
        )
        await self._store().save_sync_run(run)

        try:
            batch = await provider.sync_messages(refreshed)
            normalized_records: list[RecruiterMessageImportRecord] = []
            import_candidates: list[ProviderMessage] = []
            duplicate_count = 0
            skipped_count = 0
            errors: list[str] = []

            for item in batch.items:
                if not item.provider_message_id or not item.provider_thread_id:
                    skipped_count += 1
                    continue
                existing = await self._store().get_synced_message(refreshed.connection_id, item.provider_message_id)
                if existing is not None and existing.canonical_message_id:
                    duplicate_count += 1
                    continue
                if not item.recruiter_email and not item.sender_email:
                    skipped_count += 1
                    errors.append(f"Skipped provider message {item.provider_message_id} because no usable sender identity was available.")
                    continue
                import_candidates.append(item)
                normalized_records.append(
                    RecruiterMessageImportRecord(
                        external_message_id=_provider_external_message_id(refreshed, item),
                        external_thread_id=_provider_external_thread_id(refreshed, item),
                        recruiter_name=item.recruiter_name,
                        recruiter_email=item.recruiter_email,
                        sender_email=item.sender_email,
                        sender_name=item.sender_name,
                        recipients=list(item.recipients),
                        subject=item.subject,
                        body_text=item.body_text,
                        body_reference=item.body_reference,
                        company=item.company,
                        job_title=item.job_title,
                        received_at=item.received_at,
                        source=refreshed.provider,
                        metadata=_sync_message_metadata(refreshed, item),
                    )
                )

            imported_messages = await self._recruiter().import_messages(refreshed.user_id, normalized_records) if normalized_records else []
            now = _iso_now()
            for provider_message, canonical_message in zip(import_candidates, imported_messages, strict=False):
                await self._store().save_synced_message(
                    EmailSyncedMessage(
                        sync_message_id=_synced_message_id(refreshed.connection_id, provider_message.provider_message_id),
                        connection_id=refreshed.connection_id,
                        user_id=refreshed.user_id,
                        provider=refreshed.provider,
                        account_email=refreshed.account_email,
                        provider_message_id=provider_message.provider_message_id,
                        provider_thread_id=provider_message.provider_thread_id,
                        canonical_message_id=canonical_message.message_id,
                        canonical_thread_id=canonical_message.thread_id,
                        provider_history_id=provider_message.provider_history_id,
                        attachment_refs=list(provider_message.attachments),
                        metadata=_sync_message_metadata(refreshed, provider_message),
                        first_synced_at=now,
                        last_synced_at=now,
                    )
                )
                await self._store().save_synced_thread(
                    EmailSyncedThread(
                        sync_thread_id=_synced_thread_id(refreshed.connection_id, provider_message.provider_thread_id),
                        connection_id=refreshed.connection_id,
                        user_id=refreshed.user_id,
                        provider=refreshed.provider,
                        account_email=refreshed.account_email,
                        provider_thread_id=provider_message.provider_thread_id,
                        canonical_thread_id=canonical_message.thread_id,
                        subject=provider_message.subject,
                        metadata={"provider": refreshed.provider},
                        first_synced_at=now,
                        last_synced_at=now,
                    )
                )

            updated_connection = EmailProviderConnection(
                connection_id=refreshed.connection_id,
                user_id=refreshed.user_id,
                provider=refreshed.provider,
                account_email=refreshed.account_email,
                status="connected",
                scopes=list(refreshed.scopes),
                connected_at=refreshed.connected_at,
                disconnected_at=refreshed.disconnected_at,
                last_sync_at=now,
                sync_cursor=batch.next_cursor or refreshed.sync_cursor,
                token_reference=refreshed.token_reference,
                token_metadata=dict(refreshed.token_metadata),
                metadata=dict(refreshed.metadata),
            )
            await self._store().save_connection(updated_connection)
            completed = EmailSyncRun(
                sync_run_id=run.sync_run_id,
                connection_id=run.connection_id,
                user_id=run.user_id,
                provider=run.provider,
                account_email=run.account_email,
                run_status="completed",
                started_at=run.started_at,
                completed_at=now,
                imported_count=len(imported_messages),
                skipped_count=skipped_count,
                duplicate_count=duplicate_count,
                error_count=len(errors),
                metadata={
                    **dict(run.metadata),
                    "sync_cursor_after": updated_connection.sync_cursor,
                    "provider_message_count": len(batch.items),
                    "provider_thread_count": len(batch.threads),
                    "provider_contact_count": len(batch.contacts),
                    "errors": errors,
                    **dict(batch.metadata),
                },
            )
            return await self._store().save_sync_run(completed)
        except Exception as exc:
            failed_at = _iso_now()
            await self._store().save_connection(
                EmailProviderConnection(
                    connection_id=refreshed.connection_id,
                    user_id=refreshed.user_id,
                    provider=refreshed.provider,
                    account_email=refreshed.account_email,
                    status="error",
                    scopes=list(refreshed.scopes),
                    connected_at=refreshed.connected_at,
                    disconnected_at=refreshed.disconnected_at,
                    last_sync_at=refreshed.last_sync_at,
                    sync_cursor=refreshed.sync_cursor,
                    token_reference=refreshed.token_reference,
                    token_metadata=dict(refreshed.token_metadata),
                    metadata=dict(refreshed.metadata),
                )
            )
            failed = EmailSyncRun(
                sync_run_id=run.sync_run_id,
                connection_id=run.connection_id,
                user_id=run.user_id,
                provider=run.provider,
                account_email=run.account_email,
                run_status="failed",
                started_at=run.started_at,
                failed_at=failed_at,
                error_count=1,
                metadata={**dict(run.metadata), "errors": [str(exc)]},
            )
            await self._store().save_sync_run(failed)
            raise


def build_email_integration_service(settings: AppSettings | None = None) -> EmailIntegrationService:
    resolved_settings = settings or get_settings()
    return EmailIntegrationService(
        settings=resolved_settings,
        store=build_email_integration_store(resolved_settings),
        provider_registry=build_email_provider_registry(resolved_settings),
        recruiter_service=build_recruiter_intelligence_service(resolved_settings),
    )
