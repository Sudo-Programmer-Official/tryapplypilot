from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from email.utils import parseaddr
from html import unescape
from typing import Awaitable, Callable, Protocol
from urllib.parse import urlencode

from app.config import AppSettings, get_settings
from app.http import HttpClientError, HttpTlsSettings, request_json

from .models import (
    EmailAttachmentReference,
    EmailProviderConnection,
    ProviderContactSnapshot,
    ProviderAuthorizationResult,
    ProviderMessage,
    ProviderSyncBatch,
    ProviderThreadSnapshot,
)
from .tokens import EmailProviderTokenSecret, EmailProviderTokenStore, build_email_provider_token_store, build_token_reference

MailboxLoader = Callable[[EmailProviderConnection], Awaitable[list[dict[str, object]]] | list[dict[str, object]]]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _ensure_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string_list(value: object) -> list[str]:
    return [str(item).strip() for item in _ensure_list(value) if str(item).strip()]


def _normalize_email_pair(value: str) -> tuple[str, str]:
    display_name, email_address = parseaddr(value)
    return display_name.strip(), email_address.strip().casefold()


def _first_counterpart_email(recipients: list[str], account_email: str) -> tuple[str, str]:
    normalized_account = account_email.strip().casefold()
    for recipient in recipients:
        display_name, email_address = _normalize_email_pair(recipient)
        if email_address and email_address != normalized_account:
            return display_name, email_address
    return "", ""


async def _load_mailbox(
    connection: EmailProviderConnection,
    loader: MailboxLoader | None,
) -> list[dict[str, object]]:
    if loader is not None:
        payload = loader(connection)
        if hasattr(payload, "__await__"):
            return list(await payload)  # type: ignore[arg-type]
        return list(payload)  # type: ignore[arg-type]
    mailbox = connection.metadata.get("mock_mailbox")
    return [item for item in _ensure_list(mailbox) if isinstance(item, dict)]


def _gmail_default_scopes() -> list[str]:
    return ["https://www.googleapis.com/auth/gmail.readonly"]


def _outlook_default_scopes() -> list[str]:
    return ["Mail.Read", "offline_access"]


def _normalize_timestamp(raw: dict[str, object]) -> str | None:
    received_at = str(raw.get("received_at") or raw.get("receivedAt") or "").strip()
    if received_at:
        return received_at
    internal_date = raw.get("internalDate")
    if internal_date is None:
        return None
    try:
        millis = int(str(internal_date))
    except ValueError:
        return None
    return datetime.fromtimestamp(millis / 1000, timezone.utc).isoformat()


def _attachment_refs(raw_attachments: object) -> list[EmailAttachmentReference]:
    refs: list[EmailAttachmentReference] = []
    for item in _ensure_list(raw_attachments):
        if not isinstance(item, dict):
            continue
        provider_attachment_id = str(item.get("id") or item.get("attachmentId") or item.get("provider_attachment_id") or "").strip()
        if not provider_attachment_id:
            continue
        size_value = item.get("size") or item.get("size_bytes")
        size_bytes: int | None
        try:
            size_bytes = int(size_value) if size_value is not None else None
        except (TypeError, ValueError):
            size_bytes = None
        refs.append(
            EmailAttachmentReference(
                provider_attachment_id=provider_attachment_id,
                file_name=str(item.get("filename") or item.get("file_name") or "").strip(),
                mime_type=str(item.get("mimeType") or item.get("mime_type") or "application/octet-stream").strip(),
                size_bytes=size_bytes,
            )
        )
    return refs


def _subject(raw: dict[str, object]) -> str:
    return str(raw.get("subject") or raw.get("snippet") or "").strip()


def _body_text(raw: dict[str, object]) -> str:
    body = raw.get("body_text") or raw.get("bodyText") or raw.get("body") or raw.get("snippet") or ""
    return str(body).strip()


def _provider_metadata(raw: dict[str, object], *, provider: str) -> dict[str, object]:
    metadata = dict(raw.get("metadata")) if isinstance(raw.get("metadata"), dict) else {}
    metadata["provider"] = provider
    if "labelIds" in raw:
        metadata["label_ids"] = _string_list(raw.get("labelIds"))
    return metadata


class EmailProvider(Protocol):
    provider_name: str

    async def connect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        ...

    async def disconnect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        ...

    async def build_authorization_url(
        self,
        *,
        state: str,
        scopes: list[str] | None = None,
        login_hint: str = "",
    ) -> str:
        ...

    async def complete_authorization(
        self,
        user_id: str,
        *,
        code: str,
        scopes: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ProviderAuthorizationResult:
        ...

    async def refresh_state(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        ...

    async def sync_messages(self, connection: EmailProviderConnection) -> ProviderSyncBatch:
        ...

    async def sync_threads(self, connection: EmailProviderConnection) -> list[ProviderThreadSnapshot]:
        ...

    async def sync_contacts(self, connection: EmailProviderConnection) -> list[ProviderContactSnapshot]:
        ...


def _html_to_text(value: str) -> str:
    collapsed = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(collapsed)).strip()


def _decode_base64url(value: str) -> str:
    if not value:
        return ""
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError):
        return ""


