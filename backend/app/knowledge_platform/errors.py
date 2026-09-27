from __future__ import annotations

from typing import Awaitable, Callable

from app.domain import AuditLogEntry


class KnowledgePlatformError(ValueError):
    pass


class KnowledgeEntityNotFoundError(KnowledgePlatformError):
    pass


class KnowledgeEvidenceError(KnowledgePlatformError):
    pass


class KnowledgeChangeConflictError(KnowledgePlatformError):
    pass


AuditRecorder = Callable[..., Awaitable[AuditLogEntry | None]]
