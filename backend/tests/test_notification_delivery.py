from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import sys
import types
import unittest
from unittest.mock import patch

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
from app.domain import UserAccount
from app.notification_delivery import evaluate_notification_decision
from app.scoring import MatchResult


class NotificationDeliveryTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_initial_sync_suppression_is_explicit(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        user = UserAccount(
            id="user-1",
            email="user@example.com",
            role="user",
            telegram_chat_id="12345",
            preferences={"minimum_match_score": 90, "freshness_hours": 24, "notification_frequency": "instant"},
        )
        job = NormalizedJobRecord(
            connector_key="greenhouse",
            external_job_id="job-1",
            company="Anthropic",
            title="Staff+ Software Engineer, Backend",
            location="San Francisco",
            remote_policy="Remote",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
            apply_url="https://example.com/jobs/1",
            description_text="Backend platform role",
            job_fingerprint="fingerprint",
            raw_payload={},
        )
        match = MatchResult(
            score=93,
            decision="APPLY_NOW",
            top_strengths=["Python"],
            gaps=["Kubernetes"],
            recommended_resume="Backend_AI_v5.pdf",
            provider="heuristic",
        )

        decision = evaluate_notification_decision(
            job=job,
            match=match,
            user=user,
            settings=settings,
            published_at=job.published_at or datetime.now(timezone.utc),
            now=datetime.now(timezone.utc),
            initial_sync=True,
            remaining_initial_alert_budget=0,
            delivery_phase="fresh",
            minimum_match_score_override=90,
            freshness_hours_override=24,
        )

        self.assertFalse(decision.should_send)
        self.assertEqual(decision.notification_status, "suppressed")
        self.assertEqual(decision.reason_code, "initial_sync_suppressed")
        self.assertEqual(decision.notification_type, "fresh_alert")

    def test_daily_digest_jobs_are_tracked_without_immediate_send(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()

        user = UserAccount(
            id="user-2",
            email="digest@example.com",
            role="user",
            telegram_chat_id="12345",
            preferences={"minimum_match_score": 90, "freshness_hours": 24, "notification_frequency": "morning_digest"},
        )
        job = NormalizedJobRecord(
            connector_key="greenhouse",
            external_job_id="job-2",
            company="OpenAI",
            title="Backend Engineer",
            location="Remote",
            remote_policy="Remote",
            published_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            apply_url="https://example.com/jobs/2",
            description_text="Distributed systems role",
            job_fingerprint="fingerprint-2",
            raw_payload={},
        )
        match = MatchResult(
            score=95,
            decision="APPLY_NOW",
            top_strengths=["Distributed Systems"],
            gaps=[],
            recommended_resume="Backend_AI_v5.pdf",
            provider="heuristic",
        )

        decision = evaluate_notification_decision(
            job=job,
            match=match,
            user=user,
            settings=settings,
            published_at=job.published_at or datetime.now(timezone.utc),
            now=datetime.now(timezone.utc),
            initial_sync=False,
            remaining_initial_alert_budget=0,
            delivery_phase="fresh",
            minimum_match_score_override=90,
            freshness_hours_override=24,
        )

        self.assertFalse(decision.should_send)
        self.assertEqual(decision.notification_status, "digest_pending")
        self.assertEqual(decision.reason_code, "daily_digest_scheduled")
        self.assertEqual(decision.notification_type, "daily_digest")


if __name__ == "__main__":
    unittest.main()
