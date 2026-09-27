from __future__ import annotations

from uuid import uuid4

from .completeness import analyze_profile_gaps
from .conversation import ProfileEvolutionQuestion, ProfileEvolutionSession, TOPIC_SCHEMAS, TopicGap


def remaining_topics(session: ProfileEvolutionSession, gaps: list[TopicGap]) -> list[str]:
    blocked = set(session.completed_topics) | set(session.skipped_topics)
    return [gap.topic for gap in gaps if gap.topic not in blocked]


def plan_next_question(
    *,
    session: ProfileEvolutionSession,
    gaps: list[TopicGap],
) -> ProfileEvolutionQuestion | None:
    active_topic = session.current_topic
    if active_topic:
        progress = session.progress_for(active_topic)
        schema = TOPIC_SCHEMAS[active_topic]
        for field_name in schema.required_fields:
            if field_name in progress.extracted_fields:
                continue
            if field_name in progress.asked_follow_ups:
                continue
            prompt = schema.follow_up_questions.get(field_name)
            if prompt:
                progress.asked_follow_ups.append(field_name)
                return ProfileEvolutionQuestion(
                    id=str(uuid4()),
                    topic=active_topic,
                    prompt=prompt,
                    rationale=f"{active_topic.replace('_', ' ').title()} is still missing {field_name.replace('_', ' ')}.",
                    missing_fields=[field_name],
                    confidence=max(0.5, progress.confidence),
                )
    available = remaining_topics(session, gaps)
    if not available:
        return None
    topic = available[0]
    schema = TOPIC_SCHEMAS[topic]
    session.current_topic = topic
    progress = session.progress_for(topic)
    return ProfileEvolutionQuestion(
        id=str(uuid4()),
        topic=topic,
        prompt=schema.initial_question,
        rationale=gaps[0].rationale if gaps and gaps[0].topic == topic else f"{topic.replace('_', ' ').title()} is the highest-value remaining gap.",
        missing_fields=list(schema.required_fields),
        confidence=max(0.55, progress.confidence),
    )
