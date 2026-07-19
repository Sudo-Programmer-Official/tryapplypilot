from __future__ import annotations

from datetime import timezone
import json
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.amazon_jobs import AmazonJobsConnector, build_amazon_career_site


def _location(
    *,
    normalized_location: str,
    type: str,
    country_iso2a: str = "US",
    country_iso3a: str = "USA",
) -> str:
    return json.dumps(
        {
            "normalizedLocation": normalized_location,
            "location": normalized_location,
            "countryIso2a": country_iso2a,
            "countryIso3a": country_iso3a,
            "type": type,
        },
        separators=(",", ":"),
    )


def _job(
    *,
    job_id: str,
    title: str,
    apply_url: str,
    company: str = "Amazon Development Center U.S., Inc.",
    location: str = "Seattle, Washington, USA",
    type: str = "REMOTE",
    country_code: str = "USA",
    description: str = "Build distributed systems for large-scale search infrastructure.",
) -> dict[str, object]:
    return {
        "id": f"uuid-{job_id}",
        "id_icims": job_id,
        "title": title,
        "company_name": company,
        "country_code": country_code,
        "description": description,
        "basic_qualifications": "- Python\n- Distributed systems",
        "preferred_qualifications": "- AI infrastructure",
        "job_category": "Software Development",
        "job_schedule_type": "full-time",
        "job_path": f"/en/jobs/{job_id}/{title.casefold().replace(' ', '-')}",
        "location": f"US, WA, {location.split(',')[0]}",
        "locations": [
            _location(
                normalized_location=location,
                type=type,
                country_iso2a="US" if country_code == "USA" else "IN",
                country_iso3a=country_code,
            )
        ],
        "normalized_location": location,
        "posted_date": "July 18, 2026",
        "updated_time": "1 day",
        "url_next_step": apply_url,
        "business_category": "aws",
    }


class AmazonJobsConnectorTests(unittest.TestCase):
    def _connector(self, *, max_pages_per_run: int = 3, page_size: int = 1) -> AmazonJobsConnector:
        return AmazonJobsConnector(
            site=build_amazon_career_site(
                company="Amazon",
                career_url="https://www.amazon.jobs/en/search?base_query=software+development+engineer&country=USA&sort=recent",
                external_identifier="amazon",
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
                rate_limit_per_minute=12,
            ),
        )

    def test_collect_paginates_amazon_jobs_and_filters_country(self) -> None:
        connector = self._connector(max_pages_per_run=3, page_size=1)
        urls: list[str] = []
        payloads = [
            {
                "hits": 2,
                "jobs": [
                    _job(
                        job_id="10477971",
                        title="Software Development Engineer",
                        apply_url="https://account.amazon.jobs/jobs/10477971/apply",
                        type="REMOTE",
                    )
                ],
            },
            {
                "hits": 2,
                "jobs": [
                    _job(
                        job_id="10477972",
                        title="Senior Software Engineer",
                        apply_url="https://account.amazon.jobs/jobs/10477972/apply",
                        location="Bengaluru, Karnataka, India",
                        type="ONSITE",
                        country_code="IND",
                        description="India-only role.",
                    )
                ],
            },
        ]

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            urls.append(url)
            return payloads[len(urls) - 1]

        with patch("app.connectors.amazon_jobs.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.expected_pages, 2)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        self.assertTrue(any("offset=1" in url for url in urls))
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "amazon-jobs:amazon")
        self.assertEqual(job.company, "Amazon Development Center U.S., Inc.")
        self.assertEqual(job.title, "Software Development Engineer")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(job.apply_url, "https://account.amazon.jobs/jobs/10477971/apply")
        self.assertIn("distributed systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = self._connector(max_pages_per_run=1, page_size=1)
        payload = {
            "hits": 3,
            "jobs": [
                _job(
                    job_id="10477971",
                    title="Software Development Engineer",
                    apply_url="https://account.amazon.jobs/jobs/10477971/apply",
                )
            ],
        }

        with patch("app.connectors.amazon_jobs.request_json", return_value=payload):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 3)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
