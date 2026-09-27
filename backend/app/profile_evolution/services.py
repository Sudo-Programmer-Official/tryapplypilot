from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from uuid import uuid4

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.knowledge_platform import KnowledgePlatformClient, build_knowledge_platform_client

from .completeness import analyze_profile_gaps
from .conversation import (
    ProfileEvolutionQuestion,
    ProfileEvolutionSession,
    ProfileEvolutionSubmissionResult,
    TOPIC_SCHEMAS,
)
from .evidence import build_conversation_evidence_metadata
from .extraction import extract_facts_from_answer
from .interfaces import ProfileEvolutionStore
from .planner import plan_next_question, remaining_topics
from .scoring import calculate_knowledge_gain
from .staging import stage_extracted_facts


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InMemoryProfileEvolutionStore:
    sessions: dict[str, ProfileEvolutionSession] | None = None

    def __post_init__(self) -> None:
        self.sessions = {} if self.sessions is None else self.sessions

    async def get_session(self, user_id: str) -> ProfileEvolutionSession | None:
        return self.sessions.get(user_id)

    async def save_session(self, session: ProfileEvolutionSession) -> ProfileEvolutionSession:
        self.sessions[session.user_id] = session
        return session


def _row_to_session(row) -> ProfileEvolutionSession:
    state = row["state"]
    payload = state if isinstance(state, dict) else json.loads(state)
    return ProfileEvolutionSession.from_dict(payload)


class PostgresProfileEvolutionStore:
    async def get_session(self, user_id: str) -> ProfileEvolutionSession | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT state
                FROM profile_evolution_sessions
                WHERE user_id = $1
                """,
                user_id,
            )
        return _row_to_session(row) if row is not None else None

    async def save_session(self, session: ProfileEvolutionSession) -> ProfileEvolutionSession:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO profile_evolution_sessions (
                    session_id,
                    user_id,
                    current_topic,
                    state,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4::jsonb, COALESCE($5::timestamptz, NOW()), COALESCE($6::timestamptz, NOW()))
                ON CONFLICT (user_id) DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    current_topic = EXCLUDED.current_topic,
                    state = EXCLUDED.state,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                RETURNING state
                """,
                session.id,
                session.user_id,
                session.current_topic,
                json.dumps(session.to_dict()),
                session.created_at,
                session.updated_at,
            )
        assert row is not None
        return _row_to_session(row)


