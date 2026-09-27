from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable
from uuid import uuid4

from app.domain import KnowledgeTimelineEvent


@dataclass(frozen=True)
class KnowledgeDomainEvent:
    id: str
    user_id: str
    event_type: str
    title: str
    entity_id: str | None = None
    evidence_id: str | None = None
    payload: dict[str, object] = field(default_factory=dict)
    created_at: str | None = None

    def to_timeline_event(self) -> KnowledgeTimelineEvent:
        return KnowledgeTimelineEvent(
            id=self.id,
            user_id=self.user_id,
            event_type=self.event_type,
            title=self.title,
            entity_id=self.entity_id,
            evidence_id=self.evidence_id,
            payload=self.payload,
            created_at=self.created_at,
        )


KnowledgeEventHandler = Callable[[KnowledgeDomainEvent], Awaitable[None] | None]


def create_domain_event(
    *,
    user_id: str,
    event_type: str,
    title: str,
    entity_id: str | None = None,
    evidence_id: str | None = None,
    payload: dict[str, object] | None = None,
    created_at: str | None = None,
) -> KnowledgeDomainEvent:
    return KnowledgeDomainEvent(
        id=str(uuid4()),
        user_id=user_id,
        event_type=event_type,
        title=title,
        entity_id=entity_id,
        evidence_id=evidence_id,
        payload=payload or {},
        created_at=created_at,
    )
