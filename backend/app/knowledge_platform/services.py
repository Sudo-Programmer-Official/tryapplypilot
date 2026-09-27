from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import inspect
from typing import Sequence
from uuid import uuid4

from app.audit_logs import record_audit_event
from app.config import AppSettings, get_settings
from app.domain import (
    KnowledgeAlias,
    KnowledgeEntity,
    KnowledgeEntityType,
    KnowledgeTimelineEvent,
    KnowledgeEntityVersion,
    KnowledgeEvidence,
    KnowledgeEvidenceSourceType,
)

from .errors import (
    AuditRecorder,
    KnowledgeChangeConflictError,
    KnowledgeEntityNotFoundError,
    KnowledgeEvidenceError,
    KnowledgePlatformError,
)
from .events import KnowledgeEventHandler, create_domain_event
from .health import build_health_report
from .interfaces import KnowledgePlatformStore
from .linking import LinkResolution, normalize_alias, resolve_entity_alias
from .queries import (
    compute_knowledge_completeness,
    compute_knowledge_completeness_report,
    entity_text,
    rank_evidence_items,
    select_quantified_achievements,
    sort_best_examples,
)
from .schema_version import KNOWLEDGE_SCHEMA_VERSION
from .store import InMemoryKnowledgePlatformStore, PostgresKnowledgePlatformStore
from .utils import isoformat, normalize_name


