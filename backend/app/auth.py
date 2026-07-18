from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt

from app.config import AppSettings, get_settings
from app.domain import AuthTokens, OnboardingStatus, OnboardingStep, UserAccount
from app.job_metadata import normalize_supported_country

ROLE_RANK = {
    "user": 1,
    "admin": 2,
    "super_admin": 3,
}

PASSWORD_HASHER = PasswordHasher()


def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _base_claims(user: UserAccount, settings: AppSettings, *, token_type: str, ttl: timedelta, token_id: str) -> dict[str, Any]:
    issued_at = _utc_now()
    expires_at = issued_at + ttl
    return {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "type": token_type,
        "iss": settings.auth.jwt_issuer,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": token_id,
    }


def create_access_token(user: UserAccount, settings: AppSettings | None = None) -> tuple[str, int]:
    resolved_settings = settings or get_settings()
    ttl = timedelta(minutes=resolved_settings.auth.access_token_minutes)
    payload = _base_claims(
        user,
        resolved_settings,
        token_type="access",
        ttl=ttl,
        token_id=str(uuid4()),
    )
    return (
        jwt.encode(payload, resolved_settings.auth.jwt_secret, algorithm="HS256"),
        int(ttl.total_seconds()),
    )


def create_refresh_token(user: UserAccount, settings: AppSettings | None = None) -> tuple[str, str, str, datetime, int]:
    resolved_settings = settings or get_settings()
    ttl = timedelta(days=resolved_settings.auth.refresh_token_days)
    refresh_token_id = str(uuid4())
    payload = _base_claims(
        user,
        resolved_settings,
        token_type="refresh",
        ttl=ttl,
        token_id=refresh_token_id,
    )
    token = jwt.encode(payload, resolved_settings.auth.jwt_secret, algorithm="HS256")
    expires_at = datetime.fromtimestamp(int(payload["exp"]), timezone.utc)
    return token, refresh_token_id, hash_refresh_token(token), expires_at, int(ttl.total_seconds())


def create_telegram_connect_token(user: UserAccount, settings: AppSettings | None = None) -> tuple[str, int]:
    resolved_settings = settings or get_settings()
    ttl = timedelta(minutes=15)
    payload = _base_claims(
        user,
        resolved_settings,
        token_type="telegram_link",
        ttl=ttl,
        token_id=str(uuid4()),
    )
    return (
        jwt.encode(payload, resolved_settings.auth.jwt_secret, algorithm="HS256"),
        int(ttl.total_seconds()),
    )


def decode_token(token: str, *, expected_type: str, settings: AppSettings | None = None) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    payload = jwt.decode(
        token,
        resolved_settings.auth.jwt_secret,
        algorithms=["HS256"],
        issuer=resolved_settings.auth.jwt_issuer,
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Unexpected token type: {payload.get('type')}")
    return payload


def issue_auth_tokens(user: UserAccount, settings: AppSettings | None = None) -> tuple[AuthTokens, str, str, datetime]:
    resolved_settings = settings or get_settings()
    access_token, access_expires_in_seconds = create_access_token(user, resolved_settings)
    refresh_token, refresh_token_id, refresh_token_hash, refresh_expires_at, refresh_expires_in_seconds = create_refresh_token(
        user,
        resolved_settings,
    )
    return (
        AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in_seconds=access_expires_in_seconds,
            refresh_expires_in_seconds=refresh_expires_in_seconds,
        ),
        refresh_token_id,
        refresh_token_hash,
        refresh_expires_at,
    )


def extract_telegram_start_token(text: str | None) -> str | None:
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    parts = stripped.split(maxsplit=1)
    if not parts:
        return None
    command = parts[0].casefold()
    if command != "/start" and not command.startswith("/start@"):
        return None
    if len(parts) < 2:
        return None
    token = parts[1].strip()
    return token or None


def onboarding_status_for_user(user: UserAccount) -> OnboardingStatus:
    profile = dict(user.profile)
    preferences = dict(user.preferences)
    preference_locations = preferences.get("locations", [])
    preferred_companies = preferences.get("preferred_companies", [])
    preferred_roles = preferences.get("preferred_roles", [])
    steps = [
        OnboardingStep(id="account_created", label="Account Created", completed=True),
        OnboardingStep(id="resume_uploaded", label="Resume Uploaded", completed=bool(profile.get("resume_uploaded"))),
        OnboardingStep(
            id="preferences_set",
            label="Preferences Set",
            completed=bool(
                normalize_supported_country(str(preferences.get("country", user.country)))
                and isinstance(preference_locations, list)
                and len(preference_locations) > 0
                and isinstance(preferred_companies, list)
                and len(preferred_companies) > 0
                and isinstance(preferred_roles, list)
                and len(preferred_roles) > 0
            ),
        ),
        OnboardingStep(id="telegram_connected", label="Telegram Connected", completed=bool(user.telegram_chat_id)),
    ]
    completed_steps = sum(1 for step in steps if step.completed)
    return OnboardingStatus(
        progress_percent=int((completed_steps / len(steps)) * 100),
        steps=steps,
    )


def role_allows(user_role: str, required_role: str) -> bool:
    return ROLE_RANK.get(user_role, 0) >= ROLE_RANK.get(required_role, 0)
