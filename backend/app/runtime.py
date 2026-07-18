from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from app.config import AppSettings, get_settings
from app.connectors.registry import ConnectorRegistry, build_default_registry
from app.db.schema import load_schema_sql
from app.logging_utils import get_logger
from app.repositories.interfaces import RadarRepositories
from app.repositories.memory import build_seed_repositories
from app.repositories.postgres import build_postgres_repositories


@dataclass(frozen=True)
class DatabaseRuntimeStatus:
    backend: str
    target: str
    schema_tables: tuple[str, ...]
    connected: bool
    mode: str


@dataclass(frozen=True)
class AppRuntime:
    settings: AppSettings
    repositories: RadarRepositories
    connectors: ConnectorRegistry
    database: DatabaseRuntimeStatus


def _discover_schema_tables(schema_sql: str) -> tuple[str, ...]:
    table_names: list[str] = []
    for line in schema_sql.splitlines():
        normalized = line.strip().lower()
        if not normalized.startswith("create table if not exists "):
            continue
        table_name = normalized.removeprefix("create table if not exists ").split(" ", 1)[0]
        table_names.append(table_name)
    return tuple(table_names)


def _database_target_from_dsn(dsn: str) -> str:
    parsed = urlsplit(dsn)
    if parsed.hostname is None:
        return "local"
    port_segment = f":{parsed.port}" if parsed.port is not None else ""
    database_name = parsed.path.lstrip("/") or "default"
    return f"{parsed.hostname}{port_segment}/{database_name}"


@lru_cache(maxsize=1)
def get_runtime() -> AppRuntime:
    settings = get_settings()
    schema_sql = load_schema_sql()
    logger = get_logger("app.runtime")
    connectors = build_default_registry()
    if settings.radar.mode == "seed":
        repositories = build_seed_repositories()
        database_mode = "seed-repositories"
        connected = False
    else:
        repositories = build_postgres_repositories(connectors)
        database_mode = "postgres-repositories"
        connected = True
    logger.info(
        "Initialized app runtime",
        extra={
            "operation_name": "runtime.bootstrap",
            "connector_key": settings.database.backend,
        },
    )
    return AppRuntime(
        settings=settings,
        repositories=repositories,
        connectors=connectors,
        database=DatabaseRuntimeStatus(
            backend=settings.database.backend,
            target=_database_target_from_dsn(settings.database.dsn),
            schema_tables=_discover_schema_tables(schema_sql),
            connected=connected,
            mode=database_mode,
        ),
    )
