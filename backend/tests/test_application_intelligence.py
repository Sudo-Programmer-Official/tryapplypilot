from __future__ import annotations

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

from app.application_intelligence import (
    ApplicationIntelligenceService,
    ApplicationJobSnapshot,
    InMemoryApplicationStore,
)
from app.resume_intelligence import InMemoryResumeVersionStore, ResumeVersionRecord


class ApplicationIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.application_store = InMemoryApplicationStore()
        self.version_store = InMemoryResumeVersionStore()
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
            metadata={
                "evaluation": {"status": "pass", "score": 96},
                "critique": {"verdict": "ready_for_review"},
                "blocked_requirements": [],
            },
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:00:00+00:00",
        )
        await self.version_store.save(self.resume_version)

        self.job = ApplicationJobSnapshot(
            job_id="job-1",
            company="Ramp",
            title="Staff Platform Engineer",
            location="New York, NY",
            remote_policy="Hybrid",
            apply_url="https://example.com/jobs/1/apply",
            match_score=95,
            decision="APPLY_NOW",
            why=["Python", "Kubernetes"],
            gaps=["Terraform"],
            published_at="2026-07-20T00:00:00+00:00",
        )

        async def job_loader(user_id: str, job_id: str) -> ApplicationJobSnapshot | None:
            self.assertEqual(user_id, "user-1")
            return self.job if job_id == "job-1" else None

        self.service = ApplicationIntelligenceService(
            application_store=self.application_store,
            version_store=self.version_store,
            job_loader=job_loader,
        )

    async def test_build_application_package_sets_structured_defaults(self) -> None:
        record = await self.service.build_application_package(
            "user-1",
            "job-1",
            resume_version_id="rv_1",
            notes="Apply with the reviewed platform variant.",
        )

        self.assertEqual(record.status, "ready_to_apply")
        self.assertEqual(record.resume_version_id, "rv_1")
        self.assertEqual(record.company, "Ramp")
        self.assertEqual(record.structured_metadata.location, "New York, NY")
        self.assertEqual(record.structured_metadata.work_arrangement, "Hybrid")
        self.assertEqual(record.structured_metadata.application_portal, "https://example.com/jobs/1/apply")
        self.assertEqual(record.submission.resume_version_id, "rv_1")
        self.assertEqual(len(record.artifacts), 2)
        self.assertEqual(record.artifacts[0].kind, "resume")
        self.assertEqual(record.tasks[2].task_id, "submit_application")
        self.assertEqual(record.timeline[0].event_type, "ApplicationPackageBuilt")
        self.assertEqual(record.metadata["package_notes"], "Apply with the reviewed platform variant.")

        duplicate = await self.service.build_application_package(
            "user-1",
            "job-1",
            resume_version_id="rv_1",
            notes="Different note should not create a duplicate package.",
        )
        self.assertEqual(duplicate.application_id, record.application_id)

    async def test_metadata_answers_artifacts_and_submit_build_complete_record(self) -> None:
        record = await self.service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        record = await self.service.update_application_metadata(
            "user-1",
            record.application_id,
            updates={
                "recruiter_name": "Avery Chen",
                "recruiter_email": "avery@example.com",
                "deadline": "2026-07-25T17:00:00+00:00",
                "assessment_deadline": "2026-07-27T17:00:00+00:00",
                "follow_up_date": "2026-07-29T17:00:00+00:00",
            },
        )
        self.assertEqual(record.structured_metadata.recruiter_name, "Avery Chen")
        generated_deadlines = {task.task_id for task in record.tasks}
        self.assertIn("submission_deadline", generated_deadlines)
        self.assertIn("assessment_deadline", generated_deadlines)
        self.assertIn("follow_up_due", generated_deadlines)
        self.assertTrue(any(item.event_type == "RecruiterAdded" for item in record.timeline))
        self.assertTrue(any(item.event_type == "DeadlineAdded" for item in record.timeline))

        record = await self.service.add_application_answer(
            "user-1",
            record.application_id,
            question="Why do you want to work here?",
            question_key="why_company",
            answer="I want to work on high-scale platform systems with strong product ownership.",
            source="user_manual",
            reusable=True,
        )
        self.assertEqual(len(record.answers), 1)
        self.assertEqual(record.answers[0].normalized_question_key, "why_company")
        self.assertTrue(record.answers[0].reusable)
        self.assertTrue(any(item.kind == "application_answer" for item in record.artifacts))
        self.assertTrue(any(item.event_type == "AnswerSaved" for item in record.timeline))

        record = await self.service.add_application_artifact(
            "user-1",
            record.application_id,
            kind="supporting_document",
            title="Visa support letter",
            source="manual_upload",
            detail="Optional supporting document reference.",
        )
        self.assertTrue(any(item.kind == "supporting_document" for item in record.artifacts))
        self.assertTrue(any(item.event_type == "ArtifactAttached" for item in record.timeline))

        answer_id = record.answers[0].answer_id
        artifact_ids = [artifact.artifact_id for artifact in record.artifacts]
        submitted = await self.service.submit_application(
            "user-1",
            record.application_id,
            submitted_at="2026-07-21T18:00:00+00:00",
            portal="Greenhouse",
            confirmation_number="CONF-123",
            external_application_id="APP-789",
            submitted_url="https://boards.example.com/submissions/APP-789",
            answer_ids=[answer_id],
            artifact_ids=artifact_ids,
            notes="Submitted on Tuesday, July 21, 2026 after final review.",
        )
        self.assertEqual(submitted.status, "applied")
        self.assertEqual(submitted.submission.portal, "Greenhouse")
        self.assertEqual(submitted.submission.confirmation_number, "CONF-123")
        self.assertIn(answer_id, submitted.submission.answer_ids)
        self.assertEqual(submitted.applied_at, "2026-07-21T18:00:00+00:00")
        self.assertTrue(any(item.kind == "confirmation" for item in submitted.artifacts))
        self.assertTrue(any(item.event_type == "ApplicationSubmitted" for item in submitted.timeline))
        self.assertTrue(any(item.event_type == "ConfirmationRecorded" for item in submitted.timeline))

        reusable_answers = await self.service.list_reusable_answers("user-1")
        self.assertEqual(len(reusable_answers), 1)
        self.assertEqual(reusable_answers[0].normalized_question_key, "why_company")

    async def test_submit_requires_valid_answer_and_artifact_ids(self) -> None:
        record = await self.service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        with self.assertRaisesRegex(ValueError, "unknown application answers"):
            await self.service.submit_application(
                "user-1",
                record.application_id,
                answer_ids=["missing-answer"],
                artifact_ids=[],
            )

    async def test_ready_to_apply_cannot_jump_to_applied_via_generic_status_patch(self) -> None:
        record = await self.service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        with self.assertRaisesRegex(ValueError, "Invalid application transition from ready_to_apply to applied"):
            await self.service.update_application_status(
                "user-1",
                record.application_id,
                status="applied",
                notes="This should go through submit_application instead.",
            )

    async def test_post_submit_status_flow_and_task_updates_work(self) -> None:
        record = await self.service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        record = await self.service.submit_application(
            "user-1",
            record.application_id,
            submitted_at="2026-07-21T18:00:00+00:00",
            portal="Greenhouse",
        )
        self.assertEqual(record.tasks[2].status, "completed")
        self.assertEqual(record.tasks[3].status, "in_progress")

        record = await self.service.update_application_task(
            "user-1",
            record.application_id,
            task_id="capture_confirmation",
            status="completed",
            detail="Confirmation captured and saved.",
        )
        self.assertEqual(next(task for task in record.tasks if task.task_id == "capture_confirmation").status, "completed")
        self.assertTrue(any(item.event_type == "TaskCompleted" for item in record.timeline))

        record = await self.service.add_application_note(
            "user-1",
            record.application_id,
            body="Recruiter asked for availability on Wednesday, July 29, 2026.",
            note_type="follow_up",
        )
        self.assertEqual(record.notes[0].note_type, "follow_up")
        self.assertEqual(record.timeline[-1].event_type, "NoteAdded")

        interviewing = await self.service.update_application_status(
            "user-1",
            record.application_id,
            status="interviewing",
            notes="Recruiter screen scheduled for Friday, July 24, 2026.",
        )
        self.assertEqual(interviewing.status, "interviewing")
        self.assertEqual(next(task for task in interviewing.tasks if task.task_id == "follow_up_tracker").status, "in_progress")


if __name__ == "__main__":
    unittest.main()
