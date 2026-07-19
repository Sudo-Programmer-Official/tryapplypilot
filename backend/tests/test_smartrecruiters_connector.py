from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.smartrecruiters import SmartRecruitersJobConnector, build_smartrecruiters_site


def _posting(
    *,
    posting_id: str,
    title: str,
    location_country: str = "us",
    full_location: str = "Seattle, Washington, United States",
    remote: bool = False,
    hybrid: bool = True,
) -> dict[str, object]:
    return {
        "id": posting_id,
        "name": title,
        "uuid": f"uuid-{posting_id}",
        "company": {"identifier": "ServiceNow", "name": "ServiceNow"},
        "releasedDate": "2026-07-19T10:16:34.476Z",
        "location": {
            "city": "Seattle",
            "country": location_country,
            "remote": remote,
            "hybrid": hybrid,
            "fullLocation": full_location,
        },
        "jobAdId": f"ad-{posting_id}",
        "defaultJobAd": True,
        "refNumber": "JB0073193",
        "typeOfEmployment": {"id": "permanent", "label": "Full-time"},
        "customField": [
            {"fieldLabel": "Country/Region", "valueId": location_country, "valueLabel": "United States"},
        ],
        "ref": f"https://api.smartrecruiters.com/v1/companies/ServiceNow/postings/{posting_id}",
    }


def _detail(
    *,
    posting_id: str,
    apply_url: str,
    title: str = "Senior Platform Engineer",
) -> dict[str, object]:
    return {
        "id": posting_id,
        "name": title,
        "applyUrl": apply_url,
        "postingUrl": apply_url.replace("?oga=true", ""),
        "jobAd": {
            "sections": {
                "jobDescription": {
                    "title": "Job Description",
                    "text": "<p>Build distributed systems and AI platform tooling.</p>",
                },
                "qualifications": {
                    "title": "Qualifications",
                    "text": "<ul><li>Python</li><li>Kubernetes</li></ul>",
                },
            }
        },
    }


class SmartRecruitersConnectorTests(unittest.TestCase):
    def _connector(self, *, max_pages_per_run: int = 2, max_detail_requests_per_run: int = 2) -> SmartRecruitersJobConnector:
        return SmartRecruitersJobConnector(
            site=build_smartrecruiters_site(
                company="ServiceNow",
                career_url="https://careers.smartrecruiters.com/ServiceNow",
                external_identifier="ServiceNow",
                country="US",
                role_families=("Platform Engineering",),
                page_size=1,
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

    def test_collect_paginates_and_filters_country(self) -> None:
        connector = self._connector(max_pages_per_run=2, max_detail_requests_per_run=2)
        calls: list[str] = []

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            calls.append(url)
            if url.endswith("/744000138497339"):
                return _detail(
                    posting_id="744000138497339",
                    apply_url="https://jobs.smartrecruiters.com/ServiceNow/744000138497339-senior-platform-engineer?oga=true",
                )
            if url.endswith("/744000138497340"):
                return _detail(
                    posting_id="744000138497340",
                    apply_url="https://jobs.smartrecruiters.com/ServiceNow/744000138497340-security-engineer?oga=true",
                    title="Security Engineer",
                )
            if "offset=0" in url:
                return {"offset": 0, "limit": 1, "totalFound": 2, "content": [_posting(posting_id="744000138497339", title="Senior Platform Engineer", remote=True, hybrid=False)]}
            return {"offset": 1, "limit": 1, "totalFound": 2, "content": [_posting(posting_id="744000138497340", title="Security Engineer", location_country="in", full_location="Bengaluru, Karnataka, India", remote=False, hybrid=False)]}

        with patch("app.connectors.smartrecruiters.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 4)
        self.assertEqual(result.pages_scanned, 2)
        self.assertEqual(result.expected_pages, 2)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        self.assertTrue(any("offset=1" in url for url in calls))
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "smartrecruiters:ServiceNow")
        self.assertEqual(job.company, "ServiceNow")
        self.assertEqual(job.title, "Senior Platform Engineer")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertIn("distributed systems", job.description_text.casefold())
        self.assertEqual(
            job.apply_url,
            "https://jobs.smartrecruiters.com/ServiceNow/744000138497339-senior-platform-engineer?oga=true",
        )
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = self._connector(max_pages_per_run=1, max_detail_requests_per_run=1)
        payload = {"offset": 0, "limit": 1, "totalFound": 3, "content": [_posting(posting_id="744000138497339", title="Senior Platform Engineer")]}

        def _request_json(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if url.endswith("/744000138497339"):
                return _detail(
                    posting_id="744000138497339",
                    apply_url="https://jobs.smartrecruiters.com/ServiceNow/744000138497339-senior-platform-engineer?oga=true",
                )
            return payload

        with patch("app.connectors.smartrecruiters.request_json", side_effect=_request_json):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 3)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
