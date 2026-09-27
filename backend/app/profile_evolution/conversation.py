from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


ProfileEvolutionStatus = Literal["pending", "completed", "skipped"]


@dataclass(frozen=True)
class TopicSchema:
    topic: str
    initial_question: str
    required_fields: tuple[str, ...]
    optional_fields: tuple[str, ...]
    follow_up_questions: dict[str, str]
    completion_threshold: int
    priority: int


TOPIC_SCHEMAS: dict[str, TopicSchema] = {
    "project": TopicSchema(
        topic="project",
        initial_question="Tell me about the largest system or project you've built.",
        required_fields=("project_name", "problem", "role", "outcome"),
        optional_fields=("technologies", "domain", "business_impact"),
        follow_up_questions={
            "project_name": "What was that project or system called?",
            "problem": "What problem was that system solving?",
            "role": "What was your role in that project?",
            "outcome": "What was the outcome or result?",
        },
        completion_threshold=3,
        priority=95,
    ),
    "architecture": TopicSchema(
        topic="architecture",
        initial_question="Tell me about the architecture of the largest system you've built.",
        required_fields=("architecture", "cloud", "database", "scale", "role"),
        optional_fields=("caching", "queue", "performance"),
        follow_up_questions={
            "architecture": "What were the main services or components in that architecture?",
            "cloud": "Which cloud provider or infrastructure platform did it run on?",
            "database": "What database or storage layer did it use?",
            "scale": "What scale was the system operating at?",
            "role": "What part of that architecture did you personally own?",
            "caching": "Did the system use caching anywhere?",
            "queue": "Did you use queues, streams, or background workers?",
        },
        completion_threshold=4,
        priority=100,
    ),
    "leadership": TopicSchema(
        topic="leadership",
        initial_question="Tell me about a time you led a project or technical initiative.",
        required_fields=("leadership_scope", "team_size", "outcome"),
        optional_fields=("mentoring", "cross_functional"),
        follow_up_questions={
            "leadership_scope": "What exactly were you leading or owning?",
            "team_size": "How many engineers or stakeholders were involved?",
            "outcome": "What was the final outcome?",
            "mentoring": "Did you mentor or unblock other engineers during that work?",
        },
        completion_threshold=3,
        priority=92,
    ),
    "scale": TopicSchema(
        topic="scale",
        initial_question="What is the highest-scale system you've worked on, and how large was it?",
        required_fields=("scale", "traffic", "latency", "reliability"),
        optional_fields=("cost", "throughput"),
        follow_up_questions={
            "scale": "Roughly how many users, jobs, or requests did it handle?",
            "traffic": "What kind of request or processing volume did it see?",
            "latency": "Were there latency or performance targets you improved?",
            "reliability": "What reliability or uptime requirements did it have?",
        },
        completion_threshold=3,
        priority=90,
    ),
    "cloud": TopicSchema(
        topic="cloud",
        initial_question="What cloud or infrastructure platforms have you worked with most deeply?",
        required_fields=("cloud", "deployment", "operations"),
        optional_fields=("kubernetes", "iac"),
        follow_up_questions={
            "cloud": "Which cloud provider did you use most?",
            "deployment": "How were systems deployed and managed there?",
            "operations": "What operational responsibilities did you own?",
            "iac": "Did you use any infrastructure-as-code tools?",
        },
        completion_threshold=2,
        priority=80,
    ),
    "ai_ml": TopicSchema(
        topic="ai_ml",
        initial_question="Have you built or supported any AI or machine learning systems?",
        required_fields=("ai_problem", "model_or_workflow", "impact"),
        optional_fields=("data", "evaluation", "inference"),
        follow_up_questions={
            "ai_problem": "What AI or ML problem was the system solving?",
            "model_or_workflow": "What model, agent, or ML workflow was involved?",
            "impact": "What measurable impact did it have?",
            "evaluation": "How did you measure whether it was working well?",
        },
        completion_threshold=2,
        priority=78,
    ),
    "performance": TopicSchema(
        topic="performance",
        initial_question="Tell me about the most important performance improvement you've made.",
        required_fields=("bottleneck", "improvement", "metric_before", "metric_after"),
        optional_fields=("tooling", "caching"),
        follow_up_questions={
            "bottleneck": "What was the main performance bottleneck?",
            "improvement": "What change did you make?",
            "metric_before": "What was the performance before the change?",
            "metric_after": "What was the performance after the change?",
        },
        completion_threshold=3,
        priority=76,
    ),
    "mentoring": TopicSchema(
        topic="mentoring",
        initial_question="Tell me about how you've mentored or grown other engineers.",
        required_fields=("mentoring_scope", "people_supported", "outcome"),
        optional_fields=("process", "career_growth"),
        follow_up_questions={
            "mentoring_scope": "What kind of mentoring or coaching did you provide?",
            "people_supported": "How many people did you support?",
            "outcome": "What changed for them or the team as a result?",
        },
        completion_threshold=2,
        priority=74,
    ),
    "business_impact": TopicSchema(
        topic="business_impact",
        initial_question="What project you worked on had the strongest business impact?",
        required_fields=("business_impact", "customer_or_revenue", "outcome"),
        optional_fields=("product_impact", "metric"),
        follow_up_questions={
            "business_impact": "How did that work help the business?",
            "customer_or_revenue": "Did it affect customers, revenue, cost, or adoption?",
            "outcome": "What measurable result came from it?",
        },
        completion_threshold=2,
        priority=72,
    ),
}


