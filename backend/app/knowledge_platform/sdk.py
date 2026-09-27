from __future__ import annotations

from dataclasses import dataclass

from app.config import AppSettings
from app.domain import KnowledgeEntityType, KnowledgeEvidenceSourceType

from .services import KnowledgePlatformService, build_knowledge_platform_service


@dataclass(frozen=True)
class KnowledgePlatformClient:
    service: KnowledgePlatformService

    async def get_profile(self, user_id: str) -> dict[str, list[object]]:
        return await self.service.get_user_profile(user_id)

    async def find_projects(
        self,
        user_id: str,
        *,
        skill: str | None = None,
        technology: str | None = None,
        domain: str | None = None,
        limit: int = 10,
    ):
        if skill:
            return await self.service.find_projects_by_skill(user_id, skill, limit=limit)
        if technology:
            return await self.service.find_projects_by_technology(user_id, technology, limit=limit)
        if domain:
            return await self.service.find_domain_experience(user_id, domain, limit=limit)
        return await self.service.search_projects(user_id, "", limit=limit)

    async def search_projects(self, user_id: str, query: str, *, limit: int = 10):
        return await self.service.search_projects(user_id, query, limit=limit)

    async def find_best_examples(self, user_id: str, *, topic: str, limit: int = 5):
        normalized = topic.casefold().strip()
        if normalized in {"leadership", "mentorship", "ownership"}:
            return await self.service.find_best_leadership_examples(user_id, limit=limit)
        if normalized in {"achievement", "achievements", "metrics", "impact"}:
            return await self.service.find_quantified_achievements(user_id, limit=limit)
        return await self.service.find_domain_experience(user_id, topic, limit=limit)

    async def find_cloud_experience(self, user_id: str, *, platform: str | None = None, limit: int = 10):
        return await self.service.find_cloud_experience(user_id, platform=platform, limit=limit)

    async def find_recent_experience(self, user_id: str, *, limit: int = 5):
        return await self.service.find_recent_experience(user_id, limit=limit)

    async def find_backend_projects(self, user_id: str, *, limit: int = 10):
        return await self.service.find_backend_projects(user_id, limit=limit)

    async def find_ai_projects(self, user_id: str, *, limit: int = 10):
        return await self.service.find_ai_projects(user_id, limit=limit)

    async def find_evidence(
        self,
        user_id: str,
        *,
        entity_id: str | None = None,
        query: str = "",
        limit: int = 10,
    ):
        if entity_id:
            entity = await self.service.get_entity(entity_id)
            if entity is None:
                return []
            return await self.service.rank_evidence(user_id, entity.evidence_ids[:limit])
        return await self.service.find_resume_evidence(user_id, query=query, limit=limit)

    async def search_skills(self, user_id: str, query: str, *, limit: int = 10):
        return await self.service.search_skills(user_id, query, limit=limit)

    async def get_timeline(self, user_id: str, *, limit: int = 50):
        return await self.service.get_timeline(user_id, limit=limit)

    async def get_metrics(self, user_id: str):
        return await self.service.get_metrics(user_id)

    async def get_completeness(self, user_id: str):
        return await self.service.get_profile_completeness(user_id)

    async def create_evidence(
        self,
        user_id: str,
        *,
        source_type: KnowledgeEvidenceSourceType,
        source_id: str,
        excerpt: str,
        metadata: dict[str, object] | None = None,
    ):
        return await self.service.add_evidence(
            user_id,
            source_type=source_type,
            source_id=source_id,
            excerpt=excerpt,
            metadata=metadata,
        )

    async def stage_update(
        self,
        user_id: str,
        *,
        entity_type: KnowledgeEntityType,
        canonical_name: str,
        new_content: dict[str, object],
        source: str,
        reason: str,
        evidence_ids: list[str],
        actor_user_id: str | None = None,
        confidence: float = 1.0,
        agent_name: str = "",
    ):
        return await self.service.stage_change(
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

    async def get_schema_info(self):
        return await self.service.get_schema_info()


def build_knowledge_platform_client(settings: AppSettings | None = None) -> KnowledgePlatformClient:
    return KnowledgePlatformClient(service=build_knowledge_platform_service(settings))
