from __future__ import annotations

from datetime import timezone
import unittest
from urllib.parse import parse_qs, urlsplit
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
                max_detail_requests_per_run=2,
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
        search_payloads = [
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
        search_index = {"value": 0}

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            calls.append(url)
            if "position_details" in url:
                query = parse_qs(urlsplit(url).query)
                position_id = query["position_id"][0]
                return {
                    "data": {
                        "jobDescription": f"<p>Detailed backend platform description for role {position_id}</p>",
                        "publicUrl": f"https://careers.microsoft.com/us/en/job/{position_id}",
                    }
                }
            payload = search_payloads[search_index["value"]]
            search_index["value"] += 1
            return payload

        with patch("app.connectors.microsoft_careers.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 11)
        self.assertEqual(result.requests_made, 4)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.expected_pages, 2)
        self.assertIsNone(result.partial_reason)
        self.assertIn("filter_career_discipline=Software+Engineering", calls[0])
        self.assertTrue(any("start=10" in call for call in calls))
        self.assertEqual(sum(1 for call in calls if "position_details" in call), 2)
        first_job = result.jobs[0]
        self.assertEqual(first_job.connector_key, "microsoft-careers:microsoft.com")
        self.assertEqual(first_job.company, "Microsoft")
        self.assertEqual(first_job.remote_policy, "Remote")
        self.assertEqual(first_job.published_at.tzinfo, timezone.utc)
        self.assertEqual(first_job.apply_url, "https://careers.microsoft.com/us/en/job/1")
        self.assertIn("Detailed backend platform description", first_job.description_text)

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = MicrosoftCareersJobConnector(
            site=MicrosoftCareerSite(
                company="Microsoft",
                domain="microsoft.com",
                country="US",
                role_families=("Platform Engineering",),
                max_pages_per_run=1,
                max_detail_requests_per_run=1,
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

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if "position_details" in url:
                return {
                    "data": {
                        "jobDescription": "<p>Detailed description</p>",
                        "publicUrl": "https://careers.microsoft.com/us/en/job/1",
                    }
                }
            return payload

        with patch("app.connectors.microsoft_careers.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 10)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 3)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
