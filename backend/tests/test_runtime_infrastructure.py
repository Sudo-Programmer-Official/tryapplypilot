from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

if "asyncpg" not in sys.modules:
    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "jwt" not in sys.modules:
    jwt_stub = types.ModuleType("jwt")

    class _InvalidTokenError(Exception):
        pass

    jwt_stub.InvalidTokenError = _InvalidTokenError
    jwt_stub.encode = lambda payload, secret, algorithm=None: "stub-token"
    jwt_stub.decode = lambda token, secret, algorithms=None, issuer=None: {"type": "access"}
    sys.modules["jwt"] = jwt_stub

from app.config import get_settings
from app.connectors.registry import build_default_registry
from app.db.schema import load_schema_sql
from app.retry import RetryPolicy, retry_sync
from app.runtime import get_runtime


class RuntimeInfrastructureTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()
        get_runtime.cache_clear()

    def test_schema_asset_contains_core_tables(self) -> None:
        schema_sql = load_schema_sql()
        self.assertIn("CREATE TABLE IF NOT EXISTS jobs", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS seen_jobs", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS alerts", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS companies", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS watchlists", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS user_preferences", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS saved_jobs", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS user_watchlists", schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS audit_logs", schema_sql)
        self.assertIn("inventory_complete BOOLEAN NOT NULL DEFAULT TRUE", schema_sql)
        self.assertIn("pages_scanned INTEGER NOT NULL DEFAULT 1", schema_sql)

    def test_schema_applies_column_backfills_before_dependent_indexes(self) -> None:
        schema_sql = load_schema_sql()
        self.assertLess(
            schema_sql.index("ALTER TABLE jobs"),
            schema_sql.index("CREATE INDEX IF NOT EXISTS jobs_company_lifecycle_idx"),
        )
        self.assertLess(
            schema_sql.index("ALTER TABLE connector_runs"),
            schema_sql.index("CREATE INDEX IF NOT EXISTS connector_runs_company_started_idx"),
        )

    def test_runtime_exposes_schema_tables_and_database_target(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            get_runtime.cache_clear()
            settings = get_settings()
            runtime = get_runtime()
        self.assertIn("jobs", runtime.database.schema_tables)
        self.assertIn("alerts", runtime.database.schema_tables)
        self.assertTrue(runtime.database.target.endswith(f"/{settings.database.name}"))

    def test_database_name_can_be_derived_from_template_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "JOB_RADAR_DATABASE_TEMPLATE_URL": "postgresql+asyncpg://postgres:password@example.com:5432/postgres?ssl=require",
                "JOB_RADAR_DATABASE_NAME": "job_hunter_app",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertEqual(settings.database.name, "job_hunter_app")
        self.assertIn("/job_hunter_app", settings.database.dsn)
        self.assertIn("/postgres", settings.database.admin_dsn)
        self.assertIn("ssl=require", settings.database.dsn)

    def test_connector_registry_keeps_greenhouse_first(self) -> None:
        registry = build_default_registry()
        definitions = registry.list_definitions()
        self.assertGreater(len(definitions), 0)
        self.assertEqual(definitions[0].key, "greenhouse")
        self.assertEqual(definitions[0].layer, "official_ats")
        self.assertEqual(definitions[0].admin_status, "live")
        self.assertEqual(definitions[0].rollout_stage, "live")

    def test_default_cors_origins_include_production_domains(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertIn("https://tryapplypilot.com", settings.cors_allowed_origins)
        self.assertIn("https://www.tryapplypilot.com", settings.cors_allowed_origins)

    def test_cors_origins_can_be_overridden(self) -> None:
        with patch.dict(
            os.environ,
            {
                "JOB_RADAR_CORS_ORIGINS": "https://www.tryapplypilot.com,https://admin.tryapplypilot.com",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertEqual(
            settings.cors_allowed_origins,
            ("https://www.tryapplypilot.com", "https://admin.tryapplypilot.com"),
        )

    def test_retry_sync_retries_before_succeeding(self) -> None:
        attempts = {"count": 0}

        def flaky_operation() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("transient failure")
            return "ok"

        result = retry_sync(
            flaky_operation,
            policy=RetryPolicy(
                max_attempts=3,
                base_delay_seconds=0.0,
                max_delay_seconds=0.0,
                backoff_multiplier=2.0,
            ),
            sleep=lambda _: None,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(attempts["count"], 3)


if __name__ == "__main__":
    unittest.main()
