from __future__ import annotations

from .conversation import ExtractedFactCandidate

_TOPIC_GAIN_WEIGHTS: dict[str, int] = {
    "project": 4,
    "leadership": 6,
    "architecture": 8,
    "scale": 6,
    "cloud": 4,
    "ai_ml": 6,
    "performance": 5,
    "mentoring": 4,
    "business_impact": 5,
}


def calculate_knowledge_gain(
    *,
    topic: str,
    candidates: list[ExtractedFactCandidate],
) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for candidate in candidates:
        key = candidate.topic
        breakdown[key] = breakdown.get(key, 0) + _TOPIC_GAIN_WEIGHTS.get(candidate.topic, 3)
        if candidate.entity_type == "technology":
            breakdown["technology"] = breakdown.get("technology", 0) + 2
        if candidate.entity_type == "achievement":
            breakdown["achievement"] = breakdown.get("achievement", 0) + 3
    if topic not in breakdown:
        breakdown[topic] = _TOPIC_GAIN_WEIGHTS.get(topic, 3)
    breakdown["total"] = sum(value for key, value in breakdown.items())
    return breakdown
