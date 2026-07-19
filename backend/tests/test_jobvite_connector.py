from __future__ import annotations

from datetime import timezone
import unittest
from unittest.mock import patch

from app.config import ConnectorSettings
from app.connectors.jobvite import JobviteJobConnector, build_jobvite_site

_LIST_HTML = """
<html>
  <body>
    <h3 class="h2">Engineering Platform</h3>
    <table class="jv-job-list">
      <tbody>
        <tr>
          <td class="jv-job-list-name">
            <a href="/progress/job/ojob123">Principal Software Engineer - Distributed Systems</a>
          </td>
          <td class="jv-job-list-location">
            Remote,
            United States
          </td>
        </tr>
        <tr>
          <td class="jv-job-list-name">
            <a href="/progress/job/ojob124">Senior Platform Engineer</a>
          </td>
          <td class="jv-job-list-location">
            Bengaluru,
            India
          </td>
        </tr>
      </tbody>
    </table>
  </body>
</html>
"""

_DETAIL_HTML = """
<html>
  <body>
    <script type="application/ld+json">
      {
        "@context": "http://schema.org",
        "@type": "JobPosting",
        "datePosted": "2026-07-18",
        "description": "<div><strong>Build AI platform services.</strong></div><div>Python and distributed systems.</div>",
        "industry": "Engineering Platform",
        "identifier": "ojob123",
        "title": "Principal Software Engineer - Distributed Systems"
      }
    </script>
    <a class="jv-button jv-button-primary jv-button-apply" href="/progress/job/ojob123/apply">
      Apply
    </a>
  </body>
</html>
"""


class JobviteConnectorTests(unittest.TestCase):
    def _connector(self) -> JobviteJobConnector:
        return JobviteJobConnector(
            site=build_jobvite_site(
                company="Progress",
                career_url="https://jobs.jobvite.com/careers/progress/jobs",
                external_identifier="progress",
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

    def test_collect_parses_jobvite_list_and_detail_pages(self) -> None:
        connector = self._connector()
        urls: list[str] = []

        def _request_text(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            urls.append(url)
            if url.endswith("/jobs"):
                return _LIST_HTML
            return _DETAIL_HTML

        with patch("app.connectors.jobvite.request_text", side_effect=_request_text):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        self.assertEqual(result.requests_made, 3)
        self.assertEqual(result.pages_scanned, 1)
        self.assertTrue(result.exhausted)
        self.assertIsNone(result.partial_reason)
        self.assertTrue(any(url.endswith("/progress/job/ojob123") for url in urls))
        job = result.jobs[0]
        self.assertEqual(job.connector_key, "jobvite:progress")
        self.assertEqual(job.company, "Progress")
        self.assertEqual(job.title, "Principal Software Engineer - Distributed Systems")
        self.assertEqual(job.location, "Remote, United States")
        self.assertEqual(job.remote_policy, "Remote")
        self.assertEqual(job.apply_url, "https://jobs.jobvite.com/progress/job/ojob123/apply")
        self.assertIn("distributed systems", job.description_text.casefold())
        self.assertIsNotNone(job.published_at)
        self.assertEqual(job.published_at.tzinfo, timezone.utc)

    def test_collect_falls_back_when_detail_page_is_unavailable(self) -> None:
        connector = self._connector()

        def _request_text(*args, **kwargs):
            url = str(kwargs.get("url") or args[1])
            if url.endswith("/jobs"):
                return """
                <html><body>
                  <h3 class="h2">Engineering Platform</h3>
                  <table class="jv-job-list"><tbody>
                    <tr>
                      <td class="jv-job-list-name"><a href="/progress/job/ojob999">Platform Engineer</a></td>
                      <td class="jv-job-list-location">Remote, United States</td>
                    </tr>
                  </tbody></table>
                </body></html>
                """
            raise RuntimeError("detail unavailable")

        with patch("app.connectors.jobvite.request_text", side_effect=_request_text):
            result = connector.collect()

        self.assertEqual(len(result.jobs), 1)
        job = result.jobs[0]
        self.assertEqual(job.apply_url, "https://jobs.jobvite.com/progress/job/ojob999/apply")
        self.assertIsNone(job.published_at)
        self.assertIn("Engineering Platform", job.description_text)


if __name__ == "__main__":
    unittest.main()
