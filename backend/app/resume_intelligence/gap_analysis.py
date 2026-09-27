from __future__ import annotations

from typing import Iterable

from app.domain import KnowledgeEntity, KnowledgeEvidence
from app.knowledge_platform import KnowledgePlatformService
from app.knowledge_platform.queries import entity_text
from app.resume_library import ResumeDocument

from .models import GapAnalysisResult, GapEvidence, JobRequirement, RequirementAssessment, ResumeIntelligenceJobContext
from .selection import requirement_matches_entity, requirement_matches_resume


def _resume_excerpt(resume: ResumeDocument, requirement: JobRequirement, *, window: int = 180) -> str:
    lower_text = resume.extracted_text.casefold()
    for candidate in (requirement.label, *requirement.keywords):
        index = lower_text.find(candidate.casefold())
        if index >= 0:
            start = max(0, index - 40)
            end = min(len(resume.extracted_text), index + window)
            return " ".join(resume.extracted_text[start:end].split())
    return " ".join(resume.extracted_text.split())[:window].strip()


def _dedupe_labels(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _entity_confidence_percent(entities: list[KnowledgeEntity]) -> int:
    if not entities:
        return 0
    return int(round((sum(entity.confidence for entity in entities) / len(entities)) * 100))


def _to_gap_evidence(items: list[KnowledgeEvidence]) -> list[GapEvidence]:
    evidence: list[GapEvidence] = []
    for item in items:
        confidence = item.metadata.get("confidence")
        numeric_confidence = float(confidence) if isinstance(confidence, (int, float)) else 0.8
        evidence.append(
            GapEvidence(
                source_type=item.source_type,
                source_id=item.source_id,
                excerpt=item.excerpt,
                confidence=max(0.0, min(numeric_confidence, 1.0)),
            )
        )
    return evidence


async def analyze_resume_gaps(
    *,
    knowledge: KnowledgePlatformService,
    user_id: str,
    job: ResumeIntelligenceJobContext,
    requirements: list[JobRequirement],
    selected_resume: ResumeDocument | None,
    knowledge_entities: list[KnowledgeEntity],
) -> GapAnalysisResult:
    covered: list[RequirementAssessment] = []
    weak: list[RequirementAssessment] = []
    missing: list[RequirementAssessment] = []
    keyword_opportunities: list[str] = []
    risk_flags: list[str] = []

    for requirement in requirements:
        matching_entities = [entity for entity in knowledge_entities if requirement_matches_entity(requirement, entity)]
        ranked_evidence = []
        if matching_entities:
            evidence_ids = _dedupe_labels(
                evidence_id
                for entity in matching_entities
                for evidence_id in entity.evidence_ids
            )
            if evidence_ids:
                ranked_evidence = await knowledge.rank_evidence(user_id, evidence_ids[:12])
        evidence = _to_gap_evidence(ranked_evidence[:2])
        if selected_resume is not None and requirement_matches_resume(requirement, selected_resume):
            resume_excerpt = _resume_excerpt(selected_resume, requirement)
            assessment_evidence = [
                GapEvidence(
                    source_type="resume_asset",
                    source_id=selected_resume.id,
                    excerpt=resume_excerpt,
                    confidence=0.95,
                ),
                *evidence,
            ]
            covered.append(
                RequirementAssessment(
                    label=requirement.label,
                    category=requirement.category,
                    status="covered",
                    source="resume",
                    confidence=max(75, _entity_confidence_percent(matching_entities) or 88),
                    reason=f"The selected resume already emphasizes {requirement.label}.",
                    evidence=assessment_evidence[:3],
                )
            )
            continue

        if matching_entities or evidence:
            weak.append(
                RequirementAssessment(
                    label=requirement.label,
                    category=requirement.category,
                    status="weak",
                    source="knowledge",
                    confidence=max(60, _entity_confidence_percent(matching_entities) or 70),
                    reason=f"Approved knowledge supports {requirement.label}, but the selected resume does not surface it clearly yet.",
                    evidence=evidence[:3],
                )
            )
            keyword_opportunities.append(requirement.label)
            if requirement.label in job.gaps:
                risk_flags.append(
                    f"{requirement.label} is already flagged as a match gap and still needs stronger resume emphasis."
                )
            continue

        missing.append(
            RequirementAssessment(
                label=requirement.label,
                category=requirement.category,
                status="missing",
                source="unsupported",
                confidence=25,
                reason=f"No approved resume or knowledge evidence currently supports {requirement.label}.",
                evidence=[],
            )
        )
        if requirement.category not in {"seniority", "signal"}:
            risk_flags.append(
                f"The job asks for {requirement.label}, but Resume Intelligence cannot verify that claim yet."
            )

    return GapAnalysisResult(
        covered_requirements=covered,
        weak_requirements=weak,
        missing_requirements=missing,
        keyword_opportunities=_dedupe_labels(keyword_opportunities),
        risk_flags=_dedupe_labels(risk_flags),
    )
