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
    RecruiterDraftGeneratePayload,
    RecruiterDraftUpdatePayload,
    RecruiterMessageImportItemPayload,
    RecruiterMessageImportPayload,
    current_user_application_communication,
    current_user_application_communication_health,
    current_user_application_conversation_state,
    current_user_recruiter_contact,
    current_user_recruiter_contacts,
    current_user_recruiter_drafts,
    current_user_recruiter_message,
    current_user_recruiter_message_summary,
    current_user_recruiter_message_suggestions,
    current_user_recruiter_messages,
    current_user_recruiter_thread,
    current_user_recruiter_thread_summary,
    current_user_recruiter_threads,
    generate_current_user_recruiter_draft,
    import_current_user_recruiter_messages,
    update_current_user_recruiter_draft,
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


def _message_dict() -> dict[str, object]:
    return {
        "message_id": "message-1",
        "thread_id": "thread-1",
        "user_id": "user-1",
        "application_id": "app-1",
        "recruiter": {"display_name": "Avery Chen", "email": "avery@example.com"},
        "sender": "avery@example.com",
        "recipients": ["user@example.com"],
        "subject": "Interview invitation",
        "body_reference": "import://message-1",
        "body_preview": "Preview",
        "received_at": "2026-07-21T16:00:00+00:00",
        "message_type": "interview_invitation",
        "confidence": 0.94,
        "source": "manual_import",
        "timeline_id": "event-1",
        "company": "Ramp",
        "job_title": "Staff Platform Engineer",
        "matched": True,
        "match_confidence": 0.95,
        "match_reason": "recruiter email matched",
        "classification_reason": "interview invitation language detected",
        "suggested_actions": ["Reply within 24 hours"],
        "metadata": {},
        "created_at": "2026-07-21T16:00:00+00:00",
        "updated_at": "2026-07-21T16:00:00+00:00",
    }


def _thread_dict() -> dict[str, object]:
    return {
        "thread_id": "thread-1",
        "user_id": "user-1",
        "application_id": "app-1",
        "recruiter": {"display_name": "Avery Chen", "email": "avery@example.com"},
        "subject": "Interview invitation",
        "company": "Ramp",
        "job_title": "Staff Platform Engineer",
        "last_message_id": "message-1",
        "last_message_at": "2026-07-21T16:00:00+00:00",
        "message_count": 1,
        "source": "manual_import",
        "confidence": 0.95,
        "conversation_status": "waiting_for_candidate",
        "pending_action": "Reply to recruiter",
        "response_overdue": False,
        "created_at": "2026-07-21T16:00:00+00:00",
        "updated_at": "2026-07-21T16:00:00+00:00",
        "metadata": {},
    }


def _summary_dict(scope_type: str, scope_id: str) -> dict[str, object]:
    return {
        "summary_id": f"summary-{scope_type}-{scope_id}",
        "scope_type": scope_type,
        "scope_id": scope_id,
        "thread_id": "thread-1",
        "application_id": "app-1",
        "message_id": "message-1",
        "title": "Interview invitation",
        "summary": "A recruiter reached out about the interview process.",
        "communication_objective": "Reply to the recruiter",
        "key_points": ["Waiting on: candidate"],
        "pending_action": "Reply to recruiter",
        "risks": [],
        "evidence": [{"source_type": "recruiter_message", "source_id": "message-1", "label": "Interview invitation", "excerpt": "Preview"}],
        "assumptions": [],
        "confidence": 0.92,
        "strategy_version": "recruiter-assistant.v1",
        "generated_at": "2026-07-21T16:00:00+00:00",
    }


def _draft_dict(version_number: int = 1, *, draft_id: str = "draft-1", parent_draft_id: str = "", status: str = "generated") -> dict[str, object]:
    return {
        "draft_id": draft_id,
        "draft_group_id": "group-1",
        "version_number": version_number,
        "user_id": "user-1",
        "thread_id": "thread-1",
        "draft_kind": "reply",
        "tone": "professional",
        "status": status,
        "intended_recipient": "Avery Chen",
        "intended_recipient_email": "avery@example.com",
        "communication_objective": "Reply to the recruiter",
        "subject": "Re: Interview invitation",
        "body": "Hi Avery,\n\nThanks for reaching out.\n\nBest,",
        "confidence": 0.9,
        "explanation": "Grounded in the latest recruiter message.",
        "strategy_version": "recruiter-assistant.v1",
        "model_key": "deterministic_template",
        "application_id": "app-1",
        "source_message_id": "message-1",
        "parent_draft_id": parent_draft_id,
        "evidence": [{"source_type": "recruiter_message", "source_id": "message-1", "label": "Interview invitation", "excerpt": "Preview"}],
        "assumptions": [],
        "user_edited": version_number > 1,
        "generated_at": "2026-07-21T16:00:00+00:00",
        "created_at": "2026-07-21T16:00:00+00:00",
        "updated_at": "2026-07-21T16:00:00+00:00",
    }


class MainRecruiterAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_recruiter_routes_return_items(self) -> None:
        message = SimpleNamespace(to_dict=lambda: _message_dict(), message_id="message-1", application_id="app-1", source="manual_import")
        thread = SimpleNamespace(to_dict=_thread_dict)
        contact = SimpleNamespace(to_dict=lambda: {"contact": {"contact_id": "contact-1", "email": "avery@example.com"}})
        suggestion = SimpleNamespace(to_dict=lambda: {"action_type": "reply_to_recruiter", "label": "Reply to recruiter"})
        message_summary = SimpleNamespace(to_dict=lambda: _summary_dict("message", "message-1"))
        thread_summary = SimpleNamespace(to_dict=lambda: _summary_dict("thread", "thread-1"))
        draft_payload = _draft_dict()
        updated_draft_payload = _draft_dict(2, draft_id="draft-2", parent_draft_id="draft-1", status="approved")
        draft = SimpleNamespace(to_dict=lambda: draft_payload, **draft_payload)
        updated_draft = SimpleNamespace(to_dict=lambda: updated_draft_payload, **updated_draft_payload)
        state = SimpleNamespace(to_dict=lambda: {"state": "waiting_for_candidate", "waiting_on": "candidate"})
        health = SimpleNamespace(to_dict=lambda: {"status": "healthy"})
        service = SimpleNamespace(
            list_messages=AsyncMock(return_value=[message]),
            list_threads=AsyncMock(return_value=[thread]),
            get_thread=AsyncMock(return_value=thread),
            get_thread_summary=AsyncMock(return_value=thread_summary),
            list_contacts=AsyncMock(return_value=[contact]),
            get_contact=AsyncMock(return_value=contact),
            get_message=AsyncMock(return_value=message),
            get_message_summary=AsyncMock(return_value=message_summary),
            get_message_suggestions=AsyncMock(return_value=[suggestion]),
            list_drafts=AsyncMock(return_value=[draft]),
            generate_draft=AsyncMock(return_value=draft),
            update_draft=AsyncMock(return_value=updated_draft),
            import_messages=AsyncMock(return_value=[message]),
            get_application_conversation_state=AsyncMock(return_value=state),
            get_application_communication_health=AsyncMock(return_value=health),
            get_application_communication=AsyncMock(
                return_value={
                    "application_id": "app-1",
                    "summary": {"last_message_id": "message-1"},
                    "conversation_state": {"state": "waiting_for_candidate"},
                    "health": {"status": "healthy"},
                    "suggestions": [{"action_type": "reply_to_recruiter"}],
                    "messages": [],
                    "threads": [],
                    "events": [],
                    "contacts": [],
                    "activity_timeline": [],
                }
            ),
        )
        with patch("app.main.build_recruiter_intelligence_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ):
            messages = await current_user_recruiter_messages(user=_user(), application_id=None, message_type=None, thread_id=None, matched_only=False)
            threads = await current_user_recruiter_threads(user=_user(), application_id=None)
            thread_detail = await current_user_recruiter_thread("thread-1", _user())
            thread_summary_payload = await current_user_recruiter_thread_summary("thread-1", _user())
            contacts = await current_user_recruiter_contacts(user=_user())
            contact_detail = await current_user_recruiter_contact("contact-1", _user())
            detail = await current_user_recruiter_message("message-1", _user())
            message_summary_payload = await current_user_recruiter_message_summary("message-1", _user())
            suggestions = await current_user_recruiter_message_suggestions("message-1", _user())
            drafts = await current_user_recruiter_drafts(user=_user(), thread_id="thread-1", application_id=None, latest_only=True)
            generated = await generate_current_user_recruiter_draft(
                RecruiterDraftGeneratePayload(thread_id="thread-1", draft_kind="reply", tone="professional", source_message_id="message-1"),
                _user(),
            )
            updated = await update_current_user_recruiter_draft(
                "draft-1",
                RecruiterDraftUpdatePayload(subject="Re: Interview invitation", body="Updated", status="approved"),
                _user(),
            )
            imported = await import_current_user_recruiter_messages(
                RecruiterMessageImportPayload(
                    items=[
                        RecruiterMessageImportItemPayload(
                            recruiter_email="avery@example.com",
                            sender_email="avery@example.com",
                            subject="Interview invitation",
                        )
                    ]
                ),
                _user(),
            )
            conversation_state = await current_user_application_conversation_state("app-1", _user())
            communication_health = await current_user_application_communication_health("app-1", _user())
            communication = await current_user_application_communication("app-1", _user())
        self.assertEqual(messages["items"][0]["message_id"], "message-1")
        self.assertEqual(threads["items"][0]["thread_id"], "thread-1")
        self.assertEqual(thread_detail["item"]["conversation_status"], "waiting_for_candidate")
        self.assertEqual(thread_summary_payload["item"]["scope_type"], "thread")
        self.assertEqual(contacts["items"][0]["contact"]["email"], "avery@example.com")
        self.assertEqual(contact_detail["item"]["contact"]["contact_id"], "contact-1")
        self.assertEqual(detail["item"]["application_id"], "app-1")
        self.assertEqual(message_summary_payload["item"]["scope_type"], "message")
        self.assertEqual(suggestions["items"][0]["action_type"], "reply_to_recruiter")
        self.assertEqual(drafts["items"][0]["draft_id"], "draft-1")
        self.assertEqual(generated["item"]["draft_id"], "draft-1")
        self.assertEqual(updated["item"]["version_number"], 2)
        self.assertEqual(imported["items"][0]["message_type"], "interview_invitation")
        self.assertEqual(conversation_state["item"]["state"], "waiting_for_candidate")
        self.assertEqual(communication_health["item"]["status"], "healthy")
        self.assertEqual(communication["summary"]["last_message_id"], "message-1")

    async def test_recruiter_message_route_raises_not_found(self) -> None:
        service = SimpleNamespace(get_message=AsyncMock(return_value=None))
        with patch("app.main.build_recruiter_intelligence_service", return_value=service):
            with self.assertRaises(Exception) as context:
                await current_user_recruiter_message("missing", _user())
        self.assertEqual(getattr(context.exception, "status_code", None), 404)

    async def test_recruiter_contact_and_analysis_routes_raise_not_found(self) -> None:
        service = SimpleNamespace(
            get_thread=AsyncMock(return_value=None),
            get_thread_summary=AsyncMock(side_effect=ValueError("Unknown recruiter thread.")),
            get_contact=AsyncMock(return_value=None),
            get_message_summary=AsyncMock(side_effect=ValueError("Unknown recruiter message.")),
            get_message_suggestions=AsyncMock(side_effect=ValueError("Unknown recruiter message.")),
            generate_draft=AsyncMock(side_effect=ValueError("Unknown recruiter thread.")),
            update_draft=AsyncMock(side_effect=ValueError("Unknown recruiter communication draft.")),
            get_application_conversation_state=AsyncMock(side_effect=ValueError("Unknown application package.")),
            get_application_communication_health=AsyncMock(side_effect=ValueError("Unknown application package.")),
        )
        with patch("app.main.build_recruiter_intelligence_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ):
            with self.assertRaises(Exception) as missing_thread:
                await current_user_recruiter_thread("missing-thread", _user())
            with self.assertRaises(Exception) as missing_thread_summary:
                await current_user_recruiter_thread_summary("missing-thread", _user())
            with self.assertRaises(Exception) as missing_contact:
                await current_user_recruiter_contact("missing-contact", _user())
            with self.assertRaises(Exception) as missing_message_summary:
                await current_user_recruiter_message_summary("missing-message", _user())
            with self.assertRaises(Exception) as missing_suggestions:
                await current_user_recruiter_message_suggestions("missing-message", _user())
            with self.assertRaises(Exception) as missing_generated_draft:
                await generate_current_user_recruiter_draft(
                    RecruiterDraftGeneratePayload(thread_id="missing-thread"),
                    _user(),
                )
            with self.assertRaises(Exception) as missing_updated_draft:
                await update_current_user_recruiter_draft("missing-draft", RecruiterDraftUpdatePayload(), _user())
            with self.assertRaises(Exception) as missing_state:
                await current_user_application_conversation_state("missing-app", _user())
            with self.assertRaises(Exception) as missing_health:
                await current_user_application_communication_health("missing-app", _user())
        self.assertEqual(getattr(missing_thread.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_thread_summary.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_contact.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_message_summary.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_suggestions.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_generated_draft.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_updated_draft.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_state.exception, "status_code", None), 404)
        self.assertEqual(getattr(missing_health.exception, "status_code", None), 404)


if __name__ == "__main__":
    unittest.main()
