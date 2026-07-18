from __future__ import annotations

import unittest

from app.job_metadata import (
    country_display,
    freshness_label,
    infer_country_code,
    matches_country_preference,
    recommendation_label,
)


class JobMetadataTests(unittest.TestCase):
    def test_infer_country_code_recognizes_us_location(self) -> None:
        self.assertEqual(infer_country_code("San Francisco, CA"), "US")

    def test_infer_country_code_recognizes_explicit_other_country(self) -> None:
        self.assertEqual(infer_country_code("Tokyo, Japan"), "OTHER")
        self.assertEqual(
            infer_country_code(
                "Berlin, Germany",
                "If access to export-controlled technology is required, a U.S. government license may be needed.",
            ),
            "OTHER",
        )

    def test_country_preference_allows_unknown_but_rejects_explicit_mismatch(self) -> None:
        self.assertTrue(matches_country_preference(None, "US"))
        self.assertFalse(matches_country_preference("OTHER", "US"))

    def test_freshness_label_is_human_friendly(self) -> None:
        self.assertIn("Just posted", freshness_label(18, alert_freshness_hours=6, dashboard_freshness_hours=24))
        self.assertIn("2h 41m", freshness_label(161, alert_freshness_hours=6, dashboard_freshness_hours=24))

    def test_recommendation_label_maps_decision(self) -> None:
        self.assertEqual(recommendation_label("APPLY_NOW"), "Apply Immediately")
        self.assertEqual(recommendation_label("REVIEW"), "Review Before Applying")
        self.assertEqual(recommendation_label("IGNORE"), "Skip")

    def test_country_display_includes_flag(self) -> None:
        self.assertEqual(country_display("US"), "🇺🇸 United States")


if __name__ == "__main__":
    unittest.main()
