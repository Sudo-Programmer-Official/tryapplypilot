from __future__ import annotations

import importlib.util
import sys
import types
import unittest

if "asyncpg" not in sys.modules and importlib.util.find_spec("asyncpg") is None:
    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "jwt" not in sys.modules and importlib.util.find_spec("jwt") is None:
    jwt_stub = types.ModuleType("jwt")

    class _InvalidTokenError(Exception):
        pass

    jwt_stub.InvalidTokenError = _InvalidTokenError
    jwt_stub.encode = lambda payload, secret, algorithm=None: "stub-token"
    jwt_stub.decode = lambda token, secret, algorithms=None, issuer=None: {"type": "access"}
    sys.modules["jwt"] = jwt_stub

from app.knowledge_platform import (
    InMemoryKnowledgePlatformStore,
    KnowledgeChangeConflictError,
    KnowledgeEvidenceError,
    KnowledgePlatformService,
    build_knowledge_platform_client,
    compute_knowledge_completeness,
    extract_resume_items,
    ingest_resume_into_knowledge_platform,
)
from app.domain import KnowledgeEntity, ResumeAsset


class KnowledgePlatformTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.audit_events: list[dict[str, object]] = []

        async def audit_recorder(**payload):
            self.audit_events.append(payload)
            return None

        self.service = KnowledgePlatformService(
            store=InMemoryKnowledgePlatformStore(),
            audit_recorder=audit_recorder,
        )

    async def test_stage_and_approve_change_creates_canonical_entity(self) -> None:
        evidence = await self.service.add_evidence(
            "user-1",
            source_type="resume",
            source_id="resume-1",
            excerpt="Built a Kubernetes-based scheduler handling distributed workloads.",
            metadata={"resume_id": "resume-1"},
        )

        version = await self.service.stage_change(
            "user-1",
            entity_type="project",
            canonical_name="Scheduler Platform",
            new_content={
                "summary": "Built a distributed scheduler platform.",
                "technologies": ["Python", "Kubernetes"],
            },
            source="resume_import",
            reason="Create canonical project from resume evidence.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
            confidence=0.95,
            agent_name="resume-import",
        )

        profile_before = await self.service.read_profile("user-1")
        self.assertEqual(profile_before, {})

        entity = await self.service.approve_change(version.id, reviewed_by_user_id="admin-1")
        profile_after = await self.service.read_profile("user-1")

        self.assertEqual(entity.canonical_name, "Scheduler Platform")
        self.assertEqual(entity.version, 1)
        self.assertEqual(entity.status, "approved")
        self.assertIn("project", profile_after)
        self.assertEqual(profile_after["project"][0].evidence_ids, [evidence.id])
        self.assertEqual(
            [event["event_type"] for event in self.audit_events],
            ["knowledge.change_staged", "knowledge.change_approved"],
        )

    async def test_reject_change_preserves_previous_approved_version(self) -> None:
        evidence = await self.service.add_evidence(
            "user-1",
            source_type="project",
            source_id="project-1",
            excerpt="Implemented appointment and payment APIs in Python.",
        )
        initial_version = await self.service.stage_change(
            "user-1",
            entity_type="project",
            canonical_name="Payments API",
            new_content={"summary": "Built payment APIs.", "technologies": ["Python"]},
            source="manual_import",
            reason="Initial canonical project.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
        )
        approved = await self.service.approve_change(initial_version.id, reviewed_by_user_id="admin-1")

        followup_evidence = await self.service.add_evidence(
            "user-1",
            source_type="conversation",
            source_id="fact-1",
            excerpt="Mentioned healthcare platform work without enough verified context.",
        )
        followup_version = await self.service.stage_change(
            "user-1",
            entity_type="project",
            canonical_name="Payments API",
            new_content={"summary": "Built healthcare payment APIs.", "technologies": ["Python"]},
            source="conversation_fact",
            reason="Attempt to add healthcare domain context.",
            evidence_ids=[followup_evidence.id],
            actor_user_id="system",
        )
        rejected = await self.service.reject_change(
            followup_version.id,
            reviewed_by_user_id="admin-2",
            review_notes="Healthcare context is not yet sufficiently verified.",
        )
        profile = await self.service.read_profile("user-1")

        self.assertEqual(approved.content["summary"], "Built payment APIs.")
        self.assertEqual(profile["project"][0].content["summary"], "Built payment APIs.")
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.reviewed_by_user_id, "admin-2")

    async def _stage_payments_change(self, summary: str) -> str:
        evidence = await self.service.add_evidence(
            "user-1",
            source_type="project",
            source_id=f"project-{summary}",
            excerpt=summary,
        )
        version = await self.service.stage_change(
            "user-1",
            entity_type="project",
            canonical_name="Payments API",
            new_content={"summary": summary},
            source="manual_import",
            reason=f"Set summary to {summary}.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
        )
        return version.id

    async def test_reviewed_changes_cannot_be_reviewed_again(self) -> None:
        approved_id = await self._stage_payments_change("Built payment APIs.")
        await self.service.approve_change(approved_id, reviewed_by_user_id="admin-1")
        rejected_id = await self._stage_payments_change("Unverified healthcare claim.")
        await self.service.reject_change(rejected_id, reviewed_by_user_id="admin-1")

        with self.assertRaises(KnowledgeChangeConflictError):
            await self.service.approve_change(rejected_id, reviewed_by_user_id="admin-1")
        with self.assertRaises(KnowledgeChangeConflictError):
            await self.service.reject_change(approved_id, reviewed_by_user_id="admin-1")
        with self.assertRaises(KnowledgeChangeConflictError):
            await self.service.approve_change(approved_id, reviewed_by_user_id="admin-1")

        profile = await self.service.read_profile("user-1")
        self.assertEqual(profile["project"][0].content["summary"], "Built payment APIs.")
        self.assertEqual(profile["project"][0].version, 1)

    async def test_approving_superseded_change_does_not_roll_back_entity(self) -> None:
        older_id = await self._stage_payments_change("Older summary.")
        newer_id = await self._stage_payments_change("Newer summary.")
        await self.service.approve_change(newer_id, reviewed_by_user_id="admin-1")

        with self.assertRaises(KnowledgeChangeConflictError):
            await self.service.approve_change(older_id, reviewed_by_user_id="admin-1")

        profile = await self.service.read_profile("user-1")
        self.assertEqual(profile["project"][0].content["summary"], "Newer summary.")
        self.assertEqual(profile["project"][0].version, 2)

    async def test_query_helpers_and_evidence_retrieval_work_from_canonical_store(self) -> None:
        skill_evidence = await self.service.add_evidence(
            "user-9",
            source_type="profile",
            source_id="profile-1",
            excerpt="Primary languages include Python and Go.",
        )
        project_evidence = await self.service.add_evidence(
            "user-9",
            source_type="resume",
            source_id="resume-9",
            excerpt="Built distributed systems on Kubernetes for internal platforms.",
        )

        skill_version = await self.service.stage_change(
            "user-9",
            entity_type="skill",
            canonical_name="Python",
            new_content={"level": "expert", "years": 8},
            source="profile_import",
            reason="Canonical skill from profile.",
            evidence_ids=[skill_evidence.id],
            actor_user_id="system",
        )
        project_version = await self.service.stage_change(
            "user-9",
            entity_type="project",
            canonical_name="Platform Scheduler",
            new_content={"summary": "Built Kubernetes-based distributed scheduling services."},
            source="resume_import",
            reason="Canonical project from resume.",
            evidence_ids=[project_evidence.id],
            actor_user_id="system",
        )
        await self.service.approve_change(skill_version.id, reviewed_by_user_id="admin-1")
        await self.service.approve_change(project_version.id, reviewed_by_user_id="admin-1")

        project_matches = await self.service.search_projects("user-9", "kubernetes")
        skill_matches = await self.service.search_skills("user-9", "python")
        evidence_matches = await self.service.retrieve_evidence("user-9", query="distributed")

        self.assertEqual(project_matches[0].canonical_name, "Platform Scheduler")
        self.assertEqual(skill_matches[0].canonical_name, "Python")
        self.assertEqual(evidence_matches[0].source_id, "resume-9")

    async def test_stage_change_blocks_missing_evidence(self) -> None:
        with self.assertRaises(KnowledgeEvidenceError):
            await self.service.stage_change(
                "user-1",
                entity_type="achievement",
                canonical_name="Scaled platform",
                new_content={"summary": "Scaled the platform to 90,000 jobs."},
                source="manual_entry",
                reason="Unsupported fact.",
                evidence_ids=["missing-evidence-id"],
                actor_user_id="system",
            )

    async def test_resume_ingestion_extracts_canonical_entities_and_sections(self) -> None:
        resume = ResumeAsset(
            id="resume-1",
            user_id="user-77",
            display_name="Backend Resume",
            original_filename="backend.pdf",
            storage_path="/tmp/backend.pdf",
            mime_type="application/pdf",
            file_size_bytes=123,
            extracted_text_preview="Senior backend engineer working on Python, Kubernetes, and payments.",
            extracted_skills=["Python", "Kubernetes", "Backend"],
            role_focus="Backend",
            created_at="2026-07-20T00:00:00+00:00",
        )
        text = """
        Summary
        Senior backend engineer building payment systems.

        Experience
        Staff Software Engineer | Microsoft Corporation
        Built distributed payment services on Kubernetes with Python.
        Led platform migrations across internal teams.

        Projects
        Checkout Platform
        Built appointment and payment APIs in Python and gRPC.

        Skills
        Python, ReactJS, React.js, Kubernetes, Distributed Systems, TypeScript

        Education
        B.Tech in Computer Science
        """
        result = await ingest_resume_into_knowledge_platform(
            service=self.service,
            user_id="user-77",
            resume=resume,
            extracted_text=text,
            actor_user_id="user-77",
        )

        profile = await self.service.get_user_profile("user-77")
        tech_names = {entity.canonical_name for entity in profile.get("technology", [])}

        self.assertTrue(any(section.name == "experience" for section in result.parsed_sections))
        self.assertIn("React", tech_names)
        self.assertIn("Python", tech_names)
        self.assertIn("TypeScript", tech_names)
        self.assertNotIn("ReactJS", tech_names)
        self.assertIn("project", profile)
        self.assertIn("experience", profile)
        self.assertIn("education", profile)

    async def test_resume_reingestion_stages_updates_instead_of_overwriting(self) -> None:
        resume = ResumeAsset(
            id="resume-2",
            user_id="user-88",
            display_name="Platform Resume",
            original_filename="platform.pdf",
            storage_path="/tmp/platform.pdf",
            mime_type="application/pdf",
            file_size_bytes=123,
            extracted_text_preview="Platform engineer.",
            extracted_skills=["Python", "Kubernetes"],
            role_focus="Platform",
            created_at="2026-07-20T00:00:00+00:00",
        )
        first_text = """
        Experience
        Payments Platform
        Built payment APIs in Python.

        Skills
        Python, Kubernetes
        """
        second_text = """
        Experience
        Payments Platform
        Built healthcare payment APIs in Python with Kubernetes.

        Skills
        Python
        """
        await ingest_resume_into_knowledge_platform(
            service=self.service,
            user_id="user-88",
            resume=resume,
            extracted_text=first_text,
            actor_user_id="user-88",
        )
        result = await ingest_resume_into_knowledge_platform(
            service=self.service,
            user_id="user-88",
            resume=resume,
            extracted_text=second_text,
            actor_user_id="user-88",
        )
        profile = await self.service.get_user_profile("user-88")

        self.assertEqual(profile["experience"][0].content["text"], "Payments Platform\nBuilt payment APIs in Python.")
        self.assertGreaterEqual(len(result.staged_versions), 1)
        self.assertTrue(any(version.status == "suggested" for version in result.staged_versions))

    async def test_completeness_flags_missing_areas(self) -> None:
        resume = ResumeAsset(
            id="resume-3",
            user_id="user-99",
            display_name="Minimal Resume",
            original_filename="minimal.pdf",
            storage_path="/tmp/minimal.pdf",
            mime_type="application/pdf",
            file_size_bytes=10,
            extracted_text_preview="Python engineer.",
            extracted_skills=["Python"],
            role_focus="Backend",
            created_at="2026-07-20T00:00:00+00:00",
        )
        result = await ingest_resume_into_knowledge_platform(
            service=self.service,
            user_id="user-99",
            resume=resume,
            extracted_text="Skills\nPython",
            actor_user_id="user-99",
        )

        self.assertEqual(result.completeness["project"]["status"], "missing")
        self.assertEqual(result.completeness["technology"]["status"], "ready")
        self.assertTrue(result.completeness["project"]["suggested_action"])
        self.assertIn("overall_score", result.completeness_report)
        self.assertIn("ai_experience", result.completeness_report["areas"])

    async def test_entity_linking_registers_aliases_and_normalizes_canonical_names(self) -> None:
        evidence = await self.service.add_evidence(
            "user-link",
            source_type="resume",
            source_id="resume-link",
            excerpt="Built ReactJS interfaces for internal tools.",
        )
        version = await self.service.stage_change(
            "user-link",
            entity_type="technology",
            canonical_name="ReactJS",
            new_content={"label": "ReactJS"},
            source="resume_import",
            reason="Canonical technology from resume.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
        )
        entity = await self.service.approve_change(version.id, reviewed_by_user_id="admin-1")
        aliases = await self.service.list_aliases("user-link", entity_type="technology")

        self.assertEqual(entity.canonical_name, "React")
        self.assertTrue(any(alias.alias_value == "ReactJS" and alias.canonical_name == "React" for alias in aliases))

    async def test_query_engine_returns_projects_evidence_and_completeness(self) -> None:
        resume = ResumeAsset(
            id="resume-query",
            user_id="user-query",
            display_name="Query Resume",
            original_filename="query.pdf",
            storage_path="/tmp/query.pdf",
            mime_type="application/pdf",
            file_size_bytes=99,
            extracted_text_preview="Backend and AI platform engineer.",
            extracted_skills=["Python", "Kubernetes", "AI"],
            role_focus="Platform",
            created_at="2026-07-20T00:00:00+00:00",
        )
        text = """
        Experience
        Staff Engineer | Microsoft Corp.
        Built cloud payment systems on AWS and Kubernetes from 2022 to 2025.

        Projects
        AI Scheduling Platform
        Designed a backend orchestration service for 90000 jobs using Python and Kubernetes.

        Skills
        Python, Kubernetes, Backend, AI
        """
        await ingest_resume_into_knowledge_platform(
            service=self.service,
            user_id="user-query",
            resume=resume,
            extracted_text=text,
            actor_user_id="user-query",
        )

        projects = await self.service.find_projects_by_technology("user-query", "K8s")
        cloud = await self.service.find_cloud_experience("user-query")
        resume_evidence = await self.service.find_resume_evidence("user-query", query="90000")
        completeness = await self.service.get_profile_completeness("user-query")

        self.assertTrue(any(project.canonical_name == "AI Scheduling Platform" for project in projects))
        self.assertGreaterEqual(len(cloud), 1)
        self.assertEqual(resume_evidence[0].source_type, "resume")
        self.assertIn("overall_score", completeness)
        self.assertIn("architecture", completeness["areas"])
        metrics = await self.service.get_metrics("user-query")
        self.assertEqual(metrics["schema_version"], 1)
        self.assertIn("timeline_events", metrics)

    async def test_health_checks_flag_duplicates_orphans_and_missing_provenance(self) -> None:
        orphaned = await self.service.add_evidence(
            "user-health",
            source_type="conversation",
            source_id="fact-health",
            excerpt="Mentioned unsupported achievement with no linked entity.",
        )
        await self.service.store.save_entity(
            KnowledgeEntity(
                id="entity-react",
                user_id="user-health",
                entity_type="technology",
                canonical_name="React",
                content={"label": "React"},
                source="manual_import",
                confidence=1.0,
                evidence_ids=[],
                version=1,
                status="approved",
                created_at="2026-07-20T00:00:00+00:00",
                updated_at="2026-07-20T00:00:00+00:00",
            )
        )
        await self.service.store.save_entity(
            KnowledgeEntity(
                id="entity-reactjs",
                user_id="user-health",
                entity_type="technology",
                canonical_name="ReactJS",
                content={"label": "ReactJS"},
                source="manual_import",
                confidence=1.0,
                evidence_ids=[],
                version=1,
                status="approved",
                created_at="2026-07-20T00:00:00+00:00",
                updated_at="2026-07-20T00:00:00+00:00",
            )
        )

        report = await self.service.run_health_checks("user-health")

        self.assertEqual(orphaned.source_type, "conversation")
        self.assertEqual(report["status"], "critical")
        self.assertGreaterEqual(report["summary"]["duplicate_entities"], 1)
        self.assertGreaterEqual(report["summary"]["orphaned_evidence"], 1)
        self.assertGreaterEqual(report["summary"]["missing_provenance"], 1)

    async def test_timeline_and_sdk_expose_stable_consumption_surface(self) -> None:
        evidence = await self.service.add_evidence(
            "user-sdk",
            source_type="resume",
            source_id="resume-sdk",
            excerpt="Built Kubernetes backend systems.",
        )
        version = await self.service.stage_change(
            "user-sdk",
            entity_type="project",
            canonical_name="Platform Engine",
            new_content={"summary": "Built Kubernetes backend systems."},
            source="resume_import",
            reason="Canonical project from resume.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
        )
        entity = await self.service.approve_change(version.id, reviewed_by_user_id="admin-1")
        client = build_knowledge_platform_client()
        object.__setattr__(client, "service", self.service)

        timeline = await client.get_timeline("user-sdk")
        evidence_rows = await client.find_evidence("user-sdk", entity_id=entity.id)
        schema_info = await client.get_schema_info()

        self.assertTrue(any(item.event_type == "EvidenceAdded" for item in timeline))
        self.assertTrue(any(item.event_type == "KnowledgeUpdated" for item in timeline))
        self.assertEqual(evidence_rows[0].id, evidence.id)
        self.assertEqual(schema_info["version"], 1)



class ProfileKnowledgeSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_sync_failure_does_not_fail_the_profile_save(self) -> None:
        from unittest.mock import AsyncMock, patch

        from app.config import get_settings
        from app.domain import OnboardingStatus, UserAccount
        from app.user_accounts import _sync_profile_to_knowledge_platform

        user = UserAccount(
            id="user-1",
            email="user@example.com",
            role="user",
            full_name="Demo User",
            onboarding=OnboardingStatus(progress_percent=0, steps=[]),
        )
        failing_sync = AsyncMock(side_effect=RuntimeError("knowledge store unavailable"))
        with patch("app.knowledge_platform.sync_profile_snapshot_to_knowledge_platform", failing_sync), patch(
            "app.knowledge_platform.build_knowledge_platform_service",
            return_value=object(),
        ), self.assertLogs("app.user_accounts", level="ERROR") as logs:
            await _sync_profile_to_knowledge_platform(user, get_settings())

        failing_sync.assert_awaited_once()
        self.assertIn("user-1", logs.output[0])



class _FakeReviewConnection:
    def __init__(self, *, current_version: int, version_still_suggested: bool) -> None:
        self.current_version = current_version
        self.version_still_suggested = version_still_suggested
        self.in_transaction = False
        self.transaction_rolled_back = False
        self.statements: list[tuple[str, bool]] = []

    def transaction(self):
        conn = self

        class _Transaction:
            async def __aenter__(self_inner):
                conn.in_transaction = True

            async def __aexit__(self_inner, exc_type, exc, tb):
                conn.in_transaction = False
                conn.transaction_rolled_back = exc_type is not None
                return False

        return _Transaction()

    async def fetchval(self, query: str, *args):
        self.statements.append(("select_for_update", self.in_transaction))
        return self.current_version

    async def fetchrow(self, query: str, *args):
        if "UPDATE knowledge_entity_versions" in query:
            self.statements.append(("update_version", self.in_transaction))
            if not self.version_still_suggested:
                return None
            return {
                "version_id": args[0], "entity_id": "entity-1", "user_id": "user-1", "version_number": 2,
                "status": args[1], "source": "manual", "reason": "", "actor_user_id": None,
                "reviewed_by_user_id": args[2], "agent_name": "", "confidence": 1.0, "evidence": "[]",
                "previous_content": "{}", "new_content": "{}", "created_at": None, "reviewed_at": None,
                "review_notes": args[4],
            }
        self.statements.append(("save_entity", self.in_transaction))
        return {
            "entity_id": args[0], "user_id": args[1], "entity_type": args[2], "canonical_name": args[3],
            "content": args[4], "source": args[6], "confidence": args[7], "evidence": args[8],
            "current_version": args[9], "approval_status": args[10], "created_at": None, "updated_at": None,
        }