def _payload_headers(payload: dict[str, object]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in _ensure_list(payload.get("headers")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().casefold()
        value = str(item.get("value") or "").strip()
        if name and value and name not in headers:
            headers[name] = value
    return headers


def _extract_gmail_parts(
    payload: dict[str, object],
    *,
    body_chunks: list[str],
    html_chunks: list[str],
    attachments: list[EmailAttachmentReference],
) -> None:
    mime_type = str(payload.get("mimeType") or "").strip().casefold()
    filename = str(payload.get("filename") or "").strip()
    body = payload.get("body")
    body_data = body.get("data") if isinstance(body, dict) else None
    attachment_id = str(body.get("attachmentId") or "").strip() if isinstance(body, dict) else ""
    size_value = body.get("size") if isinstance(body, dict) else None
    try:
        size_bytes = int(size_value) if size_value is not None else None
    except (TypeError, ValueError):
        size_bytes = None
    if filename and attachment_id:
        attachments.append(
            EmailAttachmentReference(
                provider_attachment_id=attachment_id,
                file_name=filename,
                mime_type=str(payload.get("mimeType") or "application/octet-stream").strip(),
                size_bytes=size_bytes,
            )
        )
    if body_data and mime_type == "text/plain":
        decoded = _decode_base64url(str(body_data))
        if decoded.strip():
            body_chunks.append(decoded.strip())
    elif body_data and mime_type == "text/html":
        decoded = _decode_base64url(str(body_data))
        if decoded.strip():
            html_chunks.append(decoded.strip())
    for part in _ensure_list(payload.get("parts")):
        if isinstance(part, dict):
            _extract_gmail_parts(part, body_chunks=body_chunks, html_chunks=html_chunks, attachments=attachments)


def _gmail_body_and_attachments(message_payload: dict[str, object]) -> tuple[str, list[EmailAttachmentReference]]:
    body_chunks: list[str] = []
    html_chunks: list[str] = []
    attachments: list[EmailAttachmentReference] = []
    _extract_gmail_parts(message_payload, body_chunks=body_chunks, html_chunks=html_chunks, attachments=attachments)
    if body_chunks:
        return "\n\n".join(chunk for chunk in body_chunks if chunk), attachments
    if html_chunks:
        return "\n\n".join(_html_to_text(chunk) for chunk in html_chunks if chunk), attachments
    body = message_payload.get("body")
    if isinstance(body, dict):
        fallback = _decode_base64url(str(body.get("data") or ""))
        if fallback.strip():
            return fallback.strip(), attachments
    return "", attachments


def _gmail_message_to_raw(message: dict[str, object]) -> dict[str, object]:
    payload = message.get("payload")
    payload_object = payload if isinstance(payload, dict) else {}
    headers = _payload_headers(payload_object)
    body_text, attachments = _gmail_body_and_attachments(payload_object)
    recipients = []
    for header_name in ("to", "cc", "bcc"):
        header_value = headers.get(header_name, "")
        if header_value:
            recipients.extend([item.strip() for item in header_value.split(",") if item.strip()])
    return {
        "id": str(message.get("id") or "").strip(),
        "threadId": str(message.get("threadId") or "").strip(),
        "historyId": str(message.get("historyId") or "").strip(),
        "internalDate": str(message.get("internalDate") or "").strip(),
        "from": headers.get("from", ""),
        "to": recipients,
        "subject": headers.get("subject", ""),
        "body_text": body_text or str(message.get("snippet") or "").strip(),
        "snippet": str(message.get("snippet") or "").strip(),
        "attachments": [item.to_dict() for item in attachments],
        "labelIds": _string_list(message.get("labelIds")),
        "metadata": {"gmail_labels": _string_list(message.get("labelIds"))},
    }


def _thread_snapshots_from_messages(messages: list[ProviderMessage], *, provider: str) -> list[ProviderThreadSnapshot]:
    grouped: dict[str, ProviderThreadSnapshot] = {}
    for item in messages:
        existing = grouped.get(item.provider_thread_id)
        item_time = _parse_datetime(item.received_at or "") or datetime.min.replace(tzinfo=timezone.utc)
        existing_time = _parse_datetime(existing.last_message_at or "") if existing is not None else None
        if existing is None or item_time >= (existing_time or datetime.min.replace(tzinfo=timezone.utc)):
            grouped[item.provider_thread_id] = ProviderThreadSnapshot(
                provider_thread_id=item.provider_thread_id,
                subject=item.subject or (existing.subject if existing is not None else ""),
                last_message_at=item.received_at,
                message_count=(existing.message_count if existing is not None else 0) + 1,
                metadata={"provider": provider},
            )
        else:
            grouped[item.provider_thread_id] = ProviderThreadSnapshot(
                provider_thread_id=existing.provider_thread_id,
                subject=existing.subject,
                last_message_at=existing.last_message_at,
                message_count=existing.message_count + 1,
                metadata=dict(existing.metadata),
            )
    return list(grouped.values())


def _contact_snapshots_from_messages(messages: list[ProviderMessage], *, provider: str) -> list[ProviderContactSnapshot]:
    contacts: dict[str, ProviderContactSnapshot] = {}
    for item in messages:
        if not item.recruiter_email:
            continue
        contacts[item.recruiter_email] = ProviderContactSnapshot(
            email=item.recruiter_email,
            display_name=item.recruiter_name,
            company=item.company,
            title=item.job_title,
            metadata={"provider": provider},
        )
    return list(contacts.values())


@dataclass
class GmailProvider:
    mailbox_loader: MailboxLoader | None = None
    settings: AppSettings | None = None
    token_store: EmailProviderTokenStore | None = None
    request_json_func: Callable[..., object] = request_json
    provider_name: str = "gmail"

    def _settings(self) -> AppSettings:
        return self.settings or get_settings()

    def _token_store(self) -> EmailProviderTokenStore:
        if self.token_store is not None:
            return self.token_store
        return build_email_provider_token_store(self._settings())

    def _tls(self) -> HttpTlsSettings:
        gmail_settings = self._settings().gmail
        return HttpTlsSettings(
            ca_bundle_path=gmail_settings.ca_bundle_path,
            skip_ssl_verify=gmail_settings.skip_ssl_verify,
        )

    def _timeout_seconds(self) -> int:
        return self._settings().gmail.timeout_seconds

    def _is_live_mode(self) -> bool:
        gmail_settings = self._settings().gmail
        return self.mailbox_loader is None and gmail_settings.enabled

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, object] | list[object] | None = None,
        form_body: dict[str, object] | None = None,
    ) -> object:
        return self.request_json_func(
            method,
            url,
            timeout_seconds=self._timeout_seconds(),
            tls=self._tls(),
            headers=headers,
            body=body,
            form_body=form_body,
        )

    async def _load_live_token(self, token_reference: str) -> EmailProviderTokenSecret | None:
        return await self._token_store().get_token(token_reference)

    async def _save_live_token(self, token: EmailProviderTokenSecret) -> EmailProviderTokenSecret:
        return await self._token_store().save_token(token)

    async def _refresh_live_token_if_needed(self, token: EmailProviderTokenSecret) -> EmailProviderTokenSecret:
        expires_at = _parse_datetime(token.expires_at)
        if expires_at is None:
            return token
        if expires_at > datetime.now(timezone.utc) + timedelta(seconds=60):
            return token
        if not token.refresh_token.strip():
            raise ValueError("Gmail connection requires re-authorization because no refresh token is available.")
        gmail_settings = self._settings().gmail
        payload = self._request_json(
            "POST",
            gmail_settings.token_url,
            headers={"Accept": "application/json"},
            form_body={
                "client_id": gmail_settings.client_id or "",
                "client_secret": gmail_settings.client_secret or "",
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("Gmail token refresh returned an invalid response.")
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("Gmail token refresh did not return an access token.")
        expires_in = int(payload.get("expires_in") or 3600)
        refreshed = EmailProviderTokenSecret(
            token_reference=token.token_reference,
            user_id=token.user_id,
            provider=token.provider,
            account_email=token.account_email,
            access_token=access_token,
            refresh_token=str(payload.get("refresh_token") or token.refresh_token).strip(),
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 0))).isoformat(),
            scope=str(payload.get("scope") or token.scope).strip(),
            token_type=str(payload.get("token_type") or token.token_type or "Bearer").strip(),
            metadata=dict(token.metadata),
            created_at=token.created_at,
            updated_at=_iso_now(),
        )
        return await self._save_live_token(refreshed)

    async def build_authorization_url(
        self,
        *,
        state: str,
        scopes: list[str] | None = None,
        login_hint: str = "",
    ) -> str:
        gmail_settings = self._settings().gmail
        if not gmail_settings.enabled:
            raise ValueError("Gmail OAuth is not configured for this environment.")
        resolved_scopes = [item.strip() for item in (scopes or list(gmail_settings.scopes) or _gmail_default_scopes()) if item.strip()]
        query = urlencode(
            {
                "client_id": gmail_settings.client_id or "",
                "redirect_uri": gmail_settings.redirect_uri or "",
                "response_type": "code",
                "scope": " ".join(resolved_scopes),
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
                **({"login_hint": login_hint.strip()} if login_hint.strip() else {}),
            }
        )
        return f"{gmail_settings.auth_base_url}?{query}"

    async def complete_authorization(
        self,
        user_id: str,
        *,
        code: str,
        scopes: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ProviderAuthorizationResult:
        gmail_settings = self._settings().gmail
        if not gmail_settings.enabled:
            raise ValueError("Gmail OAuth is not configured for this environment.")
        payload = self._request_json(
            "POST",
            gmail_settings.token_url,
            headers={"Accept": "application/json"},
            form_body={
                "client_id": gmail_settings.client_id or "",
                "client_secret": gmail_settings.client_secret or "",
                "code": code.strip(),
                "grant_type": "authorization_code",
                "redirect_uri": gmail_settings.redirect_uri or "",
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("Gmail OAuth exchange returned an invalid response.")
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("Gmail OAuth exchange did not return an access token.")
        profile_response = self._request_json(
            "GET",
            f"{gmail_settings.api_base_url.rstrip('/')}/users/me/profile",
            headers={"Accept": "application/json", "Authorization": f"Bearer {access_token}"},
        )
        if not isinstance(profile_response, dict):
            raise ValueError("Gmail profile lookup returned an invalid response.")
        account_email = str(profile_response.get("emailAddress") or "").strip().casefold()
        if not account_email:
            raise ValueError("Gmail profile lookup did not return an account email.")
        expires_in = int(payload.get("expires_in") or 3600)
        granted_scope = str(payload.get("scope") or " ".join(scopes or list(gmail_settings.scopes))).strip()
        token_reference = build_token_reference(user_id, self.provider_name)
        await self._save_live_token(
            EmailProviderTokenSecret(
                token_reference=token_reference,
                user_id=user_id,
                provider=self.provider_name,
                account_email=account_email,
                access_token=access_token,
                refresh_token=str(payload.get("refresh_token") or "").strip(),
                expires_at=(datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 0))).isoformat(),
                scope=granted_scope,
                token_type=str(payload.get("token_type") or "Bearer").strip(),
                metadata={
                    "history_id": str(profile_response.get("historyId") or "").strip(),
                    **(dict(metadata or {})),
                },
                created_at=_iso_now(),
                updated_at=_iso_now(),
            )
        )
        return ProviderAuthorizationResult(
            provider=self.provider_name,
            account_email=account_email,
            token_reference=token_reference,
            scopes=[item.strip() for item in granted_scope.split(" ") if item.strip()],
            token_metadata={
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=max(expires_in, 0))).isoformat(),
                "scope": granted_scope,
                "granted_scopes": [item.strip() for item in granted_scope.split(" ") if item.strip()],
                "token_type": str(payload.get("token_type") or "Bearer").strip(),
            },
            metadata={
                "provider_account_email": account_email,
                "provider_history_id": str(profile_response.get("historyId") or "").strip(),
                **dict(metadata or {}),
            },
        )

    async def connect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        if not connection.account_email.strip():
            raise ValueError("Gmail connections require an account email.")
        if not connection.token_reference.strip():
            raise ValueError("Gmail connections require a secure token reference.")
        scopes = connection.scopes or _gmail_default_scopes()
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email.strip().casefold(),
            status="connected",
            scopes=list(scopes),
            connected_at=connection.connected_at or _iso_now(),
            disconnected_at=None,
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference=connection.token_reference,
            token_metadata=dict(connection.token_metadata),
            metadata=dict(connection.metadata),
        )

    async def disconnect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        if connection.token_reference.strip():
            await self._token_store().delete_token(connection.token_reference)
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email,
            status="disconnected",
            scopes=list(connection.scopes),
            connected_at=connection.connected_at,
            disconnected_at=_iso_now(),
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference="",
            token_metadata={},
            metadata=dict(connection.metadata),
        )

    async def refresh_state(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        if self._is_live_mode():
            token_secret = await self._load_live_token(connection.token_reference)
            if token_secret is None:
                status = "needs_reauth"
                token_metadata = {}
            else:
                refreshed_token = await self._refresh_live_token_if_needed(token_secret)
                status = "connected" if refreshed_token.access_token.strip() else "needs_reauth"
                token_metadata = refreshed_token.public_metadata()
            return EmailProviderConnection(
                connection_id=connection.connection_id,
                user_id=connection.user_id,
                provider=self.provider_name,
                account_email=connection.account_email,
                status=status,
                scopes=list(connection.scopes or _gmail_default_scopes()),
                connected_at=connection.connected_at or _iso_now(),
                disconnected_at=connection.disconnected_at,
                last_sync_at=connection.last_sync_at,
                sync_cursor=connection.sync_cursor,
                token_reference=connection.token_reference,
                token_metadata=token_metadata,
                metadata=dict(connection.metadata),
            )
        status = "connected" if connection.token_reference.strip() else "needs_reauth"
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email,
            status=status,
            scopes=list(connection.scopes or _gmail_default_scopes()),
            connected_at=connection.connected_at or _iso_now(),
            disconnected_at=connection.disconnected_at,
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference=connection.token_reference,
            token_metadata=dict(connection.token_metadata),
            metadata=dict(connection.metadata),
        )

    async def sync_messages(self, connection: EmailProviderConnection) -> ProviderSyncBatch:
        if self._is_live_mode():
            token_secret = await self._load_live_token(connection.token_reference)
            if token_secret is None:
                raise ValueError("Gmail connection requires re-authorization because no provider token was found.")
            token_secret = await self._refresh_live_token_if_needed(token_secret)
            gmail_settings = self._settings().gmail
            headers = {"Accept": "application/json", "Authorization": f"Bearer {token_secret.access_token}"}
            max_pages = max(1, gmail_settings.full_sync_max_pages)
            page_size = max(1, min(gmail_settings.page_size, 500))
            message_ids: list[str] = []
            history_cursor = connection.sync_cursor.strip()
            metadata: dict[str, object] = {"incremental": bool(history_cursor), "provider": self.provider_name}
            try:
                if history_cursor:
                    page_token = ""
                    pages_scanned = 0
                    latest_history_id = history_cursor
                    while pages_scanned < max_pages:
                        url = f"{gmail_settings.api_base_url.rstrip('/')}/users/me/history?{urlencode({'startHistoryId': history_cursor, 'maxResults': page_size, **({'pageToken': page_token} if page_token else {})})}"
                        response = self._request_json("GET", url, headers=headers)
                        if not isinstance(response, dict):
                            raise ValueError("Gmail history sync returned an invalid response.")
                        latest_history_id = str(response.get("historyId") or latest_history_id).strip() or latest_history_id
                        for history_item in _ensure_list(response.get("history")):
                            if not isinstance(history_item, dict):
                                continue
                            for message_added in _ensure_list(history_item.get("messagesAdded")):
                                if not isinstance(message_added, dict):
                                    continue
                                message = message_added.get("message")
                                if isinstance(message, dict):
                                    message_id = str(message.get("id") or "").strip()
                                    if message_id:
                                        message_ids.append(message_id)
                        page_token = str(response.get("nextPageToken") or "").strip()
                        pages_scanned += 1
                        if not page_token:
                            break
                    metadata["history_cursor_after"] = latest_history_id
                    metadata["pages_scanned"] = pages_scanned
                else:
                    page_token = ""
                    pages_scanned = 0
                    while pages_scanned < max_pages:
                        url = f"{gmail_settings.api_base_url.rstrip('/')}/users/me/messages?{urlencode({'maxResults': page_size, **({'pageToken': page_token} if page_token else {})})}"
                        response = self._request_json("GET", url, headers=headers)
                        if not isinstance(response, dict):
                            raise ValueError("Gmail message listing returned an invalid response.")
                        for item in _ensure_list(response.get("messages")):
                            if not isinstance(item, dict):
                                continue
                            message_id = str(item.get("id") or "").strip()
                            if message_id:
                                message_ids.append(message_id)
                        page_token = str(response.get("nextPageToken") or "").strip()
                        pages_scanned += 1
                        if not page_token:
                            break
                    metadata["pages_scanned"] = pages_scanned
            except HttpClientError as exc:
                if history_cursor and "HTTP 404" in str(exc):
                    connection = EmailProviderConnection(
                        connection_id=connection.connection_id,
                        user_id=connection.user_id,
                        provider=connection.provider,
                        account_email=connection.account_email,
                        status=connection.status,
                        scopes=list(connection.scopes),
                        connected_at=connection.connected_at,
                        disconnected_at=connection.disconnected_at,
                        last_sync_at=connection.last_sync_at,
                        sync_cursor="",
                        token_reference=connection.token_reference,
                        token_metadata=dict(connection.token_metadata),
                        metadata=dict(connection.metadata),
                    )
                    metadata["incremental_fallback"] = "history_expired"
                    return await self.sync_messages(connection)
                raise

            unique_message_ids = list(dict.fromkeys(message_ids))
            raw_messages: list[dict[str, object]] = []
            latest_history_id = history_cursor
            for message_id in unique_message_ids:
                url = f"{gmail_settings.api_base_url.rstrip('/')}/users/me/messages/{message_id}?{urlencode({'format': 'full'})}"
                response = self._request_json("GET", url, headers=headers)
                if not isinstance(response, dict):
                    raise ValueError("Gmail message detail lookup returned an invalid response.")
                raw_messages.append(_gmail_message_to_raw(response))
                detail_history_id = str(response.get("historyId") or "").strip()
                if detail_history_id.isdigit() and (not latest_history_id.isdigit() or int(detail_history_id) > int(latest_history_id)):
                    latest_history_id = detail_history_id

            profile_response = self._request_json(
                "GET",
                f"{gmail_settings.api_base_url.rstrip('/')}/users/me/profile",
                headers=headers,
            )
            if isinstance(profile_response, dict):
                profile_history_id = str(profile_response.get("historyId") or "").strip()
                if profile_history_id.isdigit() and (not latest_history_id.isdigit() or int(profile_history_id) > int(latest_history_id)):
                    latest_history_id = profile_history_id
            normalized: list[tuple[int | None, ProviderMessage]] = []
            current_history = int(history_cursor) if history_cursor.isdigit() else None
            for raw in raw_messages:
                provider_message_id = str(raw.get("id") or "").strip()
                provider_thread_id = str(raw.get("threadId") or provider_message_id).strip()
                if not provider_message_id or not provider_thread_id:
                    continue
                provider_history_id = str(raw.get("historyId") or "").strip()
                history_number = int(provider_history_id) if provider_history_id.isdigit() else None
                if current_history is not None and history_number is not None and history_number <= current_history:
                    continue
                recipients = _string_list(raw.get("to"))
                sender_name, sender_email = _normalize_email_pair(str(raw.get("from") or ""))
                counterpart_name = ""
                counterpart_email = ""
                if sender_email and sender_email != connection.account_email.strip().casefold():
                    counterpart_name = sender_name
                    counterpart_email = sender_email
                else:
                    counterpart_name, counterpart_email = _first_counterpart_email(recipients, connection.account_email)
                message = ProviderMessage(
                    provider_message_id=provider_message_id,
                    provider_thread_id=provider_thread_id,
                    provider_history_id=provider_history_id,
                    subject=_subject(raw),
                    body_text=_body_text(raw),
                    body_reference=f"gmail://{connection.account_email}/{provider_message_id}",
                    received_at=_normalize_timestamp(raw),
                    sender_email=sender_email,
                    sender_name=sender_name or counterpart_name,
                    recipients=recipients,
                    recruiter_email=counterpart_email,
                    recruiter_name=counterpart_name,
                    attachments=_attachment_refs(raw.get("attachments")),
                    metadata=_provider_metadata(raw, provider=self.provider_name),
                )
                normalized.append((history_number, message))
            normalized.sort(
                key=lambda item: (
                    item[0] if item[0] is not None else -1,
                    _parse_datetime(item[1].received_at or "") or datetime.min.replace(tzinfo=timezone.utc),
                    item[1].provider_message_id,
                )
            )
            messages = [item for _, item in normalized]
            return ProviderSyncBatch(
                provider=self.provider_name,
                account_email=connection.account_email,
                items=messages,
                threads=_thread_snapshots_from_messages(messages, provider=self.provider_name),
                contacts=_contact_snapshots_from_messages(messages, provider=self.provider_name),
                next_cursor=latest_history_id or history_cursor,
                metadata={**metadata, "message_count": len(messages)},
            )
        mailbox = await _load_mailbox(connection, self.mailbox_loader)
        current_cursor = connection.sync_cursor.strip()
        current_history = int(current_cursor) if current_cursor.isdigit() else None
        normalized: list[tuple[int | None, ProviderMessage]] = []
        for raw in mailbox:
            provider_message_id = str(raw.get("id") or raw.get("provider_message_id") or "").strip()
            provider_thread_id = str(raw.get("threadId") or raw.get("provider_thread_id") or provider_message_id).strip()
            if not provider_message_id:
                continue
            provider_history_id = str(raw.get("historyId") or raw.get("provider_history_id") or "").strip()
            history_number = int(provider_history_id) if provider_history_id.isdigit() else None
            if current_history is not None and history_number is not None and history_number <= current_history:
                continue
            recipients = _string_list(raw.get("recipients") or raw.get("to"))
            sender_name, sender_email = _normalize_email_pair(str(raw.get("from") or raw.get("sender_email") or ""))
            if not sender_email:
                sender_name = str(raw.get("sender_name") or "").strip()
                sender_email = str(raw.get("sender_email") or "").strip().casefold()
            counterpart_name = str(raw.get("recruiter_name") or "").strip()
            counterpart_email = str(raw.get("recruiter_email") or "").strip().casefold()
            account_email = connection.account_email.strip().casefold()
            if not counterpart_email:
                if sender_email and sender_email != account_email:
                    counterpart_name = counterpart_name or sender_name
                    counterpart_email = sender_email
                else:
                    derived_name, derived_email = _first_counterpart_email(recipients, connection.account_email)
                    counterpart_name = counterpart_name or derived_name
                    counterpart_email = derived_email
            normalized.append(
                (
                    history_number,
                    ProviderMessage(
                        provider_message_id=provider_message_id,
                        provider_thread_id=provider_thread_id,
                        provider_history_id=provider_history_id,
                        subject=_subject(raw),
                        body_text=_body_text(raw),
                        body_reference=f"gmail://{connection.account_email}/{provider_message_id}",
                        received_at=_normalize_timestamp(raw),
                        sender_email=sender_email,
                        sender_name=sender_name or counterpart_name,
                        recipients=recipients,
                        recruiter_email=counterpart_email,
                        recruiter_name=counterpart_name,
                        company=str(raw.get("company") or "").strip(),
                        job_title=str(raw.get("job_title") or raw.get("jobTitle") or "").strip(),
                        attachments=_attachment_refs(raw.get("attachments")),
                        metadata=_provider_metadata(raw, provider=self.provider_name),
                    ),
                )
            )
        normalized.sort(key=lambda item: (item[0] if item[0] is not None else -1, _parse_datetime(item[1].received_at or "") or datetime.min.replace(tzinfo=timezone.utc), item[1].provider_message_id))
        messages = [item for _, item in normalized]
        next_cursor = current_cursor
        numeric_histories = [history for history, _ in normalized if history is not None]
        if numeric_histories:
            next_cursor = str(max(numeric_histories))
        elif messages and not next_cursor:
            next_cursor = messages[-1].provider_history_id
        return ProviderSyncBatch(
            provider=self.provider_name,
            account_email=connection.account_email,
            items=messages,
            threads=await self.sync_threads(connection),
            contacts=await self.sync_contacts(connection),
            next_cursor=next_cursor,
            metadata={"incremental": True, "message_count": len(messages)},
        )

    async def sync_threads(self, connection: EmailProviderConnection) -> list[ProviderThreadSnapshot]:
        if self._is_live_mode():
            return []
        mailbox = await _load_mailbox(connection, self.mailbox_loader)
        grouped: dict[str, ProviderThreadSnapshot] = {}
        for raw in mailbox:
            provider_thread_id = str(raw.get("threadId") or raw.get("provider_thread_id") or raw.get("id") or "").strip()
            if not provider_thread_id:
                continue
            last_message_at = _normalize_timestamp(raw)
            existing = grouped.get(provider_thread_id)
            if existing is None or (_parse_datetime(last_message_at) or datetime.min.replace(tzinfo=timezone.utc)) >= (
                _parse_datetime(existing.last_message_at or "") or datetime.min.replace(tzinfo=timezone.utc)
            ):
                grouped[provider_thread_id] = ProviderThreadSnapshot(
                    provider_thread_id=provider_thread_id,
                    subject=_subject(raw),
                    last_message_at=last_message_at,
                    message_count=(existing.message_count if existing is not None else 0) + 1,
                    metadata={"provider": self.provider_name},
                )
            elif existing is not None:
                grouped[provider_thread_id] = ProviderThreadSnapshot(
                    provider_thread_id=existing.provider_thread_id,
                    subject=existing.subject,
                    last_message_at=existing.last_message_at,
                    message_count=existing.message_count + 1,
                    metadata=dict(existing.metadata),
                )
        return list(grouped.values())

    async def sync_contacts(self, connection: EmailProviderConnection) -> list[ProviderContactSnapshot]:
        if self._is_live_mode():
            return []
        mailbox = await _load_mailbox(connection, self.mailbox_loader)
        contacts: dict[str, ProviderContactSnapshot] = {}
        for raw in mailbox:
            recipients = _string_list(raw.get("recipients") or raw.get("to"))
            sender_name, sender_email = _normalize_email_pair(str(raw.get("from") or raw.get("sender_email") or ""))
            if not sender_email:
                sender_name = str(raw.get("sender_name") or "").strip()
                sender_email = str(raw.get("sender_email") or "").strip().casefold()
            recruiter_name = str(raw.get("recruiter_name") or "").strip()
            recruiter_email = str(raw.get("recruiter_email") or "").strip().casefold()
            account_email = connection.account_email.strip().casefold()
            if not recruiter_email:
                if sender_email and sender_email != account_email:
                    recruiter_name = recruiter_name or sender_name
                    recruiter_email = sender_email
                else:
                    derived_name, derived_email = _first_counterpart_email(recipients, connection.account_email)
                    recruiter_name = recruiter_name or derived_name
                    recruiter_email = derived_email
            if not recruiter_email:
                continue
            contacts[recruiter_email] = ProviderContactSnapshot(
                email=recruiter_email,
                display_name=recruiter_name,
                company=str(raw.get("company") or "").strip(),
                title=str(raw.get("job_title") or raw.get("jobTitle") or "").strip(),
                metadata={"provider": self.provider_name},
            )
        return list(contacts.values())


