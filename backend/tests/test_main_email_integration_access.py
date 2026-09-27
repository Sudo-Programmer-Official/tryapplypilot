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
    RecruiterProviderConnectPayload,
    RecruiterProviderOAuthCompletePayload,
    RecruiterProviderOAuthStartPayload,
    RecruiterSyncPayload,
    complete_connect_current_user_gmail,
    connect_current_user_gmail,
    current_user_recruiter_provider_status,
    current_user_recruiter_providers,
    current_user_recruiter_sync_history,
    disconnect_current_user_gmail,
    start_connect_current_user_gmail,
    sync_current_user_recruiter_provider,
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


class MainEmailIntegrationAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_connection_and_sync_routes_return_items(self) -> None:
        connection = SimpleNamespace(
            to_dict=lambda: {
                "connection_id": "conn-1",
                "user_id": "user-1",
                "provider": "gmail",
                "account_email": "user@example.com",
                "status": "connected",
                "token_configured": True,
            },
            connection_id="conn-1",
            user_id="user-1",
            provider="gmail",
            account_email="user@example.com",
            scopes=["scope-1"],
        )
        status_item = SimpleNamespace(
            to_dict=lambda: {"provider": "gmail", "status": "connected", "last_imported_count": 1}
        )
        oauth_request = SimpleNamespace(
            to_dict=lambda: {
                "provider": "gmail",
                "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?state=signed-state",
                "expires_in_seconds": 900,
                "scopes": [],
            }
        )
        sync_run = SimpleNamespace(
            to_dict=lambda: {"sync_run_id": "run-1", "provider": "gmail", "imported_count": 1, "duplicate_count": 0, "error_count": 0},
            connection_id="conn-1",
            provider="gmail",
            imported_count=1,
            duplicate_count=0,
            error_count=0,
        )
        service = SimpleNamespace(
            begin_provider_oauth=AsyncMock(return_value=oauth_request),
            complete_provider_oauth=AsyncMock(return_value=connection),
            connect_provider=AsyncMock(return_value=connection),
            disconnect_provider=AsyncMock(return_value=connection),
            list_connections=AsyncMock(return_value=[connection]),
            list_provider_statuses=AsyncMock(return_value=[status_item]),
            sync=AsyncMock(return_value=[sync_run]),
            list_sync_history=AsyncMock(return_value=[sync_run]),
        )
        with patch("app.main.build_email_integration_service", return_value=service), patch(
            "app.main.record_audit_event",
            AsyncMock(return_value=None),
        ), patch(
            "app.main.get_user_by_id",
            AsyncMock(return_value=_user()),
        ):
            connected = await connect_current_user_gmail(
                RecruiterProviderConnectPayload(
                    account_email="user@example.com",
                    token_reference="vault://gmail/user-1",
                ),
                _user(),
            )
            started = await start_connect_current_user_gmail(RecruiterProviderOAuthStartPayload(), _user())
            completed = await complete_connect_current_user_gmail(
                RecruiterProviderOAuthCompletePayload(code="oauth-code", state="signed-state"),
                _user(),
            )
            disconnected = await disconnect_current_user_gmail(_user())
            providers = await current_user_recruiter_providers(_user())
            statuses = await current_user_recruiter_provider_status(_user())
            synced = await sync_current_user_recruiter_provider(RecruiterSyncPayload(provider="gmail"), _user())
            history = await current_user_recruiter_sync_history(provider="gmail", limit=20, user=_user())
        self.assertEqual(connected["item"]["provider"], "gmail")
        self.assertIn("accounts.google.com", started["item"]["authorization_url"])
        self.assertEqual(completed["item"]["connection_id"], "conn-1")
        service.complete_provider_oauth.assert_awaited_once_with(
            "gmail",
            user_id=_user().id,
            state_token="signed-state",
            code="oauth-code",
        )
        self.assertEqual(disconnected["item"]["account_email"], "user@example.com")
        self.assertEqual(providers["items"][0]["connection_id"], "conn-1")
        self.assertEqual(statuses["items"][0]["last_imported_count"], 1)
        self.assertEqual(synced["items"][0]["sync_run_id"], "run-1")
        self.assertEqual(history["items"][0]["provider"], "gmail")

    async def test_provider_routes_raise_expected_errors(self) -> None:
        service = SimpleNamespace(
            connect_provider=AsyncMock(side_effect=ValueError("Gmail connections require a secure token reference.")),
            disconnect_provider=AsyncMock(side_effect=ValueError("Unknown email provider connection.")),
            sync=AsyncMock(side_effect=ValueError("No connected email providers are available to sync.")),
        )
        with patch("app.main.build_email_integration_service", return_value=service):
            with self.assertRaises(Exception) as connect_error:
                await connect_current_user_gmail(
                    RecruiterProviderConnectPayload(account_email="user@example.com", token_reference="vault://unknown"),
                    _user(),
                )
            with self.assertRaises(Exception) as disconnect_error:
                await disconnect_current_user_gmail(_user())
            with self.assertRaises(Exception) as sync_error:
                await sync_current_user_recruiter_provider(RecruiterSyncPayload(provider="gmail"), _user())
        self.assertEqual(getattr(connect_error.exception, "status_code", None), 400)
        self.assertEqual(getattr(disconnect_error.exception, "status_code", None), 404)
        self.assertEqual(getattr(sync_error.exception, "status_code", None), 404)


if __name__ == "__main__":
    unittest.main()
