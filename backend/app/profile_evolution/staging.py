from __future__ import annotations

from app.knowledge_platform import KnowledgePlatformClient

from .conversation import ExtractedFactCandidate


async def stage_extracted_facts(
    *,
    knowledge: KnowledgePlatformClient,
    user_id: str,
    actor_user_id: str,
    session_id: str,
    evidence_id: str,
    candidates: list[ExtractedFactCandidate],
) -> list[str]:
    version_ids: list[str] = []
    for candidate in candidates:
        version = await knowledge.stage_update(
            user_id,
            entity_type=candidate.entity_type,
            canonical_name=candidate.canonical_name,
            new_content={**candidate.content, "profile_evolution_session_id": session_id},
            source="profile_evolution",
            reason=candidate.reason,
            evidence_ids=[evidence_id],
            actor_user_id=actor_user_id,
            confidence=candidate.confidence,
            agent_name="profile_evolution",
        )
        version_ids.append(version.id)
    return version_ids
