from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Sequence

from app.db.client import connection
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

from .errors import KnowledgeChangeConflictError
from .interfaces import KnowledgePlatformStore
from .utils import content_search_text, isoformat, json_list, json_object, normalize_name


@dataclass
class InMemoryKnowledgePlatformStore:
    entities: dict[str, KnowledgeEntity] | None = None
    aliases: dict[str, KnowledgeAlias] | None = None
    evidence: dict[str, KnowledgeEvidence] | None = None
    timeline_events: dict[str, KnowledgeTimelineEvent] | None = None
    versions: dict[str, KnowledgeEntityVersion] | None = None

    def __post_init__(self) -> None:
        self.entities = {} if self.entities is None else self.entities
        self.aliases = {} if self.aliases is None else self.aliases
        self.evidence = {} if self.evidence is None else self.evidence
        self.timeline_events = {} if self.timeline_events is None else self.timeline_events
        self.versions = {} if self.versions is None else self.versions

    async def list_entities(
        self,
        user_id: str,
        *,
        entity_types: Sequence[KnowledgeEntityType] | None = None,
        statuses: Sequence[KnowledgeChangeStatus] | None = None,
    ) -> list[KnowledgeEntity]:
        entity_type_filter = set(entity_types or [])
        status_filter = set(statuses or [])
        rows = [
            entity
            for entity in self.entities.values()
            if entity.user_id == user_id
            and (not entity_type_filter or entity.entity_type in entity_type_filter)
            and (not status_filter or entity.status in status_filter)
        ]
        return sorted(rows, key=lambda item: (item.entity_type, item.canonical_name.casefold()))

    async def search_entities(
        self,
        user_id: str,
        query: str,
        *,
        entity_types: Sequence[KnowledgeEntityType] | None = None,
        statuses: Sequence[KnowledgeChangeStatus] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeEntity]:
        needle = query.casefold().strip()
        rows = await self.list_entities(user_id, entity_types=entity_types, statuses=statuses)
        if needle:
            rows = [
                entity
                for entity in rows
                if needle in content_search_text(entity.canonical_name, entity.content)
            ]
        return rows[: max(1, limit)]

    async def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        return self.entities.get(entity_id)

    async def get_entity_by_key(
        self,
        user_id: str,
        entity_type: KnowledgeEntityType,
        canonical_name: str,
    ) -> KnowledgeEntity | None:
        normalized_name = normalize_name(canonical_name).casefold()
        for entity in self.entities.values():
            if entity.user_id != user_id or entity.entity_type != entity_type:
                continue
            if entity.canonical_name.casefold() == normalized_name:
                return entity
        return None

    async def save_entity(self, entity: KnowledgeEntity) -> KnowledgeEntity:
        self.entities[entity.id] = entity
        return entity

    async def list_aliases(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType | None = None,
    ) -> list[KnowledgeAlias]:
        rows = [
            alias
            for alias in self.aliases.values()
            if alias.user_id == user_id and (entity_type is None or alias.entity_type == entity_type)
        ]
        return sorted(rows, key=lambda item: (item.entity_type, item.normalized_alias))

    async def get_alias(
        self,
        user_id: str,
        entity_type: KnowledgeEntityType,
        normalized_alias: str,
    ) -> KnowledgeAlias | None:
        for alias in self.aliases.values():
            if alias.user_id == user_id and alias.entity_type == entity_type and alias.normalized_alias == normalized_alias:
                return alias
        return None

    async def save_alias(self, alias: KnowledgeAlias) -> KnowledgeAlias:
        self.aliases[alias.id] = alias
        return alias

    async def add_entity_evidence(self, entity_id: str, evidence_ids: Sequence[str]) -> KnowledgeEntity | None:
        entity = self.entities.get(entity_id)
        if entity is None:
            return None
        merged = list(dict.fromkeys([*entity.evidence_ids, *[str(item) for item in evidence_ids if str(item).strip()]]))
        updated = replace(entity, evidence_ids=merged)
        self.entities[entity_id] = updated
        return updated

    async def add_evidence(self, evidence: KnowledgeEvidence) -> KnowledgeEvidence:
        self.evidence[evidence.id] = evidence
        return evidence

    async def append_timeline_event(self, event: KnowledgeTimelineEvent) -> KnowledgeTimelineEvent:
        self.timeline_events[event.id] = event
        return event

    async def list_evidence(
        self,
        user_id: str,
        *,
        query: str = "",
        source_types: Sequence[KnowledgeEvidenceSourceType] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEvidence]:
        needle = query.casefold().strip()
        source_filter = set(source_types or [])
        rows = [
            item
            for item in self.evidence.values()
            if item.user_id == user_id and (not source_filter or item.source_type in source_filter)
        ]
        if needle:
            rows = [item for item in rows if needle in f"{item.excerpt} {json.dumps(item.metadata)}".casefold()]
        return sorted(rows, key=lambda item: (item.created_at or "", item.id), reverse=True)[: max(1, limit)]

    async def get_evidence_by_ids(self, user_id: str, evidence_ids: Sequence[str]) -> list[KnowledgeEvidence]:
        rows: list[KnowledgeEvidence] = []
        for evidence_id in evidence_ids:
            evidence = self.evidence.get(evidence_id)
            if evidence is not None and evidence.user_id == user_id:
                rows.append(evidence)
        return rows

    async def list_timeline_events(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> list[KnowledgeTimelineEvent]:
        rows = [event for event in self.timeline_events.values() if event.user_id == user_id]
        return sorted(rows, key=lambda item: (item.created_at or "", item.id), reverse=True)[: max(1, limit)]

    async def add_version(self, version: KnowledgeEntityVersion) -> KnowledgeEntityVersion:
        self.versions[version.id] = version
        return version

    async def get_version(self, version_id: str) -> KnowledgeEntityVersion | None:
        return self.versions.get(version_id)

    async def list_versions(self, entity_id: str) -> list[KnowledgeEntityVersion]:
        rows = [version for version in self.versions.values() if version.entity_id == entity_id]
        return sorted(rows, key=lambda item: item.version_number)

    async def update_version(self, version: KnowledgeEntityVersion) -> KnowledgeEntityVersion:
        self.versions[version.id] = version
        return version

    async def review_version(
        self,
        version: KnowledgeEntityVersion,
        entity: KnowledgeEntity | None = None,
    ) -> tuple[KnowledgeEntityVersion, KnowledgeEntity | None]:
        current = self.versions.get(version.id)
        if current is None or current.status != "suggested":
            raise KnowledgeChangeConflictError("Knowledge change is no longer awaiting review.")
        stored_entity = self.entities.get(version.entity_id)
        if version.status == "approved" and stored_entity is not None and stored_entity.version >= version.version_number:
            raise KnowledgeChangeConflictError("Knowledge change has been superseded by a newer approved version.")
        self.versions[version.id] = version
        saved_entity = await self.save_entity(entity) if entity is not None else None
        return version, saved_entity


def _row_to_entity(row) -> KnowledgeEntity:
    return KnowledgeEntity(
        id=str(row["entity_id"]),
        user_id=str(row["user_id"]),
        entity_type=str(row["entity_type"]),
        canonical_name=str(row["canonical_name"]),
        content=json_object(row["content"]),
        source=str(row["source"]),
        confidence=float(row["confidence"]),
        evidence_ids=json_list(row["evidence"]),
        version=int(row["current_version"]),
        status=str(row["approval_status"]),
        created_at=isoformat(row["created_at"]),
        updated_at=isoformat(row["updated_at"]),
    )


def _row_to_alias(row) -> KnowledgeAlias:
    return KnowledgeAlias(
        id=str(row["alias_id"]),
        user_id=str(row["user_id"]),
        entity_type=str(row["entity_type"]),
        alias_value=str(row["alias_value"]),
        normalized_alias=str(row["normalized_alias"]),
        canonical_name=str(row["canonical_name"]),
        confidence=float(row["confidence"]),
        is_manual_override=bool(row["is_manual_override"]),
        created_at=isoformat(row["created_at"]),
        updated_at=isoformat(row["updated_at"]),
    )


def _row_to_evidence(row) -> KnowledgeEvidence:
    return KnowledgeEvidence(
        id=str(row["evidence_id"]),
        user_id=str(row["user_id"]),
        source_type=str(row["source_type"]),
        source_id=str(row["source_id"]),
        excerpt=str(row["excerpt"]),
        metadata=json_object(row["metadata"]),
        created_at=isoformat(row["created_at"]),
    )


def _row_to_timeline_event(row) -> KnowledgeTimelineEvent:
    return KnowledgeTimelineEvent(
        id=str(row["timeline_event_id"]),
        user_id=str(row["user_id"]),
        event_type=str(row["event_type"]),
        title=str(row["title"]),
        entity_id=str(row["entity_id"]) if row["entity_id"] is not None else None,
        evidence_id=str(row["evidence_id"]) if row["evidence_id"] is not None else None,
        payload=json_object(row["payload"]),
        created_at=isoformat(row["created_at"]),
    )


def _row_to_version(row) -> KnowledgeEntityVersion:
    return KnowledgeEntityVersion(
        id=str(row["version_id"]),
        entity_id=str(row["entity_id"]),
        user_id=str(row["user_id"]),
        version_number=int(row["version_number"]),
        status=str(row["status"]),
        source=str(row["source"]),
        reason=str(row["reason"]),
        actor_user_id=str(row["actor_user_id"]) if row["actor_user_id"] is not None else None,
        reviewed_by_user_id=str(row["reviewed_by_user_id"]) if row["reviewed_by_user_id"] is not None else None,
        agent_name=str(row["agent_name"]),
        confidence=float(row["confidence"]),
        evidence_ids=json_list(row["evidence"]),
        previous_content=json_object(row["previous_content"]),
        new_content=json_object(row["new_content"]),
        created_at=isoformat(row["created_at"]),
        reviewed_at=isoformat(row["reviewed_at"]),
        review_notes=str(row["review_notes"]),
    )


class PostgresKnowledgePlatformStore:
    async def list_entities(
        self,
        user_id: str,
        *,
        entity_types: Sequence[KnowledgeEntityType] | None = None,
        statuses: Sequence[KnowledgeChangeStatus] | None = None,
    ) -> list[KnowledgeEntity]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_entities
                WHERE user_id = $1
                  AND ($2::text[] IS NULL OR entity_type = ANY($2::text[]))
                  AND ($3::text[] IS NULL OR approval_status = ANY($3::text[]))
                ORDER BY entity_type ASC, canonical_name ASC
                """,
                user_id,
                list(entity_types) if entity_types else None,
                list(statuses) if statuses else None,
            )
        return [_row_to_entity(row) for row in rows]

    async def search_entities(
        self,
        user_id: str,
        query: str,
        *,
        entity_types: Sequence[KnowledgeEntityType] | None = None,
        statuses: Sequence[KnowledgeChangeStatus] | None = None,
        limit: int = 10,
    ) -> list[KnowledgeEntity]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_entities
                WHERE user_id = $1
                  AND ($2::text[] IS NULL OR entity_type = ANY($2::text[]))
                  AND ($3::text[] IS NULL OR approval_status = ANY($3::text[]))
                  AND search_text LIKE $4
                ORDER BY updated_at DESC, canonical_name ASC
                LIMIT $5
                """,
                user_id,
                list(entity_types) if entity_types else None,
                list(statuses) if statuses else None,
                f"%{query.casefold().strip()}%",
                max(1, limit),
            )
        return [_row_to_entity(row) for row in rows]

    async def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM knowledge_entities
                WHERE entity_id = $1
                """,
                entity_id,
            )
        return _row_to_entity(row) if row is not None else None

    async def get_entity_by_key(
        self,
        user_id: str,
        entity_type: KnowledgeEntityType,
        canonical_name: str,
    ) -> KnowledgeEntity | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM knowledge_entities
                WHERE user_id = $1
                  AND entity_type = $2
                  AND LOWER(canonical_name) = LOWER($3)
                """,
                user_id,
                entity_type,
                normalize_name(canonical_name),
            )
        return _row_to_entity(row) if row is not None else None

    async def save_entity(self, entity: KnowledgeEntity) -> KnowledgeEntity:
        async with connection() as conn:
            return await self._save_entity(conn, entity)

    async def _save_entity(self, conn, entity: KnowledgeEntity) -> KnowledgeEntity:
        row = await conn.fetchrow(
            """
            INSERT INTO knowledge_entities (
                entity_id,
                user_id,
                entity_type,
                canonical_name,
                content,
                search_text,
                source,
                confidence,
                evidence,
                current_version,
                approval_status,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9::jsonb, $10, $11, COALESCE($12::timestamptz, NOW()), COALESCE($13::timestamptz, NOW()))
            ON CONFLICT (entity_id) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                content = EXCLUDED.content,
                search_text = EXCLUDED.search_text,
                source = EXCLUDED.source,
                confidence = EXCLUDED.confidence,
                evidence = EXCLUDED.evidence,
                current_version = EXCLUDED.current_version,
                approval_status = EXCLUDED.approval_status,
                updated_at = COALESCE(EXCLUDED.updated_at, NOW())
            RETURNING *
            """,
            entity.id,
            entity.user_id,
            entity.entity_type,
            entity.canonical_name,
            json.dumps(entity.content),
            content_search_text(entity.canonical_name, entity.content),
            entity.source,
            entity.confidence,
            json.dumps(entity.evidence_ids),
            entity.version,
            entity.status,
            entity.created_at,
            entity.updated_at,
        )
        assert row is not None
        return _row_to_entity(row)

    async def list_aliases(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType | None = None,
    ) -> list[KnowledgeAlias]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_aliases
                WHERE user_id = $1
                  AND ($2::text IS NULL OR entity_type = $2)
                ORDER BY entity_type ASC, normalized_alias ASC
                """,
                user_id,
                entity_type,
            )
        return [_row_to_alias(row) for row in rows]

    async def get_alias(
        self,
        user_id: str,
        entity_type: KnowledgeEntityType,
        normalized_alias: str,
    ) -> KnowledgeAlias | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM knowledge_aliases
                WHERE user_id = $1
                  AND entity_type = $2
                  AND normalized_alias = $3
                """,
                user_id,
                entity_type,
                normalized_alias,
            )
        return _row_to_alias(row) if row is not None else None

    async def save_alias(self, alias: KnowledgeAlias) -> KnowledgeAlias:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_aliases (
                    alias_id,
                    user_id,
                    entity_type,
                    alias_value,
                    normalized_alias,
                    canonical_name,
                    confidence,
                    is_manual_override,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, COALESCE($9::timestamptz, NOW()), COALESCE($10::timestamptz, NOW()))
                ON CONFLICT (user_id, entity_type, normalized_alias) DO UPDATE SET
                    alias_value = EXCLUDED.alias_value,
                    canonical_name = EXCLUDED.canonical_name,
                    confidence = EXCLUDED.confidence,
                    is_manual_override = EXCLUDED.is_manual_override,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                RETURNING *
                """,
                alias.id,
                alias.user_id,
                alias.entity_type,
                alias.alias_value,
                alias.normalized_alias,
                alias.canonical_name,
                alias.confidence,
                alias.is_manual_override,
                alias.created_at,
                alias.updated_at,
            )
        assert row is not None
        return _row_to_alias(row)

    async def add_entity_evidence(self, entity_id: str, evidence_ids: Sequence[str]) -> KnowledgeEntity | None:
        if not evidence_ids:
            return await self.get_entity(entity_id)
        entity = await self.get_entity(entity_id)
        if entity is None:
            return None
        merged = list(dict.fromkeys([*entity.evidence_ids, *[str(item) for item in evidence_ids if str(item).strip()]]))
        return await self.save_entity(replace(entity, evidence_ids=merged))

    async def add_evidence(self, evidence: KnowledgeEvidence) -> KnowledgeEvidence:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_evidence (
                    evidence_id,
                    user_id,
                    source_type,
                    source_id,
                    excerpt,
                    metadata,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, COALESCE($7::timestamptz, NOW()))
                RETURNING *
                """,
                evidence.id,
                evidence.user_id,
                evidence.source_type,
                evidence.source_id,
                evidence.excerpt,
                json.dumps(evidence.metadata),
                evidence.created_at,
            )
        assert row is not None
        return _row_to_evidence(row)

    async def append_timeline_event(self, event: KnowledgeTimelineEvent) -> KnowledgeTimelineEvent:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_timeline_events (
                    timeline_event_id,
                    user_id,
                    event_type,
                    title,
                    entity_id,
                    evidence_id,
                    payload,
                    created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, COALESCE($8::timestamptz, NOW()))
                RETURNING *
                """,
                event.id,
                event.user_id,
                event.event_type,
                event.title,
                event.entity_id,
                event.evidence_id,
                json.dumps(event.payload),
                event.created_at,
            )
        assert row is not None
        return _row_to_timeline_event(row)

    async def list_evidence(
        self,
        user_id: str,
        *,
        query: str = "",
        source_types: Sequence[KnowledgeEvidenceSourceType] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEvidence]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_evidence
                WHERE user_id = $1
                  AND ($2::text[] IS NULL OR source_type = ANY($2::text[]))
                  AND (LOWER(excerpt || ' ' || metadata::text) LIKE $3)
                ORDER BY created_at DESC
                LIMIT $4
                """,
                user_id,
                list(source_types) if source_types else None,
                f"%{query.casefold().strip()}%",
                max(1, limit),
            )
        return [_row_to_evidence(row) for row in rows]

    async def get_evidence_by_ids(self, user_id: str, evidence_ids: Sequence[str]) -> list[KnowledgeEvidence]:
        if not evidence_ids:
            return []
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_evidence
                WHERE user_id = $1
                  AND evidence_id = ANY($2::text[])
                """,
                user_id,
                list(evidence_ids),
            )
        mapped = {row["evidence_id"]: _row_to_evidence(row) for row in rows}
        return [mapped[evidence_id] for evidence_id in evidence_ids if evidence_id in mapped]

    async def list_timeline_events(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> list[KnowledgeTimelineEvent]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_timeline_events
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                user_id,
                max(1, limit),
            )
        return [_row_to_timeline_event(row) for row in rows]

    async def add_version(self, version: KnowledgeEntityVersion) -> KnowledgeEntityVersion:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_entity_versions (
                    version_id,
                    entity_id,
                    user_id,
                    version_number,
                    status,
                    source,
                    reason,
                    actor_user_id,
                    reviewed_by_user_id,
                    agent_name,
                    confidence,
                    evidence,
                    previous_content,
                    new_content,
                    created_at,
                    reviewed_at,
                    review_notes
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, $13::jsonb, $14::jsonb, COALESCE($15::timestamptz, NOW()), $16::timestamptz, $17)
                RETURNING *
                """,
                version.id,
                version.entity_id,
                version.user_id,
                version.version_number,
                version.status,
                version.source,
                version.reason,
                version.actor_user_id,
                version.reviewed_by_user_id,
                version.agent_name,
                version.confidence,
                json.dumps(version.evidence_ids),
                json.dumps(version.previous_content),
                json.dumps(version.new_content),
                version.created_at,
                version.reviewed_at,
                version.review_notes,
            )
        assert row is not None
        return _row_to_version(row)

    async def get_version(self, version_id: str) -> KnowledgeEntityVersion | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM knowledge_entity_versions
                WHERE version_id = $1
                """,
                version_id,
            )
        return _row_to_version(row) if row is not None else None

    async def list_versions(self, entity_id: str) -> list[KnowledgeEntityVersion]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM knowledge_entity_versions
                WHERE entity_id = $1
                ORDER BY version_number ASC
                """,
                entity_id,
            )
        return [_row_to_version(row) for row in rows]

    async def update_version(self, version: KnowledgeEntityVersion) -> KnowledgeEntityVersion:
        async with connection() as conn:
            row = await self._update_version(conn, version)
        assert row is not None
        return _row_to_version(row)

    async def _update_version(self, conn, version: KnowledgeEntityVersion, *, only_if_suggested: bool = False):
        return await conn.fetchrow(
            f"""
            UPDATE knowledge_entity_versions
            SET
                status = $2,
                reviewed_by_user_id = $3,
                reviewed_at = $4::timestamptz,
                review_notes = $5
            WHERE version_id = $1
              {"AND status = 'suggested'" if only_if_suggested else ""}
            RETURNING *
            """,
            version.id,
            version.status,
            version.reviewed_by_user_id,
            version.reviewed_at,
            version.review_notes,
        )

    async def review_version(
        self,
        version: KnowledgeEntityVersion,
        entity: KnowledgeEntity | None = None,
    ) -> tuple[KnowledgeEntityVersion, KnowledgeEntity | None]:
        async with connection() as conn:
            async with conn.transaction():
                current_version = await conn.fetchval(
                    "SELECT current_version FROM knowledge_entities WHERE entity_id = $1 FOR UPDATE",
                    version.entity_id,
                )
                if version.status == "approved" and current_version is not None and int(current_version) >= version.version_number:
                    raise KnowledgeChangeConflictError("Knowledge change has been superseded by a newer approved version.")
                row = await self._update_version(conn, version, only_if_suggested=True)
                if row is None:
                    raise KnowledgeChangeConflictError("Knowledge change is no longer awaiting review.")
                saved_entity = await self._save_entity(conn, entity) if entity is not None else None
        return _row_to_version(row), saved_entity