class PostgresKnowledgeReviewTests(unittest.IsolatedAsyncioTestCase):
    def _version_and_entity(self):
        from app.domain import KnowledgeEntityVersion

        version = KnowledgeEntityVersion(
            id="version-2", entity_id="entity-1", user_id="user-1", version_number=2, status="approved",
            source="manual", reason="", reviewed_by_user_id="user-1",
        )
        entity = KnowledgeEntity(
            id="entity-1", user_id="user-1", entity_type="project", canonical_name="Payments API",
            content={"summary": "v2"}, version=2, status="approved",
        )
        return version, entity

    async def _review(self, conn):
        from contextlib import asynccontextmanager
        from unittest.mock import patch

        from app.knowledge_platform.store import PostgresKnowledgePlatformStore

        @asynccontextmanager
        async def fake_connection():
            yield conn

        version, entity = self._version_and_entity()
        with patch("app.knowledge_platform.store.connection", fake_connection):
            return await PostgresKnowledgePlatformStore().review_version(version, entity)

    async def test_approval_updates_version_and_entity_in_one_transaction(self) -> None:
        conn = _FakeReviewConnection(current_version=1, version_still_suggested=True)
        saved_version, saved_entity = await self._review(conn)

        self.assertEqual(saved_version.status, "approved")
        self.assertEqual(saved_entity.version, 2)
        self.assertEqual(
            conn.statements,
            [("select_for_update", True), ("update_version", True), ("save_entity", True)],
        )

    async def test_concurrently_reviewed_change_rolls_back_without_saving_entity(self) -> None:
        conn = _FakeReviewConnection(current_version=1, version_still_suggested=False)
        with self.assertRaises(KnowledgeChangeConflictError):
            await self._review(conn)

        self.assertTrue(conn.transaction_rolled_back)
        self.assertNotIn("save_entity", [name for name, _ in conn.statements])

    async def test_superseded_approval_is_refused_inside_the_transaction(self) -> None:
        conn = _FakeReviewConnection(current_version=3, version_still_suggested=True)
        with self.assertRaisesRegex(KnowledgeChangeConflictError, "superseded"):
            await self._review(conn)

        self.assertEqual(conn.statements, [("select_for_update", True)])
        self.assertTrue(conn.transaction_rolled_back)


if __name__ == "__main__":
    unittest.main()
