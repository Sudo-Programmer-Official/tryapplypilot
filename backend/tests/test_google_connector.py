from __future__ import annotations

from datetime import timezone
import json
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.google_careers import GoogleCareersJobConnector, build_google_career_site


def _job(
    *,
    job_id: str,
    title: str,
    apply_url: str,
    company: str = "Google",
    location_label: str = "Seattle, WA, USA",
    country_code: str = "US",
    description: str = "Build distributed systems for AI workloads.",
    responsibilities: str = "<ul><li>Build backend platforms.</li></ul>",
    qualifications: str = "<h3>Minimum qualifications:</h3><ul><li>Python</li></ul>",
) -> list[object]:
    return [
        job_id,
        title,
        apply_url,
        [None, responsibilities],
        [None, qualifications],
        "projects/gweb-careers-proto/company/google",
        None,
        company,
        "en-US",
        [[location_label, [location_label], "Seattle", "98101", "WA", country_code]],
        [None, description],
        [2],
        [1784200000, 0],
        [1784300000, 0],
        [1784300500, 0],
        [None, "The application window will remain open based on business needs."],
        None,
        None,
        [None, f"Preferred working location: <b>{location_label}</b>."],
        [None, qualifications],
        3,
    ]


def _html_for_jobs(jobs: list[list[object]], *, total: int, page_size: int) -> str:
    payload = json.dumps([jobs, None, total, page_size], separators=(",", ":"))
    return (
        "<html><head></head><body>"
        f"<script>AF_initDataCallback({{key: 'ds:1', hash: '2', data:{payload}, sideChannel: {{}}}});</script>"
        "</body></html>"
    )


class GoogleConnectorTests(unittest.TestCase):
    def _connector(self, *, max_pages_per_run: int = 3) -> GoogleCareersJobConnector:
        return GoogleCareersJobConnector(
            site=build_google_career_site(
                company="Google",
                career_url="https://www.google.com/about/careers/applications/jobs/results/?hl=en_US",
                external_identifier="google",
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
                rate_limit_per_minute=12,
            ),
        )

    def test_collect_paginates_google_jobs_and_filters_country(self) -> None:
        connector = self._connector(max_pages_per_run=3)
        page_calls: list[str] = []
        html_pages = [
            _html_for_jobs(
                [
                    _job(
                        job_id="job-1",
                        title="Senior Software Engineer, AI/ML",
                        apply_url="https://www.google.com/about/careers/applications/signin?jobId=job-1",
                        description="Remote eligible role building distributed systems for AI workloads.",
                    )
                ],
                total=2,
                page_size=1,
            ),
            _html_for_jobs(
                [
                    _job(
                        job_id="job-2",
                        title="Senior Applied AI Engineer",
                        apply_url="https://www.google.com/about/careers/applications/signin?jobId=job-2",
                        location_label="Bengaluru, Karnataka, India",
                        country_code="IN",
                        description="India-only role.",
                    )
                ],
                total=2,
                page_size=1,
            ),
        ]

        def _request_text(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            page_calls.append(url)
            return html_pages[len(page_calls) - 1]

        with patch("app.connectors.google_careers.request_text", side_effect=_request_text):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.expected_pages, 2)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        self.assertTrue(any("page=2" in url for url in page_calls))
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "google-careers:google")
        self.assertEqual(job.company, "Google")
        self.assertEqual(job.title, "Senior Software Engineer, AI/ML")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(job.apply_url, "https://www.google.com/about/careers/applications/signin?jobId=job-1")
        self.assertIn("distributed systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = self._connector(max_pages_per_run=1)
        html_page = _html_for_jobs(
            [
                _job(
                    job_id="job-1",
                    title="Senior Software Engineer, Search",
                    apply_url="https://www.google.com/about/careers/applications/signin?jobId=job-1",
                )
            ],
            total=3,
            page_size=1,
        )

        with patch("app.connectors.google_careers.request_text", return_value=html_page):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 1)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 3)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
