from __future__ import annotations

import unittest

from app.connectors.base import NormalizedJobRecord
from app.config import get_settings
from app.domain import OnboardingStatus, UserAccount
from app.user_matching import (
    build_user_profile_text,
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
    preferences: dict[str, object] | None = None,
) -> UserAccount:
    base_preferences: dict[str, object] = {
        "country": country,
        "locations": locations,
        "preferred_companies": companies,
        "preferred_roles": roles,
        "work_arrangements": ["Remote", "Hybrid"],
        "experience_levels": ["Senior", "Staff"],
        "minimum_match_score": threshold,
        "freshness_hours": 6,
        "skills": skills if skills is not None else ["Python", "Distributed Systems"],
    }
    if preferences:
        base_preferences.update(preferences)
    return UserAccount(
        id="user-1",
        email="user@example.com",
        role="user",
        full_name="Abhishek",
        country=country,
        profile=profile or {},
        preferences=base_preferences,
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

    def test_build_user_profile_text_uses_structured_preferences_and_resume_metadata(self) -> None:
        settings = get_settings()
        user = _user(
            locations=["Seattle", "Remote"],
            companies=["Microsoft", "OpenAI"],
            roles=["Senior Backend Engineer", "AI Platform Engineer"],
            skills=["Python", "FastAPI", "Distributed Systems"],
            profile={
                "years_of_experience": 7,
                "resume_uploaded": True,
                "resume_skill_keywords": ["RAG", "PostgreSQL", "Kubernetes"],
                "resume_library": [{"role_focus": "AI Platform"}],
                "linkedin_url": "https://linkedin.com/in/example",
            },
        )
        profile_text = build_user_profile_text(user, settings)
        self.assertIn("Preferred roles: Senior Backend Engineer, AI Platform Engineer.", profile_text)
        self.assertIn("Preferred companies: Microsoft, OpenAI.", profile_text)
        self.assertIn("Preferred locations: Seattle, Remote.", profile_text)
        self.assertIn("Core skills: Python, FastAPI, Distributed Systems.", profile_text)
        self.assertIn("Resume skill signals: RAG, PostgreSQL, Kubernetes.", profile_text)
        self.assertIn("Resume role focus: AI Platform.", profile_text)
        self.assertIn("Years of experience: 7.", profile_text)

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

    def test_company_priorities_drive_visible_company_scope(self) -> None:
        settings = get_settings()
        user = _user(
            locations=["Remote"],
            companies=[],
            roles=["AI Engineer"],
            preferences={
                "company_priorities": {
                    "Microsoft": "dream",
                    "Databricks": "high",
                    "Oracle": "hidden",
                },
            },
        )
        self.assertIsNone(filter_reason_for_user(_job(company="Microsoft", location="Remote - US"), user, settings))
        self.assertEqual(filter_reason_for_user(_job(company="Oracle", location="Remote - US"), user, settings), "company")

    def test_filter_reason_for_user_respects_job_type_preferences(self) -> None:
        settings = get_settings()
        user = _user(
            locations=["Remote"],
            companies=["Microsoft"],
            roles=["Senior Software Engineer"],
            preferences={"job_types": ["full_time"]},
        )
        self.assertEqual(
            filter_reason_for_user(
                _job(
                    company="Microsoft",
                    location="Remote - US",
                    title="Contract Senior Software Engineer",
                    description_text="12 month contract backend role with Python.",
                ),
                user,
                settings,
            ),
            "job_type",
        )

    def test_filter_reason_for_user_respects_visa_constraints(self) -> None:
        settings = get_settings()
        user = _user(
            locations=["Remote"],
            companies=["Microsoft"],
            roles=["Senior Software Engineer"],
            preferences={"visa_status": "need_sponsorship"},
        )
        self.assertEqual(
            filter_reason_for_user(
                _job(
                    company="Microsoft",
                    location="Remote - US",
                    description_text="US citizenship required. Security clearance preferred for this backend platform role.",
                ),
                user,
                settings,
            ),
            "visa",
        )

    def test_filter_reason_for_user_respects_travel_preference(self) -> None:
        settings = get_settings()
        user = _user(
            locations=["Remote"],
            companies=["Microsoft"],
            roles=["Senior Software Engineer"],
            preferences={"travel_preference": "up_to_10"},
        )
        self.assertEqual(
            filter_reason_for_user(
                _job(
                    company="Microsoft",
                    location="Remote - US",
                    description_text="Platform engineering role with up to 25% travel across customer sites.",
                ),
                user,
                settings,
            ),
            "travel",
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
