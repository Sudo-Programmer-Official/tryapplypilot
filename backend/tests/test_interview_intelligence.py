from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import sys
import types
import unittest

if "asyncpg" not in sys.modules and importlib.util.find_spec("asyncpg") is None:
    asyncpg_stub = types.ModuleType("asyncpg")

    class _UniqueViolationError(Exception):
        pass

    asyncpg_stub.UniqueViolationError = _UniqueViolationError
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "fastapi" not in sys.modules and importlib.util.find_spec("fastapi") is None:
    fastapi_stub = types.ModuleType("fastapi")

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    class _FastAPI:
        def __init__(self, *args, **kwargs):
            self.state = types.SimpleNamespace()

        def add_middleware(self, *args, **kwargs):
            return None

        def get(self, *args, **kwargs):
            return lambda func: func

        def post(self, *args, **kwargs):
            return lambda func: func

        def put(self, *args, **kwargs):
            return lambda func: func

        def patch(self, *args, **kwargs):
            return lambda func: func

        def delete(self, *args, **kwargs):
            return lambda func: func

    class _UploadFile:
        pass

    fastapi_stub.Depends = lambda dependency=None: dependency
    fastapi_stub.FastAPI = _FastAPI
    fastapi_stub.File = lambda default=None: default
    fastapi_stub.HTTPException = _HTTPException
    fastapi_stub.Query = lambda default=None, **kwargs: default
    fastapi_stub.Request = object
    fastapi_stub.UploadFile = _UploadFile
    fastapi_stub.status = types.SimpleNamespace(
        HTTP_400_BAD_REQUEST=400,
        HTTP_401_UNAUTHORIZED=401,
        HTTP_403_FORBIDDEN=403,
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
        HTTP_503_SERVICE_UNAVAILABLE=503,
    )
    sys.modules["fastapi"] = fastapi_stub

    middleware_stub = types.ModuleType("fastapi.middleware")
    cors_stub = types.ModuleType("fastapi.middleware.cors")
    cors_stub.CORSMiddleware = object
    sys.modules["fastapi.middleware"] = middleware_stub
    sys.modules["fastapi.middleware.cors"] = cors_stub

    security_stub = types.ModuleType("fastapi.security")

    class _HTTPAuthorizationCredentials:
        def __init__(self, credentials: str = ""):
            self.credentials = credentials

    class _HTTPBearer:
        def __init__(self, auto_error: bool = False):
            self.auto_error = auto_error

        def __call__(self, *args, **kwargs):
            return None

    security_stub.HTTPAuthorizationCredentials = _HTTPAuthorizationCredentials
    security_stub.HTTPBearer = _HTTPBearer
    sys.modules["fastapi.security"] = security_stub

from app.application_intelligence import ApplicationIntelligenceService, ApplicationJobSnapshot, InMemoryApplicationStore
from app.interview_intelligence import (
    InMemoryInterviewPreparationPlanStore,
    InMemoryInterviewQuestionBankStore,
    InMemoryInterviewStoryStore,
    InMemoryInterviewStore,
    InterviewIntelligenceService,
)
from app.knowledge_platform import (
    InMemoryKnowledgePlatformStore,
    KnowledgePlatformClient,
    KnowledgePlatformService,
)
from app.recruiter_intelligence import InMemoryRecruiterStore, RecruiterIntelligenceService, RecruiterMessageImportRecord
from app.resume_intelligence import InMemoryResumeVersionStore, ResumeIntelligenceService, ResumeVersionRecord
from app.resume_intelligence.models import ResumeIntelligenceJobContext


class InterviewIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        async def audit_recorder(**kwargs):
            return None

        self.application_store = InMemoryApplicationStore()
        self.interview_store = InMemoryInterviewStore()
        self.preparation_store = InMemoryInterviewPreparationPlanStore()
        self.question_store = InMemoryInterviewQuestionBankStore()
        self.story_store = InMemoryInterviewStoryStore()
        self.recruiter_store = InMemoryRecruiterStore()
        self.version_store = InMemoryResumeVersionStore()
        self.knowledge_service = KnowledgePlatformService(
            store=InMemoryKnowledgePlatformStore(),
            audit_recorder=audit_recorder,
        )
        self.knowledge_client = KnowledgePlatformClient(service=self.knowledge_service)
        self.resume_version = ResumeVersionRecord(
            version_id="rv_1",
            user_id="user-1",
            job_id="job-1",
            source_resume_id="resume-1",
            source_resume_name="Platform Resume",
            file_name="Platform_Resume.pdf",
            pdf_storage_path="/tmp/platform.pdf",
            text_storage_path="/tmp/platform.txt",
            status="generated",
            version_signature="sig-1",
            accepted_changes=[
                {
                    "change_id": "change-1",
                    "decision": "approved",
                    "original_text": "- Built services",
                    "final_text": "- Built Python platform services on Kubernetes and improved deployment reliability.",
                    "job_requirements": ["Python", "Kubernetes"],
                },
                {
                    "change_id": "change-2",
                    "decision": "approved",
                    "original_text": "- Worked on backend APIs",
                    "final_text": "- Designed distributed backend APIs and PostgreSQL data flows for production systems.",
                    "job_requirements": ["Distributed Systems", "PostgreSQL"],
                },
            ],
            metadata={
                "evaluation": {"status": "pass", "score": 96},
                "critique": {"verdict": "ready_for_review"},
                "selection": {"matched_requirements": ["Python", "Kubernetes", "Distributed Systems"]},
            },
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:00:00+00:00",
        )
        await self.version_store.save(self.resume_version)

        self.jobs = {
            "job-1": ApplicationJobSnapshot(
                job_id="job-1",
                company="Ramp",
                title="Staff Platform Engineer",
                location="New York, NY",
                remote_policy="Hybrid",
                apply_url="https://example.com/jobs/1/apply",
                match_score=95,
                decision="APPLY_NOW",
                why=["Python", "Kubernetes", "Distributed Systems"],
                gaps=["Terraform"],
                published_at="2026-07-20T00:00:00+00:00",
            )
        }

        async def job_loader(user_id: str, job_id: str) -> ApplicationJobSnapshot | None:
            self.assertEqual(user_id, "user-1")
            return self.jobs.get(job_id)

        async def resume_job_loader(user_id: str, job_id: str) -> ResumeIntelligenceJobContext | None:
            self.assertEqual(user_id, "user-1")
            job = self.jobs.get(job_id)
            if job is None:
                return None
            return ResumeIntelligenceJobContext(
                job_id=job.job_id,
                user_id=user_id,
                company=job.company,
                title=job.title,
                location=job.location,
                remote_policy=job.remote_policy,
                apply_url=job.apply_url,
                description_text=(
                    "Build Python and Kubernetes-based backend systems with PostgreSQL, distributed systems, "
                    "and infrastructure depth. Terraform experience is helpful."
                ),
                published_at=job.published_at,
                match_score=job.match_score,
                decision=job.decision,
                recommended_resume="Platform Resume",
                why=list(job.why),
                gaps=list(job.gaps),
            )

        self.application_service = ApplicationIntelligenceService(
            application_store=self.application_store,
            version_store=self.version_store,
            job_loader=job_loader,
        )
        self.recruiter_service = RecruiterIntelligenceService(
            recruiter_store=self.recruiter_store,
            application_service=self.application_service,
        )
        self.resume_service = ResumeIntelligenceService(
            knowledge=self.knowledge_service,
            job_loader=resume_job_loader,
            version_store=self.version_store,
        )
        self.interview_service = InterviewIntelligenceService(
            interview_store=self.interview_store,
            application_service=self.application_service,
            preparation_store=self.preparation_store,
            question_store=self.question_store,
            story_store=self.story_store,
            knowledge_client=self.knowledge_client,
            recruiter_service=self.recruiter_service,
            resume_service=self.resume_service,
            version_store=self.version_store,
        )

        await self._approve_entity(
            entity_type="project",
            canonical_name="Kubernetes Migration",
            content={
                "summary": "Led a Kubernetes migration for platform services and improved deployment reliability.",
                "technologies": ["Python", "Kubernetes", "PostgreSQL"],
            },
            excerpt="Led a Kubernetes migration for platform services and improved deployment reliability.",
        )
        await self._approve_entity(
            entity_type="project",
            canonical_name="Distributed API Platform",
            content={
                "summary": "Designed distributed Python APIs backed by PostgreSQL for high-throughput workflows.",
                "technologies": ["Python", "PostgreSQL", "Distributed Systems"],
            },
            excerpt="Designed distributed Python APIs backed by PostgreSQL for high-throughput workflows.",
        )
        await self._approve_entity(
            entity_type="leadership",
            canonical_name="Cross-team Mentorship",
            content={"summary": "Mentored engineers across teams and coordinated delivery for a multi-service migration."},
            excerpt="Mentored engineers across teams and coordinated delivery for a multi-service migration.",
        )
        await self._approve_entity(
            entity_type="achievement",
            canonical_name="Reliability Improvement",
            content={"text": "Improved deployment reliability by 37% after reworking the release pipeline."},
            excerpt="Improved deployment reliability by 37% after reworking the release pipeline.",
        )

    async def _approve_entity(
        self,
        *,
        entity_type: str,
        canonical_name: str,
        content: dict[str, object],
        excerpt: str,
        source_type: str = "project",
    ) -> None:
        evidence = await self.knowledge_service.add_evidence(
            "user-1",
            source_type=source_type,
            source_id=f"{entity_type}-{canonical_name.casefold().replace(' ', '-')}",
            excerpt=excerpt,
            metadata={"seed": True, "confidence": 0.92},
        )
        version = await self.knowledge_service.stage_change(
            "user-1",
            entity_type=entity_type,
            canonical_name=canonical_name,
            new_content=content,
            source="tests",
            reason="Seed interview preparation evidence.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
            confidence=0.92,
            agent_name="tests",
        )
        await self.knowledge_service.approve_change(version.id, reviewed_by_user_id="admin-1")

    async def test_create_interview_creates_canonical_record_and_updates_application_timeline(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        future = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="technical",
            interview_round="Round 2",
            interview_status="scheduled",
            scheduled_start_at=future,
            timezone_name="America/Denver",
            meeting_url="https://meet.example.com/interview",
            recruiter_name="Avery Chen",
            recruiter_email="avery@example.com",
        )

        self.assertEqual(interview.application_id, application.application_id)
        self.assertEqual(interview.interview_type, "technical")
        self.assertEqual(interview.interview_status, "scheduled")
        self.assertEqual(interview.preparation_status, "not_started")
        self.assertGreaterEqual(len(interview.preparation_checklist), 5)
        self.assertTrue(any(item.event_type == "InterviewCreated" for item in interview.timeline))
        self.assertTrue(any(item.event_type == "InterviewScheduled" for item in interview.timeline))

        upcoming = await self.interview_service.list_upcoming("user-1")
        self.assertEqual(len(upcoming), 1)
        self.assertEqual(upcoming[0].interview_id, interview.interview_id)

        updated_application = await self.application_service.get_application("user-1", application.application_id)
        assert updated_application is not None
        self.assertIn(interview.interview_id, updated_application.metadata["interview_ids"])
        self.assertTrue(any(item.event_type == "InterviewCreated" for item in updated_application.timeline))

    async def test_update_interview_persists_status_and_timeline(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="behavioral",
            interview_round="Round 1",
            interview_status="planned",
        )
        checklist = interview.preparation_checklist
        first = checklist[0]
        updated = await self.interview_service.update_interview(
            "user-1",
            interview.interview_id,
            interview_status="completed",
            notes="Completed the hiring manager screen.",
            preparation_checklist=[
                {
                    "item_id": first.item_id,
                    "label": first.label,
                    "status": "completed",
                    "detail": first.detail,
                    "category": first.category,
                    "source": first.source,
                    "generated": True,
                }
            ]
            + [item.to_dict() for item in checklist[1:]],
        )

        self.assertEqual(updated.interview_status, "completed")
        self.assertIsNotNone(updated.completed_at)
        self.assertEqual(updated.notes, "Completed the hiring manager screen.")
        self.assertTrue(any(item.event_type == "InterviewCompleted" for item in updated.timeline))
        self.assertTrue(any(item.event_type == "InterviewUpdated" for item in updated.audit_history))

        updated_application = await self.application_service.get_application("user-1", application.application_id)
        assert updated_application is not None
        self.assertTrue(any(item.event_type == "InterviewCompleted" for item in updated_application.timeline))

    async def test_prepare_interview_generates_versioned_evidence_backed_plan(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="technical",
            interview_round="Round 2",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat(),
            recruiter_name="Avery Chen",
            recruiter_email="avery@example.com",
        )
        await self.recruiter_service.import_messages(
            "user-1",
            [
                RecruiterMessageImportRecord(
                    recruiter_name="Avery Chen",
                    recruiter_email="avery@example.com",
                    sender_email="avery@example.com",
                    recipients=["user@example.com"],
                    subject="Interview invitation for Staff Platform Engineer",
                    body_text="We'd like to focus on Python, distributed systems, and platform depth in the next round.",
                    company="Ramp",
                    job_title="Staff Platform Engineer",
                    received_at="2026-07-21T12:00:00+00:00",
                )
            ],
        )

        plan = await self.interview_service.prepare_interview("user-1", interview.interview_id)

        self.assertEqual(plan.version_number, 1)
        self.assertGreaterEqual(len(plan.sections), 6)
        self.assertIn("Python", plan.focus_labels)
        self.assertTrue(any(section.title == "Interview Focus Areas" for section in plan.sections))
        self.assertTrue(any(section.evidence_references for section in plan.sections))
        self.assertTrue(any(item.reason for item in plan.checklist))
        self.assertTrue(any(item.supporting_evidence for item in plan.checklist))
        self.assertTrue(any("Terraform" in risk.title for risk in plan.risks))

        refreshed_interview = await self.interview_service.get_interview("user-1", interview.interview_id)
        assert refreshed_interview is not None
        self.assertEqual(refreshed_interview.metadata["preparation_plan_current"]["version_number"], 1)
        self.assertTrue(any(item.event_type == "InterviewPreparationGenerated" for item in refreshed_interview.timeline))

    async def test_regenerate_preparation_creates_new_version_and_preserves_progress(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="system_design",
            interview_round="Final Round",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=4)).replace(microsecond=0).isoformat(),
        )

        initial_plan = await self.interview_service.prepare_interview("user-1", interview.interview_id)
        first_item = initial_plan.checklist[0]
        updated_plan = await self.interview_service.update_preparation(
            "user-1",
            interview.interview_id,
            checklist=[
                {
                    **first_item.to_dict(),
                    "status": "completed",
                    "completed_at": "2026-07-21T18:00:00+00:00",
                }
            ]
            + [item.to_dict() for item in initial_plan.checklist[1:]],
        )
        regenerated = await self.interview_service.regenerate_preparation("user-1", interview.interview_id)

        self.assertEqual(updated_plan.version_number, 1)
        self.assertEqual(regenerated.version_number, 2)
        matching = next(item for item in regenerated.checklist if item.label == first_item.label)
        self.assertEqual(matching.status, "completed")

        latest = await self.interview_service.get_preparation("user-1", interview.interview_id)
        assert latest is not None
        self.assertEqual(latest.version_number, 2)

        refreshed_interview = await self.interview_service.get_interview("user-1", interview.interview_id)
        assert refreshed_interview is not None
        self.assertTrue(any(item.event_type == "InterviewPreparationRegenerated" for item in refreshed_interview.timeline))

    async def test_generate_question_set_creates_versioned_grounded_questions(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="technical",
            interview_round="Round 2",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0).isoformat(),
            recruiter_name="Avery Chen",
            recruiter_email="avery@example.com",
        )
        await self.interview_service.prepare_interview("user-1", interview.interview_id)

        question_set = await self.interview_service.generate_question_set("user-1", interview.interview_id)

        self.assertEqual(question_set.version_number, 1)
        self.assertEqual(question_set.status, "active")
        self.assertGreaterEqual(len(question_set.questions), 8)
        self.assertTrue(any(item.category == "technical" for item in question_set.questions))
        self.assertTrue(any(item.category == "resume_deep_dive" for item in question_set.questions))
        self.assertTrue(any(item.related_evidence for item in question_set.questions))
        self.assertTrue(all(item.rationale for item in question_set.questions))
        self.assertTrue(all(item.confidence > 0.0 for item in question_set.questions))
        self.assertTrue(any(item.follow_up_questions for item in question_set.questions))

        current = await self.interview_service.get_current_question_set("user-1", interview.interview_id)
        assert current is not None
        self.assertEqual(current.question_set_id, question_set.question_set_id)

        refreshed_interview = await self.interview_service.get_interview("user-1", interview.interview_id)
        assert refreshed_interview is not None
        self.assertEqual(refreshed_interview.metadata["question_set_current"]["version_number"], 1)
        self.assertTrue(any(item.event_type == "InterviewQuestionSetGenerated" for item in refreshed_interview.timeline))

    async def test_regenerate_question_set_supersedes_previous_version(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="system_design",
            interview_round="Final Round",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=4)).replace(microsecond=0).isoformat(),
        )
        await self.interview_service.prepare_interview("user-1", interview.interview_id)
        initial = await self.interview_service.generate_question_set("user-1", interview.interview_id)

        regenerated = await self.interview_service.regenerate_question_set("user-1", interview.interview_id)

        self.assertEqual(initial.version_number, 1)
        self.assertEqual(regenerated.version_number, 2)
        self.assertEqual(regenerated.status, "active")
        versions = await self.interview_service.list_question_sets("user-1", interview.interview_id)
        self.assertEqual(versions[0].version_number, 2)
        self.assertEqual(versions[1].status, "superseded")
        self.assertEqual(versions[1].superseded_by_question_set_id, regenerated.question_set_id)

    async def test_update_question_and_add_note_persist_state(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="behavioral",
            interview_round="Round 3",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat(),
        )
        await self.interview_service.prepare_interview("user-1", interview.interview_id)
        question_set = await self.interview_service.generate_question_set("user-1", interview.interview_id)
        question = question_set.questions[0]

        updated = await self.interview_service.update_question(
            "user-1",
            question.question_id,
            preparation_status="prepared",
            priority="high",
            sequence_order=2,
        )
        noted = await self.interview_service.add_question_note(
            "user-1",
            question.question_id,
            body="Need a tighter answer on measurable impact.",
        )

        self.assertEqual(updated.preparation_status, "prepared")
        self.assertEqual(updated.priority, "high")
        self.assertEqual(updated.sequence_order, 2)
        self.assertEqual(len(noted.user_notes), 1)
        self.assertIn("measurable impact", noted.user_notes[0].body)

        refreshed_interview = await self.interview_service.get_interview("user-1", interview.interview_id)
        assert refreshed_interview is not None
        self.assertTrue(any(item.event_type == "InterviewQuestionPrepared" for item in refreshed_interview.timeline))

    async def test_generate_question_set_requires_preparation_plan(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="technical",
            interview_round="Round 1",
            interview_status="planned",
        )

        with self.assertRaises(ValueError):
            await self.interview_service.generate_question_set("user-1", interview.interview_id)

    async def test_generate_question_set_supports_sparse_context_without_recruiter_messages(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="executive",
            interview_round="Leadership Round",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=5)).replace(microsecond=0).isoformat(),
        )
        await self.interview_service.prepare_interview("user-1", interview.interview_id)

        question_set = await self.interview_service.generate_question_set("user-1", interview.interview_id)

        self.assertGreaterEqual(len(question_set.questions), 8)
        self.assertTrue(any(item.category == "career_motivation" for item in question_set.questions))
        self.assertTrue(any(item.category == "candidate_questions" for item in question_set.questions))

    async def test_generate_stories_creates_evidence_backed_story_library(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="technical",
            interview_round="Panel",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat(),
        )
        await self.interview_service.prepare_interview("user-1", interview.interview_id)
        await self.interview_service.generate_question_set("user-1", interview.interview_id)

        stories = await self.interview_service.generate_stories("user-1", interview.interview_id)

        self.assertGreaterEqual(len(stories), 2)
        self.assertTrue(all(item.status == "review" for item in stories))
        self.assertTrue(all(item.source_evidence for item in stories))
        self.assertTrue(all(item.coverage for item in stories))
        self.assertTrue(all(item.quality.overall_score > 0 for item in stories))
        self.assertTrue(any(section.section_key == "situation" for section in stories[0].sections))

        refreshed_interview = await self.interview_service.get_interview("user-1", interview.interview_id)
        assert refreshed_interview is not None
        self.assertEqual(refreshed_interview.metadata["story_library_current"]["story_count"], len(stories))
        self.assertTrue(any(item.event_type == "InterviewStoryLibraryGenerated" for item in refreshed_interview.timeline))

    async def test_story_versioning_supports_approval_revision_regeneration_and_archive(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="behavioral",
            interview_round="Leadership Round",
            interview_status="scheduled",
            scheduled_start_at=(datetime.now(timezone.utc) + timedelta(days=4)).replace(microsecond=0).isoformat(),
        )
        await self.interview_service.prepare_interview("user-1", interview.interview_id)
        await self.interview_service.generate_question_set("user-1", interview.interview_id)
        story = (await self.interview_service.generate_stories("user-1", interview.interview_id))[0]

        approved = await self.interview_service.approve_story("user-1", story.story_id)
        revised = await self.interview_service.update_story(
            "user-1",
            approved.story_id,
            measurable_outcomes=["Improved release reliability by 25% after the migration."],
            status="review",
        )
        regenerated = await self.interview_service.regenerate_story("user-1", revised.story_id)
        archived = await self.interview_service.archive_story("user-1", regenerated.story_id)

        self.assertEqual(approved.status, "approved")
        self.assertEqual(revised.version_number, approved.version_number + 1)
        self.assertNotEqual(revised.story_id, approved.story_id)
        self.assertEqual(regenerated.version_number, revised.version_number + 1)
        self.assertEqual(archived.status, "archived")

        versions = await self.story_store.list_for_group(story.story_group_id, user_id="user-1")
        self.assertEqual(versions[0].version_number, archived.version_number)
        self.assertTrue(any(item.status == "superseded" for item in versions))
        self.assertTrue(any(item.status == "approved" for item in versions))

    async def test_delete_interview_removes_record_and_updates_application_metadata(self) -> None:
        application = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        interview = await self.interview_service.create_interview(
            "user-1",
            application.application_id,
            interview_type="system_design",
            interview_round="Final Round",
            interview_status="planned",
        )
        await self.interview_service.prepare_interview("user-1", interview.interview_id)
        await self.interview_service.generate_question_set("user-1", interview.interview_id)
        stories = await self.interview_service.generate_stories("user-1", interview.interview_id)

        deleted = await self.interview_service.delete_interview("user-1", interview.interview_id)
        self.assertEqual(deleted.interview_id, interview.interview_id)
        self.assertIsNone(await self.interview_service.get_interview("user-1", interview.interview_id))
        self.assertIsNone(await self.interview_service.get_preparation("user-1", interview.interview_id))
        self.assertEqual(await self.interview_service.get_current_question_set("user-1", interview.interview_id), None)
        for item in stories:
            self.assertIsNone(await self.interview_service.get_story("user-1", item.story_id))

        updated_application = await self.application_service.get_application("user-1", application.application_id)
        assert updated_application is not None
        self.assertEqual(updated_application.metadata["interview_ids"], [])
        self.assertTrue(any(item.event_type == "InterviewDeleted" for item in updated_application.timeline))


if __name__ == "__main__":
    unittest.main()
