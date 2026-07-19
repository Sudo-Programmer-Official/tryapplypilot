from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.oracle_recruiting_cloud import OracleRecruitingCloudConnector, build_oracle_recruiting_cloud_site


def _job(
    *,
    job_id: str,
    title: str,
    location: str,
    country: str,
    workplace_type: str = "Remote",
    posted_date: str = "2026-07-19",
    description: str = "Build distributed cloud systems.",
) -> dict[str, object]:
    return {
        "Id": job_id,
        "Title": title,
        "PostedDate": posted_date,
        "PrimaryLocation": location,
        "PrimaryLocationCountry": country,
        "WorkplaceType": workplace_type,
        "ShortDescriptionStr": description,
        "ExternalResponsibilitiesStr": "<p>Lead platform delivery.</p>",
        "ExternalQualificationsStr": "<p>Python and distributed systems.</p>",
    }


class OracleRecruitingCloudConnectorTests(unittest.TestCase):
    def _connector(self, *, max_pages_per_run: int = 2) -> OracleRecruitingCloudConnector:
        return OracleRecruitingCloudConnector(
            site=build_oracle_recruiting_cloud_site(
                company="Oracle",
                career_url="https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs",
                external_identifier="CX_45001",
                country="US",
                role_families=("Platform Engineering",),
                max_pages_per_run=max_pages_per_run,
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

    def test_collect_normalizes_oracle_jobs_and_filters_country(self) -> None:
        connector = self._connector(max_pages_per_run=2)
        calls: list[str] = []
        page_payloads = [
            {
                "items": [
                    {
                        "TotalJobsCount": 26,
                        "requisitionList": [
                            _job(
                                job_id="333254",
                                title="Principal Data Center E2E Project Manager",
                                location="Abilene, TX, United States",
                                country="United States",
                            )
                        ],
                    }
                ]
            },
            {
                "items": [
                    {
                        "TotalJobsCount": 26,
                        "requisitionList": [
                            _job(
                                job_id="333255",
                                title="Principal Platform Engineer",
                                location="Bengaluru, India",
                                country="India",
                            )
                        ],
                    }
                ]
            },
        ]

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            calls.append(url)
            return page_payloads[len(calls) - 1]

        with patch("app.connectors.oracle_recruiting_cloud.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.expected_pages, 2)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        self.assertTrue(any("offset=25" in url for url in calls))
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "oracle-recruiting-cloud:CX_45001")
        self.assertEqual(job.company, "Oracle")
        self.assertEqual(job.title, "Principal Data Center E2E Project Manager")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(
            job.apply_url,
            "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/333254/",
        )
        self.assertIn("distributed cloud systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = self._connector(max_pages_per_run=1)
        payload = {
            "items": [
                {
                    "TotalJobsCount": 26,
                    "requisitionList": [
                        _job(
                            job_id="333254",
                            title="Principal Data Center E2E Project Manager",
                            location="Abilene, TX, United States",
                            country="United States",
                        )
                    ],
                }
            ]
        }

        with patch("app.connectors.oracle_recruiting_cloud.request_json", return_value=payload):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 2)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
