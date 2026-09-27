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
from app.recruiter_intelligence import (
    InMemoryRecruiterStore,
    RecruiterIntelligenceService,
    RecruiterMessageImportRecord,
)
from app.resume_intelligence import InMemoryResumeVersionStore, ResumeVersionRecord


class RecruiterIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.application_store = InMemoryApplicationStore()
        self.recruiter_store = InMemoryRecruiterStore()
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
            metadata={"evaluation": {"status": "pass", "score": 96}, "critique": {"verdict": "ready_for_review"}},
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:00:00+00:00",
        )
        self.resume_version_two = ResumeVersionRecord(
            version_id="rv_2",
            user_id="user-1",
            job_id="job-2",
            source_resume_id="resume-1",
            source_resume_name="Platform Resume",
            file_name="Backend_Resume.pdf",
            pdf_storage_path="/tmp/backend.pdf",
            text_storage_path="/tmp/backend.txt",
            status="generated",
            version_signature="sig-2",
            metadata={"evaluation": {"status": "pass", "score": 94}, "critique": {"verdict": "ready_for_review"}},
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:00:00+00:00",
        )
        await self.version_store.save(self.resume_version)
        await self.version_store.save(self.resume_version_two)

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
                why=["Python", "Kubernetes"],
                gaps=["Terraform"],
                published_at="2026-07-20T00:00:00+00:00",
            ),
            "job-2": ApplicationJobSnapshot(
                job_id="job-2",
                company="Stripe",
                title="Senior Backend Engineer",
                location="Seattle, WA",
                remote_policy="Remote",
                apply_url="https://example.com/jobs/2/apply",
                match_score=93,
                decision="APPLY_NOW",
                why=["Python", "API design"],
                gaps=[],
                published_at="2026-07-20T00:00:00+00:00",
            ),
        }

        async def job_loader(user_id: str, job_id: str) -> ApplicationJobSnapshot | None:
            self.assertEqual(user_id, "user-1")
            return self.jobs.get(job_id)

        self.application_service = ApplicationIntelligenceService(
            application_store=self.application_store,
            version_store=self.version_store,
            job_loader=job_loader,
        )
        self.recruiter_service = RecruiterIntelligenceService(
            recruiter_store=self.recruiter_store,
            application_service=self.application_service,
        )

    async def test_import_classifies_matches_and_updates_application_workflow(self) -> None:
        record = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        record = await self.application_service.update_application_metadata(
            "user-1",
            record.application_id,
            updates={"recruiter_name": "Avery Chen", "recruiter_email": "avery@example.com"},
        )

        items = await self.recruiter_service.import_messages(
            "user-1",
            [
                RecruiterMessageImportRecord(
                    recruiter_name="Avery Chen",
                    recruiter_email="avery@example.com",
                    sender_email="avery@example.com",
                    recipients=["user@example.com"],
                    subject="Interview invitation for Staff Platform Engineer",
                    body_text="We would like to invite you to interview with the Ramp platform team.",
                    company="Ramp",
                    job_title="Staff Platform Engineer",
                    received_at="2026-07-21T16:00:00+00:00",
                )
            ],
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].message_type, "interview_invitation")
        self.assertEqual(items[0].application_id, record.application_id)
        self.assertIn("recruiter email", items[0].match_reason)

        updated = await self.application_service.get_application("user-1", record.application_id)
        assert updated is not None
        self.assertTrue(any(event.event_type == "InterviewRequested" for event in updated.timeline))
        self.assertTrue(any(task.task_id == "recruiter_next_action" for task in updated.tasks))
        self.assertEqual(updated.metadata["communication_summary"]["last_message_type"], "interview_invitation")
        self.assertEqual(updated.metadata["communication_summary"]["pending_action"], "Reply to schedule the interview")

        communication = await self.recruiter_service.get_application_communication("user-1", record.application_id)
        self.assertEqual(communication["summary"]["last_message_id"], items[0].message_id)
        self.assertEqual(communication["events"][0]["event_type"], "InterviewRequested")
        self.assertEqual(communication["threads"][0]["message_count"], 1)
        self.assertEqual(communication["conversation_state"]["state"], "waiting_for_candidate")
        self.assertEqual(communication["summary"]["waiting_on"], "candidate")
        self.assertTrue(any(item["action_type"] == "reply_to_recruiter" for item in communication["suggestions"]))

    async def test_plain_email_links_to_application_by_sender_address(self) -> None:
        record = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        await self.application_service.update_application_metadata(
            "user-1",
            record.application_id,
            updates={"recruiter_name": "Avery Chen", "recruiter_email": "avery@example.com"},
        )

        items = await self.recruiter_service.import_messages(
            "user-1",
            [
                RecruiterMessageImportRecord(
                    sender_email="Avery@Example.com",
                    sender_name="Avery Chen",
                    recipients=["user@example.com"],
                    subject="Next steps",
                    body_text="Thanks for applying. Could you share a few times for a phone screen?",
                    received_at="2026-07-21T16:00:00+00:00",
                )
            ],
        )

        self.assertEqual(items[0].application_id, record.application_id)
        self.assertIn("recruiter email", items[0].match_reason)

    async def test_low_confidence_messages_remain_unattached(self) -> None:
        record = await self.application_service.build_application_package("user-1", "job-2", resume_version_id="rv_2")
        before = await self.application_service.get_application("user-1", record.application_id)
        assert before is not None

        items = await self.recruiter_service.import_messages(
            "user-1",
            [
                RecruiterMessageImportRecord(
                    recruiter_name="Morgan",
                    recruiter_email="morgan@example.com",
                    sender_email="morgan@example.com",
                    subject="Quick chat",
                    body_text="Hello there.",
                    received_at="2026-07-21T18:30:00+00:00",
                )
            ],
        )

        self.assertIsNone(items[0].application_id)
        self.assertEqual(items[0].message_type, "general")
        self.assertEqual(items[0].match_confidence, 0.0)

        after = await self.application_service.get_application("user-1", record.application_id)
        assert after is not None
        self.assertEqual(len(after.timeline), len(before.timeline))
        communication = await self.recruiter_service.get_application_communication("user-1", record.application_id)
        self.assertEqual(communication["messages"], [])
        self.assertEqual(communication["summary"]["last_message_id"], "")

    async def test_candidate_reply_drives_follow_up_health_and_contact_profile(self) -> None:
        record = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        await self.application_service.update_application_metadata(
            "user-1",
            record.application_id,
            updates={"recruiter_name": "Avery Chen", "recruiter_email": "avery@example.com"},
        )

        now = datetime.now(timezone.utc)
        recruiter_at = (now - timedelta(days=6, hours=5)).isoformat()
        candidate_at = (now - timedelta(days=6)).isoformat()
        await self.recruiter_service.import_messages(
            "user-1",
            [
                RecruiterMessageImportRecord(
                    external_thread_id="thread-1",
                    recruiter_name="Avery Chen",
                    recruiter_email="avery@example.com",
                    sender_email="avery@example.com",
                    recipients=["user@example.com"],
                    subject="Interview invitation",
                    body_text="Can you share your availability for an interview next week?",
                    company="Ramp",
                    job_title="Staff Platform Engineer",
                    received_at=recruiter_at,
                ),
                RecruiterMessageImportRecord(
                    external_thread_id="thread-1",
                    recruiter_name="Avery Chen",
                    recruiter_email="avery@example.com",
                    sender_email="user@example.com",
                    recipients=["avery@example.com"],
                    subject="Re: Interview invitation",
                    body_text="Thanks. Here are my available time slots for the interview.",
                    company="Ramp",
                    job_title="Staff Platform Engineer",
                    received_at=candidate_at,
                ),
            ],
        )

        state = await self.recruiter_service.get_application_conversation_state("user-1", record.application_id)
        self.assertEqual(state.state, "waiting_for_recruiter")
        self.assertEqual(state.waiting_on, "recruiter")
        self.assertAlmostEqual(state.sla.response_latency_hours or 0.0, 5.0, places=1)

        health = await self.recruiter_service.get_application_communication_health("user-1", record.application_id)
        self.assertEqual(health.status, "needs_follow_up")

        communication = await self.recruiter_service.get_application_communication("user-1", record.application_id)
        self.assertTrue(any(item["event_type"] == "CandidateReplied" for item in communication["events"]))
        self.assertTrue(any(item["action_type"] == "follow_up_with_recruiter" for item in communication["suggestions"]))
        self.assertEqual(communication["summary"]["waiting_on"], "recruiter")

        contacts = await self.recruiter_service.list_contacts("user-1")
        self.assertEqual(len(contacts), 1)
        profile = contacts[0]
        self.assertEqual(profile.contact.email, "avery@example.com")
        self.assertEqual(profile.total_conversations, 1)
        self.assertEqual(profile.total_messages, 2)
        self.assertAlmostEqual(profile.average_response_time_hours or 0.0, 5.0, places=1)
        self.assertEqual(profile.waiting_on, "recruiter")
        self.assertEqual(len(profile.applications_connected), 1)

    async def test_summaries_and_versioned_drafts_are_grounded_in_thread_context(self) -> None:
        record = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        await self.application_service.update_application_metadata(
            "user-1",
            record.application_id,
            updates={"recruiter_name": "Avery Chen", "recruiter_email": "avery@example.com"},
        )

        items = await self.recruiter_service.import_messages(
            "user-1",
            [
                RecruiterMessageImportRecord(
                    recruiter_name="Avery Chen",
                    recruiter_email="avery@example.com",
                    sender_email="avery@example.com",
                    recipients=["user@example.com"],
                    subject="Interview invitation for Staff Platform Engineer",
                    body_text="We would like to invite you to a technical interview with the Ramp platform team next week.",
                    company="Ramp",
                    job_title="Staff Platform Engineer",
                    received_at="2026-07-21T16:00:00+00:00",
                )
            ],
        )

        message = items[0]
        thread = (await self.recruiter_service.list_threads("user-1"))[0]
        message_summary = await self.recruiter_service.get_message_summary("user-1", message.message_id)
        thread_summary = await self.recruiter_service.get_thread_summary("user-1", thread.thread_id)

        self.assertEqual(message_summary.scope_type, "message")
        self.assertEqual(message_summary.scope_id, message.message_id)
        self.assertEqual(message_summary.pending_action, "Reply to schedule the interview")
        self.assertTrue(any(item.source_type == "recruiter_message" for item in message_summary.evidence))

        self.assertEqual(thread_summary.scope_type, "thread")
        self.assertEqual(thread_summary.scope_id, thread.thread_id)
        self.assertEqual(thread_summary.thread_id, thread.thread_id)
        self.assertGreaterEqual(thread_summary.confidence, 0.8)

        draft = await self.recruiter_service.generate_draft(
            "user-1",
            thread_id=thread.thread_id,
            draft_kind="reply",
            tone="professional",
            source_message_id=message.message_id,
        )
        self.assertEqual(draft.version_number, 1)
        self.assertEqual(draft.status, "generated")
        self.assertTrue(draft.subject.startswith("Re:"))
        self.assertIn("latest recruiter message", draft.explanation)

        updated = await self.recruiter_service.update_draft(
            "user-1",
            draft.draft_id,
            subject="Re: Interview invitation for Staff Platform Engineer",
            body="Hi Avery,\n\nThanks for reaching out. I can share availability today.\n\nBest,",
            status="approved",
        )
        self.assertEqual(updated.version_number, 2)
        self.assertEqual(updated.parent_draft_id, draft.draft_id)
        self.assertEqual(updated.status, "approved")
        self.assertTrue(updated.user_edited)

        all_versions = await self.recruiter_service.list_drafts("user-1", thread_id=thread.thread_id, latest_only=False)
        latest_only = await self.recruiter_service.list_drafts("user-1", thread_id=thread.thread_id)
        self.assertEqual(len(all_versions), 2)
        self.assertEqual(len(latest_only), 1)
        self.assertEqual(latest_only[0].draft_id, updated.draft_id)


if __name__ == "__main__":
    unittest.main()
