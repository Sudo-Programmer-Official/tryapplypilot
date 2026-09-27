from __future__ import annotations

import sys
import types
import unittest

if "asyncpg" not in sys.modules:
    asyncpg_stub = types.ModuleType("asyncpg")
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "jwt" not in sys.modules:
    jwt_stub = types.ModuleType("jwt")

    class _InvalidTokenError(Exception):
        pass

    jwt_stub.InvalidTokenError = _InvalidTokenError
    jwt_stub.encode = lambda payload, secret, algorithm=None: "stub-token"
    jwt_stub.decode = lambda token, secret, algorithms=None, issuer=None: {"type": "access"}
    sys.modules["jwt"] = jwt_stub

from app.knowledge_platform import (
    InMemoryKnowledgePlatformStore,
    KnowledgePlatformClient,
    KnowledgePlatformService,
)
from app.profile_evolution import (
    InMemoryProfileEvolutionStore,
    ProfileEvolutionService,
    TOPIC_SCHEMAS,
    analyze_profile_gaps,
)


class ProfileEvolutionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        async def audit_recorder(**payload):
            return None

        self.knowledge_service = KnowledgePlatformService(
            store=InMemoryKnowledgePlatformStore(),
            audit_recorder=audit_recorder,
        )
        self.knowledge = KnowledgePlatformClient(service=self.knowledge_service)
        self.service = ProfileEvolutionService(
            store=InMemoryProfileEvolutionStore(),
            knowledge=self.knowledge,
        )

    async def _approve_entity(
        self,
        *,
        user_id: str = "user-1",
        entity_type: str,
        canonical_name: str,
        content: dict[str, object],
        excerpt: str,
        source_type: str = "resume",
    ) -> None:
        evidence = await self.knowledge_service.add_evidence(
            user_id,
            source_type=source_type,
            source_id=f"{entity_type}-{canonical_name.casefold().replace(' ', '-')}",
            excerpt=excerpt,
            metadata={"seed": True},
        )
        version = await self.knowledge_service.stage_change(
            user_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            new_content=content,
            source="test_seed",
            reason="Seed canonical knowledge for profile evolution tests.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
            confidence=0.95,
            agent_name="tests",
        )
        await self.knowledge_service.approve_change(version.id, reviewed_by_user_id="admin-1")

    async def test_gap_analysis_prioritizes_architecture_when_project_context_exists(self) -> None:
        await self._approve_entity(
            entity_type="project",
            canonical_name="Scheduler Platform",
            content={
                "summary": "Built a distributed scheduling platform for internal jobs.",
                "technologies": ["Python"],
            },
            excerpt="Built a distributed scheduling platform for internal jobs.",
        )
        await self._approve_entity(
            entity_type="experience",
            canonical_name="Staff Software Engineer",
            content={"company": "TryApplyPilot", "text": "Built backend systems."},
            excerpt="Built backend systems.",
        )
        await self._approve_entity(
            entity_type="leadership",
            canonical_name="Migration Lead",
            content={"text": "Led a migration across three teams."},
            excerpt="Led a migration across three teams.",
        )

        profile = await self.knowledge.get_profile("user-1")
        completeness = await self.knowledge.get_completeness("user-1")
        gaps = analyze_profile_gaps(profile=profile, completeness_report=completeness)

        self.assertGreater(len(gaps), 0)
        self.assertEqual(gaps[0].topic, "architecture")
        self.assertIn("cloud", gaps[0].missing_fields)

    async def test_get_next_question_keeps_topic_active_until_required_fields_are_filled(self) -> None:
        await self._approve_entity(
            entity_type="project",
            canonical_name="Scheduler Platform",
            content={
                "summary": "Built a distributed scheduling platform for internal jobs.",
                "technologies": ["Python"],
            },
            excerpt="Built a distributed scheduling platform for internal jobs.",
        )
        await self._approve_entity(
            entity_type="leadership",
            canonical_name="Migration Lead",
            content={"text": "Led a migration across three teams."},
            excerpt="Led a migration across three teams.",
        )

        question = await self.service.get_next_question("user-1")
        self.assertIsNotNone(question)
        assert question is not None
        self.assertEqual(question.topic, "architecture")
        self.assertEqual(question.prompt, TOPIC_SCHEMAS["architecture"].initial_question)

        result = await self.service.submit_answer(
            "user-1",
            answer="It was a microservice platform with PostgreSQL as the main database.",
            actor_user_id="user-1",
            topic="architecture",
            question=question,
        )

        self.assertIsNotNone(result.next_question)
        assert result.next_question is not None
        self.assertEqual(result.next_question.topic, "architecture")
        self.assertEqual(
            result.next_question.prompt,
            TOPIC_SCHEMAS["architecture"].follow_up_questions["cloud"],
        )

        state = await self.service.get_state("user-1")
        progress = state.progress_for("architecture")
        self.assertEqual(state.current_topic, "architecture")
        self.assertEqual(progress.status, "pending")
        self.assertIn("database", progress.extracted_fields)
        self.assertIn("architecture", progress.extracted_fields)

    async def test_submit_answer_creates_conversation_evidence_and_staged_updates(self) -> None:
        await self._approve_entity(
            entity_type="project",
            canonical_name="Scheduler Platform",
            content={
                "summary": "Built a distributed scheduling platform for internal jobs.",
                "technologies": ["Python"],
            },
            excerpt="Built a distributed scheduling platform for internal jobs.",
        )
        await self._approve_entity(
            entity_type="leadership",
            canonical_name="Migration Lead",
            content={"text": "Led a migration across three teams."},
            excerpt="Led a migration across three teams.",
        )

        question = await self.service.get_next_question("user-1")
        assert question is not None
        result = await self.service.submit_answer(
            "user-1",
            answer=(
                "I designed the architecture for a Kubernetes-based scheduling platform on AWS "
                "with PostgreSQL that handled 90,000 jobs per day."
            ),
            actor_user_id="user-1",
            topic="architecture",
            question=question,
        )

        self.assertGreaterEqual(len(result.staged_version_ids), 4)
        self.assertGreater(result.knowledge_gain["total"], 0)
        self.assertTrue(any(fact.entity_type == "achievement" for fact in result.extracted_facts))
        self.assertTrue(any(fact.entity_type == "technology" for fact in result.extracted_facts))

        state = await self.service.get_state("user-1")
        progress = state.progress_for("architecture")
        self.assertIn("architecture", state.completed_topics)
        self.assertEqual(progress.status, "completed")
        self.assertIn("cloud", progress.extracted_fields)
        self.assertIn("scale", progress.extracted_fields)

        evidence_items = await self.knowledge_service.retrieve_evidence("user-1", query="90,000")
        self.assertEqual(evidence_items[0].source_type, "conversation")
        self.assertEqual(evidence_items[0].metadata["source"], "profile_evolution")

        store = self.knowledge_service.store
        assert isinstance(store, InMemoryKnowledgePlatformStore)
        version_statuses = [store.versions[version_id].status for version_id in result.staged_version_ids]
        self.assertTrue(all(status == "suggested" for status in version_statuses))


if __name__ == "__main__":
    unittest.main()
