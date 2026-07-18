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
from app.runtime import get_runtime
from app.services.dashboard import build_dashboard_snapshot, build_health_snapshot, get_job, list_jobs


class DashboardServiceTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()
        get_runtime.cache_clear()

    async def test_job_lookup_returns_expected_company(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            get_runtime.cache_clear()
            job = await get_job("databricks-ml-platform")
        self.assertIsNotNone(job)
        self.assertEqual(job["company"], "Databricks")

    async def test_job_filter_respects_min_score(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            get_runtime.cache_clear()
            jobs = await list_jobs(min_score=90)
        self.assertGreater(len(jobs), 0)
        self.assertTrue(all(job["match_score"] >= 90 for job in jobs))
        self.assertTrue(all(job["decision"] == "APPLY_NOW" for job in jobs))

    async def test_dashboard_meets_five_minute_operating_target(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            get_runtime.cache_clear()
            snapshot = await build_dashboard_snapshot()
        self.assertEqual(snapshot["summary"]["polling_interval_minutes"], 5)
        self.assertLessEqual(snapshot["summary"]["notification_sla_minutes"], 5)
        self.assertEqual(snapshot["agent"]["name"], "Market Scout Agent")
        self.assertEqual(snapshot["agent"]["current_connector"], "Greenhouse")
        self.assertEqual(snapshot["product"]["name"], "TryApplyPilot")
        self.assertGreater(len(snapshot["settings"]["companies"]), 20)
        self.assertEqual(snapshot["settings"]["companies"][0]["tier"], 1)
        self.assertIn("role_families", snapshot["settings"])
        self.assertIn("work_arrangements", snapshot["settings"])
        self.assertIn("experience_levels", snapshot["settings"])
        self.assertIn("excluded_keywords", snapshot["settings"])
        self.assertIn("watchlists", snapshot["settings"])
        self.assertGreater(len(snapshot["settings"]["watchlists"]), 0)
        self.assertIn("scheduler", snapshot)
        self.assertIn("source_coverage", snapshot)
        self.assertIn("connector_roadmap", snapshot)
        self.assertGreater(len(snapshot["source_coverage"]), 0)
        self.assertEqual(snapshot["source_coverage"][0]["layer"], "official_ats")
        self.assertIn("jobs_matched", snapshot["system_status"]["stats"])
        self.assertIn("errors", snapshot["system_status"]["stats"])

    async def test_health_snapshot_reports_connector_status(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            get_runtime.cache_clear()
            health = await build_health_snapshot()
        self.assertEqual(health["service"], "ai-job-radar-api")
        self.assertGreater(len(health["connectors"]), 0)
        self.assertEqual(health["connectors"][0]["source"], "Greenhouse")
        self.assertEqual(health["connectors"][0]["layer"], "official_ats")
        self.assertIn("source_layers", health)
        self.assertIn("scheduler", health)
        self.assertIn("running", health["scheduler"])


if __name__ == "__main__":
    unittest.main()