@dataclass
class OutlookProvider:
    provider_name: str = "outlook"

    async def connect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        if not connection.account_email.strip():
            raise ValueError("Outlook connections require an account email.")
        if not connection.token_reference.strip():
            raise ValueError("Outlook connections require a secure token reference.")
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email.strip().casefold(),
            status="connected",
            scopes=list(connection.scopes or _outlook_default_scopes()),
            connected_at=connection.connected_at or _iso_now(),
            disconnected_at=None,
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference=connection.token_reference,
            token_metadata=dict(connection.token_metadata),
            metadata=dict(connection.metadata),
        )

    async def disconnect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email,
            status="disconnected",
            scopes=list(connection.scopes),
            connected_at=connection.connected_at,
            disconnected_at=_iso_now(),
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference="",
            token_metadata={},
            metadata=dict(connection.metadata),
        )

    async def build_authorization_url(
        self,
        *,
        state: str,
        scopes: list[str] | None = None,
        login_hint: str = "",
    ) -> str:
        raise ValueError("Outlook OAuth is not implemented yet.")

    async def complete_authorization(
        self,
        user_id: str,
        *,
        code: str,
        scopes: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ProviderAuthorizationResult:
        raise ValueError("Outlook OAuth is not implemented yet.")

    async def refresh_state(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        status = "connected" if connection.token_reference.strip() else "needs_reauth"
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email,
            status=status,
            scopes=list(connection.scopes or _outlook_default_scopes()),
            connected_at=connection.connected_at or _iso_now(),
            disconnected_at=connection.disconnected_at,
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference=connection.token_reference,
            token_metadata=dict(connection.token_metadata),
            metadata=dict(connection.metadata),
        )

    async def sync_messages(self, connection: EmailProviderConnection) -> ProviderSyncBatch:
        return ProviderSyncBatch(provider=self.provider_name, account_email=connection.account_email, next_cursor=connection.sync_cursor)

    async def sync_threads(self, connection: EmailProviderConnection) -> list[ProviderThreadSnapshot]:
        return []

    async def sync_contacts(self, connection: EmailProviderConnection) -> list[ProviderContactSnapshot]:
        return []


@dataclass
class MockProvider:
    mailbox_loader: MailboxLoader | None = None
    provider_name: str = "mock"

    async def connect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        if not connection.account_email.strip():
            raise ValueError("Mock provider connections require an account email.")
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email.strip().casefold(),
            status="connected",
            scopes=list(connection.scopes or ["mock.read"]),
            connected_at=connection.connected_at or _iso_now(),
            disconnected_at=None,
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference=connection.token_reference or "mock-token-reference",
            token_metadata=dict(connection.token_metadata),
            metadata=dict(connection.metadata),
        )

    async def disconnect(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email,
            status="disconnected",
            scopes=list(connection.scopes),
            connected_at=connection.connected_at,
            disconnected_at=_iso_now(),
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference="",
            token_metadata={},
            metadata=dict(connection.metadata),
        )

    async def build_authorization_url(
        self,
        *,
        state: str,
        scopes: list[str] | None = None,
        login_hint: str = "",
    ) -> str:
        raise ValueError("Mock provider does not support OAuth authorization.")

    async def complete_authorization(
        self,
        user_id: str,
        *,
        code: str,
        scopes: list[str] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ProviderAuthorizationResult:
        raise ValueError("Mock provider does not support OAuth authorization.")

    async def refresh_state(self, connection: EmailProviderConnection) -> EmailProviderConnection:
        return EmailProviderConnection(
            connection_id=connection.connection_id,
            user_id=connection.user_id,
            provider=self.provider_name,
            account_email=connection.account_email,
            status="connected",
            scopes=list(connection.scopes or ["mock.read"]),
            connected_at=connection.connected_at or _iso_now(),
            disconnected_at=connection.disconnected_at,
            last_sync_at=connection.last_sync_at,
            sync_cursor=connection.sync_cursor,
            token_reference=connection.token_reference or "mock-token-reference",
            token_metadata=dict(connection.token_metadata),
            metadata=dict(connection.metadata),
        )

    async def sync_messages(self, connection: EmailProviderConnection) -> ProviderSyncBatch:
        mailbox = await _load_mailbox(connection, self.mailbox_loader)
        current_cursor = connection.sync_cursor.strip()
        items: list[ProviderMessage] = []
        next_cursor = current_cursor
        numeric_cursors: list[int] = []
        for raw in mailbox:
            provider_message_id = str(raw.get("provider_message_id") or raw.get("id") or "").strip()
            provider_thread_id = str(raw.get("provider_thread_id") or raw.get("thread_id") or provider_message_id).strip()
            provider_history_id = str(raw.get("provider_history_id") or raw.get("history_id") or "").strip()
            if current_cursor and provider_history_id and provider_history_id <= current_cursor:
                continue
            if provider_history_id.isdigit():
                numeric_cursors.append(int(provider_history_id))
            items.append(
                ProviderMessage(
                    provider_message_id=provider_message_id,
                    provider_thread_id=provider_thread_id,
                    provider_history_id=provider_history_id,
                    subject=str(raw.get("subject") or "").strip(),
                    body_text=str(raw.get("body_text") or "").strip(),
                    body_reference=str(raw.get("body_reference") or f"mock://{connection.account_email}/{provider_message_id}").strip(),
                    received_at=str(raw.get("received_at") or "").strip() or None,
                    sender_email=str(raw.get("sender_email") or "").strip().casefold(),
                    sender_name=str(raw.get("sender_name") or "").strip(),
                    recipients=_string_list(raw.get("recipients")),
                    recruiter_email=str(raw.get("recruiter_email") or "").strip().casefold(),
                    recruiter_name=str(raw.get("recruiter_name") or "").strip(),
                    company=str(raw.get("company") or "").strip(),
                    job_title=str(raw.get("job_title") or "").strip(),
                    attachments=_attachment_refs(raw.get("attachments")),
                    metadata={"provider": self.provider_name, **(dict(raw.get("metadata")) if isinstance(raw.get("metadata"), dict) else {})},
                )
            )
        if numeric_cursors:
            next_cursor = str(max(numeric_cursors))
        elif items:
            next_cursor = items[-1].provider_history_id or current_cursor
        return ProviderSyncBatch(
            provider=self.provider_name,
            account_email=connection.account_email,
            items=items,
            threads=await self.sync_threads(connection),
            contacts=await self.sync_contacts(connection),
            next_cursor=next_cursor,
            metadata={"incremental": True, "message_count": len(items)},
        )

    async def sync_threads(self, connection: EmailProviderConnection) -> list[ProviderThreadSnapshot]:
        mailbox = await _load_mailbox(connection, self.mailbox_loader)
        grouped: dict[str, ProviderThreadSnapshot] = {}
        for raw in mailbox:
            thread_id = str(raw.get("provider_thread_id") or raw.get("thread_id") or raw.get("provider_message_id") or "").strip()
            if not thread_id:
                continue
            existing = grouped.get(thread_id)
            grouped[thread_id] = ProviderThreadSnapshot(
                provider_thread_id=thread_id,
                subject=str(raw.get("subject") or (existing.subject if existing is not None else "")).strip(),
                last_message_at=str(raw.get("received_at") or (existing.last_message_at if existing is not None else "")).strip() or None,
                message_count=(existing.message_count if existing is not None else 0) + 1,
                metadata={"provider": self.provider_name},
            )
        return list(grouped.values())

    async def sync_contacts(self, connection: EmailProviderConnection) -> list[ProviderContactSnapshot]:
        mailbox = await _load_mailbox(connection, self.mailbox_loader)
        contacts: dict[str, ProviderContactSnapshot] = {}
        for raw in mailbox:
            recruiter_email = str(raw.get("recruiter_email") or "").strip().casefold()
            if not recruiter_email:
                continue
            contacts[recruiter_email] = ProviderContactSnapshot(
                email=recruiter_email,
                display_name=str(raw.get("recruiter_name") or "").strip(),
                company=str(raw.get("company") or "").strip(),
                title=str(raw.get("job_title") or "").strip(),
                metadata={"provider": self.provider_name},
            )
        return list(contacts.values())


@dataclass
class EmailProviderRegistry:
    providers: dict[str, EmailProvider]

    def get(self, provider: str) -> EmailProvider:
        key = provider.strip().casefold()
        if key not in self.providers:
            raise ValueError(f"Unsupported email provider: {provider}")
        return self.providers[key]

    def list_names(self) -> list[str]:
        return sorted(self.providers.keys())


def build_email_provider_registry(settings: AppSettings | None = None) -> EmailProviderRegistry:
    resolved_settings = settings or get_settings()
    return EmailProviderRegistry(
        providers={
            "gmail": GmailProvider(settings=resolved_settings),
            "outlook": OutlookProvider(),
            "mock": MockProvider(),
        }
    )
