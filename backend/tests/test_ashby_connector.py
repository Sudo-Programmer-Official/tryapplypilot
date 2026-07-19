from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.ashby import AshbyBoard, AshbyJobConnector


class AshbyConnectorTests(unittest.TestCase):
    def test_collect_normalizes_ashby_jobs_and_filters_country(self) -> None:
        connector = AshbyJobConnector(
            board=AshbyBoard(company="Ramp", token="ramp", country="US"),
            connector_settings=ConnectorSettings(
                request_timeout_seconds=20,
                retry_attempts=3,
                base_retry_delay_seconds=0.5,
                max_retry_delay_seconds=8.0,
                backoff_multiplier=2.0,
                rate_limit_per_minute=20,
            ),
        )
        payload = {
            "apiVersion": "1",
            "jobs": [
                {
                    "id": "job-1",
                    "title": "Senior Platform Engineer",
                    "location": "New York, NY, USA",
                    "secondaryLocations": [{"location": "Remote (United States)"}],
                    "department": "Engineering",
                    "team": "Platform",
                    "isListed": True,
                    "isRemote": True,
                    "workplaceType": "Remote",
                    "descriptionPlain": "Build backend infrastructure and distributed systems.",
                    "publishedAt": "2026-07-18T17:12:35.753+00:00",
                    "employmentType": "FullTime",
                    "jobUrl": "https://jobs.ashbyhq.com/ramp/job-1",
                    "applyUrl": "https://jobs.ashbyhq.com/ramp/job-1/application",
                },
                {
                    "id": "job-2",
                    "title": "Platform Engineer",
                    "location": "Toronto, ON, Canada",
                    "secondaryLocations": [],
                    "isListed": True,
                    "isRemote": False,
                    "workplaceType": "OnSite",
                    "descriptionPlain": "Canada-only role.",
                    "publishedAt": "2026-07-18T19:12:35.753+00:00",
                    "jobUrl": "https://jobs.ashbyhq.com/ramp/job-2",
                    "applyUrl": "https://jobs.ashbyhq.com/ramp/job-2/application",
                },
            ],
        }

        with patch("app.connectors.ashby.request_json", return_value=payload):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "ashby:ramp")
        self.assertEqual(job.external_job_id, "job-1")
        self.assertEqual(job.company, "Ramp")
        self.assertEqual(job.title, "Senior Platform Engineer")
        self.assertIn("Remote (United States)", job.location)
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(job.apply_url, "https://jobs.ashbyhq.com/ramp/job-1/application")
        self.assertIn("distributed systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 1)


if __name__ == "__main__":
    unittest.main()
