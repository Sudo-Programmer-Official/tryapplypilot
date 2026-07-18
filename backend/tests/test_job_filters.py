from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.config import get_settings
from app.connectors.base import NormalizedJobRecord
from app.job_filters import filter_reason


def _job(*, title: str, remote_policy: str = "Hybrid") -> NormalizedJobRecord:
    return NormalizedJobRecord(
        connector_key="greenhouse:databricks",
        external_job_id="job-1",
        company="Databricks",
        title=title,
        location="San Francisco, CA",
        remote_policy=remote_policy,
        published_at=None,
        apply_url="https://boards.greenhouse.io/databricks/jobs/1",
        description_text="Distributed systems and backend platform work.",
        job_fingerprint="fingerprint",
        raw_payload={},
    )


class JobFilterTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_relevant_backend_role_passes_filters(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertIsNone(filter_reason(_job(title="Senior Backend Engineer"), settings))

    def test_onsite_role_is_filtered_when_onsite_disabled(self) -> None:
        with patch.dict(
            os.environ,
            {
                "JOB_RADAR_RUNTIME_MODE": "seed",
                "JOB_RADAR_WORK_ARRANGEMENTS": "Remote,Hybrid",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertEqual(filter_reason(_job(title="Senior Backend Engineer", remote_policy="Onsite"), settings), "work_arrangement")

    def test_junior_role_is_filtered_by_experience_preferences(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertEqual(filter_reason(_job(title="Software Engineer Intern"), settings), "experience_level")

    def test_excluded_title_keyword_is_filtered_after_role_match(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertEqual(filter_reason(_job(title="Senior Software Engineer, Finance Systems"), settings), "excluded_keyword")


if __name__ == "__main__":
    unittest.main()
