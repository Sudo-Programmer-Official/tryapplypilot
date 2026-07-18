from __future__ import annotations

import argparse
import asyncio
import re

import asyncpg

from app.config import get_settings
from app.db.client import connect_kwargs_from_dsn
from app.db.schema import load_schema_sql
from app.logging_utils import get_logger

DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


async def ensure_database_exists(admin_dsn: str, database_name: str) -> bool:
    if not DATABASE_NAME_PATTERN.match(database_name):
        raise ValueError(f"Unsafe database name: {database_name}")

    connection = await asyncpg.connect(**connect_kwargs_from_dsn(admin_dsn))
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            database_name,
        )
        if exists:
            return False

        await connection.execute(f'CREATE DATABASE "{database_name}"')
        return True
    finally:
        await connection.close()


async def apply_schema(target_dsn: str, schema_sql: str) -> None:
    connection = await asyncpg.connect(**connect_kwargs_from_dsn(target_dsn))
    try:
        await connection.execute(schema_sql)
    finally:
        await connection.close()


async def bootstrap_database() -> None:
    settings = get_settings()
    logger = get_logger("app.db.bootstrap")
    database_name = settings.database.name

    created = await ensure_database_exists(settings.database.admin_dsn, database_name)
    logger.info(
        "Ensured database exists",
        extra={
            "operation_name": "db.ensure_database",
            "connector_key": database_name,
        },
    )
    if created:
        logger.info(
            "Created database",
            extra={
                "operation_name": "db.create_database",
                "connector_key": database_name,
            },
        )

    await apply_schema(settings.database.dsn, load_schema_sql())
    logger.info(
        "Applied schema",
        extra={
            "operation_name": "db.apply_schema",
            "connector_key": database_name,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the project database and apply the schema.")
    parser.parse_args()
    asyncio.run(bootstrap_database())


if __name__ == "__main__":
    main()
