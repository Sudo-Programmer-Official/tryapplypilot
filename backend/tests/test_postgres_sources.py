from __future__ import annotations

from datetime import datetime, timezone
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
from app.repositories.postgres import AggregatedSourcesRepository


class _FakeConnection:
    def __init__(self, aggregate: dict[str, object], latest_run: dict[str, object]) -> None:
        self._aggregate = aggregate
        self._latest_run = latest_run

    async def fetchrow(self, query: str, key: str, key_prefix: str) -> dict[str, object]:
        del key, key_prefix
        if "SUM(jobs_inserted)" in query:
            return self._aggregate
        return self._latest_run


class PostgresSourcesTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    async def test_build_source_status_sets_next_scheduled_poll(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        repository = AggregatedSourcesRepository(settings=settings, registry=build_default_registry())
        definition = build_default_registry().get("greenhouse")
        assert definition is not None
        last_run_at = datetime(2026, 7, 18, 18, 0, tzinfo=timezone.utc)
        source = await repository._build_source_status(
            _FakeConnection(
                aggregate={
                    "new_jobs_today": 4,
                    "jobs_collected": 20,
                    "retries_today": 0,
                    "average_runtime_seconds": 2.2,
                    "last_run_at": last_run_at,
                    "last_successful_sync": last_run_at,
                    "last_failed_sync": None,
                },
                latest_run={
                    "run_status": "succeeded",
                    "started_at": last_run_at,
                    "finished_at": last_run_at,
                    "error_message": None,
                },
            ),
            definition,
            settings,
        )

        self.assertEqual(source.connector_key, "greenhouse")
        self.assertEqual(source.layer, "official_ats")
        self.assertEqual(source.admin_status, "live")
        self.assertEqual(source.cadence_minutes, 5)
        self.assertGreater(source.companies_enabled, 0)
        self.assertTrue(source.next_scheduled_poll)
        self.assertTrue(source.next_scheduled_poll.startswith("2026-07-18T18:05:00"))


if __name__ == "__main__":
    unittest.main()
