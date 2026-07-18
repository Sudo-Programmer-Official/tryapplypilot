from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from app.domain import ConnectorRolloutStage

PaginationMode = Literal["cursor", "page", "none"]


@dataclass(frozen=True)
class ConnectorDefinition:
    key: str
    display_name: str
    rollout_stage: ConnectorRolloutStage
    pagination_mode: PaginationMode
    supports_incremental_sync: bool
    rate_limit_per_minute: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ConnectorCursor:
    cursor: str | None = None
    last_published_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.last_published_at is not None:
            payload["last_published_at"] = self.last_published_at.isoformat()
        return payload


@dataclass(frozen=True)
class NormalizedJobRecord:
    connector_key: str
    external_job_id: str
    company: str
    title: str
    location: str
    remote_policy: str
    published_at: datetime | None
    apply_url: str
    description_text: str
    job_fingerprint: str
    raw_payload: dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.published_at is not None:
            payload["published_at"] = self.published_at.isoformat()
        return payload


@dataclass(frozen=True)
class ConnectorRunResult:
    jobs: list[NormalizedJobRecord]
    next_cursor: ConnectorCursor
    exhausted: bool
    requests_made: int

    def to_dict(self) -> dict[str, object]:
        return {
            "jobs": [job.to_dict() for job in self.jobs],
            "next_cursor": self.next_cursor.to_dict(),
            "exhausted": self.exhausted,
            "requests_made": self.requests_made,
        }


class JobConnector(ABC):
    definition: ConnectorDefinition

    @abstractmethod
    def collect(self, cursor: ConnectorCursor | None = None) -> ConnectorRunResult:
        """Collect a batch of normalized jobs from the connector."""

