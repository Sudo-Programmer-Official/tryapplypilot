from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

if "asyncpg" not in sys.modules and importlib.util.find_spec("asyncpg") is None:
    asyncpg_stub = types.ModuleType("asyncpg")

    class _UniqueViolationError(Exception):
        pass

    asyncpg_stub.UniqueViolationError = _UniqueViolationError
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "jwt" not in sys.modules and importlib.util.find_spec("jwt") is None:
    jwt_stub = types.ModuleType("jwt")

    class _PyJWTError(Exception):
        pass

    jwt_stub.PyJWTError = _PyJWTError
    jwt_stub.InvalidTokenError = _PyJWTError
    jwt_stub.encode = lambda payload, secret, algorithm=None: "stub-token"
    jwt_stub.decode = lambda token, secret, algorithms=None, issuer=None: {"type": "access", "sub": "user-1"}
    sys.modules["jwt"] = jwt_stub

if "fastapi" not in sys.modules and importlib.util.find_spec("fastapi") is None:
    fastapi_stub = types.ModuleType("fastapi")

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    class _FastAPI:
        def __init__(self, *args, **kwargs):
            self.state = SimpleNamespace()

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
    fastapi_stub.status = SimpleNamespace(
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

if "pydantic" not in sys.modules and importlib.util.find_spec("pydantic") is None:
    pydantic_stub = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

    pydantic_stub.BaseModel = _BaseModel
    pydantic_stub.Field = lambda default=None, **kwargs: default
    sys.modules["pydantic"] = pydantic_stub

if "argon2" not in sys.modules and importlib.util.find_spec("argon2") is None:
    argon2_stub = types.ModuleType("argon2")

    class _PasswordHasher:
        def hash(self, password: str) -> str:
            return f"hashed:{password}"

        def verify(self, password_hash: str, password: str) -> bool:
            return password_hash == f"hashed:{password}"

    argon2_stub.PasswordHasher = _PasswordHasher
    sys.modules["argon2"] = argon2_stub

    argon2_exceptions_stub = types.ModuleType("argon2.exceptions")

    class _VerifyMismatchError(Exception):
        pass

    argon2_exceptions_stub.VerifyMismatchError = _VerifyMismatchError
    sys.modules["argon2.exceptions"] = argon2_exceptions_stub

if "pypdf" not in sys.modules and importlib.util.find_spec("pypdf") is None:
    pypdf_stub = types.ModuleType("pypdf")

    class _PdfReader:
        def __init__(self, *args, **kwargs):
            self.pages = []

    pypdf_stub.PdfReader = _PdfReader
    sys.modules["pypdf"] = pypdf_stub

from app.domain import OnboardingStatus, UserAccount
from app.main import (
    InterviewCreatePayload,
    InterviewPreparationEvidencePayload,
    InterviewParticipantPayload,
    InterviewPreparationItemPayload,
    InterviewPreparationUpdatePayload,
    InterviewQuestionNotePayload,
    InterviewQuestionUpdatePayload,
    InterviewStoryGapPromptPayload,
    InterviewStorySectionPayload,
    InterviewStoryUpdatePayload,
    InterviewUpdatePayload,
    add_current_user_interview_question_note,
    approve_current_user_story,
    archive_current_user_story,
    create_current_user_interview,
    current_user_interview_current_question_set,
    current_user_interview,
    current_user_interview_preparation,
    current_user_interview_question_set,
    current_user_interview_question_sets,
    current_user_interview_stories,
    current_user_interviews,
    current_user_stories,
    current_user_story,
    current_user_upcoming_interviews,
    delete_current_user_interview,
    generate_current_user_interview_questions,
    generate_current_user_interview_stories,
    prepare_current_user_interview,
    regenerate_current_user_story,
    regenerate_current_user_interview_questions,
    regenerate_current_user_interview_preparation,
    update_current_user_interview_question,
    update_current_user_interview_preparation,
    update_current_user_story,
    update_current_user_interview,
)


def _user() -> UserAccount:
    return UserAccount(
        id="user-1",
        email="user@example.com",
        role="user",
        full_name="Abhishek",
        telegram_chat_id=None,
        country="US",
        profile={},
        preferences={},
        onboarding=OnboardingStatus(progress_percent=0, steps=[]),
    )


def _interview_record(*, interview_status: str = "scheduled") -> dict[str, object]:
    return {
        "interview_id": "interview-1",
        "application_id": "app-1",
        "user_id": "user-1",
        "interview_type": "technical",
        "interview_round": "Round 2",
        "interview_status": interview_status,
        "preparation_status": "not_started",
        "scheduled_start_at": "2026-07-24T18:00:00+00:00",
        "scheduled_end_at": "2026-07-24T19:00:00+00:00",
        "timezone": "America/Denver",
        "meeting_url": "https://meet.example.com/interview",
        "recruiter_name": "Avery Chen",
        "recruiter_email": "avery@example.com",
        "recruiter_contact_id": "contact-1",
        "notes": "Bring system design examples.",
        "source": "manual",
        "interviewers": [{"participant_id": "person-1", "name": "Taylor", "email": "taylor@example.com", "title": "Hiring Manager", "role": "interviewer", "source_contact_id": ""}],
        "preparation_checklist": [{"item_id": "item-1", "label": "Review recruiter communication", "status": "pending", "detail": "", "category": "context", "source": "interview_intelligence", "due_at": "2026-07-24T18:00:00+00:00", "completed_at": None, "generated": True, "updated_at": "2026-07-21T00:00:00+00:00"}],
        "timeline": [{"event_type": "InterviewCreated", "label": "Interview created", "detail": "Round 2 · technical", "occurred_at": "2026-07-21T00:00:00+00:00"}],
        "audit_history": [{"event_type": "InterviewCreated", "detail": "Interview workspace created.", "actor_user_id": "user-1", "created_at": "2026-07-21T00:00:00+00:00"}],
        "metadata": {"application_company": "Ramp"},
        "created_at": "2026-07-21T00:00:00+00:00",
        "updated_at": "2026-07-21T00:00:00+00:00",
        "completed_at": None,
    }


def _preparation_plan(*, version_number: int = 1) -> dict[str, object]:
    return {
        "plan_id": f"prep-{version_number}",
        "interview_id": "interview-1",
        "application_id": "app-1",
        "user_id": "user-1",
        "version_number": version_number,
        "status": "generated",
        "strategy_version": "interview_preparation_v1",
        "focus_labels": ["Python", "Distributed Systems"],
        "overall_confidence": 0.82,
        "sections": [
            {
                "section_key": "focus_areas",
                "title": "Interview Focus Areas",
                "content": ["Expect emphasis on Python and distributed systems."],
                "evidence_references": [
                    {
                        "reference_id": "ref-1",
                        "source_type": "job_requirement",
                        "source_id": "job-1:python",
                        "label": "Python",
                        "excerpt": "The job context highlights Python.",
                        "confidence": 0.9,
                        "entity_type": "",
                        "entity_id": "",
                        "metadata": {},
                    }
                ],
                "confidence": 0.84,
                "generated_at": "2026-07-21T00:00:00+00:00",
                "strategy_version": "interview_preparation_v1",
            }
        ],
        "checklist": [
            {
                "item_id": "prep-item-1",
                "label": "Review role summary and focus areas",
                "status": "pending",
                "detail": "Review the generated focus areas.",
                "reason": "Focus areas are tied to the job and recruiter context.",
                "estimated_effort": "15m",
                "priority": "high",
                "category": "context",
                "source": "interview_preparation",
                "due_at": "2026-07-24T18:00:00+00:00",
                "completed_at": None,
                "generated": True,
                "updated_at": "2026-07-21T00:00:00+00:00",
                "supporting_evidence": [],
            }
        ],
        "risks": [
            {
                "risk_id": "risk-1",
                "title": "Limited approved evidence for Terraform",
                "detail": "The role mentions Terraform but approved evidence is limited.",
                "recommendation": "Prepare the nearest real example and note the gap.",
                "severity": "medium",
                "confidence": 0.72,
                "evidence_references": [],
                "generated_at": "2026-07-21T00:00:00+00:00",
                "strategy_version": "interview_preparation_v1",
            }
        ],
        "metadata": {"job_id": "job-1"},
        "generated_at": "2026-07-21T00:00:00+00:00",
        "updated_at": "2026-07-21T00:00:00+00:00",
    }


def _question_set(*, version_number: int = 1) -> dict[str, object]:
    return {
        "question_set_id": f"question-set-{version_number}",
        "interview_id": "interview-1",
        "application_id": "app-1",
        "user_id": "user-1",
        "version_number": version_number,
        "status": "active" if version_number == 1 else "superseded",
        "title": "Round 2 Question Bank",
        "interview_type": "technical",
        "interview_round": "Round 2",
        "strategy_version": "interview_questions_v1",
        "source_preparation_plan_id": "prep-1",
        "provider": "deterministic",
        "model_key": "",
        "metadata": {"categories": ["technical", "resume_deep_dive"], "question_count": 2},
        "generated_at": "2026-07-21T00:00:00+00:00",
        "updated_at": "2026-07-21T00:00:00+00:00",
        "superseded_by_question_set_id": "",
        "questions": [
            {
                "question_id": f"question-{version_number}-1",
                "question_set_id": f"question-set-{version_number}",
                "interview_id": "interview-1",
                "application_id": "app-1",
                "user_id": "user-1",
                "category": "technical",
                "question": "Tell me about a production system where you used Python.",
                "rationale": "Python is a highlighted role signal.",
                "evaluation_dimensions": ["technical depth", "tradeoff reasoning"],
                "related_job_requirements": ["Python"],
                "related_evidence": [
                    {
                        "reference_id": "ref-1",
                        "source_type": "job_requirement",
                        "source_id": "job-1:python",
                        "label": "Python",
                        "excerpt": "The role emphasizes Python.",
                        "evidence_id": "",
                        "relevance_explanation": "This is a highlighted job requirement.",
                        "confidence": 0.9,
                        "entity_type": "",
                        "entity_id": "",
                        "metadata": {},
                    }
                ],
                "follow_up_questions": [
                    {
                        "follow_up_id": "follow-up-1",
                        "question": "What tradeoff mattered most?",
                        "rationale": "Probe for decision quality.",
                        "evaluation_dimensions": ["technical depth"],
                        "confidence": 0.7,
                    }
                ],
                "difficulty": "advanced",
                "priority": "must_prepare",
                "confidence": 0.82,
                "expected_answer_outline": ["Context", "Decision", "Outcome"],
                "risk_tags": [],
                "sequence_order": 1,
                "preparation_status": "not_started",
                "hidden": False,
                "archived": False,
                "user_notes": [],
                "metadata": {},
                "created_at": "2026-07-21T00:00:00+00:00",
                "updated_at": "2026-07-21T00:00:00+00:00",
            }
        ],
    }


def _story(*, version_number: int = 1, status: str = "review") -> dict[str, object]:
    return {
        "story_id": f"story-{version_number}",
        "story_group_id": "story-group-1",
        "user_id": "user-1",
        "application_id": "app-1",
        "interview_id": "interview-1",
        "linked_application_ids": ["app-1"],
        "linked_interview_ids": ["interview-1"],
        "title": "Kubernetes migration",
        "category": "project",
        "source_evidence": [
            {
                "reference_id": "story-ref-1",
                "source_type": "knowledge_project",
                "source_id": "project-1",
                "label": "Kubernetes Migration",
                "excerpt": "Led a migration to Kubernetes for backend services.",
                "evidence_id": "",
                "relevance_explanation": "Approved knowledge evidence.",
                "confidence": 0.88,
                "entity_type": "project",
                "entity_id": "entity-1",
                "metadata": {},
            }
        ],
        "related_projects": ["Kubernetes Migration"],
        "related_resume_version_id": "rv_1",
        "related_question_ids": ["question-1-1"],
        "interview_types": ["technical"],
        "tags": ["Python", "Kubernetes", "Distributed Systems"],
        "version_number": version_number,
        "status": status,
        "sections": [
            {
                "section_key": "situation",
                "title": "Situation",
                "content": ["We needed to migrate platform services to Kubernetes."],
                "evidence_references": [],
                "missing_fields": [],
            },
            {
                "section_key": "action",
                "title": "Action",
                "content": ["I designed the rollout plan and led the migration."],
                "evidence_references": [],
                "missing_fields": [],
            },
            {
                "section_key": "result",
                "title": "Result",
                "content": ["Reliability improved and deployments became more predictable."],
                "evidence_references": [],
                "missing_fields": [],
            },
        ],
        "technical_decisions": ["Used Kubernetes to standardize service deployment."],
        "tradeoffs": ["Balanced migration speed against rollback safety."],
        "leadership_moments": ["Aligned multiple teams on the rollout sequence."],
        "measurable_outcomes": ["Improved release reliability by 25%."],
        "lessons_learned": ["Stage migrations behind clear rollback checkpoints."],
        "interviewer_follow_ups": ["Be ready to explain the hardest tradeoff."],
        "coverage": [
            {
                "question_id": "question-1-1",
                "question": "Tell me about a production system where you used Python.",
                "category": "technical",
                "coverage_score": 0.82,
                "reason": "Shares supporting evidence with the interview question.",
                "confidence": 0.86,
            }
        ],
        "quality": {
            "overall_score": 84,
            "dimensions": [
                {"label": "completeness", "score": 85, "rationale": "Well supported."},
                {"label": "interview_relevance", "score": 83, "rationale": "Strong coverage."},
            ],
            "summary": "Story is interview-ready.",
            "generated_at": "2026-07-21T00:00:00+00:00",
            "strategy_version": "interview_stories_v1",
        },
        "missing_information_prompts": [
            {
                "prompt_id": "prompt-1",
                "field_key": "reflection",
                "prompt": "What would you do differently now?",
                "reason": "Reflection is useful for follow-up questions.",
                "topic": "project",
                "status": "open",
                "related_evidence": [],
                "profile_evolution_payload": {"topic": "project", "question_prompt": "What would you do differently now?"},
                "created_at": "2026-07-21T00:00:00+00:00",
                "updated_at": "2026-07-21T00:00:00+00:00",
            }
        ],
        "superseded_by_story_id": "",
        "metadata": {"question_set_id": "question-set-1"},
        "created_at": "2026-07-21T00:00:00+00:00",
        "updated_at": "2026-07-21T00:00:00+00:00",
    }


class MainInterviewAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_interview_routes_return_items(self) -> None:
        interview_payload = _interview_record()
        interview = SimpleNamespace(to_dict=lambda: interview_payload, **interview_payload)
        completed_payload = _interview_record(interview_status="completed")
        completed = SimpleNamespace(to_dict=lambda: completed_payload, **completed_payload)
        preparation_payload = _preparation_plan()
        preparation = SimpleNamespace(to_dict=lambda: preparation_payload, **preparation_payload)
        regenerated_payload = _preparation_plan(version_number=2)
        regenerated = SimpleNamespace(to_dict=lambda: regenerated_payload, **regenerated_payload)
        question_payload = _question_set()
        question_set = SimpleNamespace(to_dict=lambda: question_payload, **question_payload)
        regenerated_question_payload = _question_set(version_number=2)
        regenerated_question_set = SimpleNamespace(to_dict=lambda: regenerated_question_payload, **regenerated_question_payload)
        updated_question_payload = dict(question_payload["questions"][0])
        updated_question_payload["preparation_status"] = "prepared"
        updated_question = SimpleNamespace(to_dict=lambda: updated_question_payload, **updated_question_payload)
        story_payload = _story()
        story = SimpleNamespace(to_dict=lambda: story_payload, **story_payload)
        approved_story_payload = _story(status="approved")
        approved_story = SimpleNamespace(to_dict=lambda: approved_story_payload, **approved_story_payload)
        regenerated_story_payload = _story(version_number=2)
        regenerated_story = SimpleNamespace(to_dict=lambda: regenerated_story_payload, **regenerated_story_payload)
        service = SimpleNamespace(
            list_interviews=AsyncMock(return_value=[interview]),
            list_upcoming=AsyncMock(return_value=[interview]),
            get_interview=AsyncMock(return_value=interview),
            get_preparation=AsyncMock(return_value=preparation),
            list_question_sets=AsyncMock(return_value=[question_set, regenerated_question_set]),
            get_current_question_set=AsyncMock(return_value=question_set),
            get_question_set=AsyncMock(return_value=question_set),
            prepare_interview=AsyncMock(return_value=preparation),
            update_preparation=AsyncMock(return_value=preparation),
            regenerate_preparation=AsyncMock(return_value=regenerated),
            generate_question_set=AsyncMock(return_value=question_set),
            regenerate_question_set=AsyncMock(return_value=regenerated_question_set),
            update_question=AsyncMock(return_value=updated_question),
            add_question_note=AsyncMock(return_value=updated_question),
            list_interview_stories=AsyncMock(return_value=[story]),
            generate_stories=AsyncMock(return_value=[story]),
            list_stories=AsyncMock(return_value=[story, approved_story]),
            get_story=AsyncMock(return_value=story),
            update_story=AsyncMock(return_value=story),
            approve_story=AsyncMock(return_value=approved_story),
            archive_story=AsyncMock(return_value=story),
            regenerate_story=AsyncMock(return_value=regenerated_story),
            create_interview=AsyncMock(return_value=interview),
            update_interview=AsyncMock(return_value=completed),
            delete_interview=AsyncMock(return_value=interview),
        )
        with patch("app.main.build_interview_intelligence_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ):
            items = await current_user_interviews(user=_user(), application_id=None, interview_status=None)
            upcoming = await current_user_upcoming_interviews(user=_user(), limit=5)
            detail = await current_user_interview("interview-1", _user())
            preparation_detail = await current_user_interview_preparation("interview-1", _user())
            generated = await prepare_current_user_interview("interview-1", _user())
            question_sets = await current_user_interview_question_sets("interview-1", _user())
            current_question_set = await current_user_interview_current_question_set("interview-1", _user())
            question_set_detail = await current_user_interview_question_set("question-set-1", _user())
            generated_questions = await generate_current_user_interview_questions("interview-1", _user())
            interview_stories = await current_user_interview_stories("interview-1", _user())
            generated_stories = await generate_current_user_interview_stories("interview-1", _user())
            all_stories = await current_user_stories(user=_user(), application_id=None, interview_id=None, status_value=None)
            story_detail = await current_user_story("story-1", _user())
            preparation_updated = await update_current_user_interview_preparation(
                "interview-1",
                InterviewPreparationUpdatePayload(
                    checklist=[
                        InterviewPreparationItemPayload(
                            label="Review role summary and focus areas",
                            status="completed",
                            supporting_evidence=[InterviewPreparationEvidencePayload(label="Python", source_type="job_requirement", source_id="job-1:python")],
                        )
                    ],
                    status="updated",
                    metadata={"source": "ui"},
                ),
                _user(),
            )
            updated_question_item = await update_current_user_interview_question(
                "question-1-1",
                InterviewQuestionUpdatePayload(
                    preparation_status="prepared",
                    priority="high",
                    sequence_order=2,
                ),
                _user(),
            )
            noted_question_item = await add_current_user_interview_question_note(
                "question-1-1",
                InterviewQuestionNotePayload(body="Need a tighter story on tradeoffs."),
                _user(),
            )
            updated_story_item = await update_current_user_story(
                "story-1",
                InterviewStoryUpdatePayload(
                    title="Kubernetes migration story",
                    status="review",
                    sections=[
                        InterviewStorySectionPayload(
                            section_key="result",
                            title="Result",
                            content=["Improved release reliability by 25%."],
                        )
                    ],
                    measurable_outcomes=["Improved release reliability by 25%."],
                    tags=["Kubernetes", "Python"],
                    missing_information_prompts=[
                        InterviewStoryGapPromptPayload(
                            prompt_id="prompt-1",
                            field_key="reflection",
                            prompt="What would you do differently now?",
                            topic="project",
                            status="open",
                        )
                    ],
                    metadata={"source": "ui"},
                ),
                _user(),
            )
            approved_story_item = await approve_current_user_story("story-1", _user())
            archived_story_item = await archive_current_user_story("story-1", _user())
            regenerated_story_item = await regenerate_current_user_story("story-1", _user())
            regenerated_plan = await regenerate_current_user_interview_preparation("interview-1", _user())
            regenerated_questions = await regenerate_current_user_interview_questions("interview-1", _user())
            created = await create_current_user_interview(
                "app-1",
                InterviewCreatePayload(
                    interview_type="technical",
                    interview_round="Round 2",
                    interview_status="scheduled",
                    scheduled_start_at="2026-07-24T18:00:00+00:00",
                    scheduled_end_at="2026-07-24T19:00:00+00:00",
                    timezone="America/Denver",
                    meeting_url="https://meet.example.com/interview",
                    recruiter_name="Avery Chen",
                    recruiter_email="avery@example.com",
                    interviewers=[InterviewParticipantPayload(name="Taylor", email="taylor@example.com")],
                    preparation_checklist=[InterviewPreparationItemPayload(label="Review recruiter communication", status="pending")],
                ),
                _user(),
            )
            updated = await update_current_user_interview(
                "interview-1",
                InterviewUpdatePayload(interview_status="completed", notes="Completed"),
                _user(),
            )
            deleted = await delete_current_user_interview("interview-1", _user())

        self.assertEqual(items["items"][0]["interview_id"], "interview-1")
        self.assertEqual(upcoming["items"][0]["interview_status"], "scheduled")
        self.assertEqual(detail["item"]["application_id"], "app-1")
        self.assertEqual(preparation_detail["item"]["plan_id"], "prep-1")
        self.assertEqual(generated["item"]["version_number"], 1)
        self.assertEqual(question_sets["items"][0]["question_set_id"], "question-set-1")
        self.assertEqual(current_question_set["item"]["question_set_id"], "question-set-1")
        self.assertEqual(question_set_detail["item"]["questions"][0]["category"], "technical")
        self.assertEqual(generated_questions["item"]["version_number"], 1)
        self.assertEqual(interview_stories["items"][0]["story_id"], "story-1")
        self.assertEqual(generated_stories["items"][0]["story_group_id"], "story-group-1")
        self.assertEqual(all_stories["items"][1]["status"], "approved")
        self.assertEqual(story_detail["item"]["title"], "Kubernetes migration")
        self.assertEqual(preparation_updated["item"]["version_number"], 1)
        self.assertEqual(updated_question_item["item"]["preparation_status"], "prepared")
        self.assertEqual(noted_question_item["item"]["question_id"], "question-1-1")
        self.assertEqual(updated_story_item["item"]["story_id"], "story-1")
        self.assertEqual(approved_story_item["item"]["status"], "approved")
        self.assertEqual(archived_story_item["item"]["story_id"], "story-1")
        self.assertEqual(regenerated_story_item["item"]["version_number"], 2)
        self.assertEqual(regenerated_plan["item"]["version_number"], 2)
        self.assertEqual(regenerated_questions["item"]["version_number"], 2)
        self.assertEqual(created["item"]["interview_type"], "technical")
        self.assertEqual(updated["item"]["interview_status"], "completed")
        self.assertEqual(deleted["item"]["interview_id"], "interview-1")

    async def test_interview_routes_raise_not_found_and_validation(self) -> None:
        service = SimpleNamespace(
            get_interview=AsyncMock(return_value=None),
            get_preparation=AsyncMock(return_value=None),
            list_question_sets=AsyncMock(side_effect=ValueError("Unknown interview workspace.")),
            get_current_question_set=AsyncMock(return_value=None),
            get_question_set=AsyncMock(return_value=None),
            prepare_interview=AsyncMock(side_effect=ValueError("Unknown interview workspace.")),
            update_preparation=AsyncMock(side_effect=ValueError("No preparation plan exists for this interview yet.")),
            regenerate_preparation=AsyncMock(side_effect=ValueError("Unknown interview workspace.")),
            generate_question_set=AsyncMock(side_effect=ValueError("No preparation plan exists for this interview yet.")),
            regenerate_question_set=AsyncMock(side_effect=ValueError("Unknown interview workspace.")),
            update_question=AsyncMock(side_effect=ValueError("Unsupported interview question priority.")),
            add_question_note=AsyncMock(side_effect=ValueError("Unknown interview question.")),
            list_interview_stories=AsyncMock(side_effect=ValueError("Unknown interview workspace.")),
            generate_stories=AsyncMock(side_effect=ValueError("No question set exists for this interview yet.")),
            list_stories=AsyncMock(return_value=[]),
            get_story=AsyncMock(return_value=None),
            update_story=AsyncMock(side_effect=ValueError("Unknown interview story.")),
            approve_story=AsyncMock(side_effect=ValueError("Unknown interview story.")),
            archive_story=AsyncMock(side_effect=ValueError("Unknown interview story.")),
            regenerate_story=AsyncMock(side_effect=ValueError("Unknown interview story.")),
            create_interview=AsyncMock(side_effect=ValueError("Unknown application package.")),
            update_interview=AsyncMock(side_effect=ValueError("Unknown interview workspace.")),
            delete_interview=AsyncMock(side_effect=ValueError("Unknown interview workspace.")),
        )
        with patch("app.main.build_interview_intelligence_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ):
            with self.assertRaises(Exception) as missing_detail:
                await current_user_interview("missing", _user())
            with self.assertRaises(Exception) as missing_preparation:
                await current_user_interview_preparation("missing", _user())
            with self.assertRaises(Exception) as missing_question_sets:
                await current_user_interview_question_sets("missing", _user())
            with self.assertRaises(Exception) as missing_current_question_set:
                await current_user_interview_current_question_set("missing", _user())
            with self.assertRaises(Exception) as missing_question_set_detail:
                await current_user_interview_question_set("missing", _user())
            with self.assertRaises(Exception) as missing_prepare:
                await prepare_current_user_interview("missing", _user())
            with self.assertRaises(Exception) as missing_generate_questions:
                await generate_current_user_interview_questions("missing", _user())
            with self.assertRaises(Exception) as missing_story_list:
                await current_user_interview_stories("missing", _user())
            with self.assertRaises(Exception) as missing_story_generate:
                await generate_current_user_interview_stories("missing", _user())
            stories = await current_user_stories(user=_user(), application_id=None, interview_id=None, status_value=None)
            with self.assertRaises(Exception) as missing_story_detail:
                await current_user_story("missing-story", _user())
            with self.assertRaises(Exception) as missing_preparation_update:
                await update_current_user_interview_preparation(
                    "missing",
                    InterviewPreparationUpdatePayload(status="updated"),
                    _user(),
                )
            with self.assertRaises(Exception) as invalid_question_update:
                await update_current_user_interview_question(
                    "missing-question",
                    InterviewQuestionUpdatePayload(priority="bad"),
                    _user(),
                )
            with self.assertRaises(Exception) as missing_question_note:
                await add_current_user_interview_question_note(
                    "missing-question",
                    InterviewQuestionNotePayload(body="x"),
                    _user(),
                )
            with self.assertRaises(Exception) as missing_story_update:
                await update_current_user_story("missing-story", InterviewStoryUpdatePayload(status="review"), _user())
            with self.assertRaises(Exception) as missing_story_approve:
                await approve_current_user_story("missing-story", _user())
            with self.assertRaises(Exception) as missing_story_archive:
                await archive_current_user_story("missing-story", _user())
            with self.assertRaises(Exception) as missing_story_regenerate:
                await regenerate_current_user_story("missing-story", _user())
            with self.assertRaises(Exception) as missing_preparation_regenerate:
                await regenerate_current_user_interview_preparation("missing", _user())
            with self.assertRaises(Exception) as missing_questions_regenerate:
                await regenerate_current_user_interview_questions("missing", _user())
            with self.assertRaises(Exception) as missing_create:
                await create_current_user_interview(
                    "missing-app",
                    InterviewCreatePayload(
                        interview_type="technical",
                        interview_round="",
                        interview_status="planned",
                        scheduled_start_at="",
                        scheduled_end_at="",
                        timezone="UTC",
                        meeting_url="",
                        recruiter_name="",
                        recruiter_email="",
                        recruiter_contact_id="",
                        notes="",
                        preparation_status="",
                        interviewers=[],
                        preparation_checklist=[],
                        source="manual",
                        metadata={},
                    ),
                    _user(),
                )
            with self.assertRaises(Exception) as missing_update:
                await update_current_user_interview(
                    "missing",
                    InterviewUpdatePayload(
                        interview_type=None,
                        interview_round=None,
                        interview_status=None,
                        scheduled_start_at=None,
                        scheduled_end_at=None,
                        timezone=None,
                        meeting_url=None,
                        recruiter_name=None,
                        recruiter_email=None,
                        recruiter_contact_id=None,
                        notes="x",
                        preparation_status=None,
                        interviewers=None,
                        preparation_checklist=None,
                        source=None,
                        metadata=None,
                    ),
                    _user(),
                )
            with self.assertRaises(Exception) as missing_delete:
                await delete_current_user_interview("missing", _user())

        self.assertEqual(getattr(missing_detail.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_preparation.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_question_sets.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_current_question_set.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_question_set_detail.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_prepare.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_generate_questions.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_story_list.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_story_generate.exception, "status_code", None), 404)
        self.assertEqual(stories["items"], [])
        self.assertEqual(getattr(missing_story_detail.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_preparation_update.exception, "status_code", None), 404)
        self.assertEqual(getattr(invalid_question_update.exception, "status_code", None), 400)
        self.assertEqual(getattr(missing_question_note.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_story_update.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_story_approve.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_story_archive.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_story_regenerate.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_preparation_regenerate.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_questions_regenerate.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_create.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_update.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_delete.exception, "status_code", None), 404)


if __name__ == "__main__":
    unittest.main()
