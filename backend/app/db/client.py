from __future__ import annotations

from contextlib import asynccontextmanager
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


async def connect() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(**connect_kwargs_from_dsn(settings.database.dsn))


@asynccontextmanager
async def connection() -> asyncpg.Connection:
    conn = await connect()
    try:
        yield conn
    finally:
        await conn.close()
