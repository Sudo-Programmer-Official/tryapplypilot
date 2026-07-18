from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from app.domain import CompanyPreference, OnboardingStatus, UserAccount
from app.main import companies_catalog, current_user_companies


def _user(*, role: str) -> UserAccount:
    return UserAccount(
        id="user-1",
        email="user@example.com",
        role=role,  # type: ignore[arg-type]
        full_name="Abhishek",
        telegram_chat_id=None,
        country="US",
        profile={},
        preferences={},
        onboarding=OnboardingStatus(progress_percent=0, steps=[]),
    )


class MainCatalogAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_catalog_only_returns_enabled_companies_for_regular_user(self) -> None:
        companies = [
            CompanyPreference(id="enabled-1", company="Databricks", enabled=True),
            CompanyPreference(id="disabled-1", company="Google", enabled=False),
        ]
        with patch("app.main.list_catalog_companies", AsyncMock(return_value=companies)):
            payload = await current_user_companies(_user(role="user"))
        self.assertEqual([item["company"] for item in payload["items"]], ["Databricks"])

    async def test_admin_catalog_returns_full_catalog(self) -> None:
        companies = [
            CompanyPreference(id="enabled-1", company="Databricks", enabled=True),
            CompanyPreference(id="disabled-1", company="Google", enabled=False),
        ]
        with patch("app.main.list_catalog_companies", AsyncMock(return_value=companies)):
            payload = await companies_catalog(_user(role="admin"))
        self.assertEqual([item["company"] for item in payload["items"]], ["Databricks", "Google"])


if __name__ == "__main__":
    unittest.main()
