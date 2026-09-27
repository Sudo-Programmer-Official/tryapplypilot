from __future__ import annotations

from app.domain import KnowledgeEntity
from app.knowledge_platform import KnowledgePlatformService

from .models import EvidenceRetrievalResult, GapEvidence, JobRequirement, RetrievedRequirementEvidence
from .selection import requirement_matches_entity


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


async def retrieve_requirement_evidence(
    *,
    knowledge: KnowledgePlatformService,
    user_id: str,
    requirements: list[JobRequirement],
    knowledge_entities: list[KnowledgeEntity],
) -> EvidenceRetrievalResult:
    items: list[RetrievedRequirementEvidence] = []
    missing_proof_flags: list[str] = []

    for requirement in requirements:
        matching_entities = [
            entity
            for entity in knowledge_entities
            if requirement_matches_entity(requirement, entity)
        ]
        if not matching_entities:
            items.append(
                RetrievedRequirementEvidence(
                    requirement_label=requirement.label,
                    category=requirement.category,
                    support_level="missing_proof",
                    rationale=f"No approved knowledge evidence currently supports {requirement.label}.",
                    entity_names=[],
                    evidence=[],
                )
            )
            if requirement.category not in {"seniority", "signal"}:
                missing_proof_flags.append(requirement.label)
            continue

        evidence_ids = _dedupe_strings(
            [
                evidence_id
                for entity in matching_entities
                for evidence_id in entity.evidence_ids
            ]
        )
        ranked_evidence = await knowledge.rank_evidence(user_id, evidence_ids[:20]) if evidence_ids else []
        evidence = [
            GapEvidence(
                source_type=item.source_type,
                source_id=item.source_id,
                excerpt=item.excerpt,
                confidence=float(item.metadata.get("confidence", 0.85))
                if isinstance(item.metadata.get("confidence"), (int, float))
                else 0.85,
            )
            for item in ranked_evidence[:3]
        ]
        items.append(
            RetrievedRequirementEvidence(
                requirement_label=requirement.label,
                category=requirement.category,
                support_level="supported",
                rationale=f"Approved knowledge already contains reusable evidence for {requirement.label}.",
                entity_names=_dedupe_strings([entity.canonical_name for entity in matching_entities])[:5],
                evidence=evidence,
            )
        )

    return EvidenceRetrievalResult(
        items=items,
        missing_proof_flags=_dedupe_strings(missing_proof_flags),
    )
