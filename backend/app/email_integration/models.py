from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class EmailAttachmentReference:
    provider_attachment_id: str
    file_name: str
    mime_type: str
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderContactSnapshot:
    email: str
    display_name: str = ""
    company: str = ""
    title: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderThreadSnapshot:
    provider_thread_id: str
    subject: str
    last_message_at: str | None = None
    message_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderMessage:
    provider_message_id: str
    provider_thread_id: str
    provider_history_id: str = ""
    subject: str = ""
    body_text: str = ""
    body_reference: str = ""
    received_at: str | None = None
    sender_email: str = ""
    sender_name: str = ""
    recipients: list[str] = field(default_factory=list)
    recruiter_email: str = ""
    recruiter_name: str = ""
    company: str = ""
    job_title: str = ""
    attachments: list[EmailAttachmentReference] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["attachments"] = [item.to_dict() for item in self.attachments]
        return payload


@dataclass(frozen=True)
class ProviderSyncBatch:
    provider: str
    account_email: str
    items: list[ProviderMessage] = field(default_factory=list)
    threads: list[ProviderThreadSnapshot] = field(default_factory=list)
    contacts: list[ProviderContactSnapshot] = field(default_factory=list)
    next_cursor: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "account_email": self.account_email,
            "items": [item.to_dict() for item in self.items],
            "threads": [item.to_dict() for item in self.threads],
            "contacts": [item.to_dict() for item in self.contacts],
            "next_cursor": self.next_cursor,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProviderAuthorizationRequest:
    provider: str
    authorization_url: str
    expires_in_seconds: int
    scopes: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderAuthorizationResult:
    provider: str
    account_email: str
    token_reference: str
    scopes: list[str] = field(default_factory=list)
    token_metadata: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EmailProviderConnection:
    connection_id: str
    user_id: str
    provider: str
    account_email: str
    status: str
    scopes: list[str] = field(default_factory=list)
    connected_at: str | None = None
    disconnected_at: str | None = None
    last_sync_at: str | None = None
    sync_cursor: str = ""
    token_reference: str = ""
    token_metadata: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "provider": self.provider,
            "account_email": self.account_email,
            "status": self.status,
            "scopes": list(self.scopes),
            "connected_at": self.connected_at,
            "disconnected_at": self.disconnected_at,
            "last_sync_at": self.last_sync_at,
            "sync_cursor": self.sync_cursor,
            "token_configured": bool(self.token_reference),
        }


@dataclass(frozen=True)
class EmailProviderStatus:
    provider: str
    account_email: str
    status: str
    connected_at: str | None = None
    disconnected_at: str | None = None
    last_sync_at: str | None = None
    sync_cursor: str = ""
    token_configured: bool = False
    last_run_status: str = "idle"
    last_run_started_at: str | None = None
    last_run_completed_at: str | None = None
    last_imported_count: int = 0
    last_skipped_count: int = 0
    last_duplicate_count: int = 0
    last_error_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EmailSyncRun:
    sync_run_id: str
    connection_id: str
    user_id: str
    provider: str
    account_email: str
    run_status: str
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    imported_count: int = 0
    skipped_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EmailSyncedMessage:
    sync_message_id: str
    connection_id: str
    user_id: str
    provider: str
    account_email: str
    provider_message_id: str
    provider_thread_id: str
    canonical_message_id: str = ""
    canonical_thread_id: str = ""
    provider_history_id: str = ""
    attachment_refs: list[EmailAttachmentReference] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    first_synced_at: str | None = None
    last_synced_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "sync_message_id": self.sync_message_id,
            "connection_id": self.connection_id,
            "user_id": self.user_id,
            "provider": self.provider,
            "account_email": self.account_email,
            "provider_message_id": self.provider_message_id,
            "provider_thread_id": self.provider_thread_id,
            "canonical_message_id": self.canonical_message_id,
            "canonical_thread_id": self.canonical_thread_id,
            "provider_history_id": self.provider_history_id,
            "attachment_refs": [item.to_dict() for item in self.attachment_refs],
            "metadata": dict(self.metadata),
            "first_synced_at": self.first_synced_at,
            "last_synced_at": self.last_synced_at,
        }


@dataclass(frozen=True)
class EmailSyncedThread:
    sync_thread_id: str
    connection_id: str
    user_id: str
    provider: str
    account_email: str
    provider_thread_id: str
    canonical_thread_id: str = ""
    subject: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
    first_synced_at: str | None = None
    last_synced_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
