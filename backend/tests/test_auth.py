from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.auth import (
    create_access_token,
    create_telegram_connect_token,
    decode_token,
    extract_telegram_start_token,
    hash_password,
    onboarding_status_for_user,
    role_allows,
    verify_password,
)
from app.config import get_settings
from app.domain import OnboardingStatus, UserAccount


def _user(
    *,
    role: str = "user",
    telegram_chat_id: str | None = None,
    resume_uploaded: bool = False,
    preferences: dict[str, object] | None = None,
) -> UserAccount:
    resolved_preferences = {
        "country": "US",
        "locations": [],
        "preferred_companies": ["Microsoft"],
        "preferred_roles": [],
    }
    if preferences:
        resolved_preferences.update(preferences)
    return UserAccount(
        id="user-1",
        email="user@example.com",
        role=role,  # type: ignore[arg-type]
        full_name="Abhishek",
        telegram_chat_id=telegram_chat_id,
        country="US",
        profile={
            "resume_uploaded": resume_uploaded,
            "resume_skill_keywords": ["Python", "Distributed Systems"] if resume_uploaded else [],
            "resume_library": [{"role_focus": "Platform"}] if resume_uploaded else [],
        },
        preferences=resolved_preferences,
        onboarding=OnboardingStatus(progress_percent=0, steps=[]),
    )


class AuthTests(unittest.TestCase):
    TEST_SECRET = "unit-test-secret-with-32-bytes-minimum"

    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_password_hash_roundtrip(self) -> None:
        password_hash = hash_password("VerySecret123!")
        self.assertTrue(verify_password("VerySecret123!", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_access_token_roundtrip(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_JWT_SECRET": self.TEST_SECRET}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            token, _ = create_access_token(_user(role="admin"), settings)
            payload = decode_token(token, expected_type="access", settings=settings)
        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["role"], "admin")

    def test_telegram_connect_token_roundtrip(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_JWT_SECRET": self.TEST_SECRET}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
            token, _ = create_telegram_connect_token(_user(role="user"), settings)
            payload = decode_token(token, expected_type="telegram_link", settings=settings)
        self.assertEqual(payload["sub"], "user-1")
        self.assertEqual(payload["email"], "user@example.com")

    def test_extract_telegram_start_token(self) -> None:
        self.assertEqual(extract_telegram_start_token("/start abc123"), "abc123")
        self.assertEqual(extract_telegram_start_token("/start@jobradar_agent_bot abc123"), "abc123")
        self.assertIsNone(extract_telegram_start_token("/help"))
        self.assertIsNone(extract_telegram_start_token(None))

    def test_onboarding_progress_reflects_resume_and_telegram(self) -> None:
        onboarding = onboarding_status_for_user(_user(telegram_chat_id="123", resume_uploaded=True))
        self.assertEqual(onboarding.progress_percent, 100)
        self.assertTrue(all(step.completed for step in onboarding.steps))

    def test_onboarding_preferences_can_complete_from_resume_signals(self) -> None:
        onboarding = onboarding_status_for_user(_user(resume_uploaded=True))
        preferences_step = next(step for step in onboarding.steps if step.id == "preferences_set")
        self.assertTrue(preferences_step.completed)

    def test_onboarding_preferences_can_complete_from_company_priorities(self) -> None:
        onboarding = onboarding_status_for_user(
            _user(
                preferences={
                    "preferred_companies": [],
                    "company_priorities": {"OpenAI": "dream", "Oracle": "hidden"},
                    "skills": ["Python"],
                }
            )
        )
        preferences_step = next(step for step in onboarding.steps if step.id == "preferences_set")
        self.assertTrue(preferences_step.completed)

    def test_onboarding_preferences_require_visible_company_scope(self) -> None:
        onboarding = onboarding_status_for_user(
            _user(
                preferences={
                    "preferred_companies": [],
                    "company_priorities": {"Oracle": "hidden"},
                    "skills": ["Python"],
                }
            )
        )
        preferences_step = next(step for step in onboarding.steps if step.id == "preferences_set")
        self.assertFalse(preferences_step.completed)

    def test_role_allows_respects_hierarchy(self) -> None:
        self.assertTrue(role_allows("super_admin", "admin"))
        self.assertTrue(role_allows("admin", "user"))
        self.assertFalse(role_allows("user", "admin"))


if __name__ == "__main__":
    unittest.main()
