from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.successfactors import SuccessFactorsJobConnector, build_successfactors_site


def _search_html(*, total: int, pages: int, rows: list[tuple[str, str, str]]) -> str:
    rendered_rows = "\n".join(
        f'<tr><td><a href="{href}">{title}</a></td><td>{location}</td></tr>'
        for href, title, location in rows
    )
    return f"""
    <html><body>
    <div>Results 1 – 25 of {total} Page 1 of {pages}</div>
    <table id="searchresults">
      {rendered_rows}
    </table>
    </body></html>
    """


def _detail_html(*, title: str, apply_id: str, location: str, posted_date: str, summary: str) -> str:
    return f"""
    <html><body>
    <a href="/talentcommunity/apply/{apply_id}/?locale=en_US">Apply now »</a>
    <h1>{title}</h1>
    <div>Posted Date: {posted_date}</div>
    <div>Location: {location}</div>
    <div>#LI-Hybrid {summary}</div>
    <div>Find similar jobs:</div>
    </body></html>
    """


class SuccessFactorsConnectorTests(unittest.TestCase):
    def _connector(self, *, max_pages_per_run: int = 2, max_detail_requests_per_run: int = 4) -> SuccessFactorsJobConnector:
        return SuccessFactorsJobConnector(
            site=build_successfactors_site(
                company="SAP",
                career_url="https://jobs.sap.com/search/?sortColumn=referencedate&sortDirection=desc",
                external_identifier="sap",
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
                rate_limit_per_minute=8,
            ),
        )

    def test_collect_normalizes_successfactors_jobs_and_filters_country(self) -> None:
        connector = self._connector(max_pages_per_run=2, max_detail_requests_per_run=4)
        list_html = _search_html(
            total=2,
            pages=1,
            rows=[
                (
                    "/job/Newtown-Square-SAP-NS2-AI-Consultant-Specialist/1400000001/",
                    "SAP NS2 AI Consultant Specialist",
                    "Newtown Square, PA, US, 19073",
                ),
                (
                    "/job/Bengaluru-Backend-Engineer/1400000002/",
                    "Backend Engineer",
                    "Bengaluru, IN, 560001",
                ),
            ],
        )
        details = {
            "1400000001": _detail_html(
                title="SAP NS2 AI Consultant Specialist",
                apply_id="1400000001",
                location="Newtown Square, PA, US, 19073",
                posted_date="Jul 19, 2026",
                summary="Build AI consulting systems and platform integrations.",
            ),
            "1400000002": _detail_html(
                title="Backend Engineer",
                apply_id="1400000002",
                location="Bengaluru, IN, 560001",
                posted_date="Jul 18, 2026",
                summary="India-only backend role.",
            ),
        }

        def _request_text(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            for job_id, detail_html in details.items():
                if job_id in url:
                    return detail_html
            return list_html

        with patch("app.connectors.successfactors.request_text", side_effect=_request_text):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 3)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 1)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "successfactors:sap")
        self.assertEqual(job.company, "SAP")
        self.assertEqual(job.title, "SAP NS2 AI Consultant Specialist")
        self.assertEqual(job.remote_policy, "Hybrid")
        self.assertEqual(
            job.apply_url,
            "https://jobs.sap.com/talentcommunity/apply/1400000001/?locale=en_US",
        )
        self.assertIn("ai consulting systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)

    def test_collect_marks_partial_when_page_limit_is_reached(self) -> None:
        connector = self._connector(max_pages_per_run=1, max_detail_requests_per_run=2)
        list_html = _search_html(
            total=26,
            pages=2,
            rows=[
                (
                    "/job/Newtown-Square-SAP-NS2-AI-Consultant-Specialist/1400000001/",
                    "SAP NS2 AI Consultant Specialist",
                    "Newtown Square, PA, US, 19073",
                ),
            ],
        )
        detail_html = _detail_html(
            title="SAP NS2 AI Consultant Specialist",
            apply_id="1400000001",
            location="Newtown Square, PA, US, 19073",
            posted_date="Jul 19, 2026",
            summary="Build AI consulting systems and platform integrations.",
        )

        def _request_text(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if "/job/" in url:
                return detail_html
            return list_html

        with patch("app.connectors.successfactors.request_text", side_effect=_request_text):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 2)
        self.assertEqual(result.pages_scanned, 1)
        self.assertEqual(result.expected_pages, 2)
        self.assertFalse(result.exhausted)
        self.assertEqual(result.partial_reason, "page_limit_reached")


if __name__ == "__main__":
    unittest.main()
