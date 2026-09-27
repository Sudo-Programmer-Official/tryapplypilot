from __future__ import annotations

import re

from app.domain import KnowledgeEntity

from .conversation import TOPIC_SCHEMAS, TopicGap

_METRIC_PATTERN = re.compile(r"\b(\d[%+,]|million|billion|latency|throughput|scaled|reduced|increased|saved)\b", re.IGNORECASE)

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "architecture": ("architecture", "microservice", "distributed", "kubernetes", "queue", "event", "database"),
    "scale": ("scale", "million", "throughput", "requests", "jobs", "users", "latency"),
    "cloud": ("aws", "azure", "gcp", "cloud", "kubernetes", "terraform"),
    "ai_ml": ("ai", "machine learning", "llm", "model", "inference", "training", "rag", "agent"),
    "performance": ("latency", "throughput", "cache", "performance", "optimization", "p95", "p99"),
    "mentoring": ("mentor", "coached", "guided", "onboarded"),
    "leadership": ("led", "owned", "managed", "drove", "directed"),
    "business_impact": ("revenue", "cost", "customer", "adoption", "business", "conversion"),
}


def _entity_text(entity: KnowledgeEntity) -> str:
    parts = [entity.canonical_name]
    for value in entity.content.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, dict):
            parts.extend(str(item) for item in value.values())
    return " ".join(parts).casefold()


def _detect_topic_signal(topic: str, entities: list[KnowledgeEntity]) -> int:
    texts = [_entity_text(entity) for entity in entities]
    joined = " ".join(texts)
    if topic == "project":
        return 100 if any(entity.entity_type == "project" for entity in entities) else 0
    if topic == "leadership":
        return 100 if any(entity.entity_type == "leadership" for entity in entities) else 35 if any(keyword in joined for keyword in _TOPIC_KEYWORDS["leadership"]) else 0
    if topic == "scale":
        return 85 if _METRIC_PATTERN.search(joined) else 25 if any(entity.entity_type == "project" for entity in entities) else 0
    if topic == "business_impact":
        return 85 if any(keyword in joined for keyword in _TOPIC_KEYWORDS["business_impact"]) else 0
    keywords = _TOPIC_KEYWORDS.get(topic, ())
    matches = sum(1 for keyword in keywords if keyword in joined)
    if matches == 0:
        return 0
    return min(100, 40 + (matches * 15))


def _missing_fields_for_topic(topic: str, entities: list[KnowledgeEntity]) -> list[str]:
    schema = TOPIC_SCHEMAS[topic]
    joined = " ".join(_entity_text(entity) for entity in entities)
    missing: list[str] = []
    for field_name in schema.required_fields:
        normalized = field_name.replace("_", " ")
        if normalized not in joined:
            missing.append(field_name)
    if topic == "scale" and _METRIC_PATTERN.search(joined):
        missing = [field for field in missing if field not in {"scale", "traffic"}]
    return missing


def analyze_profile_gaps(
    *,
    profile: dict[str, list[KnowledgeEntity]],
    completeness_report: dict[str, object],
) -> list[TopicGap]:
    all_entities = [entity for entities in profile.values() for entity in entities]
    gaps: list[TopicGap] = []
    overall_areas = completeness_report.get("areas", {})
    for topic, schema in TOPIC_SCHEMAS.items():
        score = _detect_topic_signal(topic, all_entities)
        missing_fields = _missing_fields_for_topic(topic, all_entities)
        if topic == "project":
            project_area = overall_areas.get("projects", {}) if isinstance(overall_areas, dict) else {}
            score = min(100, max(score, int(project_area.get("score", 0))))
        elif topic == "leadership":
            leadership_area = overall_areas.get("leadership", {}) if isinstance(overall_areas, dict) else {}
            score = min(100, max(score, int(leadership_area.get("score", 0))))
        status = "ready" if score >= 80 else "partial" if score > 0 else "missing"
        priority = schema.priority + (20 if status == "missing" else 10 if status == "partial" else 0)
        rationale = (
            f"{topic.replace('_', ' ').title()} is missing key evidence."
            if status == "missing"
            else f"{topic.replace('_', ' ').title()} has partial coverage but needs stronger detail."
        )
        if status != "ready":
            gaps.append(
                TopicGap(
                    topic=topic,
                    score=score,
                    status=status,
                    priority=priority,
                    rationale=rationale,
                    missing_fields=missing_fields,
                )
            )
    return sorted(gaps, key=lambda item: (item.priority, -item.score), reverse=True)
