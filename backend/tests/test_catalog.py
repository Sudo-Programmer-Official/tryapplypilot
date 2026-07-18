from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.catalog import build_effective_app_settings, build_scout_settings
from app.config import get_settings


class CatalogTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    async def test_seed_catalog_exposes_watchlists_and_companies(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            settings = await build_scout_settings()
        self.assertGreater(len(settings.companies), 20)
        self.assertGreater(len(settings.watchlists), 0)
        self.assertEqual(settings.watchlists[0].name, "Priority Teams")

    async def test_effective_settings_builds_greenhouse_boards_from_catalog(self) -> None:
        with patch.dict(os.environ, {"JOB_RADAR_RUNTIME_MODE": "seed"}, clear=True):
            get_settings.cache_clear()
            effective = await build_effective_app_settings()
        greenhouse_boards = {board.company: board.token for board in effective.radar.greenhouse_boards}
        self.assertIn("Databricks", greenhouse_boards)
        self.assertEqual(greenhouse_boards["Databricks"], "databricks")
        self.assertEqual(effective.radar.selected_country, "US")


if __name__ == "__main__":
    unittest.main()
