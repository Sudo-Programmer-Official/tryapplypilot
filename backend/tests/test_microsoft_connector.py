from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.microsoft_careers import MicrosoftCareerSite, MicrosoftCareersJobConnector


def _position(job_id: int, *, country: str = "US") -> dict[str, object]:
    return {
        "id": str(job_id),
        "displayJobId": f"2000{job_id}",
        "name": f"Software Engineer {job_id}",
        "postedTs": 1784428800 - job_id,
        "creationTs": 1784420000 - job_id,
        "positionUrl": f"/careers/job/{job_id}",
        "workLocationOption": "remote" if country == "US" else "onsite",
        "locationFlexibility": "0 days / week in-office – remote" if country == "US" else None,
        "department": "Software Engineering",
        "atsJobId": f"ats-{job_id}",
        "locations": ["Seattle, WA, USA"] if country == "US" else ["Bengaluru, Karnataka, India"],
        "standardizedLocations": [country],
    }


class MicrosoftConnectorTests(unittest.TestCase):
    def test_collect_paginates_engineering_results(self) -> None:
        connector = MicrosoftCareersJobConnector(
            site=MicrosoftCareerSite(
                company="Microsoft",
                domain="microsoft.com",
                country="US",
                role_families=("Platform Engineering",),
                max_pages_per_run=5,
            ),
            connector_settings=ConnectorSettings(
                request_timeout_seconds=20,
                retry_attempts=3,
                base_retry_delay_seconds=0.5,
                max_retry_delay_seconds=8.0,
                backoff_multiplier=2.0,
                rate_limit_per_minute=12,
            ),
        )
        calls: list[str] = []
        payloads = [
            {
                "data": {
                    "count": 12,
                    "positions": [_position(index) for index in range(1, 11)],
                }
            },
            {
                "data": {
                    "count": 12,
                    "positions": [_position(11), _position(12, country="IN")],
                }
            },
        ]

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            calls.append(url)
            return payloads[len(calls) - 1]

        with patch("app.connectors.microsoft_careers.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 11)
        self.assertEqual(result.requests_made, 2)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.expected_pages, 2)
        self.assertIsNone(result.partial_reason)
        self.assertIn("filter_career_discipline=Software+Engineering", calls[0])
        self.assertIn("start=10", calls[1])
        first_job = result.jobs[0]
        self.assertEqual(first_job.connector_key, "microsoft-careers:microsoft.com")
        self.assertEqual(first_job.company, "Microsoft")
        self.assertEqual(first_job.remote_policy, "Remote")
        self.assertEqual(first_job.published_at.tzinfo, timezone.utc)
        self.assertTrue(first_job.apply_url.startswith("https://apply.careers.microsoft.com/careers/job/"))

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = MicrosoftCareersJobConnector(
            site=MicrosoftCareerSite(
                company="Microsoft",
                domain="microsoft.com",
                country="US",
                role_families=("Platform Engineering",),
                max_pages_per_run=1,
            ),
            connector_settings=ConnectorSettings(
                request_timeout_seconds=20,
                retry_attempts=3,
                base_retry_delay_seconds=0.5,
                max_retry_delay_seconds=8.0,
                backoff_multiplier=2.0,
                rate_limit_per_minute=12,
            ),
        )
        payload = {
            "data": {
                "count": 30,
                "positions": [_position(index) for index in range(1, 11)],
            }
        }

        with patch("app.connectors.microsoft_careers.request_json", return_value=payload):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 10)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 3)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
