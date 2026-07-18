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


def _user(*, role: str = "user", telegram_chat_id: str | None = None, resume_uploaded: bool = False) -> UserAccount:
    return UserAccount(
        id="user-1",
        email="user@example.com",
        role=role,  # type: ignore[arg-type]
        full_name="Abhishek",
        telegram_chat_id=telegram_chat_id,
        country="US",
        profile={
            "resume_uploaded": resume_uploaded,
        },
        preferences={
            "country": "US",
            "locations": ["Seattle"],
            "preferred_companies": ["Microsoft"],
            "preferred_roles": ["Backend Engineer"],
        },
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

    def test_role_allows_respects_hierarchy(self) -> None:
        self.assertTrue(role_allows("super_admin", "admin"))
        self.assertTrue(role_allows("admin", "user"))
        self.assertFalse(role_allows("user", "admin"))


if __name__ == "__main__":
    unittest.main()
