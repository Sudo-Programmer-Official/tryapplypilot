from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlsplit

import asyncpg

from app.config import get_settings


def normalize_asyncpg_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


def connect_kwargs_from_dsn(dsn: str) -> dict[str, object]:
    normalized_dsn = normalize_asyncpg_dsn(dsn)
    parsed = urlsplit(normalized_dsn)
    query = parse_qs(parsed.query)
    ssl_mode = query.get("sslmode", query.get("ssl", [None]))[0]
    return {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/") or "postgres",
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "ssl": ssl_mode if ssl_mode in {"require", "prefer", "allow", "verify-ca", "verify-full"} else None,
    }


_PG_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)
_PG_INFINITY = 2**63 - 1


def _encode_timestamptz(value: datetime | str) -> tuple[int]:
    # Domain models carry timestamps as ISO-8601 strings; accept them alongside datetimes
    # so stores can bind either without converting at every call site.
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return ((value - _PG_EPOCH) // timedelta(microseconds=1),)


def _decode_timestamptz(value: tuple[int]) -> datetime:
    microseconds = value[0]
    if microseconds == _PG_INFINITY:
        return datetime.max.replace(tzinfo=timezone.utc)
    if microseconds == -_PG_INFINITY - 1:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _PG_EPOCH + timedelta(microseconds=microseconds)


async def connect() -> asyncpg.Connection:
    settings = get_settings()
    conn = await asyncpg.connect(**connect_kwargs_from_dsn(settings.database.dsn))
    await conn.set_type_codec(
        "timestamptz",
        schema="pg_catalog",
        encoder=_encode_timestamptz,
        decoder=_decode_timestamptz,
        format="tuple",
    )
    return conn


@asynccontextmanager
async def connection() -> asyncpg.Connection:
    conn = await connect()
    try:
        yield conn
    finally:
        await conn.close()
