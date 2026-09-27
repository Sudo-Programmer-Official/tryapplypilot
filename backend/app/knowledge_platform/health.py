from __future__ import annotations

import re
from typing import Iterable, Sequence

from app.domain import KnowledgeEntity, KnowledgeEntityVersion, KnowledgeEvidence

from .linking import normalize_alias, resolve_entity_alias

_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
_METRIC_PATTERN = re.compile(r"\b(\d[%+,]|million|billion|latency|throughput|scaled|reduced|increased|saved)\b", re.IGNORECASE)


def _entity_text(entity: KnowledgeEntity) -> str:
    text_parts = [entity.canonical_name]
    for value in entity.content.values():
        if isinstance(value, str):
            text_parts.append(value)
        elif isinstance(value, list):
            text_parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            text_parts.extend(str(item) for item in value.values())
    return " ".join(text_parts)


def _extract_years(entity: KnowledgeEntity) -> list[int]:
    return [int(match.group(0)) for match in _YEAR_PATTERN.finditer(_entity_text(entity))]


def build_health_report(
    *,
    entities: Sequence[KnowledgeEntity],
    evidence: Sequence[KnowledgeEvidence],
    versions: Sequence[KnowledgeEntityVersion],
) -> dict[str, object]:
    duplicate_groups: dict[tuple[str, str], list[str]] = {}
    for entity in entities:
        resolution = resolve_entity_alias(entity.entity_type, entity.canonical_name)
        duplicate_groups.setdefault((entity.entity_type, normalize_alias(resolution.canonical_name)), []).append(entity.id)
    duplicates = [
        {"entity_type": entity_type, "normalized_key": normalized_key, "entity_ids": entity_ids}
        for (entity_type, normalized_key), entity_ids in duplicate_groups.items()
        if len(entity_ids) > 1
    ]

    referenced_evidence_ids = {
        evidence_id
        for entity in entities
        for evidence_id in entity.evidence_ids
    } | {
        evidence_id
        for version in versions
        for evidence_id in version.evidence_ids
    }
    orphaned_evidence = [item.id for item in evidence if item.id not in referenced_evidence_ids]
    missing_provenance = [entity.id for entity in entities if not entity.evidence_ids]

    conflicting_timelines: list[dict[str, object]] = []
    overlapping_experiences: list[dict[str, object]] = []
    experience_ranges: list[tuple[KnowledgeEntity, int, int]] = []
    for entity in entities:
        if entity.entity_type != "experience":
            continue
        years = _extract_years(entity)
        if len(years) >= 2:
            start_year = min(years)
            end_year = max(years)
            if start_year > end_year:
                conflicting_timelines.append({"entity_id": entity.id, "years": years})
            else:
                experience_ranges.append((entity, start_year, end_year))
    for index, (left_entity, left_start, left_end) in enumerate(experience_ranges):
        for right_entity, right_start, right_end in experience_ranges[index + 1 :]:
            if left_start <= right_end and right_start <= left_end:
                overlapping_experiences.append(
                    {
                        "entity_ids": [left_entity.id, right_entity.id],
                        "range": [max(left_start, right_start), min(left_end, right_end)],
                    }
                )

    unsupported_achievements = [
        entity.id
        for entity in entities
        if entity.entity_type in {"achievement", "leadership"} and not _METRIC_PATTERN.search(_entity_text(entity))
    ]
    status = "healthy"
    if duplicates or conflicting_timelines or missing_provenance:
        status = "warning"
    if duplicates or conflicting_timelines:
        status = "critical"
    return {
        "status": status,
        "summary": {
            "duplicate_entities": len(duplicates),
            "orphaned_evidence": len(orphaned_evidence),
            "missing_provenance": len(missing_provenance),
            "conflicting_timelines": len(conflicting_timelines),
            "overlapping_experiences": len(overlapping_experiences),
            "unsupported_achievements": len(unsupported_achievements),
        },
        "issues": {
            "duplicate_entities": duplicates,
            "orphaned_evidence": orphaned_evidence,
            "missing_provenance": missing_provenance,
            "conflicting_timelines": conflicting_timelines,
            "overlapping_experiences": overlapping_experiences,
            "unsupported_achievements": unsupported_achievements,
        },
    }
