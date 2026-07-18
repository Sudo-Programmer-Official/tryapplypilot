from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.lever import LeverBoard, LeverJobConnector


class LeverConnectorTests(unittest.TestCase):
    def test_collect_normalizes_lever_postings(self) -> None:
        connector = LeverJobConnector(
            board=LeverBoard(company="Linear", token="linear"),
            connector_settings=ConnectorSettings(
                request_timeout_seconds=20,
                retry_attempts=3,
                base_retry_delay_seconds=0.5,
                max_retry_delay_seconds=8.0,
                backoff_multiplier=2.0,
                rate_limit_per_minute=20,
            ),
        )
        payload = [
            {
                "id": "job-123",
                "text": "Senior Backend Engineer",
                "hostedUrl": "https://jobs.lever.co/linear/job-123",
                "descriptionPlain": "Remote role building distributed systems.",
                "updatedAt": 1784385600000,
                "categories": {
                    "location": "Remote - United States",
                    "team": "Engineering",
                    "commitment": "Full-time",
                },
            }
        ]
        with patch("app.connectors.lever.request_json", return_value=payload):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "lever:linear")
        self.assertEqual(job.external_job_id, "job-123")
        self.assertEqual(job.company, "Linear")
        self.assertEqual(job.title, "Senior Backend Engineer")
        self.assertEqual(job.location, "Remote - United States")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(job.apply_url, "https://jobs.lever.co/linear/job-123")
        self.assertIn("distributed systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)
        self.assertEqual(result.requests_made, 1)
        self.assertTrue(result.exhausted)


if __name__ == "__main__":
    unittest.main()
