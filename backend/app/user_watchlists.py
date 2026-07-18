from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import Watchlist, WatchlistTerm


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _normalize_terms(terms: list[WatchlistTerm]) -> list[WatchlistTerm]:
    normalized: list[WatchlistTerm] = []
    for term in terms:
        cleaned_term = term.term.strip()
        cleaned_company = term.company.strip()
        if not cleaned_term:
            continue
        normalized.append(
            WatchlistTerm(
                id=term.id,
                term=cleaned_term,
                company=cleaned_company,
                enabled=term.enabled,
            )
        )
    return normalized


def _build_watchlists(rows) -> list[Watchlist]:
    watchlists: dict[str, Watchlist] = {}
    for row in rows:
        watchlist_id = str(row["user_watchlist_id"])
        watchlist = watchlists.get(watchlist_id)
        if watchlist is None:
            watchlist = Watchlist(
                id=watchlist_id,
                name=str(row["name"]),
                enabled=bool(row["enabled"]),
                terms=[],
            )
            watchlists[watchlist_id] = watchlist
        if row["user_watchlist_term_id"] is None:
            continue
        watchlist.terms.append(
            WatchlistTerm(
                id=str(row["user_watchlist_term_id"]),
                term=str(row["term"]),
                company=str(row["company_name"]),
                enabled=bool(row["term_enabled"]),
            )
        )
    return list(watchlists.values())


async def _fetch_watchlists(
    *,
    user_id: str,
    watchlist_id: str | None = None,
) -> list[Watchlist]:
    params: list[object] = [user_id]
    where_clause = "uw.user_id = $1"
    if watchlist_id is not None:
        params.append(watchlist_id)
        where_clause += " AND uw.user_watchlist_id = $2"

    async with connection() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                uw.user_watchlist_id,
                uw.name,
                uw.enabled,
                uw.created_at,
                uw.updated_at,
                uwt.user_watchlist_term_id,
                uwt.term,
                uwt.company_name,
                uwt.enabled AS term_enabled
            FROM user_watchlists uw
            LEFT JOIN user_watchlist_terms uwt ON uwt.user_watchlist_id = uw.user_watchlist_id
            WHERE {where_clause}
            ORDER BY uw.updated_at DESC, uwt.created_at ASC
            """,
            *params,
        )
    return _build_watchlists(rows)


async def list_user_watchlists(user_id: str, settings: AppSettings | None = None) -> list[Watchlist]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return []
    return await _fetch_watchlists(user_id=user_id)


async def create_user_watchlist(
    user_id: str,
    *,
    name: str,
    enabled: bool,
    terms: list[WatchlistTerm],
    settings: AppSettings | None = None,
) -> Watchlist:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        raise ValueError("User watchlists are unavailable in seed mode.")

    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("Watchlist name is required.")
    cleaned_terms = _normalize_terms(terms)
    watchlist_id = str(uuid4())

    async with connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO user_watchlists (
                    user_watchlist_id,
                    user_id,
                    name,
                    enabled,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, NOW())
                """,
                watchlist_id,
                user_id,
                cleaned_name,
                enabled,
            )
            for term in cleaned_terms:
                await conn.execute(
                    """
                    INSERT INTO user_watchlist_terms (
                        user_watchlist_term_id,
                        user_watchlist_id,
                        term,
                        company_name,
                        enabled,
                        updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    """,
                    str(uuid4()),
                    watchlist_id,
                    term.term,
                    term.company,
                    term.enabled,
                )

    created = await _fetch_watchlists(user_id=user_id, watchlist_id=watchlist_id)
    if not created:
        raise ValueError("Failed to create watchlist.")
    return created[0]


async def update_user_watchlist(
    user_id: str,
    watchlist_id: str,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    terms: list[WatchlistTerm] | None = None,
    settings: AppSettings | None = None,
) -> Watchlist:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        raise ValueError("User watchlists are unavailable in seed mode.")

    existing = await _fetch_watchlists(user_id=user_id, watchlist_id=watchlist_id)
    if not existing:
        raise ValueError("Unknown watchlist.")
    current = existing[0]
    next_name = name.strip() if name is not None else current.name
    if not next_name:
        raise ValueError("Watchlist name is required.")
    next_terms = _normalize_terms(terms if terms is not None else current.terms)
    next_enabled = current.enabled if enabled is None else enabled

    async with connection() as conn:
        async with conn.transaction():
            updated = await conn.execute(
                """
                UPDATE user_watchlists
                SET name = $3,
                    enabled = $4,
                    updated_at = NOW()
                WHERE user_watchlist_id = $1
                  AND user_id = $2
                """,
                watchlist_id,
                user_id,
                next_name,
                next_enabled,
            )
            if updated == "UPDATE 0":
                raise ValueError("Unknown watchlist.")
            await conn.execute(
                "DELETE FROM user_watchlist_terms WHERE user_watchlist_id = $1",
                watchlist_id,
            )
            for term in next_terms:
                await conn.execute(
                    """
                    INSERT INTO user_watchlist_terms (
                        user_watchlist_term_id,
                        user_watchlist_id,
                        term,
                        company_name,
                        enabled,
                        updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    """,
                    str(uuid4()),
                    watchlist_id,
                    term.term,
                    term.company,
                    term.enabled,
                )

    updated_watchlists = await _fetch_watchlists(user_id=user_id, watchlist_id=watchlist_id)
    if not updated_watchlists:
        raise ValueError("Failed to update watchlist.")
    return updated_watchlists[0]


async def delete_user_watchlist(user_id: str, watchlist_id: str, settings: AppSettings | None = None) -> bool:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return False

    async with connection() as conn:
        deleted = await conn.fetchval(
            """
            DELETE FROM user_watchlists
            WHERE user_watchlist_id = $1
              AND user_id = $2
            RETURNING user_watchlist_id
            """,
            watchlist_id,
            user_id,
        )
    return deleted is not None
