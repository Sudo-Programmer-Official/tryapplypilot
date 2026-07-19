from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.workday import WorkdayJobConnector, build_workday_career_site


def _posting(path: str, *, title: str, location: str, posted_on: str = "Posted Today") -> dict[str, object]:
    return {
        "title": title,
        "externalPath": path,
        "locationsText": location,
        "postedOn": posted_on,
        "bulletFields": ["JR123456"],
    }


def _detail_payload(
    *,
    title: str,
    location: str,
    description: str,
    external_url: str,
    country_code: str,
    start_date: str = "2026-07-19",
) -> dict[str, object]:
    return {
        "jobPostingInfo": {
            "title": title,
            "jobDescription": description,
            "location": location,
            "postedOn": "Posted Today",
            "startDate": start_date,
            "timeType": "Full time",
            "externalUrl": external_url,
        },
        "jobRequisitionLocation": {
            "descriptor": location,
            "country": {
                "alpha2Code": country_code,
                "descriptor": country_code,
            },
        },
    }


class WorkdayConnectorTests(unittest.TestCase):
    def _connector(self, *, max_pages_per_run: int = 3, max_detail_requests_per_run: int = 2) -> WorkdayJobConnector:
        return WorkdayJobConnector(
            site=build_workday_career_site(
                company="NVIDIA",
                career_url="https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite",
                external_identifier="nvidia/NVIDIAExternalCareerSite",
                country="US",
                role_families=("Platform Engineering",),
                max_pages_per_run=max_pages_per_run,
                max_detail_requests_per_run=max_detail_requests_per_run,
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

    def test_collect_normalizes_workday_jobs_and_filters_country(self) -> None:
        connector = self._connector()
        calls: list[tuple[str, str]] = []

        def _request_json(*args, **kwargs):
            method = str(args[0])
            url = str(kwargs.get("url") or args[1])
            calls.append((method, url))
            if method == "POST":
                return {
                    "total": 2,
                    "jobPostings": [
                        _posting(
                            "/job/Remote-USA/Principal-Platform-Engineer_JR123456",
                            title="Principal Platform Engineer",
                            location="Remote, United States",
                        ),
                        _posting(
                            "/job/Israel-Tel-Aviv/Senior-Power-and-Performance-Architect_JR2018842-1",
                            title="Senior Power and Performance Architect",
                            location="Israel, Tel Aviv",
                        ),
                    ],
                }
            if "Principal-Platform-Engineer" in url:
                return _detail_payload(
                    title="Principal Platform Engineer",
                    location="Remote, United States",
                    description="<p>Build distributed AI platform infrastructure.</p>",
                    external_url="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/Remote-USA/Principal-Platform-Engineer_JR123456",
                    country_code="US",
                )
            return _detail_payload(
                title="Senior Power and Performance Architect",
                location="Israel, Tel Aviv",
                description="<p>International role.</p>",
                external_url="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/Israel-Tel-Aviv/Senior-Power-and-Performance-Architect_JR2018842-1",
                country_code="IL",
            )

        with patch("app.connectors.workday.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 3)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 1)
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "workday:nvidia/NVIDIAExternalCareerSite")
        self.assertEqual(job.external_job_id, "job/Remote-USA/Principal-Platform-Engineer_JR123456")
        self.assertEqual(job.company, "NVIDIA")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(
            job.apply_url,
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/Remote-USA/Principal-Platform-Engineer_JR123456",
        )
        self.assertIn("distributed ai platform infrastructure", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)
        self.assertEqual(calls[0][0], "POST")
        self.assertTrue(any(method == "GET" for method, _ in calls))

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = self._connector(max_pages_per_run=1, max_detail_requests_per_run=1)

        def _request_json(*args, **kwargs):
            method = str(args[0])
            url = str(kwargs.get("url") or args[1])
            if method == "GET":
                return _detail_payload(
                    title="Principal Platform Engineer",
                    location="Remote, United States",
                    description="<p>Build distributed systems.</p>",
                    external_url="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/Remote-USA/Principal-Platform-Engineer_JR123456",
                    country_code="US",
                )
            return {
                "total": 45,
                "jobPostings": [
                    _posting(
                        f"/job/Remote-USA/Principal-Platform-Engineer_JR12345{index}",
                        title=f"Principal Platform Engineer {index}",
                        location="Remote, United States",
                        posted_on="Posted 2 Days Ago",
                    )
                    for index in range(20)
                ],
            }

        with patch("app.connectors.workday.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 20)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 3)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
