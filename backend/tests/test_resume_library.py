from __future__ import annotations

import unittest

from app.resume_library import _extract_skills, _preview, _role_focus


class ResumeLibraryTests(unittest.TestCase):
    def test_extract_skills_detects_core_terms(self) -> None:
        text = "Senior backend engineer working on Python, FastAPI, PostgreSQL, distributed systems, AI agents, and Kubernetes."
        skills = _extract_skills(text)
        self.assertIn("Python", skills)
        self.assertIn("FastAPI", skills)
        self.assertIn("Distributed Systems", skills)
        self.assertIn("Agents", skills)

    def test_role_focus_prefers_ai_platform_when_ai_signals_exist(self) -> None:
        skills = ["Python", "AI", "LLMs", "ML Platform"]
        self.assertEqual(_role_focus(skills, "Generative AI platform"), "AI Platform")

    def test_preview_compacts_whitespace_and_truncates(self) -> None:
        preview = _preview("alpha   beta\n gamma\t delta", limit=12)
        self.assertEqual(preview, "alpha beta…")


if __name__ == "__main__":
    unittest.main()
