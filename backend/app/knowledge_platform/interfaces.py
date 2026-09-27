from __future__ import annotations

from typing import Protocol, Sequence

from app.domain import (
    KnowledgeChangeStatus,
    KnowledgeAlias,
    KnowledgeEntity,
    KnowledgeEntityType,
    KnowledgeTimelineEvent,
    KnowledgeEntityVersion,
    KnowledgeEvidence,
    KnowledgeEvidenceSourceType,
)


class KnowledgePlatformStore(Protocol):
    async def list_entities(
        self,
        user_id: str,
        *,
        entity_types: Sequence[KnowledgeEntityType] | None = None,
        statuses: Sequence[KnowledgeChangeStatus] | None = None,
    ) -> list[KnowledgeEntity]:
        ...

    async def search_entities(
        self,
        user_id: str,
        query: str,
        *,
        entity_types: Sequence[KnowledgeEntityType] | None = None,
        statuses: Sequence[KnowledgeChangeStatus] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeEntity]:
        ...

    async def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        ...

    async def get_entity_by_key(
        self,
        user_id: str,
        entity_type: KnowledgeEntityType,
        canonical_name: str,
    ) -> KnowledgeEntity | None:
        ...

    async def save_entity(self, entity: KnowledgeEntity) -> KnowledgeEntity:
        ...

    async def list_aliases(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType | None = None,
    ) -> list[KnowledgeAlias]:
        ...

    async def get_alias(
        self,
        user_id: str,
        entity_type: KnowledgeEntityType,
        normalized_alias: str,
    ) -> KnowledgeAlias | None:
        ...

    async def save_alias(self, alias: KnowledgeAlias) -> KnowledgeAlias:
        ...

    async def add_entity_evidence(self, entity_id: str, evidence_ids: Sequence[str]) -> KnowledgeEntity | None:
        ...

    async def add_evidence(self, evidence: KnowledgeEvidence) -> KnowledgeEvidence:
        ...

    async def append_timeline_event(self, event: KnowledgeTimelineEvent) -> KnowledgeTimelineEvent:
        ...

    async def list_evidence(
        self,
        user_id: str,
        *,
        query: str = "",
        source_types: Sequence[KnowledgeEvidenceSourceType] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEvidence]:
        ...

    async def get_evidence_by_ids(self, user_id: str, evidence_ids: Sequence[str]) -> list[KnowledgeEvidence]:
        ...

    async def list_timeline_events(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> list[KnowledgeTimelineEvent]:
        ...

    async def add_version(self, version: KnowledgeEntityVersion) -> KnowledgeEntityVersion:
        ...

    async def get_version(self, version_id: str) -> KnowledgeEntityVersion | None:
        ...

    async def list_versions(self, entity_id: str) -> list[KnowledgeEntityVersion]:
        ...

    async def update_version(self, version: KnowledgeEntityVersion) -> KnowledgeEntityVersion:
        ...

    async def review_version(
        self,
        version: KnowledgeEntityVersion,
        entity: KnowledgeEntity | None = None,
    ) -> tuple[KnowledgeEntityVersion, KnowledgeEntity | None]:
        """Atomically record a review decision on a suggested version and save the entity.

        Raises KnowledgeChangeConflictError if the version is no longer suggested or, for an
        approval, if a newer version has already been applied to the entity.
        """
        ...
