from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from asyncpg import Record

from app.auth import hash_password, hash_refresh_token, issue_auth_tokens, onboarding_status_for_user, verify_password
from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import AuthTokens, UserAccount, UserRole
from app.job_metadata import normalize_supported_country


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


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _default_profile(full_name: str) -> dict[str, object]:
    return {
        "full_name": full_name,
        "linkedin_url": "",
        "portfolio_url": "",
        "github_url": "",
        "years_of_experience": None,
        "visa_status": "",
        "work_authorization": "",
        "resume_uploaded": False,
    }


def _default_preferences(settings: AppSettings) -> dict[str, object]:
    return {
        "country": settings.radar.selected_country,
        "locations": [],
        "preferred_companies": [],
        "preferred_roles": [],
        "skills": [],
        "work_arrangements": list(settings.radar.preferred_work_arrangements),
        "experience_levels": list(settings.radar.preferred_experience_levels),
        "freshness_hours": settings.radar.alert_freshness_hours,
        "minimum_match_score": settings.radar.minimum_match_score,
        "notification_frequency": "instant",
        "watchlists": [],
    }


def _user_id(email: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"user:{email.strip().casefold()}"))


def _row_to_user(row: Record) -> UserAccount:
    user = UserAccount(
        id=str(row["user_id"]),
        email=str(row["email"]),
        role=str(row["role"]),  # type: ignore[arg-type]
        full_name=str(row["full_name"]),
        telegram_chat_id=row["telegram_chat_id"],
        country=normalize_supported_country(str(row["country"])),
        profile=_json_object(row["profile"]),
        preferences=_json_object(row["preferences"]),
        created_at=_isoformat(row["created_at"]),
        last_login_at=_isoformat(row["last_login_at"]),
    )
    return UserAccount(
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        telegram_chat_id=user.telegram_chat_id,
        country=user.country,
        profile=user.profile,
        preferences=user.preferences,
        onboarding=onboarding_status_for_user(user),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


async def ensure_super_admin(settings: AppSettings | None = None) -> None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return
    if not resolved_settings.auth.super_admin_email or not resolved_settings.auth.super_admin_password:
        return

    email = resolved_settings.auth.super_admin_email.strip().casefold()
    async with connection() as conn:
        existing = await conn.fetchval(
            "SELECT 1 FROM users WHERE email = $1",
            email,
        )
        if existing:
            return

        await conn.execute(
            """
            INSERT INTO users (
                user_id,
                email,
                password_hash,
                role,
                full_name,
                country,
                profile,
                preferences
            )
            VALUES ($1, $2, $3, 'super_admin', $4, $5, $6::jsonb, $7::jsonb)
            """,
            _user_id(email),
            email,
            hash_password(resolved_settings.auth.super_admin_password),
            resolved_settings.auth.super_admin_name,
            resolved_settings.radar.selected_country,
            json.dumps(_default_profile(resolved_settings.auth.super_admin_name)),
            json.dumps(_default_preferences(resolved_settings)),
        )


async def create_user(
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = "user",
    settings: AppSettings | None = None,
) -> UserAccount:
    resolved_settings = settings or get_settings()
    await ensure_super_admin(resolved_settings)
    normalized_email = email.strip().casefold()
    normalized_name = full_name.strip()
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (
                user_id,
                email,
                password_hash,
                role,
                full_name,
                country,
                profile,
                preferences
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
            RETURNING *
            """,
            _user_id(normalized_email),
            normalized_email,
            hash_password(password),
            role,
            normalized_name,
            resolved_settings.radar.selected_country,
            json.dumps(_default_profile(normalized_name)),
            json.dumps(_default_preferences(resolved_settings)),
        )
    assert row is not None
    created_user = _row_to_user(row)
    from app.audit_logs import record_audit_event

    await record_audit_event(
        actor_user=created_user,
        event_type="user.registered",
        subject_type="user",
        subject_id=created_user.id,
        message=f"{created_user.email} registered a new account.",
        metadata={"role": created_user.role},
        settings=resolved_settings,
    )
    return created_user


async def get_user_by_id(user_id: str, settings: AppSettings | None = None) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    await ensure_super_admin(resolved_settings)
    async with connection() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1 AND is_active = TRUE", user_id)
    if row is None:
        return None
    return _row_to_user(row)


async def get_user_by_email(email: str, settings: AppSettings | None = None) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    await ensure_super_admin(resolved_settings)
    async with connection() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1 AND is_active = TRUE", email.strip().casefold())
    if row is None:
        return None
    return _row_to_user(row)


async def authenticate_user(email: str, password: str, settings: AppSettings | None = None) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    await ensure_super_admin(resolved_settings)
    normalized_email = email.strip().casefold()
    async with connection() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1 AND is_active = TRUE", normalized_email)
        if row is None:
            return None
        if not verify_password(password, str(row["password_hash"])):
            return None
        await conn.execute(
            "UPDATE users SET last_login_at = NOW(), updated_at = NOW() WHERE user_id = $1",
            row["user_id"],
        )
        refreshed = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", row["user_id"])
    assert refreshed is not None
    return _row_to_user(refreshed)


async def issue_session_tokens(
    user: UserAccount,
    *,
    user_agent: str = "",
    ip_address: str = "",
    settings: AppSettings | None = None,
) -> AuthTokens:
    resolved_settings = settings or get_settings()
    tokens, refresh_token_id, refresh_token_hash, refresh_expires_at = issue_auth_tokens(user, resolved_settings)
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO refresh_tokens (
                refresh_token_id,
                user_id,
                token_hash,
                expires_at,
                user_agent,
                ip_address
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            refresh_token_id,
            user.id,
            refresh_token_hash,
            refresh_expires_at,
            user_agent[:500],
            ip_address[:100],
        )
    return tokens


async def rotate_refresh_token(
    raw_refresh_token: str,
    *,
    user_agent: str = "",
    ip_address: str = "",
    settings: AppSettings | None = None,
) -> tuple[UserAccount | None, AuthTokens | None]:
    from app.auth import decode_token

    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None, None
    payload = decode_token(raw_refresh_token, expected_type="refresh", settings=resolved_settings)
    refresh_token_id = str(payload["jti"])
    token_hash = hash_refresh_token(raw_refresh_token)
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.user_id, r.revoked_at, r.expires_at
            FROM refresh_tokens r
            WHERE r.refresh_token_id = $1 AND r.token_hash = $2
            """,
            refresh_token_id,
            token_hash,
        )
        if row is None or row["revoked_at"] is not None:
            return None, None
        if row["expires_at"] <= datetime.now(timezone.utc):
            return None, None
        await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = NOW(), last_used_at = NOW() WHERE refresh_token_id = $1",
            refresh_token_id,
        )
    user = await get_user_by_id(str(payload["sub"]), resolved_settings)
    if user is None:
        return None, None
    tokens = await issue_session_tokens(user, user_agent=user_agent, ip_address=ip_address, settings=resolved_settings)
    return user, tokens


