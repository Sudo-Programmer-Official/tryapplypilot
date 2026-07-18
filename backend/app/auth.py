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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _resume_role_focuses(profile: dict[str, object]) -> list[str]:
    resume_library = profile.get("resume_library")
    if not isinstance(resume_library, list):
        return []
    return [
        str(entry.get("role_focus", "")).strip()
        for entry in resume_library
        if isinstance(entry, dict) and str(entry.get("role_focus", "")).strip()
    ]


def _company_scope(preferences: dict[str, object]) -> list[str]:
    preferred_companies = _string_list(preferences.get("preferred_companies"))
    if preferred_companies:
        return preferred_companies
    company_priorities = preferences.get("company_priorities")
    if not isinstance(company_priorities, dict):
        return []
    return [
        company_name.strip()
        for company_name, priority in company_priorities.items()
        if company_name.strip() and str(priority).strip().casefold() != "hidden"
    ]


def _has_matching_signals(profile: dict[str, object], preferences: dict[str, object]) -> bool:
    signals = (
        _string_list(preferences.get("preferred_roles"))
        + _string_list(preferences.get("skills"))
        + [
            str(entry.get("skill", "")).strip()
            for entry in preferences.get("skill_priorities", [])
            if isinstance(entry, dict) and str(entry.get("skill", "")).strip()
        ]
        + _string_list(preferences.get("watchlists"))
        + _string_list(preferences.get("locations"))
        + _string_list(preferences.get("work_arrangements"))
        + _string_list(preferences.get("experience_levels"))
        + _string_list(preferences.get("job_types"))
        + _string_list(preferences.get("industries"))
        + _string_list(preferences.get("company_sizes"))
        + _string_list(profile.get("resume_skill_keywords"))
        + _resume_role_focuses(profile)
    )
    return len(signals) > 0


def onboarding_status_for_user(user: UserAccount) -> OnboardingStatus:
    profile = dict(user.profile)
    preferences = dict(user.preferences)
    preferred_companies = _company_scope(preferences)
    steps = [
        OnboardingStep(id="account_created", label="Account Created", completed=True),
        OnboardingStep(id="resume_uploaded", label="Resume Uploaded", completed=bool(profile.get("resume_uploaded"))),
        OnboardingStep(
            id="preferences_set",
            label="Preferences Set",
            completed=bool(
                normalize_supported_country(str(preferences.get("country", user.country)))
                and len(preferred_companies) > 0
                and _has_matching_signals(profile, preferences)
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
