from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.comeet import ComeetJobConnector, build_comeet_site


def _position(
    *,
    uid: str,
    title: str,
    location_name: str,
    country: str,
    workplace_type: str = "Remote",
    updated_at: str = "2026-07-19T16:19:06Z",
    description: str = "Build backend platform services.",
) -> dict[str, object]:
    return {
        "uid": uid,
        "name": title,
        "department": "Engineering",
        "workplace_type": workplace_type,
        "employment_type": "Full-time",
        "experience_level": "Intermediate",
        "time_updated": updated_at,
        "company_name": "Sandbox Company",
        "url_active_page": f"https://www.comeet.com/jobs/sandbox/E5.007/{uid.lower()}/{uid}",
        "url_comeet_hosted_page": f"https://www.comeet.com/jobs/sandbox/E5.007/{uid.lower()}/{uid}",
        "position_url": f"https://www.comeet.co/careers-api/2.0/company/E5.007/positions/{uid}?token=5E7236A0BCE5E7295111B55E70BCE",
        "location": {
            "name": location_name,
            "country": country,
            "city": "Seattle" if country == "US" else "Bengaluru",
            "state": "WA" if country == "US" else "KA",
            "is_remote": workplace_type.casefold() == "remote",
        },
        "categories": [
            {"name": "Team", "value": "Platform", "order": 1},
        ],
        "details": [
            {"name": "Description", "value": f"<p>{description}</p>", "order": 1},
            {"name": "Requirements", "value": "<ul><li>Python</li></ul>", "order": 2},
        ],
    }


class ComeetConnectorTests(unittest.TestCase):
    def _connector(self) -> ComeetJobConnector:
        return ComeetJobConnector(
            site=build_comeet_site(
                company="Sandbox Company",
                career_url="https://www.comeet.co/careers-api/2.0/company/E5.007/positions?token=5E7236A0BCE5E7295111B55E70BCE",
                external_identifier="E5.007:5E7236A0BCE5E7295111B55E70BCE",
                country="US",
                role_families=("Platform Engineering",),
            ),
            connector_settings=ConnectorSettings(
                request_timeout_seconds=20,
                retry_attempts=3,
                base_retry_delay_seconds=0.5,
                max_retry_delay_seconds=8.0,
                backoff_multiplier=2.0,
                rate_limit_per_minute=8,
            ),
        )

    def test_build_site_can_parse_api_url_and_token(self) -> None:
        site = build_comeet_site(
            company="Sandbox Company",
            career_url="https://www.comeet.co/careers-api/2.0/company/E5.007/positions?token=5E7236A0BCE5E7295111B55E70BCE",
            external_identifier="",
            country="US",
            role_families=("Platform Engineering",),
        )

        self.assertEqual(site.identifier, "E5.007")
        self.assertEqual(site.company_uid, "E5.007")
        self.assertEqual(site.token, "5E7236A0BCE5E7295111B55E70BCE")
        self.assertIn("/company/E5.007/positions", site.positions_url)
        self.assertIn("details=true", site.positions_url)

    def test_collect_normalizes_comeet_jobs_and_filters_country(self) -> None:
        connector = self._connector()
        payload = [
            _position(
                uid="E8.91F",
                title="Senior Platform Engineer",
                location_name="Seattle, WA",
                country="US",
                workplace_type="Remote",
            ),
            _position(
                uid="E8.91G",
                title="Platform Engineer",
                location_name="Bengaluru, KA",
                country="IN",
                workplace_type="On-site",
                description="India-only platform role.",
            ),
        ]

        with patch("app.connectors.comeet.request_json", return_value=payload):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 1)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "comeet:E5.007")
        self.assertEqual(job.company, "Sandbox Company")
        self.assertEqual(job.title, "Senior Platform Engineer")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(job.apply_url, "https://www.comeet.com/jobs/sandbox/E5.007/e8.91f/E8.91F")
        self.assertIn("build backend platform services", job.description_text.casefold())
        self.assertIn("team: platform", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
