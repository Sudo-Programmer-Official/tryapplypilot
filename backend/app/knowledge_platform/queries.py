from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

from app.domain import KnowledgeEntity, KnowledgeEvidence

from .linking import normalize_alias, resolve_entity_alias

_METRIC_PATTERN = re.compile(r"\b(\d[%+,]|million|billion|latency|throughput|scaled|reduced|increased|saved)\b", re.IGNORECASE)

_COMPLETENESS_DIMENSIONS: dict[str, tuple[tuple[str, int], ...]] = {
    "experience": (("experience", 3),),
    "projects": (("project", 2),),
    "leadership": (("leadership", 2),),
    "achievements": (("achievement", 3),),
    "architecture": (("project", 2), ("experience", 1)),
    "ai_experience": (("skill", 1), ("project", 1)),
}


@dataclass(frozen=True)
class CompletenessReport:
    overall_score: int
    areas: dict[str, dict[str, object]]


def entity_text(entity: KnowledgeEntity) -> str:
    text_parts = [entity.canonical_name]
    for value in entity.content.values():
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, list):
            text_parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            text_parts.extend(str(item) for item in value.values())
    return " ".join(text_parts).casefold()


def evidence_priority_score(evidence: KnowledgeEvidence) -> tuple[int, str]:
    metadata_source = str(evidence.metadata.get("source", "")).casefold()
    if metadata_source == "approved_edit" or evidence.metadata.get("approval_status") == "approved":
        return (500, "user-approved edit")
    if evidence.source_type == "resume":
        return (400, "resume")
    if evidence.source_type == "profile":
        return (300, "structured profile")
    if evidence.source_type == "project":
        return (200, "project description")
    if evidence.source_type == "manual_entry":
        return (150, "manual entry")
    return (100, "conversation-derived fact")


def rank_evidence_items(evidence_items: Sequence[KnowledgeEvidence]) -> list[KnowledgeEvidence]:
    return sorted(
        evidence_items,
        key=lambda item: (evidence_priority_score(item)[0], item.created_at or "", item.id),
        reverse=True,
    )


def compute_knowledge_completeness(entities: Iterable[KnowledgeEntity]) -> dict[str, dict[str, object]]:
    grouped: dict[str, int] = {}
    for entity in entities:
        grouped[entity.entity_type] = grouped.get(entity.entity_type, 0) + 1
    rules = {
        "experience": "Describe your most important role and responsibilities.",
        "project": "Tell me about your largest project.",
        "skill": "Add the skills you want the system to optimize for.",
        "technology": "List the tools and platforms you use most often.",
        "achievement": "Share outcomes with metrics so the system can cite impact.",
        "leadership": "Add examples of ownership, mentorship, or team leadership.",
        "education": "Provide your degree or formal education history.",
        "certification": "Add relevant certifications or licenses.",
    }
    completeness: dict[str, dict[str, object]] = {}
    for area, suggested_action in rules.items():
        count = grouped.get(area, 0)
        completeness[area] = {
            "status": "ready" if count > 0 else "missing",
            "count": count,
            "score": 100 if count > 0 else 0,
            "suggested_action": "" if count > 0 else suggested_action,
        }
    return completeness


def compute_knowledge_completeness_report(entities: Iterable[KnowledgeEntity]) -> CompletenessReport:
    entity_list = list(entities)
    area_scores: dict[str, dict[str, object]] = {}
    for area, requirements in _COMPLETENESS_DIMENSIONS.items():
        progress = 0.0
        maximum = 0.0
        suggested_action = ""
        for entity_type, target_count in requirements:
            maximum += 1.0
            count = len([entity for entity in entity_list if entity.entity_type == entity_type])
            coverage = min(count / max(target_count, 1), 1.0)
            progress += coverage
            if coverage < 1.0 and not suggested_action:
                suggested_action = f"Add more {entity_type} evidence to strengthen {area.replace('_', ' ')}."
        score = int(round((progress / maximum) * 100)) if maximum else 0
        area_scores[area] = {
            "score": score,
            "status": "ready" if score >= 80 else "partial" if score > 0 else "missing",
            "suggested_action": "" if score >= 80 else suggested_action,
        }
    overall = int(round(sum(int(item["score"]) for item in area_scores.values()) / max(len(area_scores), 1)))
    return CompletenessReport(overall_score=overall, areas=area_scores)


def filter_entities_by_term(
    entities: Iterable[KnowledgeEntity],
    term: str,
    *,
    entity_type: str | None = None,
) -> list[KnowledgeEntity]:
    if entity_type is None:
        filtered = list(entities)
    else:
        filtered = [entity for entity in entities if entity.entity_type == entity_type]
    if not term.strip():
        return filtered
    resolved = resolve_entity_alias("technology" if entity_type == "technology" else "skill", term)
    needle = normalize_alias(resolved.canonical_name)
    return [entity for entity in filtered if needle in normalize_alias(entity_text(entity))]


def sort_best_examples(entities: Iterable[KnowledgeEntity]) -> list[KnowledgeEntity]:
    return sorted(
        entities,
        key=lambda entity: (
            entity.confidence,
            len(str(entity.content)),
            len(entity.evidence_ids),
            entity.updated_at or "",
        ),
        reverse=True,
    )


def select_quantified_achievements(entities: Iterable[KnowledgeEntity]) -> list[KnowledgeEntity]:
    return sort_best_examples([entity for entity in entities if _METRIC_PATTERN.search(entity_text(entity))])
