from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.icims import ICIMSJobConnector, build_icims_career_site


def _job(
    *,
    slug: str,
    title: str,
    apply_url: str,
    location_name: str = "United States (Remote)",
    full_location: str = "United States",
    country_code: str = "US",
    tags2: list[str] | None = None,
    categories: list[dict[str, str]] | None = None,
    description: str = "Build distributed systems and AI platform services.",
) -> dict[str, object]:
    return {
        "data": {
            "slug": slug,
            "req_id": slug,
            "title": title,
            "description": description,
            "responsibilities": "<ul><li>Build backend platforms.</li></ul>",
            "qualifications": "<ul><li>Python</li><li>Distributed Systems</li></ul>",
            "employment_type": "FULL_TIME",
            "location_name": location_name,
            "full_location": full_location,
            "short_location": full_location,
            "country": "United States" if country_code == "US" else "India",
            "country_code": country_code,
            "categories": categories or [{"name": "Engineering"}],
            "category": [" Engineering "],
            "tags1": ["Experienced"],
            "tags2": tags2 or ["Remote"],
            "posted_date": "2026-07-18T15:54:00+0000",
            "update_date": "2026-07-19T12:00:00+0000",
            "apply_url": apply_url,
            "meta_data": {"canonical_url": f"https://careers.icims.com/jobs/{slug}?lang=en-us"},
        }
    }


class ICIMSConnectorTests(unittest.TestCase):
    def _connector(self, *, page_size: int = 1, max_pages_per_run: int = 2) -> ICIMSJobConnector:
        return ICIMSJobConnector(
            site=build_icims_career_site(
                company="iCIMS",
                career_url="https://careers.icims.com/careers-home",
                external_identifier="careers.icims.com",
                country="US",
                role_families=("Platform Engineering",),
                page_size=page_size,
                max_pages_per_run=max_pages_per_run,
            ),
            connector_settings=ConnectorSettings(
                request_timeout_seconds=20,
                retry_attempts=3,
                base_retry_delay_seconds=0.5,
                max_retry_delay_seconds=8.0,
                backoff_multiplier=2.0,
                rate_limit_per_minute=10,
            ),
        )

    def test_collect_paginates_icims_jobs_and_filters_country(self) -> None:
        connector = self._connector(page_size=1, max_pages_per_run=2)
        urls: list[str] = []
        payloads = [
            {
                "count": 2,
                "totalCount": 2,
                "jobs": [
                    _job(
                        slug="6504",
                        title="Senior Platform Engineer",
                        apply_url="https://careers-customer0.icims.com/jobs/6504/login",
                        tags2=["Remote"],
                    )
                ],
            },
            {
                "count": 2,
                "totalCount": 2,
                "jobs": [
                    _job(
                        slug="6505",
                        title="Platform Engineer, India",
                        apply_url="https://careers-customer0.icims.com/jobs/6505/login",
                        location_name="Bengaluru, Karnataka, India",
                        full_location="India",
                        country_code="IN",
                        tags2=["Onsite"],
                        description="India-only role.",
                    )
                ],
            },
        ]

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            urls.append(url)
            return payloads[len(urls) - 1]

        with patch("app.connectors.icims.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.expected_pages, 2)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        self.assertTrue(any("page=2" in url for url in urls))
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "icims:careers.icims.com")
        self.assertEqual(job.company, "iCIMS")
        self.assertEqual(job.title, "Senior Platform Engineer")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(job.apply_url, "https://careers-customer0.icims.com/jobs/6504/login")
        self.assertIn("distributed systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = self._connector(page_size=1, max_pages_per_run=1)
        payload = {
            "count": 3,
            "totalCount": 3,
            "jobs": [
                _job(
                    slug="6504",
                    title="Senior Platform Engineer",
                    apply_url="https://careers-customer0.icims.com/jobs/6504/login",
                )
            ],
        }

        with patch("app.connectors.icims.request_json", return_value=payload):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 3)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