@dataclass
class KnowledgePlatformService:
    store: KnowledgePlatformStore
    audit_recorder: AuditRecorder = record_audit_event
    settings: AppSettings | None = None
    event_handlers: Sequence[KnowledgeEventHandler] = ()

    def _resolved_settings(self) -> AppSettings:
        return self.settings or get_settings()

    async def _approved_entities(
        self,
        user_id: str,
        *,
        entity_types: Sequence[KnowledgeEntityType] | None = None,
    ) -> list[KnowledgeEntity]:
        return await self.store.list_entities(user_id, entity_types=entity_types, statuses=("approved",))

    async def _publish_event(self, event: KnowledgeTimelineEvent) -> None:
        stored = await self.store.append_timeline_event(event)
        for handler in self.event_handlers:
            result = handler(create_domain_event(
                user_id=stored.user_id,
                event_type=stored.event_type,
                title=stored.title,
                entity_id=stored.entity_id,
                evidence_id=stored.evidence_id,
                payload=stored.payload,
                created_at=stored.created_at,
            ))
            if inspect.isawaitable(result):
                await result

    async def _emit_event(
        self,
        *,
        user_id: str,
        event_type: str,
        title: str,
        entity_id: str | None = None,
        evidence_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        await self._publish_event(
            create_domain_event(
                user_id=user_id,
                event_type=event_type,
                title=title,
                entity_id=entity_id,
                evidence_id=evidence_id,
                payload=payload or {},
                created_at=isoformat(datetime.now(timezone.utc)),
            ).to_timeline_event()
        )

    async def _emit_profile_completed_if_needed(self, user_id: str) -> None:
        completeness = await self.get_profile_completeness(user_id)
        if int(completeness["overall_score"]) < 80:
            return
        recent = await self.get_timeline(user_id, limit=10)
        if any(event.event_type == "ProfileCompleted" for event in recent):
            return
        await self._emit_event(
            user_id=user_id,
            event_type="ProfileCompleted",
            title="Profile completeness reached production-ready coverage",
            payload={"overall_score": completeness["overall_score"]},
        )

    async def read_profile(self, user_id: str) -> dict[str, list[KnowledgeEntity]]:
        entities = await self._approved_entities(user_id)
        grouped: dict[str, list[KnowledgeEntity]] = {}
        for entity in entities:
            grouped.setdefault(entity.entity_type, []).append(entity)
        return grouped

    async def get_user_profile(self, user_id: str) -> dict[str, list[KnowledgeEntity]]:
        return await self.read_profile(user_id)

    async def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        return await self.store.get_entity(entity_id)

    async def list_aliases(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType | None = None,
    ) -> list[KnowledgeAlias]:
        return await self.store.list_aliases(user_id, entity_type=entity_type)

    async def resolve_entity_link(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType,
        raw_name: str,
    ) -> LinkResolution:
        normalized = normalize_alias(raw_name)
        stored_alias = await self.store.get_alias(user_id, entity_type, normalized)
        if stored_alias is not None:
            return LinkResolution(
                entity_type=entity_type,
                raw_name=raw_name,
                normalized_alias=stored_alias.normalized_alias,
                canonical_name=stored_alias.canonical_name,
                confidence=stored_alias.confidence,
                source="manual_override" if stored_alias.is_manual_override else "stored_alias",
            )
        return resolve_entity_alias(entity_type, raw_name)

    async def register_manual_alias(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType,
        alias_value: str,
        canonical_name: str,
    ) -> KnowledgeAlias:
        now = isoformat(datetime.now(timezone.utc))
        alias = await self.store.save_alias(
            KnowledgeAlias(
                id=str(uuid4()),
                user_id=user_id,
                entity_type=entity_type,
                alias_value=alias_value.strip(),
                normalized_alias=normalize_alias(alias_value),
                canonical_name=normalize_name(canonical_name),
                confidence=1.0,
                is_manual_override=True,
                created_at=now,
                updated_at=now,
            )
        )
        await self._emit_event(
            user_id=user_id,
            event_type="AliasRegistered",
            title=f"Registered canonical alias for {alias.alias_value}",
            payload={"entity_type": entity_type, "canonical_name": alias.canonical_name},
        )
        return alias

    async def _register_alias_if_needed(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType,
        raw_name: str,
        canonical_name: str,
        confidence: float,
        is_manual_override: bool = False,
    ) -> None:
        normalized_alias = normalize_alias(raw_name)
        if not normalized_alias:
            return
        if normalized_alias == normalize_alias(canonical_name) and not is_manual_override:
            return
        existing = await self.store.get_alias(user_id, entity_type, normalized_alias)
        now = isoformat(datetime.now(timezone.utc))
        if existing is not None and existing.is_manual_override and not is_manual_override:
            return
        await self.store.save_alias(
            KnowledgeAlias(
                id=existing.id if existing is not None else str(uuid4()),
                user_id=user_id,
                entity_type=entity_type,
                alias_value=raw_name.strip(),
                normalized_alias=normalized_alias,
                canonical_name=normalize_name(canonical_name),
                confidence=max(0.0, min(confidence, 1.0)),
                is_manual_override=is_manual_override if existing is None else existing.is_manual_override or is_manual_override,
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
        )

    async def search_projects(self, user_id: str, query: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        return await self.store.search_entities(
            user_id,
            query,
            entity_types=("project",),
            statuses=("approved",),
            limit=limit,
        )

    async def search_achievements(self, user_id: str, query: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        return await self.store.search_entities(
            user_id,
            query,
            entity_types=("achievement", "leadership"),
            statuses=("approved",),
            limit=limit,
        )

    async def search_experience(self, user_id: str, query: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        return await self.store.search_entities(
            user_id,
            query,
            entity_types=("experience",),
            statuses=("approved",),
            limit=limit,
        )

    async def search_skills(self, user_id: str, query: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        return await self.store.search_entities(
            user_id,
            query,
            entity_types=("skill", "technology"),
            statuses=("approved",),
            limit=limit,
        )

    async def retrieve_evidence(
        self,
        user_id: str,
        *,
        query: str = "",
        source_types: Sequence[KnowledgeEvidenceSourceType] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEvidence]:
        return await self.store.list_evidence(
            user_id,
            query=query,
            source_types=source_types,
            limit=limit,
        )

    async def get_evidence(
        self,
        user_id: str,
        *,
        query: str = "",
        source_types: Sequence[KnowledgeEvidenceSourceType] | None = None,
        limit: int = 20,
    ) -> list[KnowledgeEvidence]:
        return await self.retrieve_evidence(
            user_id,
            query=query,
            source_types=source_types,
            limit=limit,
        )

    async def rank_evidence(self, user_id: str, evidence_ids: Sequence[str]) -> list[KnowledgeEvidence]:
        evidence = await self.store.get_evidence_by_ids(user_id, list(evidence_ids))
        return rank_evidence_items(evidence)

    async def get_timeline(self, user_id: str, *, limit: int = 50) -> list[KnowledgeTimelineEvent]:
        return await self.store.list_timeline_events(user_id, limit=limit)

    async def add_entity_evidence(self, entity_id: str, evidence_ids: Sequence[str]) -> KnowledgeEntity | None:
        return await self.store.add_entity_evidence(entity_id, evidence_ids)

    async def add_evidence(
        self,
        user_id: str,
        *,
        source_type: KnowledgeEvidenceSourceType,
        source_id: str,
        excerpt: str,
        metadata: dict[str, object] | None = None,
    ) -> KnowledgeEvidence:
        cleaned_excerpt = " ".join(excerpt.split()).strip()
        if not cleaned_excerpt:
            raise KnowledgeEvidenceError("Evidence excerpt cannot be empty.")
        evidence = KnowledgeEvidence(
            id=str(uuid4()),
            user_id=user_id,
            source_type=source_type,
            source_id=source_id.strip(),
            excerpt=cleaned_excerpt,
            metadata=metadata or {},
            created_at=isoformat(datetime.now(timezone.utc)),
        )
        stored = await self.store.add_evidence(evidence)
        await self._emit_event(
            user_id=user_id,
            event_type="EvidenceAdded",
            title=f"Evidence added from {stored.source_type}",
            evidence_id=stored.id,
            payload={"source_type": stored.source_type, "source_id": stored.source_id},
        )
        return stored

    async def stage_change(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType,
        canonical_name: str,
        new_content: dict[str, object],
        source: str,
        reason: str,
        evidence_ids: Sequence[str],
        actor_user_id: str | None = None,
        confidence: float = 1.0,
        agent_name: str = "",
    ) -> KnowledgeEntityVersion:
        resolution = await self.resolve_entity_link(user_id, entity_type=entity_type, raw_name=canonical_name)
        normalized_name = normalize_name(resolution.canonical_name)
        if not normalized_name:
            raise KnowledgePlatformError("Knowledge entities require a canonical name.")
        if not reason.strip():
            raise KnowledgePlatformError("Knowledge changes require a reason.")
        evidence = await self.store.get_evidence_by_ids(user_id, list(evidence_ids))
        if len(evidence) != len(list(evidence_ids)):
            raise KnowledgeEvidenceError("Every staged change must reference valid evidence.")
        entity = await self.store.get_entity_by_key(user_id, entity_type, normalized_name)
        now = isoformat(datetime.now(timezone.utc))
        created_entity = False
        if entity is None:
            entity = KnowledgeEntity(
                id=str(uuid4()),
                user_id=user_id,
                entity_type=entity_type,
                canonical_name=normalized_name,
                content={},
                source=source.strip(),
                confidence=max(0.0, min(max(confidence, resolution.confidence), 1.0)),
                evidence_ids=[],
                version=0,
                status="suggested",
                created_at=now,
                updated_at=now,
            )
            entity = await self.store.save_entity(entity)
            created_entity = True

        existing_versions = await self.store.list_versions(entity.id)
        if existing_versions:
            latest = existing_versions[-1]
            if (
                latest.status == "suggested"
                and latest.new_content == new_content
                and latest.evidence_ids == list(evidence_ids)
                and latest.reason == reason.strip()
            ):
                return latest
        next_version_number = len(existing_versions) + 1
        version = KnowledgeEntityVersion(
            id=str(uuid4()),
            entity_id=entity.id,
            user_id=user_id,
            version_number=next_version_number,
            status="suggested",
            source=source.strip(),
            reason=reason.strip(),
            actor_user_id=actor_user_id,
            reviewed_by_user_id=None,
            agent_name=agent_name.strip(),
            confidence=max(0.0, min(max(confidence, resolution.confidence), 1.0)),
            evidence_ids=list(evidence_ids),
            previous_content=entity.content,
            new_content=new_content,
            created_at=now,
        )
        staged = await self.store.add_version(version)
        updated_entity = replace(
            entity,
            status="suggested" if entity.version == 0 else entity.status,
            updated_at=now,
        )
        await self.store.save_entity(updated_entity)
        await self._register_alias_if_needed(
            user_id,
            entity_type=entity_type,
            raw_name=canonical_name,
            canonical_name=normalized_name,
            confidence=resolution.confidence,
        )
        await self.audit_recorder(
            event_type="knowledge.change_staged",
            subject_type="knowledge_entity",
            subject_id=entity.id,
            message=f"Staged {entity_type} change for {normalized_name}",
            actor_user_id=actor_user_id,
            metadata={
                "entity_type": entity_type,
                "canonical_name": normalized_name,
                "version_number": next_version_number,
                "reason": reason.strip(),
                "evidence_ids": list(evidence_ids),
                "confidence": confidence,
                "agent_name": agent_name.strip(),
                "link_source": resolution.source,
            },
            settings=self._resolved_settings(),
        )
        if created_entity:
            await self._emit_event(
                user_id=user_id,
                event_type="EntityCreated",
                title=f"Created canonical {entity_type}: {normalized_name}",
                entity_id=entity.id,
                payload={"entity_type": entity_type, "canonical_name": normalized_name},
            )
        return staged

    async def stage_resume_changes(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType,
        canonical_name: str,
        new_content: dict[str, object],
        source: str,
        reason: str,
        evidence_ids: Sequence[str],
        actor_user_id: str | None = None,
        confidence: float = 1.0,
        agent_name: str = "",
    ) -> KnowledgeEntityVersion:
        return await self.stage_change(
            user_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            new_content=new_content,
            source=source,
            reason=reason,
            evidence_ids=evidence_ids,
            actor_user_id=actor_user_id,
            confidence=confidence,
            agent_name=agent_name,
        )

    async def upsert_approved_entity(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType,
        canonical_name: str,
        new_content: dict[str, object],
        source: str,
        reason: str,
        evidence_ids: Sequence[str],
        actor_user_id: str | None = None,
        confidence: float = 1.0,
        agent_name: str = "",
    ) -> KnowledgeEntity:
        resolution = await self.resolve_entity_link(user_id, entity_type=entity_type, raw_name=canonical_name)
        normalized_name = normalize_name(resolution.canonical_name)
        existing = await self.store.get_entity_by_key(user_id, entity_type, normalized_name)
        if existing is not None and existing.content == new_content:
            updated = await self.store.add_entity_evidence(existing.id, evidence_ids)
            if updated is not None:
                await self._register_alias_if_needed(
                    user_id,
                    entity_type=entity_type,
                    raw_name=canonical_name,
                    canonical_name=normalized_name,
                    confidence=resolution.confidence,
                )
            return updated or existing
        version = await self.stage_change(
            user_id,
            entity_type=entity_type,
            canonical_name=normalized_name,
            new_content=new_content,
            source=source,
            reason=reason,
            evidence_ids=evidence_ids,
            actor_user_id=actor_user_id,
            confidence=max(confidence, resolution.confidence),
            agent_name=agent_name,
        )
        return await self.approve_change(version.id, reviewed_by_user_id=actor_user_id)

    async def approve_change(
        self,
        version_id: str,
        *,
        reviewed_by_user_id: str | None = None,
        review_notes: str = "",
    ) -> KnowledgeEntity:
        version = await self.store.get_version(version_id)
        if version is None:
            raise KnowledgeEntityNotFoundError("Unknown knowledge change.")
        if version.status != "suggested":
            raise KnowledgeChangeConflictError(f"Knowledge change is already {version.status}.")
        entity = await self.store.get_entity(version.entity_id)
        if entity is None:
            raise KnowledgeEntityNotFoundError("Unknown knowledge entity.")
        if version.version_number <= entity.version:
            raise KnowledgeChangeConflictError("Knowledge change has been superseded by a newer approved version.")
        now = isoformat(datetime.now(timezone.utc))
        approved_version = replace(
            version,
            status="approved",
            reviewed_by_user_id=reviewed_by_user_id,
            reviewed_at=now,
            review_notes=review_notes.strip(),
        )
        await self.store.update_version(approved_version)
        approved_entity = replace(
            entity,
            content=version.new_content,
            source=version.source,
            confidence=version.confidence,
            evidence_ids=version.evidence_ids,
            version=version.version_number,
            status="approved",
            updated_at=now,
        )
        saved_entity = await self.store.save_entity(approved_entity)
        await self.audit_recorder(
            event_type="knowledge.change_approved",
            subject_type="knowledge_entity",
            subject_id=entity.id,
            message=f"Approved {entity.entity_type} change for {entity.canonical_name}",
            actor_user_id=reviewed_by_user_id,
            metadata={
                "entity_type": entity.entity_type,
                "canonical_name": entity.canonical_name,
                "version_number": version.version_number,
                "review_notes": review_notes.strip(),
                "evidence_ids": version.evidence_ids,
            },
            settings=self._resolved_settings(),
        )
        await self._emit_event(
            user_id=entity.user_id,
            event_type="KnowledgeUpdated",
            title=f"Approved {entity.entity_type} update for {entity.canonical_name}",
            entity_id=entity.id,
            payload={"entity_type": entity.entity_type, "version_number": version.version_number},
        )
        if version.version_number > 1:
            await self._emit_event(
                user_id=entity.user_id,
                event_type="MergeApproved",
                title=f"Merged canonical updates for {entity.canonical_name}",
                entity_id=entity.id,
                payload={"entity_type": entity.entity_type, "version_number": version.version_number},
            )
        await self._emit_profile_completed_if_needed(entity.user_id)
        return saved_entity

    async def approve_changes(
        self,
        version_ids: Sequence[str],
        *,
        reviewed_by_user_id: str | None = None,
        review_notes: str = "",
    ) -> list[KnowledgeEntity]:
        approved: list[KnowledgeEntity] = []
        for version_id in version_ids:
            approved.append(
                await self.approve_change(
                    version_id,
                    reviewed_by_user_id=reviewed_by_user_id,
                    review_notes=review_notes,
                )
            )
        return approved

    async def get_change(
        self,
        version_id: str,
        *,
        user_id: str | None = None,
    ) -> KnowledgeEntityVersion | None:
        version = await self.store.get_version(version_id)
        if version is None:
            return None
        if user_id is not None and version.user_id != user_id:
            return None
        return version

    async def list_suggested_changes(
        self,
        user_id: str,
        *,
        source: str | None = None,
        agent_name: str | None = None,
        limit: int = 100,
    ) -> list[KnowledgeEntityVersion]:
        entities = await self.store.list_entities(user_id)
        versions: list[KnowledgeEntityVersion] = []
        for entity in entities:
            entity_versions = await self.store.list_versions(entity.id)
            versions.extend(
                [
                    version
                    for version in entity_versions
                    if version.status == "suggested"
                    and (source is None or version.source == source)
                    and (agent_name is None or version.agent_name == agent_name)
                ]
            )
        return sorted(
            versions,
            key=lambda item: (item.created_at or "", item.id),
            reverse=True,
        )[: max(1, limit)]

    async def reject_change(
        self,
        version_id: str,
        *,
        reviewed_by_user_id: str | None = None,
        review_notes: str = "",
    ) -> KnowledgeEntityVersion:
        version = await self.store.get_version(version_id)
        if version is None:
            raise KnowledgeEntityNotFoundError("Unknown knowledge change.")
        if version.status != "suggested":
            raise KnowledgeChangeConflictError(f"Knowledge change is already {version.status}.")
        entity = await self.store.get_entity(version.entity_id)
        if entity is None:
            raise KnowledgeEntityNotFoundError("Unknown knowledge entity.")
        now = isoformat(datetime.now(timezone.utc))
        rejected_version = replace(
            version,
            status="rejected",
            reviewed_by_user_id=reviewed_by_user_id,
            reviewed_at=now,
            review_notes=review_notes.strip(),
        )
        saved_version = await self.store.update_version(rejected_version)
        if entity.version == 0:
            await self.store.save_entity(replace(entity, status="rejected", updated_at=now))
        await self.audit_recorder(
            event_type="knowledge.change_rejected",
            subject_type="knowledge_entity",
            subject_id=entity.id,
            message=f"Rejected {entity.entity_type} change for {entity.canonical_name}",
            actor_user_id=reviewed_by_user_id,
            metadata={
                "entity_type": entity.entity_type,
                "canonical_name": entity.canonical_name,
                "version_number": version.version_number,
                "review_notes": review_notes.strip(),
            },
            settings=self._resolved_settings(),
        )
        await self._emit_event(
            user_id=entity.user_id,
            event_type="KnowledgeRejected",
            title=f"Rejected {entity.entity_type} update for {entity.canonical_name}",
            entity_id=entity.id,
            payload={"entity_type": entity.entity_type, "version_number": version.version_number},
        )
        return saved_version

    async def find_projects_by_skill(self, user_id: str, skill: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        projects = await self._approved_entities(user_id, entity_types=("project",))
        resolution = await self.resolve_entity_link(user_id, entity_type="skill", raw_name=skill)
        needle = normalize_alias(resolution.canonical_name)
        matches = [entity for entity in projects if needle in normalize_alias(entity_text(entity))]
        return sort_best_examples(matches)[: max(1, limit)]

    async def find_projects_by_technology(self, user_id: str, technology: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        projects = await self._approved_entities(user_id, entity_types=("project",))
        resolution = await self.resolve_entity_link(user_id, entity_type="technology", raw_name=technology)
        needle = normalize_alias(resolution.canonical_name)
        matches = [entity for entity in projects if needle in normalize_alias(entity_text(entity))]
        return sort_best_examples(matches)[: max(1, limit)]

    async def find_best_leadership_examples(self, user_id: str, *, limit: int = 5) -> list[KnowledgeEntity]:
        leadership = await self._approved_entities(user_id, entity_types=("leadership", "achievement"))
        return sort_best_examples([entity for entity in leadership if entity.entity_type == "leadership"])[: max(1, limit)]

    async def find_quantified_achievements(self, user_id: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        achievements = await self._approved_entities(user_id, entity_types=("achievement",))
        return select_quantified_achievements(achievements)[: max(1, limit)]

    async def find_cloud_experience(
        self,
        user_id: str,
        *,
        platform: str | None = None,
        limit: int = 10,
    ) -> list[KnowledgeEntity]:
        entities = await self._approved_entities(user_id, entity_types=("experience", "project"))
        if platform and platform.strip():
            resolution = await self.resolve_entity_link(user_id, entity_type="technology", raw_name=platform)
            terms = [normalize_alias(resolution.canonical_name)]
        else:
            terms = [normalize_alias(term) for term in ("AWS", "Azure", "GCP", "cloud")]
        matches = [entity for entity in entities if any(term in normalize_alias(entity_text(entity)) for term in terms)]
        return sort_best_examples(matches)[: max(1, limit)]

    async def find_backend_projects(self, user_id: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        projects = await self._approved_entities(user_id, entity_types=("project",))
        terms = [normalize_alias(term) for term in ("backend", "api", "platform")]
        matches = [entity for entity in projects if any(term in normalize_alias(entity_text(entity)) for term in terms)]
        return sort_best_examples(matches)[: max(1, limit)]

    async def find_ai_projects(self, user_id: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        projects = await self._approved_entities(user_id, entity_types=("project",))
        terms = [normalize_alias(term) for term in ("AI", "machine learning", "LLM", "model")]
        matches = [entity for entity in projects if any(term in normalize_alias(entity_text(entity)) for term in terms)]
        return sort_best_examples(matches)[: max(1, limit)]

    async def find_resume_evidence(self, user_id: str, *, query: str = "", limit: int = 10) -> list[KnowledgeEvidence]:
        evidence = await self.retrieve_evidence(user_id, query=query, source_types=("resume",), limit=limit * 5)
        return rank_evidence_items(evidence)[: max(1, limit)]

    async def find_recent_experience(self, user_id: str, *, limit: int = 5) -> list[KnowledgeEntity]:
        experience = await self._approved_entities(user_id, entity_types=("experience",))
        return sorted(experience, key=lambda entity: (entity.updated_at or "", entity.id), reverse=True)[: max(1, limit)]

    async def find_domain_experience(self, user_id: str, domain: str, *, limit: int = 10) -> list[KnowledgeEntity]:
        entities = await self._approved_entities(user_id, entity_types=("experience", "project"))
        needle = normalize_alias(domain)
        matches = [entity for entity in entities if needle in normalize_alias(entity_text(entity))]
        return sort_best_examples(matches)[: max(1, limit)]

    async def get_profile_completeness(self, user_id: str) -> dict[str, object]:
        entities = await self._approved_entities(user_id)
        report = compute_knowledge_completeness_report(entities)
        return {
            "overall_score": report.overall_score,
            "areas": report.areas,
        }

    async def run_health_checks(self, user_id: str) -> dict[str, object]:
        entities = await self.store.list_entities(user_id)
        evidence = await self.store.list_evidence(user_id, limit=1000)
        versions: list[KnowledgeEntityVersion] = []
        for entity in entities:
            versions.extend(await self.store.list_versions(entity.id))
        return build_health_report(entities=entities, evidence=evidence, versions=versions)

    async def get_metrics(self, user_id: str) -> dict[str, object]:
        entities = await self.store.list_entities(user_id)
        approved_entities = [entity for entity in entities if entity.status == "approved"]
        evidence = await self.store.list_evidence(user_id, limit=5000)
        health = await self.run_health_checks(user_id)
        completeness = await self.get_profile_completeness(user_id)
        missing_sections = [name for name, area in compute_knowledge_completeness(approved_entities).items() if area["status"] != "ready"]
        versions: list[KnowledgeEntityVersion] = []
        for entity in entities:
            versions.extend(await self.store.list_versions(entity.id))
        conflict_count = len([
            version for version in versions
            if version.status == "suggested" and "conflict" in version.reason.casefold()
        ])
        duplicate_count = int(health["summary"]["duplicate_entities"])
        entity_count = len(approved_entities)
        duplicate_rate = round(duplicate_count / entity_count, 4) if entity_count else 0.0
        health_score = max(
            0,
            100
            - (duplicate_count * 20)
            - (int(health["summary"]["missing_provenance"]) * 10)
            - (int(health["summary"]["orphaned_evidence"]) * 5)
            - (conflict_count * 5),
        )
        return {
            "schema_version": KNOWLEDGE_SCHEMA_VERSION,
            "entities": entity_count,
            "entity_counts": {entity_type: len([entity for entity in approved_entities if entity.entity_type == entity_type]) for entity_type in sorted({entity.entity_type for entity in approved_entities})},
            "evidence_count": len(evidence),
            "coverage_percent": completeness["overall_score"],
            "duplicate_rate": duplicate_rate,
            "merge_conflicts": conflict_count,
            "health_score": health_score,
            "missing_sections": missing_sections,
            "timeline_events": len(await self.get_timeline(user_id, limit=1000)),
        }

    async def get_schema_info(self) -> dict[str, object]:
        return {
            "schema_name": "knowledge_platform",
            "version": KNOWLEDGE_SCHEMA_VERSION,
            "compatibility": "internal_v1",
        }


def build_knowledge_platform_service(settings: AppSettings | None = None) -> KnowledgePlatformService:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return KnowledgePlatformService(store=InMemoryKnowledgePlatformStore(), settings=resolved_settings)
    return KnowledgePlatformService(store=PostgresKnowledgePlatformStore(), settings=resolved_settings)
