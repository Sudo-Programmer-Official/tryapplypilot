from __future__ import annotations

import unittest

from app.connectors.base import NormalizedJobRecord
from app.config import get_settings
from app.domain import OnboardingStatus, UserAccount
from app.user_matching import (
    build_user_matching_settings,
    filter_reason_for_user,
    minimum_match_score,
)


def _user(
    *,
    locations: list[str],
    companies: list[str],
    roles: list[str],
    threshold: int = 90,
    country: str = "US",
    skills: list[str] | None = None,
    profile: dict[str, object] | None = None,
) -> UserAccount:
    return UserAccount(
        id="user-1",
        email="user@example.com",
        role="user",
        full_name="Abhishek",
        country=country,
        profile=profile or {},
        preferences={
            "country": country,
            "locations": locations,
            "preferred_companies": companies,
            "preferred_roles": roles,
            "work_arrangements": ["Remote", "Hybrid"],
            "experience_levels": ["Senior", "Staff"],
            "minimum_match_score": threshold,
            "freshness_hours": 6,
            "skills": skills if skills is not None else ["Python", "Distributed Systems"],
        },
        onboarding=OnboardingStatus(progress_percent=0, steps=[]),
    )


def _job(
    *,
    company: str,
    location: str,
    remote_policy: str = "Hybrid",
    title: str = "Senior Software Engineer",
    description_text: str = "Backend distributed systems role with Python and AI agents.",
) -> NormalizedJobRecord:
    return NormalizedJobRecord(
        connector_key="greenhouse:databricks",
        external_job_id="job-1",
        company=company,
        title=title,
        location=location,
        remote_policy=remote_policy,
        published_at=None,
        apply_url="https://example.com/apply",
        description_text=description_text,
        job_fingerprint="fingerprint-1",
        raw_payload={},
    )


class UserMatchingTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_user_matching_settings_use_user_threshold(self) -> None:
        settings = get_settings()
        user = _user(locations=["Seattle"], companies=["Microsoft"], roles=["Senior Software Engineer"], threshold=82)
        matching_settings = build_user_matching_settings(settings, user)
        self.assertEqual(minimum_match_score(user, settings), 82)
        self.assertEqual(matching_settings.radar.minimum_match_score, 82)
        self.assertEqual(matching_settings.radar.selected_country, "US")

    def test_filter_reason_for_user_respects_company_and_location(self) -> None:
        settings = get_settings()
        user = _user(locations=["Seattle", "Remote"], companies=["Microsoft"], roles=["Senior Software Engineer"])
        self.assertIsNone(filter_reason_for_user(_job(company="Microsoft", location="Seattle, WA"), user, settings))
        self.assertEqual(filter_reason_for_user(_job(company="Databricks", location="Seattle, WA"), user, settings), "company")
        self.assertEqual(filter_reason_for_user(_job(company="Microsoft", location="New York, NY"), user, settings), "location")

    def test_filter_reason_for_user_respects_selected_country(self) -> None:
        settings = get_settings()
        user = _user(
            locations=[],
            companies=["Microsoft"],
            roles=["Senior Software Engineer"],
            country="US",
        )
        self.assertEqual(filter_reason_for_user(_job(company="Microsoft", location="Toronto, Canada"), user, settings), "country")

    def test_filter_reason_for_user_uses_resume_metadata_as_domain_signal(self) -> None:
        settings = get_settings()
        user = _user(
            locations=["Remote"],
            companies=["Microsoft"],
            roles=["AI Engineer"],
            skills=[],
            profile={
                "resume_uploaded": True,
                "resume_skill_keywords": ["Distributed Systems", "Python"],
                "resume_library": [{"role_focus": "AI Platform"}],
            },
        )
        self.assertIsNone(
            filter_reason_for_user(
                _job(
                    company="Microsoft",
                    location="Remote - US",
                    title="Senior Software Engineer",
                ),
                user,
                settings,
            )
        )

    def test_filter_reason_for_user_rejects_out_of_domain_roles(self) -> None:
        settings = get_settings()
        user = _user(
            locations=["Seattle"],
            companies=["Microsoft"],
            roles=["AI Engineer"],
            skills=["LLMs"],
        )
        self.assertEqual(
            filter_reason_for_user(
                _job(
                    company="Microsoft",
                    location="Seattle, WA",
                    title="Senior Software Engineer",
                    description_text="Build internal billing dashboards and finance reporting workflows in Java.",
                ),
                user,
                settings,
            ),
            "domain_interest",
        )

    def test_filter_reason_for_user_rejects_missing_required_preferences(self) -> None:
        settings = get_settings()
        user = _user(locations=["Seattle"], companies=[], roles=[], skills=[])
        self.assertEqual(
            filter_reason_for_user(_job(company="Microsoft", location="Seattle, WA"), user, settings),
            "preferred_companies_missing",
        )


if __name__ == "__main__":
    unittest.main()
