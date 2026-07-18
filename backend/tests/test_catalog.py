from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.catalog import _persist_company, build_effective_app_settings, build_scout_settings
from app.company_catalog_defaults import (
    ENABLED_COMPANY_NAMES,
    RECOMMENDED_COMPANY_DEFAULTS,
    build_recommended_company_preferences,
    recommended_company_catalog_fingerprint,
)
from app.config import get_settings
from app.domain import CompanyPreference


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    async def test_seed_catalog_exposes_watchlists_and_companies(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = await build_scout_settings()
        self.assertEqual(len(settings.companies), len(RECOMMENDED_COMPANY_DEFAULTS))
        self.assertGreater(len(settings.watchlists), 0)
        self.assertEqual(settings.watchlists[0].name, "Priority Teams")
        enabled_names = {company.company for company in settings.companies if company.enabled}
        self.assertEqual(enabled_names, ENABLED_COMPANY_NAMES)

    async def test_effective_settings_builds_runtime_companies_from_catalog(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            effective = await build_effective_app_settings()
        runtime_companies = {company.company: company for company in effective.radar.companies}
        self.assertIn("Databricks", runtime_companies)
        self.assertEqual(runtime_companies["Databricks"].connector, "greenhouse")
        self.assertEqual(runtime_companies["Databricks"].external_identifier, "databricks")
        self.assertEqual(effective.radar.selected_country, "US")

    async def test_effective_settings_derive_enabled_connectors_from_catalog_not_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "JOB_RADAR_RUNTIME_MODE": "seed",
                "JOB_RADAR_ENABLED_CONNECTORS": "workday,lever",
            },
            clear=True,
        ):
            get_settings.cache_clear()
            effective = await build_effective_app_settings()
        self.assertIn("greenhouse", effective.radar.enabled_connectors)
        self.assertNotIn("microsoft-careers", effective.radar.enabled_connectors)
        self.assertNotIn("company-api", effective.radar.enabled_connectors)
        self.assertNotIn("google-careers", effective.radar.enabled_connectors)
        self.assertNotIn("workday", effective.radar.enabled_connectors)

    def test_recommended_catalog_fingerprint_is_stable_and_live_defaults_are_greenhouse(self) -> None:
        first = recommended_company_catalog_fingerprint()
        second = recommended_company_catalog_fingerprint()
        self.assertEqual(first, second)
        enabled_companies = [company for company in build_recommended_company_preferences() if company.enabled]
        self.assertGreater(len(enabled_companies), 0)
        self.assertEqual({company.connector for company in enabled_companies}, {"greenhouse", "lever"})

    async def test_persist_company_preserves_existing_company_id_for_same_name(self) -> None:
        class FakeConn:
            async def fetchval(self, query: str, *args: object) -> str | None:
                self.last_fetch = (query, args)
                return "existing-company-id"

            async def execute(self, query: str, *args: object) -> None:
                self.last_execute = (query, args)

        company = CompanyPreference(
            id="openai",
            company="OpenAI",
            enabled=True,
            tier=1,
            priority=1,
            connector="greenhouse",
            poll_interval_minutes=5,
            country="US",
            career_url="https://job-boards.greenhouse.io/openai",
            external_identifier="openai",
            role_families=["AI Platform", "Backend Engineering"],
        )

        persisted = await _persist_company(FakeConn(), company)
        self.assertEqual(persisted.id, "existing-company-id")


if __name__ == "__main__":
    unittest.main()
