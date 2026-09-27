from __future__ import annotations

import os
import sys
import types
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

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
    jwt_stub.decode = lambda token, secret, algorithms=None, issuer=None: {"type": "email_provider_state", "sub": "user-1", "provider": "gmail", "jti": "state-1", "exp": 4102444800}
    sys.modules["jwt"] = jwt_stub

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

if "fastapi" not in sys.modules:
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
from app.config import get_settings
from app.email_integration.tokens import ENCRYPTED_TOKEN_PREFIX, ProviderTokenCipher
from app.domain import OnboardingStatus, UserAccount
from app.email_integration import (
    EmailIntegrationService,
    EmailProviderRegistry,
    GmailProvider,
    InMemoryEmailIntegrationStore,
    InMemoryEmailProviderTokenStore,
    MockProvider,
    OutlookProvider,
)
from app.recruiter_intelligence import InMemoryRecruiterStore, RecruiterIntelligenceService
from app.resume_intelligence import InMemoryResumeVersionStore, ResumeVersionRecord


class EmailIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.application_store = InMemoryApplicationStore()
        self.recruiter_store = InMemoryRecruiterStore()
        self.version_store = InMemoryResumeVersionStore()
        self.email_store = InMemoryEmailIntegrationStore()
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
            created_at="2026-07-21T00:00:00+00:00",
            updated_at="2026-07-21T00:00:00+00:00",
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
            published_at="2026-07-21T00:00:00+00:00",
        )

        async def job_loader(user_id: str, job_id: str) -> ApplicationJobSnapshot | None:
            self.assertEqual(user_id, "user-1")
            return self.job if job_id == "job-1" else None

        self.application_service = ApplicationIntelligenceService(
            application_store=self.application_store,
            version_store=self.version_store,
            job_loader=job_loader,
        )
        self.recruiter_service = RecruiterIntelligenceService(
            recruiter_store=self.recruiter_store,
            application_service=self.application_service,
        )
        self.mailboxes: dict[str, list[dict[str, object]]] = {}

        async def mailbox_loader(connection):
            return list(self.mailboxes.get(connection.connection_id, []))

        self.provider_registry = EmailProviderRegistry(
            providers={
                "gmail": GmailProvider(mailbox_loader=mailbox_loader),
                "outlook": OutlookProvider(),
                "mock": MockProvider(mailbox_loader=mailbox_loader),
            }
        )
        self.service = EmailIntegrationService(
            store=self.email_store,
            provider_registry=self.provider_registry,
            recruiter_service=self.recruiter_service,
        )

    def tearDown(self) -> None:
        get_settings.cache_clear()

    async def test_gmail_sync_is_incremental_and_idempotent(self) -> None:
        record = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        await self.application_service.update_application_metadata(
            "user-1",
            record.application_id,
            updates={"recruiter_name": "Avery Chen", "recruiter_email": "avery@example.com"},
        )

        connection = await self.service.connect_provider(
            "user-1",
            "gmail",
            account_email="user@example.com",
            token_reference="vault://gmail/user-1",
            token_metadata={"token_kind": "reference"},
        )
        self.assertEqual(connection.status, "connected")
        self.assertTrue(connection.to_dict()["token_configured"])

        self.mailboxes[connection.connection_id] = [
            {
                "id": "m1",
                "threadId": "t1",
                "historyId": "100",
                "internalDate": "1784582400000",
                "from": "Avery Chen <avery@example.com>",
                "to": ["user@example.com"],
                "subject": "Interview invitation for Staff Platform Engineer",
                "body": "We would like to schedule an interview with the Ramp platform team.",
                "company": "Ramp",
                "job_title": "Staff Platform Engineer",
                "attachments": [
                    {"id": "att-1", "filename": "interview-details.pdf", "mimeType": "application/pdf", "size": 2048}
                ],
            }
        ]
        first_run = (await self.service.sync("user-1", provider="gmail"))[0]
        self.assertEqual(first_run.imported_count, 1)
        self.assertEqual(first_run.duplicate_count, 0)
        self.assertEqual(first_run.run_status, "completed")

        stored_connection = await self.email_store.get_connection("user-1", "gmail")
        assert stored_connection is not None
        self.assertEqual(stored_connection.sync_cursor, "100")
        self.assertIsNotNone(stored_connection.last_sync_at)

        recruiter_messages = await self.recruiter_service.list_messages("user-1", application_id=record.application_id)
        self.assertEqual(len(recruiter_messages), 1)
        self.assertEqual(recruiter_messages[0].metadata["provider_message_id"], "m1")
        self.assertEqual(recruiter_messages[0].metadata["attachments"][0]["provider_attachment_id"], "att-1")

        synced_message = await self.email_store.get_synced_message(connection.connection_id, "m1")
        self.assertIsNotNone(synced_message)
        assert synced_message is not None
        self.assertEqual(synced_message.canonical_message_id, recruiter_messages[0].message_id)
        self.assertEqual(synced_message.attachment_refs[0].provider_attachment_id, "att-1")

        self.mailboxes[connection.connection_id].append(
            {
                "id": "m2",
                "threadId": "t1",
                "historyId": "101",
                "received_at": "2026-07-21T18:00:00+00:00",
                "sender_email": "user@example.com",
                "sender_name": "Abhishek",
                "recipients": ["avery@example.com"],
                "recruiter_email": "avery@example.com",
                "recruiter_name": "Avery Chen",
                "subject": "Re: Interview invitation for Staff Platform Engineer",
                "body_text": "Thanks. Here are my available interview time slots.",
                "company": "Ramp",
                "job_title": "Staff Platform Engineer",
            }
        )
        second_run = (await self.service.sync("user-1", provider="gmail"))[0]
        self.assertEqual(second_run.imported_count, 1)
        self.assertEqual(second_run.duplicate_count, 0)

        state = await self.recruiter_service.get_application_conversation_state("user-1", record.application_id)
        self.assertEqual(state.state, "waiting_for_recruiter")

        stored_connection = await self.email_store.get_connection("user-1", "gmail")
        assert stored_connection is not None
        await self.email_store.save_connection(
            type(stored_connection)(
                connection_id=stored_connection.connection_id,
                user_id=stored_connection.user_id,
                provider=stored_connection.provider,
                account_email=stored_connection.account_email,
                status=stored_connection.status,
                scopes=list(stored_connection.scopes),
                connected_at=stored_connection.connected_at,
                disconnected_at=stored_connection.disconnected_at,
                last_sync_at=stored_connection.last_sync_at,
                sync_cursor="",
                token_reference=stored_connection.token_reference,
                token_metadata=dict(stored_connection.token_metadata),
                metadata=dict(stored_connection.metadata),
            )
        )
        third_run = (await self.service.sync("user-1", provider="gmail"))[0]
        self.assertEqual(third_run.imported_count, 0)
        self.assertEqual(third_run.duplicate_count, 2)

        statuses = await self.service.list_provider_statuses("user-1")
        self.assertEqual(statuses[0].provider, "gmail")
        self.assertEqual(statuses[0].last_duplicate_count, 2)

        history = await self.service.list_sync_history("user-1", provider="gmail", limit=10)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0].duplicate_count, 2)

    async def test_gmail_oauth_flow_persists_token_and_syncs_live_messages(self) -> None:
        record = await self.application_service.build_application_package("user-1", "job-1", resume_version_id="rv_1")
        await self.application_service.update_application_metadata(
            "user-1",
            record.application_id,
            updates={"recruiter_name": "Avery Chen", "recruiter_email": "avery@example.com"},
        )
        user = UserAccount(
            id="user-1",
            email="user@example.com",
            role="user",
            full_name="Abhishek",
            onboarding=OnboardingStatus(progress_percent=0, steps=[]),
        )
        with patch.dict(
            os.environ,
            {
                "JOB_RADAR_RUNTIME_MODE": "seed",
                "GMAIL_OAUTH_CLIENT_ID": "gmail-client-id",
                "GMAIL_OAUTH_CLIENT_SECRET": "gmail-client-secret",
                "GMAIL_OAUTH_REDIRECT_URI": "https://tryapplypilot.com/api/auth/recruiter/connect/gmail/callback",
            },
            clear=False,
        ):
            get_settings.cache_clear()
            settings = get_settings()

        token_store = InMemoryEmailProviderTokenStore()
        revoked_tokens: list[str] = []

        def request_json_stub(method, url, *, headers=None, body=None, form_body=None, timeout_seconds=None, tls=None):
            if url == settings.gmail.revoke_url and method == "POST":
                revoked_tokens.append(str((form_body or {}).get("token") or ""))
                return {}
            if url == settings.gmail.token_url and method == "POST":
                grant_type = str((form_body or {}).get("grant_type") or "")
                if grant_type == "authorization_code":
                    return {
                        "access_token": "gmail-access-token",
                        "refresh_token": "gmail-refresh-token",
                        "expires_in": 3600,
                        "scope": "https://www.googleapis.com/auth/gmail.readonly",
                        "token_type": "Bearer",
                    }
                if grant_type == "refresh_token":
                    return {
                        "access_token": "gmail-refreshed-token",
                        "expires_in": 3600,
                        "scope": "https://www.googleapis.com/auth/gmail.readonly",
                        "token_type": "Bearer",
                    }
            if url.endswith("/users/me/profile"):
                authorization = (headers or {}).get("Authorization")
                if authorization in {"Bearer gmail-access-token", "Bearer gmail-refreshed-token"}:
                    return {"emailAddress": "user@example.com", "historyId": "502"}
            if "/users/me/messages?" in url:
                return {"messages": [{"id": "gm-1"}, {"id": "gm-2"}]}
            if "/users/me/messages/gm-1?" in url:
                return {
                    "id": "gm-1",
                    "threadId": "gt-1",
                    "historyId": "500",
                    "internalDate": "1784582400000",
                    "snippet": "We would like to schedule an interview.",
                    "labelIds": ["INBOX"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Avery Chen <avery@example.com>"},
                            {"name": "To", "value": "user@example.com"},
                            {"name": "Subject", "value": "Interview invitation for Staff Platform Engineer"},
                        ],
                        "body": {"data": "V2Ugd291bGQgbGlrZSB0byBzY2hlZHVsZSBhbiBpbnRlcnZpZXcu"},
                    },
                }
            if "/users/me/messages/gm-2?" in url:
                return {
                    "id": "gm-2",
                    "threadId": "gt-1",
                    "historyId": "501",
                    "internalDate": "1784586000000",
                    "snippet": "Thanks, here are my time slots.",
                    "labelIds": ["SENT"],
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Abhishek <user@example.com>"},
                            {"name": "To", "value": "Avery Chen <avery@example.com>"},
                            {"name": "Subject", "value": "Re: Interview invitation for Staff Platform Engineer"},
                        ],
                        "body": {"data": "VGhhbmtzLCBoZXJlIGFyZSBteSB0aW1lIHNsb3RzLg"},
                    },
                }
            raise AssertionError(f"Unexpected Gmail API request: {method} {url}")

        provider_registry = EmailProviderRegistry(
            providers={
                "gmail": GmailProvider(settings=settings, token_store=token_store, request_json_func=request_json_stub),
                "outlook": OutlookProvider(),
                "mock": MockProvider(mailbox_loader=lambda connection: []),
            }
        )
        service = EmailIntegrationService(
            settings=settings,
            store=self.email_store,
            provider_registry=provider_registry,
            recruiter_service=self.recruiter_service,
        )

        oauth_request = await service.begin_provider_oauth(user, "gmail")
        self.assertIn("accounts.google.com", oauth_request.authorization_url)
        self.assertEqual(oauth_request.provider, "gmail")
        state_token = parse_qs(urlsplit(oauth_request.authorization_url).query)["state"][0]
        connection = await service.complete_provider_oauth("gmail", user_id="user-1", state_token=state_token, code="oauth-code")
        self.assertEqual(connection.provider, "gmail")
        self.assertEqual(connection.account_email, "user@example.com")
        self.assertTrue(connection.to_dict()["token_configured"])

        stored_token = await token_store.get_token(connection.token_reference)
        self.assertIsNotNone(stored_token)
        assert stored_token is not None
        await token_store.save_token(
            type(stored_token)(
                token_reference=stored_token.token_reference,
                user_id=stored_token.user_id,
                provider=stored_token.provider,
                account_email=stored_token.account_email,
                access_token=stored_token.access_token,
                refresh_token=stored_token.refresh_token,
                expires_at="2020-01-01T00:00:00+00:00",
                scope=stored_token.scope,
                token_type=stored_token.token_type,
                metadata=dict(stored_token.metadata),
                created_at=stored_token.created_at,
                updated_at=stored_token.updated_at,
            )
        )

        sync_run = (await service.sync("user-1", provider="gmail"))[0]
        self.assertEqual(sync_run.imported_count, 2)
        self.assertEqual(sync_run.duplicate_count, 0)
        refreshed_token = await token_store.get_token(connection.token_reference)
        assert refreshed_token is not None
        self.assertEqual(refreshed_token.access_token, "gmail-refreshed-token")

        recruiter_messages = await self.recruiter_service.list_messages("user-1", application_id=record.application_id)
        self.assertEqual(len(recruiter_messages), 2)
        self.assertEqual(
            {item.metadata["provider_message_id"] for item in recruiter_messages},
            {"gm-1", "gm-2"},
        )

        state = await self.recruiter_service.get_application_conversation_state("user-1", record.application_id)
        self.assertEqual(state.state, "waiting_for_recruiter")

        with self.assertRaisesRegex(ValueError, "already been used"):
            await service.complete_provider_oauth("gmail", user_id="user-1", state_token=state_token, code="oauth-code")

        second_request = await service.begin_provider_oauth(user, "gmail")
        second_state = parse_qs(urlsplit(second_request.authorization_url).query)["state"][0]
        with self.assertRaisesRegex(ValueError, "different account"):
            await service.complete_provider_oauth("gmail", user_id="user-2", state_token=second_state, code="oauth-code")

        with self.assertRaisesRegex(ValueError, "not valid for this account"):
            await service.connect_provider(
                "user-2",
                "gmail",
                account_email="attacker@example.com",
                token_reference=connection.token_reference,
            )

        disconnected = await service.disconnect_provider("user-1", "gmail")
        self.assertEqual(disconnected.status, "disconnected")
        self.assertEqual(revoked_tokens, ["gmail-refresh-token"])
        self.assertIsNone(await token_store.get_token(connection.token_reference))

    def test_provider_token_cipher_encrypts_and_reads_legacy_plaintext(self) -> None:
        cipher = ProviderTokenCipher(get_settings())
        encrypted = cipher.encrypt("gmail-refresh-token")
        self.assertTrue(encrypted.startswith(ENCRYPTED_TOKEN_PREFIX))
        self.assertNotIn("gmail-refresh-token", encrypted)
        self.assertEqual(cipher.decrypt(encrypted), "gmail-refresh-token")
        self.assertEqual(cipher.decrypt("legacy-plaintext-token"), "legacy-plaintext-token")
        self.assertEqual(cipher.encrypt(""), "")

    def test_provider_token_cipher_rejects_tokens_from_another_key(self) -> None:
        with patch.dict(os.environ, {"EMAIL_TOKEN_ENCRYPTION_KEY": "4Wq9XVh8bq3m6aPpjk1hBEJmWjWbXzA8y3kJYyC1dC4="}, clear=False):
            get_settings.cache_clear()
            other_cipher = ProviderTokenCipher(get_settings())
        get_settings.cache_clear()
        encrypted = other_cipher.encrypt("gmail-access-token")
        with self.assertRaisesRegex(ValueError, "could not be decrypted"):
            ProviderTokenCipher(get_settings()).decrypt(encrypted)

    async def test_disconnect_and_missing_sync_paths(self) -> None:
        connection = await self.service.connect_provider(
            "user-1",
            "mock",
            account_email="user@example.com",
            token_reference="mock-token-ref",
        )
        self.assertEqual(connection.provider, "mock")
        disconnected = await self.service.disconnect_provider("user-1", "mock")
        self.assertEqual(disconnected.status, "disconnected")

        with self.assertRaisesRegex(ValueError, "No connected email providers are available to sync"):
            await self.service.sync("user-1", provider="mock")

        with self.assertRaisesRegex(ValueError, "Unknown email provider connection"):
            await self.service.disconnect_provider("user-1", "gmail")


if __name__ == "__main__":
    unittest.main()
