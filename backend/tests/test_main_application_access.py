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

from app.domain import OnboardingStatus, UserAccount
from app.main import (
    ApplicationAnswerPayload,
    ApplicationArtifactPayload,
    ApplicationMetadataPayload,
    ApplicationNotePayload,
    ApplicationPackagePayload,
    ApplicationStatusPayload,
    ApplicationSubmitPayload,
    ApplicationTaskPayload,
    add_current_user_application_answer,
    add_current_user_application_artifact,
    add_current_user_application_note,
    build_current_user_application_package,
    current_user_application,
    current_user_application_answers,
    current_user_application_artifacts,
    current_user_applications,
    current_user_reusable_application_answers,
    submit_current_user_application,
    update_current_user_application_metadata,
    update_current_user_application_status,
    update_current_user_application_task,
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


def _application_record(*, status: str = "ready_to_apply") -> dict[str, object]:
    return {
        "application_id": "app-1",
        "user_id": "user-1",
        "job_id": "job-1",
        "resume_version_id": "rv-1",
        "status": status,
        "package_signature": "sig-1",
        "company": "Ramp",
        "title": "Staff Platform Engineer",
        "apply_url": "https://example.com/jobs/1/apply",
        "match_score": 95,
        "decision": "APPLY_NOW",
        "artifacts": [],
        "tasks": [],
        "notes": [],
        "answers": [],
        "structured_metadata": {},
        "submission": {},
        "timeline": [],
        "metadata": {},
        "created_at": "2026-07-20T00:00:00+00:00",
        "updated_at": "2026-07-20T00:00:00+00:00",
        "applied_at": None,
    }


class MainApplicationAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_user_applications_returns_items(self) -> None:
        service = SimpleNamespace(
            list_applications=AsyncMock(return_value=[SimpleNamespace(to_dict=lambda: _application_record())])
        )
        with patch("app.main.build_application_intelligence_service", return_value=service):
            payload = await current_user_applications(user=_user(), status=None)
        self.assertEqual(payload["items"][0]["company"], "Ramp")

    async def test_build_package_and_lookup_routes_return_items(self) -> None:
        record = SimpleNamespace(
            to_dict=lambda: _application_record(),
            application_id="app-1",
            job_id="job-1",
            resume_version_id="rv-1",
            status="ready_to_apply",
            company="Ramp",
            title="Staff Platform Engineer",
        )
        service = SimpleNamespace(
            build_application_package=AsyncMock(return_value=record),
            get_application=AsyncMock(return_value=record),
        )
        with patch("app.main.build_application_intelligence_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ) as audit_mock:
            payload = await build_current_user_application_package(
                "job-1",
                ApplicationPackagePayload(resume_version_id="rv-1", notes="ready"),
                _user(),
            )
            detail = await current_user_application("app-1", _user())
        self.assertEqual(payload["item"]["resume_version_id"], "rv-1")
        self.assertEqual(detail["item"]["application_id"], "app-1")
        audit_mock.assert_awaited_once()

    async def test_artifact_answer_metadata_submit_task_and_note_routes_return_items(self) -> None:
        record = SimpleNamespace(
            to_dict=lambda: _application_record(status="applied"),
            application_id="app-1",
            job_id="job-1",
            resume_version_id="rv-1",
            status="applied",
            company="Ramp",
            title="Staff Platform Engineer",
        )
        service = SimpleNamespace(
            list_application_artifacts=AsyncMock(return_value=[SimpleNamespace(to_dict=lambda: {"artifact_id": "artifact-1"})]),
            add_application_artifact=AsyncMock(return_value=record),
            list_application_answers=AsyncMock(return_value=[SimpleNamespace(to_dict=lambda: {"answer_id": "answer-1"})]),
            add_application_answer=AsyncMock(return_value=record),
            update_application_metadata=AsyncMock(return_value=record),
            submit_application=AsyncMock(return_value=record),
            update_application_task=AsyncMock(return_value=record),
            add_application_note=AsyncMock(return_value=record),
            list_reusable_answers=AsyncMock(return_value=[SimpleNamespace(to_dict=lambda: {"answer_id": "answer-1"})]),
        )
        with patch("app.main.build_application_intelligence_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ):
            artifacts = await current_user_application_artifacts("app-1", _user())
            artifact_mutation = await add_current_user_application_artifact(
                "app-1",
                ApplicationArtifactPayload(kind="confirmation", title="Submission confirmation"),
                _user(),
            )
            answers = await current_user_application_answers("app-1", _user())
            answer_mutation = await add_current_user_application_answer(
                "app-1",
                ApplicationAnswerPayload(question="Why here?", answer="Platform scale.", reusable=True),
                _user(),
            )
            metadata_mutation = await update_current_user_application_metadata(
                "app-1",
                ApplicationMetadataPayload(recruiter_name="Avery Chen", deadline="2026-07-25T17:00:00+00:00"),
                _user(),
            )
            submit_mutation = await submit_current_user_application(
                "app-1",
                ApplicationSubmitPayload(portal="Greenhouse", submitted_at="2026-07-21T18:00:00+00:00"),
                _user(),
            )
            task_mutation = await update_current_user_application_task(
                "app-1",
                "capture_confirmation",
                ApplicationTaskPayload(status="completed", detail="done"),
                _user(),
            )
            note_mutation = await add_current_user_application_note(
                "app-1",
                ApplicationNotePayload(body="follow up next week", note_type="follow_up"),
                _user(),
            )
            reusable = await current_user_reusable_application_answers(user=_user(), include_sensitive=False)
        self.assertEqual(artifacts["items"][0]["artifact_id"], "artifact-1")
        self.assertEqual(artifact_mutation["item"]["application_id"], "app-1")
        self.assertEqual(answers["items"][0]["answer_id"], "answer-1")
        self.assertEqual(answer_mutation["item"]["status"], "applied")
        self.assertEqual(metadata_mutation["item"]["job_id"], "job-1")
        self.assertEqual(submit_mutation["item"]["status"], "applied")
        self.assertEqual(task_mutation["item"]["company"], "Ramp")
        self.assertEqual(note_mutation["item"]["resume_version_id"], "rv-1")
        self.assertEqual(reusable["items"][0]["answer_id"], "answer-1")

    async def test_status_route_returns_item_for_post_submit_updates(self) -> None:
        record = SimpleNamespace(
            to_dict=lambda: _application_record(status="interviewing"),
            application_id="app-1",
            job_id="job-1",
            resume_version_id="rv-1",
            status="interviewing",
            company="Ramp",
            title="Staff Platform Engineer",
        )
        service = SimpleNamespace(update_application_status=AsyncMock(return_value=record))
        with patch("app.main.build_application_intelligence_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ):
            payload = await update_current_user_application_status(
                "app-1",
                ApplicationStatusPayload(status="interviewing", notes="screen set"),
                _user(),
            )
        self.assertEqual(payload["item"]["status"], "interviewing")

    async def test_current_user_application_raises_not_found(self) -> None:
        service = SimpleNamespace(get_application=AsyncMock(return_value=None))
        with patch("app.main.build_application_intelligence_service", return_value=service):
            with self.assertRaises(Exception) as context:
                await current_user_application("missing", _user())
        self.assertEqual(getattr(context.exception, "status_code", None), 404)


if __name__ == "__main__":
    unittest.main()