@dataclass
class ProfileEvolutionService:
    store: ProfileEvolutionStore
    knowledge: KnowledgePlatformClient

    async def _build_initial_session(self, user_id: str) -> ProfileEvolutionSession:
        now = _iso_now()
        profile = await self.knowledge.get_profile(user_id)
        completeness = await self.knowledge.get_completeness(user_id)
        gaps = analyze_profile_gaps(profile=profile, completeness_report=completeness)
        return ProfileEvolutionSession(
            id=str(uuid4()),
            user_id=user_id,
            current_topic=None,
            completed_topics=[],
            pending_topics=[gap.topic for gap in gaps],
            skipped_topics=[],
            confidence=0.0,
            extracted_entities=[],
            topic_progress={},
            created_at=now,
            updated_at=now,
        )

    async def get_state(self, user_id: str) -> ProfileEvolutionSession:
        session = await self.store.get_session(user_id)
        if session is None:
            session = await self._build_initial_session(user_id)
            await self.store.save_session(session)
        return session

    async def get_remaining_topics(self, user_id: str) -> list[str]:
        session = await self.get_state(user_id)
        profile = await self.knowledge.get_profile(user_id)
        completeness = await self.knowledge.get_completeness(user_id)
        gaps = analyze_profile_gaps(profile=profile, completeness_report=completeness)
        session.pending_topics = remaining_topics(session, gaps)
        session.updated_at = _iso_now()
        await self.store.save_session(session)
        return session.pending_topics

    async def complete_topic(self, user_id: str, topic: str) -> ProfileEvolutionSession:
        session = await self.get_state(user_id)
        if topic not in session.completed_topics:
            session.completed_topics.append(topic)
        if topic in session.pending_topics:
            session.pending_topics.remove(topic)
        progress = session.progress_for(topic)
        progress.status = "completed"
        session.current_topic = None if session.current_topic == topic else session.current_topic
        session.updated_at = _iso_now()
        return await self.store.save_session(session)

    async def get_next_question(self, user_id: str) -> ProfileEvolutionQuestion | None:
        session = await self.get_state(user_id)
        profile = await self.knowledge.get_profile(user_id)
        completeness = await self.knowledge.get_completeness(user_id)
        gaps = analyze_profile_gaps(profile=profile, completeness_report=completeness)
        session.pending_topics = remaining_topics(session, gaps)
        question = plan_next_question(session=session, gaps=gaps)
        session.updated_at = _iso_now()
        await self.store.save_session(session)
        return question

    async def extract_facts(self, user_id: str, *, topic: str, answer: str):
        session = await self.get_state(user_id)
        progress = session.progress_for(topic)
        return extract_facts_from_answer(topic=topic, answer=answer, existing_fields=progress.extracted_fields)

    async def stage_updates(
        self,
        user_id: str,
        *,
        topic: str,
        answer: str,
        actor_user_id: str,
        question: ProfileEvolutionQuestion | None = None,
    ) -> ProfileEvolutionSubmissionResult:
        session = await self.get_state(user_id)
        progress = session.progress_for(topic)
        candidates = extract_facts_from_answer(topic=topic, answer=answer, existing_fields=progress.extracted_fields)
        evidence = await self.knowledge.create_evidence(
            user_id,
            source_type="conversation",
            source_id=session.id,
            excerpt=answer,
            metadata=build_conversation_evidence_metadata(
                session=session,
                question=question,
                answer=answer,
                topic=topic,
                confidence=max([candidate.confidence for candidate in candidates], default=0.75),
            ),
        )
        staged_version_ids = await stage_extracted_facts(
            knowledge=self.knowledge,
            user_id=user_id,
            actor_user_id=actor_user_id,
            session_id=session.id,
            evidence_id=evidence.id,
            candidates=candidates,
        )
        progress.answers.append(answer)
        for candidate in candidates:
            progress.extracted_fields.update(candidate.extracted_fields)
        progress.staged_version_ids.extend(staged_version_ids)
        progress.confidence = max(progress.confidence, max([candidate.confidence for candidate in candidates], default=0.0))
        session.extracted_entities.extend(
            [
                {
                    "topic": candidate.topic,
                    "entity_type": candidate.entity_type,
                    "canonical_name": candidate.canonical_name,
                    "confidence": candidate.confidence,
                }
                for candidate in candidates
            ]
        )
        schema = TOPIC_SCHEMAS[topic]
        if len([field for field in schema.required_fields if field in progress.extracted_fields]) >= schema.completion_threshold:
            progress.status = "completed"
            if topic not in session.completed_topics:
                session.completed_topics.append(topic)
            session.current_topic = None if session.current_topic == topic else session.current_topic
        session.confidence = max(session.confidence, progress.confidence)
        session.updated_at = _iso_now()
        await self.store.save_session(session)
        next_question = await self.get_next_question(user_id)
        return ProfileEvolutionSubmissionResult(
            session=session,
            extracted_facts=candidates,
            staged_version_ids=staged_version_ids,
            knowledge_gain=calculate_knowledge_gain(topic=topic, candidates=candidates),
            next_question=next_question,
        )

    async def submit_answer(
        self,
        user_id: str,
        *,
        answer: str,
        actor_user_id: str,
        topic: str | None = None,
        question: ProfileEvolutionQuestion | None = None,
    ) -> ProfileEvolutionSubmissionResult:
        session = await self.get_state(user_id)
        resolved_topic = topic or session.current_topic
        if not resolved_topic:
            next_question = await self.get_next_question(user_id)
            if next_question is None:
                return ProfileEvolutionSubmissionResult(
                    session=session,
                    extracted_facts=[],
                    staged_version_ids=[],
                    knowledge_gain={"total": 0},
                    next_question=None,
                )
            resolved_topic = next_question.topic
            question = next_question
        return await self.stage_updates(
            user_id,
            topic=resolved_topic,
            answer=answer,
            actor_user_id=actor_user_id,
            question=question,
        )

    async def calculate_knowledge_gain(self, user_id: str, *, topic: str, answer: str) -> dict[str, int]:
        candidates = await self.extract_facts(user_id, topic=topic, answer=answer)
        return calculate_knowledge_gain(topic=topic, candidates=candidates)


def build_profile_evolution_service(settings: AppSettings | None = None) -> ProfileEvolutionService:
    resolved_settings = settings or get_settings()
    knowledge = build_knowledge_platform_client(resolved_settings)
    if resolved_settings.radar.mode == "seed":
        return ProfileEvolutionService(store=InMemoryProfileEvolutionStore(), knowledge=knowledge)
    return ProfileEvolutionService(store=PostgresProfileEvolutionStore(), knowledge=knowledge)