@dataclass(frozen=True)
class TopicGap:
    topic: str
    score: int
    status: str
    priority: int
    rationale: str
    missing_fields: list[str]


@dataclass(frozen=True)
class ProfileEvolutionQuestion:
    id: str
    topic: str
    prompt: str
    rationale: str
    missing_fields: list[str]
    confidence: float


@dataclass(frozen=True)
class ExtractedFactCandidate:
    topic: str
    entity_type: str
    canonical_name: str
    content: dict[str, object]
    reason: str
    confidence: float
    extracted_fields: dict[str, object] = field(default_factory=dict)


@dataclass
class TopicProgress:
    topic: str
    answers: list[str] = field(default_factory=list)
    extracted_fields: dict[str, object] = field(default_factory=dict)
    asked_follow_ups: list[str] = field(default_factory=list)
    staged_version_ids: list[str] = field(default_factory=list)
    status: ProfileEvolutionStatus = "pending"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TopicProgress:
        return cls(
            topic=str(payload.get("topic", "")),
            answers=[str(item) for item in payload.get("answers", [])] if isinstance(payload.get("answers"), list) else [],
            extracted_fields=dict(payload.get("extracted_fields", {})) if isinstance(payload.get("extracted_fields"), dict) else {},
            asked_follow_ups=[str(item) for item in payload.get("asked_follow_ups", [])] if isinstance(payload.get("asked_follow_ups"), list) else [],
            staged_version_ids=[str(item) for item in payload.get("staged_version_ids", [])] if isinstance(payload.get("staged_version_ids"), list) else [],
            status=str(payload.get("status", "pending")),  # type: ignore[arg-type]
            confidence=float(payload.get("confidence", 0.0)),
        )


@dataclass
class ProfileEvolutionSession:
    id: str
    user_id: str
    current_topic: str | None = None
    completed_topics: list[str] = field(default_factory=list)
    pending_topics: list[str] = field(default_factory=list)
    skipped_topics: list[str] = field(default_factory=list)
    confidence: float = 0.0
    extracted_entities: list[dict[str, object]] = field(default_factory=list)
    topic_progress: dict[str, TopicProgress] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def progress_for(self, topic: str) -> TopicProgress:
        if topic not in self.topic_progress:
            self.topic_progress[topic] = TopicProgress(topic=topic)
        return self.topic_progress[topic]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "current_topic": self.current_topic,
            "completed_topics": self.completed_topics,
            "pending_topics": self.pending_topics,
            "skipped_topics": self.skipped_topics,
            "confidence": self.confidence,
            "extracted_entities": self.extracted_entities,
            "topic_progress": {topic: progress.to_dict() for topic, progress in self.topic_progress.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ProfileEvolutionSession:
        progress_payload = payload.get("topic_progress", {})
        return cls(
            id=str(payload.get("id", "")),
            user_id=str(payload.get("user_id", "")),
            current_topic=str(payload.get("current_topic")) if payload.get("current_topic") is not None else None,
            completed_topics=[str(item) for item in payload.get("completed_topics", [])] if isinstance(payload.get("completed_topics"), list) else [],
            pending_topics=[str(item) for item in payload.get("pending_topics", [])] if isinstance(payload.get("pending_topics"), list) else [],
            skipped_topics=[str(item) for item in payload.get("skipped_topics", [])] if isinstance(payload.get("skipped_topics"), list) else [],
            confidence=float(payload.get("confidence", 0.0)),
            extracted_entities=[dict(item) for item in payload.get("extracted_entities", [])] if isinstance(payload.get("extracted_entities"), list) else [],
            topic_progress={
                str(topic): TopicProgress.from_dict(progress)
                for topic, progress in progress_payload.items()
                if isinstance(progress_payload, dict) and isinstance(progress, dict)
            },
            created_at=str(payload.get("created_at")) if payload.get("created_at") is not None else None,
            updated_at=str(payload.get("updated_at")) if payload.get("updated_at") is not None else None,
        )


@dataclass(frozen=True)
class ProfileEvolutionSubmissionResult:
    session: ProfileEvolutionSession
    extracted_facts: list[ExtractedFactCandidate]
    staged_version_ids: list[str]
    knowledge_gain: dict[str, int]
    next_question: ProfileEvolutionQuestion | None = None
