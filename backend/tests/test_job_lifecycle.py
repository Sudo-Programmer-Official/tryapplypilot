from __future__ import annotations

import os
import sys
import types
import unittest
from datetime import datetime, timezone
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
from app.company_catalog_defaults import ai_company_collections_for_company
from app.domain import CompanyPreference
from app.job_lifecycle import lifecycle_for_missed_syncs
from app.services.admin_connectors import _monitoring_reason, _quality_grade


class JobLifecycleTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_lifecycle_transitions_from_active_to_stale_to_closed(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
        stale = lifecycle_for_missed_syncs(
            current_status="active",
            consecutive_missed_syncs=settings.lifecycle.stale_after_missed_syncs,
            current_closed_at=None,
            current_archived_at=None,
            settings=settings,
            now=now,
        )
        self.assertEqual(stale.lifecycle_status, "stale")
        self.assertEqual(stale.source_status, "missing")
        self.assertIsNone(stale.closed_at)

        closed = lifecycle_for_missed_syncs(
            current_status="stale",
            consecutive_missed_syncs=settings.lifecycle.closed_after_missed_syncs,
            current_closed_at=None,
            current_archived_at=None,
            settings=settings,
            now=now,
        )
        self.assertEqual(closed.lifecycle_status, "closed")
        self.assertEqual(closed.source_status, "missing")
        self.assertEqual(closed.closed_at, now)

    def test_monitoring_reason_distinguishes_monitored_planned_and_disabled(self) -> None:
        monitored, _ = _monitoring_reason(
            CompanyPreference(
                id="anthropic",
                company="Anthropic",
                enabled=True,
                connector="greenhouse",
                external_identifier="anthropic",
            ),
            validation_payload={"status": "passed"},
        )
        self.assertEqual(monitored, "monitored")

        monitored_beta, _ = _monitoring_reason(
            CompanyPreference(
                id="microsoft",
                company="Microsoft",
                enabled=True,
                connector="microsoft-careers",
                external_identifier="microsoft",
            ),
            validation_payload=None,
        )
        self.assertEqual(monitored_beta, "monitored")

        disabled, _ = _monitoring_reason(
            CompanyPreference(
                id="disabled",
                company="Disabled Co",
                enabled=False,
                connector="greenhouse",
                external_identifier="disabled-co",
            ),
            validation_payload=None,
        )
        self.assertEqual(disabled, "disabled")

    def test_quality_grade_and_ai_collections_helpers(self) -> None:
        self.assertEqual(_quality_grade(96.0, "live"), "A")
        self.assertEqual(_quality_grade(88.0, "beta"), "B+")
        self.assertEqual(_quality_grade(0.0, "planned"), "Planned")
        self.assertEqual(
            ai_company_collections_for_company("OpenAI"),
            ["AI Agents", "Foundation Models"],
        )


if __name__ == "__main__":
    unittest.main()
