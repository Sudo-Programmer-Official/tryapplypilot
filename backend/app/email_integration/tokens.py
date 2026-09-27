from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from cryptography.fernet import Fernet, InvalidToken

from app.config import AppSettings, get_settings
from app.db.client import connection


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass(frozen=True)
class EmailProviderTokenSecret:
    token_reference: str
    user_id: str
    provider: str
    account_email: str
    access_token: str
    refresh_token: str = ""
    expires_at: str | None = None
    scope: str = ""
    token_type: str = "Bearer"
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def granted_scopes(self) -> list[str]:
        return [item.strip() for item in self.scope.split(" ") if item.strip()]

    def public_metadata(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "account_email": self.account_email,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "granted_scopes": self.granted_scopes(),
            "token_type": self.token_type,
        }
        if self.metadata:
            payload["provider_metadata"] = dict(self.metadata)
        return payload

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class EmailProviderTokenStore(Protocol):
    async def save_token(self, token: EmailProviderTokenSecret) -> EmailProviderTokenSecret:
        ...

    async def get_token(self, token_reference: str) -> EmailProviderTokenSecret | None:
        ...

    async def delete_token(self, token_reference: str) -> None:
        ...


def build_token_reference(user_id: str, provider: str) -> str:
    opaque_id = uuid5(NAMESPACE_URL, f"email-provider-token:{user_id}:{provider.strip().casefold()}")
    return f"vault://email-provider/{provider.strip().casefold()}/{opaque_id}"


ENCRYPTED_TOKEN_PREFIX = "fernet:v1:"


class ProviderTokenCipher:
    """Encrypts provider OAuth tokens at rest.

    Uses EMAIL_TOKEN_ENCRYPTION_KEY (a Fernet key) when configured, otherwise a key
    derived from the JWT secret so tokens are never stored in plain text.
    """

    def __init__(self, settings: AppSettings) -> None:
        configured_key = (settings.auth.provider_token_encryption_key or "").strip()
        if configured_key:
            key = configured_key.encode("utf-8")
        else:
            digest = hashlib.sha256(f"email-provider-token:{settings.auth.jwt_secret}".encode("utf-8")).digest()
            key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        return ENCRYPTED_TOKEN_PREFIX + self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        if not value.startswith(ENCRYPTED_TOKEN_PREFIX):
            # Rows written before encryption was introduced are stored in plain text.
            return value
        try:
            return self._fernet.decrypt(value[len(ENCRYPTED_TOKEN_PREFIX):].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Stored email provider token could not be decrypted; check EMAIL_TOKEN_ENCRYPTION_KEY.") from exc


def _row_to_token_secret(row, cipher: ProviderTokenCipher) -> EmailProviderTokenSecret:
    expires_at = row["expires_at"]
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return EmailProviderTokenSecret(
        token_reference=str(row["token_reference"]),
        user_id=str(row["user_id"]),
        provider=str(row["provider"]),
        account_email=str(row["account_email"] or ""),
        access_token=cipher.decrypt(str(row["access_token"] or "")),
        refresh_token=cipher.decrypt(str(row["refresh_token"] or "")),
        expires_at=expires_at.isoformat() if expires_at is not None else None,
        scope=str(row["scope"] or ""),
        token_type=str(row["token_type"] or "Bearer"),
        metadata=_json_object(row["metadata"]),
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


@dataclass
class InMemoryEmailProviderTokenStore:
    items: dict[str, EmailProviderTokenSecret] | None = None

    def __post_init__(self) -> None:
        self.items = {} if self.items is None else self.items

    async def save_token(self, token: EmailProviderTokenSecret) -> EmailProviderTokenSecret:
        assert self.items is not None
        self.items[token.token_reference] = token
        return token

    async def get_token(self, token_reference: str) -> EmailProviderTokenSecret | None:
        assert self.items is not None
        return self.items.get(token_reference)

    async def delete_token(self, token_reference: str) -> None:
        assert self.items is not None
        self.items.pop(token_reference, None)


class PostgresEmailProviderTokenStore:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self._cipher = ProviderTokenCipher(settings or get_settings())

    async def save_token(self, token: EmailProviderTokenSecret) -> EmailProviderTokenSecret:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO email_provider_token_secrets (
                    token_reference,
                    user_id,
                    provider,
                    account_email,
                    access_token,
                    refresh_token,
                    expires_at,
                    scope,
                    token_type,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7::timestamptz, $8, $9, $10::jsonb,
                    COALESCE($11::timestamptz, NOW()),
                    COALESCE($12::timestamptz, NOW())
                )
                ON CONFLICT (token_reference) DO UPDATE SET
                    account_email = EXCLUDED.account_email,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at = EXCLUDED.expires_at,
                    scope = EXCLUDED.scope,
                    token_type = EXCLUDED.token_type,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                RETURNING *
                """,
                token.token_reference,
                token.user_id,
                token.provider,
                token.account_email,
                self._cipher.encrypt(token.access_token),
                self._cipher.encrypt(token.refresh_token),
                token.expires_at,
                token.scope,
                token.token_type,
                json.dumps(token.metadata),
                token.created_at,
                token.updated_at,
            )
        assert row is not None
        return _row_to_token_secret(row, self._cipher)

    async def get_token(self, token_reference: str) -> EmailProviderTokenSecret | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM email_provider_token_secrets
                WHERE token_reference = $1
                """,
                token_reference,
            )
        return _row_to_token_secret(row, self._cipher) if row is not None else None

    async def delete_token(self, token_reference: str) -> None:
        async with connection() as conn:
            await conn.execute(
                """
                DELETE FROM email_provider_token_secrets
                WHERE token_reference = $1
                """,
                token_reference,
            )


def build_email_provider_token_store(settings: AppSettings | None = None) -> EmailProviderTokenStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryEmailProviderTokenStore()
    return PostgresEmailProviderTokenStore(resolved_settings)
