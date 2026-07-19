from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

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
from app.connectors.base import NormalizedJobRecord
from app.domain import CompanyPreference, UserAccount
from app.market_scout import ConnectorRunSummary, MarketScoutAgent, UserMatchContext


class _FakeConnectionContext:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def fetch(self, query: str, keys: list[str]):
        del query, keys
        return self._rows


class _PendingAlertConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.inserted_alerts: list[tuple[object, ...]] = []
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, job_id: str):
        del query, job_id
        return self._rows

    async def fetchval(self, query: str, *args: object):
        del query
        self.inserted_alerts.append(args)
        return args[0]

    async def execute(self, query: str, *args: object):
        self.executed.append((query, args))


class MarketScoutTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    async def test_due_companies_respect_company_poll_interval(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        companies = (
            CompanyPreference(
                id="stripe",
                company="Stripe",
                enabled=True,
                tier=1,
                priority=1,
                connector="greenhouse",
                poll_interval_minutes=15,
                country="US",
                career_url="https://job-boards.greenhouse.io/stripe",
                external_identifier="stripe",
                role_families=["Backend Engineering"],
            ),
            CompanyPreference(
                id="anthropic",
                company="Anthropic",
                enabled=True,
                tier=1,
                priority=2,
                connector="greenhouse",
                poll_interval_minutes=5,
                country="US",
                career_url="https://job-boards.greenhouse.io/anthropic",
                external_identifier="anthropic",
                role_families=["AI Platform"],
            ),
        )
        agent = MarketScoutAgent(settings=replace(settings, radar=replace(settings.radar, companies=companies)))
        current_time = datetime.now(timezone.utc)
        rows = [
            {
                "connector_key": "greenhouse:stripe",
                "last_successful_sync": current_time - timedelta(minutes=2),
            },
            {
                "connector_key": "greenhouse:anthropic",
                "last_successful_sync": current_time - timedelta(minutes=20),
            },
        ]

        with patch("app.market_scout.connection", return_value=_FakeConnectionContext(rows)):
            groups, enabled_counts, skipped_counts = await agent._due_companies_by_connector()

        self.assertEqual(enabled_counts, {"greenhouse": 2})
        self.assertEqual(skipped_counts, {"greenhouse": 1})
        self.assertEqual([company.company for company in groups["greenhouse"]], ["Anthropic"])

    def test_connector_cycle_summary_aggregates_by_connector(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            agent = MarketScoutAgent(settings=get_settings())

        summary = agent._connector_cycle_summary(
            [
                ConnectorRunSummary(
                    connector_key="greenhouse:stripe",
                    company="Stripe",
                    jobs_fetched=120,
                    jobs_inserted=4,
                    jobs_updated=10,
                    jobs_matched=8,
                    alerts_sent=2,
                    alerts_failed=1,
                ),
                ConnectorRunSummary(
                    connector_key="greenhouse:anthropic",
                    company="Anthropic",
                    jobs_fetched=90,
                    jobs_inserted=3,
                    jobs_updated=5,
                    jobs_matched=6,
                    alerts_sent=1,
                    alerts_failed=0,
                    failed=True,
                    error_message="sample failure",
                ),
                ConnectorRunSummary(
                    connector_key="lever:neon",
                    company="Neon",
                    jobs_fetched=11,
                    jobs_inserted=2,
                    jobs_updated=1,
                    jobs_matched=3,
                    alerts_sent=1,
                    alerts_failed=0,
                ),
            ],
            enabled_company_counts={"greenhouse": 3, "lever": 1},
            skipped_company_counts={"greenhouse": 1},
        )

        self.assertEqual(
            summary,
            [
                {
                    "connector": "greenhouse",
                    "companies_enabled": 3,
                    "companies_polled": 2,
                    "companies_skipped_interval": 1,
                    "jobs_fetched": 210,
                    "jobs_new": 7,
                    "jobs_updated": 15,
                    "jobs_matched": 14,
                    "alerts_sent": 3,
                    "alerts_failed": 1,
                    "failures": 1,
                },
                {
                    "connector": "lever",
                    "companies_enabled": 1,
                    "companies_polled": 1,
                    "companies_skipped_interval": 0,
                    "jobs_fetched": 11,
                    "jobs_new": 2,
                    "jobs_updated": 1,
                    "jobs_matched": 3,
                    "alerts_sent": 1,
                    "alerts_failed": 0,
                    "failures": 0,
                },
            ],
        )

    async def test_existing_job_pending_alerts_are_delivered_on_followup_cycle(self) -> None:
        with patch.dict(
            os.environ,
            {
                "JOB_RADAR_RUNTIME_MODE": "seed",
                "JOB_RADAR_ALERT_FRESHNESS_HOURS": "24",
                "JOB_RADAR_MINIMUM_MATCH_SCORE": "90",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            settings = get_settings()

        agent = MarketScoutAgent(settings=settings)
        user = UserAccount(
            id="user-1",
            email="user@example.com",
            role="user",
            telegram_chat_id="12345",
            preferences={"minimum_match_score": 90, "freshness_hours": 24},
        )
        user_context = UserMatchContext(
            user=user,
            settings=settings,
            profile_text="Backend engineer",
            minimum_match_score=90,
            freshness_hours=24,
        )
        job = NormalizedJobRecord(
            connector_key="greenhouse",
            external_job_id="anthropic-role",
            company="Anthropic",
            title="Staff+ Software Engineer, Backend",
            location="San Francisco",
            remote_policy="Remote",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            apply_url="https://example.com/jobs/anthropic-role",
            description_text="Backend distributed systems role",
            job_fingerprint="fingerprint",
            raw_payload={},
        )
        conn = _PendingAlertConnection(
            [
                {
                    "user_id": "user-1",
                    "match_score": 93,
                    "decision": "APPLY_NOW",
                    "recommended_resume": "Backend_AI_v5.pdf",
                    "why": ["Python", "Backend"],
                    "gaps": ["Kubernetes"],
                    "provider": "heuristic",
                }
            ]
        )

        with patch.object(agent, "_send_inserted_alert", AsyncMock(return_value=(1, 0))) as send_alert:
            alerts_sent, alerts_failed = await agent._deliver_pending_alerts_for_existing_job(
                conn=conn,
                job_id="job-1",
                job=job,
                user_contexts=[user_context],
                published_at=job.published_at or datetime.now(timezone.utc),
                country_code="US",
                now=datetime.now(timezone.utc),
            )

        self.assertEqual((alerts_sent, alerts_failed), (1, 0))
        self.assertEqual(len(conn.inserted_alerts), 1)
        send_alert.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
