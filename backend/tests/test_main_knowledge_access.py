from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

if "asyncpg" not in sys.modules:
    asyncpg_stub = types.ModuleType("asyncpg")

    class _UniqueViolationError(Exception):
        pass

    asyncpg_stub.UniqueViolationError = _UniqueViolationError
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "jwt" not in sys.modules:
    jwt_stub = types.ModuleType("jwt")

    class _PyJWTError(Exception):
        pass

    jwt_stub.PyJWTError = _PyJWTError
    jwt_stub.InvalidTokenError = _PyJWTError
    jwt_stub.encode = lambda payload, secret, algorithm=None: "stub-token"
    jwt_stub.decode = lambda token, secret, algorithms=None, issuer=None: {"type": "access", "sub": "user-1"}
    sys.modules["jwt"] = jwt_stub

if "fastapi" not in sys.modules:
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

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

    pydantic_stub.BaseModel = _BaseModel
    pydantic_stub.Field = lambda default=None, **kwargs: default
    sys.modules["pydantic"] = pydantic_stub

if "argon2" not in sys.modules:
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

if "pypdf" not in sys.modules:
    pypdf_stub = types.ModuleType("pypdf")

    class _PdfReader:
        def __init__(self, *args, **kwargs):
            self.pages = []

    pypdf_stub.PdfReader = _PdfReader
    sys.modules["pypdf"] = pypdf_stub

from app.domain import KnowledgeAlias, KnowledgeEntity, KnowledgeTimelineEvent, OnboardingStatus, UserAccount
from app.main import (
    KnowledgeAliasPayload,
    ProfileEvolutionAnswerPayload,
    ReviewDecisionPayload,
    approve_current_user_profile_evolution_change,
    admin_knowledge_schema,
    admin_knowledge_timeline,
    admin_register_knowledge_alias,
    current_user_profile_evolution_changes,
    current_user_knowledge_metrics,
    current_user_knowledge_profile,
    current_user_profile_evolution_next_question,
    current_user_profile_evolution_state,
    reject_current_user_profile_evolution_change,
    submit_current_user_profile_evolution_answer,
)
from app.profile_evolution import (
    ExtractedFactCandidate,
    ProfileEvolutionQuestion,
    ProfileEvolutionSession,
    ProfileEvolutionSubmissionResult,
)


def _user(*, role: str = "user") -> UserAccount:
    return UserAccount(
        id="user-1",
        email="user@example.com",
        role=role,  # type: ignore[arg-type]
        full_name="Abhishek",
        telegram_chat_id=None,
        country="US",
        profile={},
        preferences={},
        onboarding=OnboardingStatus(progress_percent=0, steps=[]),
    )


class MainKnowledgeAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_user_knowledge_profile_returns_serialized_entities(self) -> None:
        service = SimpleNamespace(
            get_user_profile=AsyncMock(
                return_value={
                    "technology": [
                        KnowledgeEntity(
                            id="entity-1",
                            user_id="user-1",
                            entity_type="technology",
                            canonical_name="Python",
                            content={"label": "Python"},
                            source="resume_upload",
                            confidence=1.0,
                            evidence_ids=["evidence-1"],
                            version=1,
                            status="approved",
                            created_at="2026-07-20T00:00:00+00:00",
                            updated_at="2026-07-20T00:00:00+00:00",
                        )
                    ]
                }
            )
        )
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await current_user_knowledge_profile(_user())
        self.assertEqual(payload["items"]["technology"][0]["canonical_name"], "Python")

    async def test_current_user_knowledge_metrics_returns_service_payload(self) -> None:
        service = SimpleNamespace(get_metrics=AsyncMock(return_value={"schema_version": 1, "entities": 5}))
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await current_user_knowledge_metrics(_user())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["entities"], 5)

    async def test_admin_register_knowledge_alias_returns_serialized_alias(self) -> None:
        alias = KnowledgeAlias(
            id="alias-1",
            user_id="user-2",
            entity_type="technology",
            alias_value="ReactJS",
            normalized_alias="reactjs",
            canonical_name="React",
            confidence=1.0,
            is_manual_override=True,
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:00:00+00:00",
        )
        service = SimpleNamespace(register_manual_alias=AsyncMock(return_value=alias))
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await admin_register_knowledge_alias(
                "user-2",
                KnowledgeAliasPayload(entity_type="technology", alias_value="ReactJS", canonical_name="React"),
                _user(role="admin"),
            )
        self.assertEqual(payload["item"]["canonical_name"], "React")
        service.register_manual_alias.assert_awaited_once()

    async def test_admin_knowledge_timeline_returns_serialized_events(self) -> None:
        service = SimpleNamespace(
            get_timeline=AsyncMock(
                return_value=[
                    KnowledgeTimelineEvent(
                        id="timeline-1",
                        user_id="user-3",
                        event_type="ResumeUploaded",
                        title="Resume uploaded: Backend Resume",
                        entity_id=None,
                        evidence_id=None,
                        payload={"resume_id": "resume-1"},
                        created_at="2026-07-20T00:00:00+00:00",
                    )
                ]
            )
        )
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await admin_knowledge_timeline("user-3", 25, _user(role="admin"))
        self.assertEqual(payload["items"][0]["event_type"], "ResumeUploaded")

    async def test_admin_knowledge_schema_returns_schema_info(self) -> None:
        service = SimpleNamespace(get_schema_info=AsyncMock(return_value={"schema_name": "knowledge_platform", "version": 1}))
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await admin_knowledge_schema(_user(role="admin"))
        self.assertEqual(payload["version"], 1)

    async def test_current_user_profile_evolution_state_returns_session_and_topics(self) -> None:
        session = ProfileEvolutionSession(
            id="session-1",
            user_id="user-1",
            current_topic="architecture",
            completed_topics=["project"],
            pending_topics=["architecture", "scale"],
            skipped_topics=[],
            confidence=0.82,
            extracted_entities=[{"topic": "project", "entity_type": "project", "canonical_name": "Scheduler Platform"}],
            topic_progress={},
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:05:00+00:00",
        )
        service = SimpleNamespace(
            get_state=AsyncMock(return_value=session),
            get_remaining_topics=AsyncMock(return_value=["architecture", "scale"]),
        )
        with patch("app.main.build_profile_evolution_service", return_value=service):
            payload = await current_user_profile_evolution_state(_user())
        self.assertEqual(payload["session"]["current_topic"], "architecture")
        self.assertEqual(payload["remaining_topics"], ["architecture", "scale"])

    async def test_current_user_profile_evolution_next_question_returns_serialized_question(self) -> None:
        question = ProfileEvolutionQuestion(
            id="question-1",
            topic="architecture",
            prompt="Tell me about the architecture of the largest system you've built.",
            rationale="Architecture is the highest-value remaining gap.",
            missing_fields=["architecture", "cloud", "database"],
            confidence=0.72,
        )
        service = SimpleNamespace(get_next_question=AsyncMock(return_value=question))
        with patch("app.main.build_profile_evolution_service", return_value=service):
            payload = await current_user_profile_evolution_next_question(_user())
        self.assertEqual(payload["item"]["topic"], "architecture")
        self.assertIn("cloud", payload["item"]["missing_fields"])

    async def test_submit_profile_evolution_answer_returns_staged_result(self) -> None:
        session = ProfileEvolutionSession(
            id="session-1",
            user_id="user-1",
            current_topic=None,
            completed_topics=["architecture"],
            pending_topics=["scale"],
            skipped_topics=[],
            confidence=0.9,
            extracted_entities=[],
            topic_progress={},
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:06:00+00:00",
        )
        result = ProfileEvolutionSubmissionResult(
            session=session,
            extracted_facts=[
                ExtractedFactCandidate(
                    topic="architecture",
                    entity_type="technology",
                    canonical_name="AWS",
                    content={"label": "AWS"},
                    reason="Conversation answer referenced AWS.",
                    confidence=0.9,
                    extracted_fields={"cloud": "AWS"},
                )
            ],
            staged_version_ids=["version-1"],
            knowledge_gain={"architecture": 8, "technology": 2, "total": 10},
            next_question=ProfileEvolutionQuestion(
                id="question-2",
                topic="scale",
                prompt="What is the highest-scale system you've worked on, and how large was it?",
                rationale="Scale still needs stronger detail.",
                missing_fields=["scale", "traffic"],
                confidence=0.78,
            ),
        )
        service = SimpleNamespace(submit_answer=AsyncMock(return_value=result))
        with patch("app.main.build_profile_evolution_service", return_value=service):
            payload = await submit_current_user_profile_evolution_answer(
                ProfileEvolutionAnswerPayload(
                    answer="I used AWS for the platform.",
                    topic="architecture",
                    question_id="question-1",
                    question_prompt="Tell me about the architecture of the largest system you've built.",
                ),
                _user(),
            )
        self.assertEqual(payload["staged_version_ids"], ["version-1"])
        self.assertEqual(payload["extracted_facts"][0]["canonical_name"], "AWS")
        self.assertEqual(payload["next_question"]["topic"], "scale")
        submitted_question = service.submit_answer.await_args.kwargs["question"]
        self.assertEqual(submitted_question.id, "question-1")
        self.assertEqual(submitted_question.prompt, "Tell me about the architecture of the largest system you've built.")

    async def test_current_user_profile_evolution_changes_returns_review_queue(self) -> None:
        version = SimpleNamespace(
            to_dict=lambda: {"id": "version-1", "source": "profile_evolution"},
            entity_id="entity-1",
            evidence_ids=["evidence-1"],
            new_content={"profile_evolution_session_id": "session-1"},
        )
        entity = KnowledgeEntity(
            id="entity-1",
            user_id="user-1",
            entity_type="project",
            canonical_name="Scheduler Platform",
            content={"summary": "Built a scheduler."},
            source="profile_evolution",
            confidence=0.9,
            evidence_ids=["evidence-1"],
            version=1,
            status="approved",
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:00:00+00:00",
        )
        evidence = SimpleNamespace(to_dict=lambda: {"id": "evidence-1", "source_type": "conversation"})
        service = SimpleNamespace(
            list_suggested_changes=AsyncMock(return_value=[version]),
            get_entity=AsyncMock(return_value=entity),
            rank_evidence=AsyncMock(return_value=[evidence]),
        )
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await current_user_profile_evolution_changes(limit=50, session_id="session-1", user=_user())
        self.assertEqual(payload["items"][0]["version"]["id"], "version-1")
        self.assertEqual(payload["items"][0]["entity"]["canonical_name"], "Scheduler Platform")
        self.assertEqual(payload["items"][0]["evidence"][0]["source_type"], "conversation")

    async def test_approve_profile_evolution_change_returns_updated_entity(self) -> None:
        version = SimpleNamespace(source="profile_evolution", agent_name="profile_evolution")
        entity = KnowledgeEntity(
            id="entity-1",
            user_id="user-1",
            entity_type="technology",
            canonical_name="AWS",
            content={"label": "AWS"},
            source="profile_evolution",
            confidence=0.95,
            evidence_ids=["evidence-1"],
            version=1,
            status="approved",
            created_at="2026-07-20T00:00:00+00:00",
            updated_at="2026-07-20T00:00:00+00:00",
        )
        service = SimpleNamespace(
            get_change=AsyncMock(return_value=version),
            approve_change=AsyncMock(return_value=entity),
        )
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await approve_current_user_profile_evolution_change(
                "version-1",
                ReviewDecisionPayload(review_notes="Looks right."),
                _user(),
            )
        self.assertEqual(payload["item"]["status"], "approved")
        self.assertEqual(payload["item"]["entity"]["canonical_name"], "AWS")
        service.approve_change.assert_awaited_once()

    async def test_reject_profile_evolution_change_returns_rejected_version(self) -> None:
        rejected = SimpleNamespace(to_dict=lambda: {"id": "version-1", "status": "rejected", "review_notes": "Not accurate."})
        service = SimpleNamespace(
            get_change=AsyncMock(return_value=SimpleNamespace(source="profile_evolution", agent_name="profile_evolution")),
            reject_change=AsyncMock(return_value=rejected),
        )
        with patch("app.main.build_knowledge_platform_service", return_value=service):
            payload = await reject_current_user_profile_evolution_change(
                "version-1",
                ReviewDecisionPayload(review_notes="Not accurate."),
                _user(),
            )
        self.assertEqual(payload["item"]["status"], "rejected")
        service.reject_change.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