async def revoke_refresh_token(raw_refresh_token: str, settings: AppSettings | None = None) -> None:
    from app.auth import decode_token

    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return
    payload = decode_token(raw_refresh_token, expected_type="refresh", settings=resolved_settings)
    await ensure_super_admin(resolved_settings)
    async with connection() as conn:
        await conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = NOW(), last_used_at = NOW()
            WHERE refresh_token_id = $1
              AND token_hash = $2
            """,
            str(payload["jti"]),
            hash_refresh_token(raw_refresh_token),
        )


async def set_user_telegram_chat(
    user_id: str,
    *,
    chat_id: str,
    username: str | None = None,
    first_name: str | None = None,
    settings: AppSettings | None = None,
) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    existing = await get_user_by_id(user_id, resolved_settings)
    if existing is None:
        return None

    profile = dict(existing.profile)
    if username:
        profile["telegram_username"] = username
    if first_name:
        profile["telegram_first_name"] = first_name

    async with connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET telegram_chat_id = $2,
                profile = $3::jsonb,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            chat_id.strip(),
            json.dumps(profile),
        )
    if row is None:
        return None
    return _row_to_user(row)


async def update_user_profile_fields(
    user_id: str,
    profile_updates: dict[str, object],
    *,
    settings: AppSettings | None = None,
) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    existing = await get_user_by_id(user_id, resolved_settings)
    if existing is None:
        return None

    profile = dict(existing.profile)
    profile.update(profile_updates)
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET profile = $2::jsonb,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            json.dumps(profile),
        )
    if row is None:
        return None
    return _row_to_user(row)


async def update_user_profile(
    user_id: str,
    payload: dict[str, Any],
    settings: AppSettings | None = None,
) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    existing = await get_user_by_id(user_id, resolved_settings)
    if existing is None:
        return None

    profile = dict(existing.profile)
    profile.update(
        {
            "linkedin_url": str(payload.get("linkedin_url", profile.get("linkedin_url", ""))).strip(),
            "portfolio_url": str(payload.get("portfolio_url", profile.get("portfolio_url", ""))).strip(),
            "github_url": str(payload.get("github_url", profile.get("github_url", ""))).strip(),
            "visa_status": str(payload.get("visa_status", profile.get("visa_status", ""))).strip(),
            "work_authorization": str(payload.get("work_authorization", profile.get("work_authorization", ""))).strip(),
            "resume_uploaded": bool(payload.get("resume_uploaded", profile.get("resume_uploaded", False))),
        }
    )
    years_of_experience = payload.get("years_of_experience", profile.get("years_of_experience"))
    profile["years_of_experience"] = int(years_of_experience) if years_of_experience not in {None, ""} else None
    full_name = str(payload.get("full_name", existing.full_name)).strip()

    async with connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET full_name = $2,
                profile = $3::jsonb,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            full_name,
            json.dumps(profile),
        )
    if row is None:
        return None
    return _row_to_user(row)


async def update_user_preferences(
    user_id: str,
    payload: dict[str, Any],
    settings: AppSettings | None = None,
) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    existing = await get_user_by_id(user_id, resolved_settings)
    if existing is None:
        return None

    preferences = dict(existing.preferences)
    preferences.update(
        {
            "country": normalize_supported_country(str(payload.get("country", preferences.get("country", existing.country)))),
            "locations": _string_list(payload.get("locations", preferences.get("locations", []))),
            "preferred_companies": _string_list(payload.get("preferred_companies", preferences.get("preferred_companies", []))),
            "preferred_roles": _string_list(payload.get("preferred_roles", preferences.get("preferred_roles", []))),
            "skills": _string_list(payload.get("skills", preferences.get("skills", []))),
            "work_arrangements": _string_list(payload.get("work_arrangements", preferences.get("work_arrangements", []))),
            "experience_levels": _string_list(payload.get("experience_levels", preferences.get("experience_levels", []))),
            "freshness_hours": int(payload.get("freshness_hours", preferences.get("freshness_hours", resolved_settings.radar.alert_freshness_hours))),
            "minimum_match_score": int(
                payload.get("minimum_match_score", preferences.get("minimum_match_score", resolved_settings.radar.minimum_match_score))
            ),
            "notification_frequency": str(payload.get("notification_frequency", preferences.get("notification_frequency", "instant"))).strip()
            or "instant",
        }
    )

    async with connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET country = $2,
                preferences = $3::jsonb,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            normalize_supported_country(str(preferences["country"])),
            json.dumps(preferences),
        )
    if row is None:
        return None
    return _row_to_user(row)


async def resolve_delivery_telegram_chat_id(settings: AppSettings | None = None) -> str | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return resolved_settings.telegram.chat_id

    await ensure_super_admin(resolved_settings)
    async with connection() as conn:
        chat_id = await conn.fetchval(
            """
            SELECT telegram_chat_id
            FROM users
            WHERE is_active = TRUE
              AND telegram_chat_id IS NOT NULL
              AND btrim(telegram_chat_id) <> ''
            ORDER BY CASE role
                WHEN 'super_admin' THEN 0
                WHEN 'admin' THEN 1
                ELSE 2
            END,
            created_at ASC
            LIMIT 1
            """
        )
    if isinstance(chat_id, str) and chat_id.strip():
        return chat_id.strip()
    return resolved_settings.telegram.chat_id


async def update_user_onboarding(
    user_id: str,
    payload: dict[str, Any],
    settings: AppSettings | None = None,
) -> UserAccount | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    existing = await get_user_by_id(user_id, resolved_settings)
    if existing is None:
        return None

    profile = dict(existing.profile)
    preferences = dict(existing.preferences)
    profile.update(
        {
            "full_name": str(payload.get("full_name", existing.full_name)).strip(),
            "linkedin_url": str(payload.get("linkedin_url", profile.get("linkedin_url", ""))).strip(),
            "portfolio_url": str(payload.get("portfolio_url", profile.get("portfolio_url", ""))).strip(),
            "github_url": str(payload.get("github_url", profile.get("github_url", ""))).strip(),
            "visa_status": str(payload.get("visa_status", profile.get("visa_status", ""))).strip(),
            "work_authorization": str(payload.get("work_authorization", profile.get("work_authorization", ""))).strip(),
            "resume_uploaded": bool(payload.get("resume_uploaded", profile.get("resume_uploaded", False))),
        }
    )
    years_of_experience = payload.get("years_of_experience", profile.get("years_of_experience"))
    profile["years_of_experience"] = int(years_of_experience) if years_of_experience not in {None, ""} else None

    preferences.update(
        {
            "country": normalize_supported_country(str(payload.get("country", preferences.get("country", existing.country)))),
            "locations": _string_list(payload.get("locations", preferences.get("locations", []))),
            "preferred_companies": _string_list(payload.get("preferred_companies", preferences.get("preferred_companies", []))),
            "preferred_roles": _string_list(payload.get("preferred_roles", preferences.get("preferred_roles", []))),
            "skills": _string_list(payload.get("skills", preferences.get("skills", []))),
            "watchlists": _string_list(payload.get("watchlists", preferences.get("watchlists", []))),
            "work_arrangements": _string_list(payload.get("work_arrangements", preferences.get("work_arrangements", []))),
            "experience_levels": _string_list(payload.get("experience_levels", preferences.get("experience_levels", []))),
            "freshness_hours": int(payload.get("freshness_hours", preferences.get("freshness_hours", resolved_settings.radar.alert_freshness_hours))),
            "minimum_match_score": int(
                payload.get("minimum_match_score", preferences.get("minimum_match_score", resolved_settings.radar.minimum_match_score))
            ),
            "notification_frequency": str(payload.get("notification_frequency", preferences.get("notification_frequency", "instant"))).strip()
            or "instant",
        }
    )

    full_name = str(payload.get("full_name", existing.full_name)).strip()
    telegram_chat_id = payload.get("telegram_chat_id", existing.telegram_chat_id)
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET full_name = $2,
                telegram_chat_id = $3,
                country = $4,
                profile = $5::jsonb,
                preferences = $6::jsonb,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            full_name,
            str(telegram_chat_id).strip() if telegram_chat_id else None,
            normalize_supported_country(str(preferences["country"])),
            json.dumps(profile),
            json.dumps(preferences),
        )
    if row is None:
        return None
    return _row_to_user(row)


async def list_users(settings: AppSettings | None = None) -> list[UserAccount]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return []
    await ensure_super_admin(resolved_settings)
    async with connection() as conn:
        rows = await conn.fetch("SELECT * FROM users WHERE is_active = TRUE ORDER BY created_at DESC")
    return [_row_to_user(row) for row in rows]
