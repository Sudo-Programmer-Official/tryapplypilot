from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from .models import InterviewPreparationEvidenceReference

STORY_STATUSES = {"draft", "review", "approved", "archived", "superseded"}
STORY_CATEGORIES = {
    "project",
    "leadership",
    "architecture",
    "technical",
    "behavioral",
    "resume_claim",
}
STORY_STRATEGY_VERSION = "interview_stories_v1"
STORY_SECTION_ORDER = ("situation", "task", "action", "result", "reflection")

_METRIC_PATTERN = re.compile(r"(\d+[%xX]|percent|latency|throughput|uptime|reliability|reduced|improved|faster)", re.IGNORECASE)
_OWNERSHIP_PATTERN = re.compile(r"\b(led|owned|designed|built|implemented|architected|mentored|drove|launched)\b", re.IGNORECASE)
_TECHNICAL_PATTERN = re.compile(r"\b(api|service|database|kubernetes|postgresql|architecture|distributed|latency|queue|cloud|deployment)\b", re.IGNORECASE)
_LEADERSHIP_PATTERN = re.compile(r"\b(team|stakeholder|mentor|led|aligned|cross-functional|ownership)\b", re.IGNORECASE)


@dataclass(frozen=True)
class StoryQuestionContext:
    question_id: str
    question: str
    category: str
    requirements: list[str] = field(default_factory=list)
    evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)


@dataclass(frozen=True)
class StorySeed:
    story_group_id: str
    seed_kind: str
    seed_id: str
    category: str
    title: str
    summary: str
    role_text: str = ""
    outcome_text: str = ""
    reflection_text: str = ""
    technical_decisions: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    leadership_moments: list[str] = field(default_factory=list)
    measurable_outcomes: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    related_projects: list[str] = field(default_factory=list)
    source_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    interview_types: list[str] = field(default_factory=list)
    related_resume_version_id: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StoryGenerationContext:
    user_id: str
    application_id: str
    interview_id: str
    interview_type: str
    interview_round: str
    company: str
    role_title: str
    focus_requirements: list[str] = field(default_factory=list)
    question_set_id: str = ""
    questions: list[StoryQuestionContext] = field(default_factory=list)
    seeds: list[StorySeed] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratedStorySection:
    section_key: str
    title: str
    content: list[str] = field(default_factory=list)
    evidence_references: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratedStoryGapPrompt:
    prompt_id: str
    field_key: str
    prompt: str
    reason: str
    topic: str
    related_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    profile_evolution_payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedStoryCoverageLink:
    question_id: str
    question: str
    category: str
    coverage_score: float
    reason: str
    confidence: float


@dataclass(frozen=True)
class GeneratedStoryQualityDimension:
    label: str
    score: int
    rationale: str


@dataclass(frozen=True)
class GeneratedStoryQualityAssessment:
    overall_score: int
    dimensions: list[GeneratedStoryQualityDimension] = field(default_factory=list)
    summary: str = ""


@dataclass(frozen=True)
class GeneratedInterviewStory:
    story_group_id: str
    seed_kind: str
    seed_id: str
    category: str
    title: str
    source_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    related_projects: list[str] = field(default_factory=list)
    related_resume_version_id: str = ""
    related_question_ids: list[str] = field(default_factory=list)
    interview_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    sections: list[GeneratedStorySection] = field(default_factory=list)
    technical_decisions: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    leadership_moments: list[str] = field(default_factory=list)
    measurable_outcomes: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    interviewer_follow_ups: list[str] = field(default_factory=list)
    coverage: list[GeneratedStoryCoverageLink] = field(default_factory=list)
    quality: GeneratedStoryQualityAssessment = field(default_factory=lambda: GeneratedStoryQualityAssessment(overall_score=0))
    missing_information_prompts: list[GeneratedStoryGapPrompt] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


class InterviewStoryGenerator(Protocol):
    async def generate(self, context: StoryGenerationContext) -> list[GeneratedInterviewStory]:
        ...


class DeterministicInterviewStoryGenerator:
    async def generate(self, context: StoryGenerationContext) -> list[GeneratedInterviewStory]:
        stories: list[GeneratedInterviewStory] = []
        for seed in context.seeds:
            coverage = _coverage_links(seed, context.questions, context.focus_requirements)
            if not coverage:
                continue
            sections = _build_sections(seed)
            gaps = _gap_prompts(seed, sections=sections)
            quality = _quality_assessment(seed, sections=sections, coverage=coverage, gaps=gaps)
            stories.append(
                GeneratedInterviewStory(
                    story_group_id=seed.story_group_id,
                    seed_kind=seed.seed_kind,
                    seed_id=seed.seed_id,
                    category=seed.category,
                    title=seed.title,
                    source_evidence=list(seed.source_evidence),
                    related_projects=list(seed.related_projects),
                    related_resume_version_id=seed.related_resume_version_id,
                    related_question_ids=[item.question_id for item in coverage],
                    interview_types=list(seed.interview_types),
                    tags=list(seed.tags),
                    sections=sections,
                    technical_decisions=list(seed.technical_decisions),
                    tradeoffs=list(seed.tradeoffs),
                    leadership_moments=list(seed.leadership_moments),
                    measurable_outcomes=list(seed.measurable_outcomes),
                    lessons_learned=list(seed.lessons_learned),
                    interviewer_follow_ups=_interviewer_follow_ups(coverage, gaps),
                    coverage=coverage,
                    quality=quality,
                    missing_information_prompts=gaps,
                    metadata={
                        "seed_kind": seed.seed_kind,
                        "seed_id": seed.seed_id,
                        "coverage_score": round(sum(item.coverage_score for item in coverage) / len(coverage), 3),
                        "question_count": len(coverage),
                    },
                )
            )
        return stories


def _build_sections(seed: StorySeed) -> list[GeneratedStorySection]:
    situation_lines = _uniq(_split_lines(seed.summary))
    task_lines = _uniq(_split_lines(seed.role_text))
    action_lines = _uniq(seed.technical_decisions or _extract_action_lines(seed.summary))
    result_lines = _uniq(seed.measurable_outcomes or _split_lines(seed.outcome_text))
    reflection_lines = _uniq(seed.lessons_learned or _split_lines(seed.reflection_text))
    all_evidence = list(seed.source_evidence)
    return [
        GeneratedStorySection(
            section_key="situation",
            title="Situation",
            content=situation_lines,
            evidence_references=all_evidence[:2],
            missing_fields=[] if situation_lines else ["situation"],
        ),
        GeneratedStorySection(
            section_key="task",
            title="Task",
            content=task_lines,
            evidence_references=all_evidence[:2],
            missing_fields=[] if task_lines else ["ownership"],
        ),
        GeneratedStorySection(
            section_key="action",
            title="Action",
            content=action_lines,
            evidence_references=all_evidence[:3],
            missing_fields=[] if action_lines else ["actions"],
        ),
        GeneratedStorySection(
            section_key="result",
            title="Result",
            content=result_lines,
            evidence_references=all_evidence[:3],
            missing_fields=[] if result_lines else ["measurable_outcome"],
        ),
        GeneratedStorySection(
            section_key="reflection",
            title="Reflection",
            content=reflection_lines,
            evidence_references=all_evidence[:2],
            missing_fields=[] if reflection_lines else ["reflection"],
        ),
    ]


def _gap_prompts(seed: StorySeed, *, sections: list[GeneratedStorySection]) -> list[GeneratedStoryGapPrompt]:
    text_blob = " ".join(
        [
            seed.summary,
            seed.role_text,
            seed.outcome_text,
            seed.reflection_text,
            " ".join(seed.measurable_outcomes),
            " ".join(seed.technical_decisions),
            " ".join(seed.lessons_learned),
        ]
    )
    prompts: list[GeneratedStoryGapPrompt] = []
    if not _OWNERSHIP_PATTERN.search(text_blob):
        prompts.append(
            _gap_prompt(
                seed,
                field_key="ownership",
                prompt="What part of the architecture or delivery did you personally own?",
                reason="Ownership is not explicit enough in the current evidence to support interview follow-ups.",
                topic="architecture" if seed.category in {"architecture", "technical"} else "project",
            )
        )
    if not _METRIC_PATTERN.search(text_blob):
        prompts.append(
            _gap_prompt(
                seed,
                field_key="measurable_outcome",
                prompt="What measurable impact did this work have?",
                reason="The current evidence does not clearly capture a measurable outcome or before/after result.",
                topic="performance" if seed.category in {"technical", "architecture"} else "project",
            )
        )
    if not sections[-1].content:
        prompts.append(
            _gap_prompt(
                seed,
                field_key="reflection",
                prompt="What did you learn from this work, and what would you do differently now?",
                reason="Reflection is useful for interviewer follow-ups and is currently missing from the canonical evidence.",
                topic="project",
            )
        )
    return prompts


def _gap_prompt(seed: StorySeed, *, field_key: str, prompt: str, reason: str, topic: str) -> GeneratedStoryGapPrompt:
    return GeneratedStoryGapPrompt(
        prompt_id=str(uuid5(NAMESPACE_URL, f"story-gap:{seed.story_group_id}:{field_key}:{prompt}")),
        field_key=field_key,
        prompt=prompt,
        reason=reason,
        topic=topic,
        related_evidence=list(seed.source_evidence[:2]),
        profile_evolution_payload={
            "topic": topic,
            "question_prompt": prompt,
        },
    )


def _coverage_links(
    seed: StorySeed,
    questions: list[StoryQuestionContext],
    focus_requirements: list[str],
) -> list[GeneratedStoryCoverageLink]:
    links: list[GeneratedStoryCoverageLink] = []
    tags = {item.casefold() for item in seed.tags}
    title_blob = f"{seed.title} {seed.summary}".casefold()
    for question in questions:
        overlap = 0.0
        reasons: list[str] = []
        for requirement in question.requirements:
            normalized = requirement.casefold()
            if normalized in title_blob or normalized in tags:
                overlap += 0.3
                reasons.append(f"Maps to {requirement}.")
        for evidence in question.evidence:
            if any(
                evidence.source_id == ref.source_id
                or (evidence.entity_id and evidence.entity_id == ref.entity_id)
                or evidence.label.casefold() in title_blob
                for ref in seed.source_evidence
            ):
                overlap += 0.35
                reasons.append("Shares supporting evidence with the interview question.")
                break
        if question.category in {"behavioral", "leadership"} and seed.category in {"leadership", "behavioral"}:
            overlap += 0.2
            reasons.append("Behavioral/leadership alignment.")
        if question.category in {"technical", "system_design", "architecture", "project_deep_dive"} and seed.category in {"project", "technical", "architecture"}:
            overlap += 0.2
            reasons.append("Technical/project depth alignment.")
        if not reasons and any(item.casefold() in title_blob for item in focus_requirements):
            overlap += 0.15
            reasons.append("Matches an active preparation focus area.")
        score = max(0.0, min(1.0, overlap))
        if score < 0.35:
            continue
        links.append(
            GeneratedStoryCoverageLink(
                question_id=question.question_id,
                question=question.question,
                category=question.category,
                coverage_score=round(score, 3),
                reason=" ".join(_uniq(reasons)),
                confidence=round(min(0.95, 0.45 + score / 2), 3),
            )
        )
    return sorted(links, key=lambda item: (item.coverage_score, item.confidence, item.question_id), reverse=True)[:6]


def _quality_assessment(
    seed: StorySeed,
    *,
    sections: list[GeneratedStorySection],
    coverage: list[GeneratedStoryCoverageLink],
    gaps: list[GeneratedStoryGapPrompt],
) -> GeneratedStoryQualityAssessment:
    section_map = {item.section_key: item for item in sections}
    completeness = 100 - (sum(20 for item in sections if not item.content))
    evidence_strength = min(100, 35 + len(seed.source_evidence) * 20)
    technical_depth = 85 if _TECHNICAL_PATTERN.search(" ".join(seed.technical_decisions + [seed.summary])) else 45
    measurable_impact = 90 if seed.measurable_outcomes or _METRIC_PATTERN.search(seed.summary) else 40
    ownership_clarity = 90 if _OWNERSHIP_PATTERN.search(f"{seed.role_text} {seed.summary}") else 35
    leadership = 85 if seed.leadership_moments or _LEADERSHIP_PATTERN.search(f"{seed.role_text} {seed.summary}") else 40
    reflection = 85 if section_map["reflection"].content else 30
    interview_relevance = min(100, 40 + int(sum(item.coverage_score for item in coverage) / max(len(coverage), 1) * 55))
    dimensions = [
        GeneratedStoryQualityDimension("completeness", max(0, completeness), _dimension_reason("Completeness", completeness, gaps)),
        GeneratedStoryQualityDimension("evidence_strength", evidence_strength, f"Grounded in {len(seed.source_evidence)} linked evidence reference(s)."),
        GeneratedStoryQualityDimension("technical_depth", technical_depth, _dimension_reason("Technical depth", technical_depth, [])),
        GeneratedStoryQualityDimension("measurable_impact", measurable_impact, _dimension_reason("Measurable impact", measurable_impact, gaps)),
        GeneratedStoryQualityDimension("ownership_clarity", ownership_clarity, _dimension_reason("Ownership clarity", ownership_clarity, gaps)),
        GeneratedStoryQualityDimension("leadership", leadership, _dimension_reason("Leadership", leadership, gaps)),
        GeneratedStoryQualityDimension("reflection", reflection, _dimension_reason("Reflection", reflection, gaps)),
        GeneratedStoryQualityDimension("interview_relevance", interview_relevance, f"Supports {len(coverage)} linked interview question(s)."),
    ]
    overall = int(round(sum(item.score for item in dimensions) / len(dimensions)))
    summary = "Story is interview-ready." if overall >= 75 and not gaps else "Story is useful, but it still needs clarification before it becomes a strong interview asset."
    return GeneratedStoryQualityAssessment(overall_score=overall, dimensions=dimensions, summary=summary)


def _dimension_reason(label: str, score: int, gaps: list[GeneratedStoryGapPrompt]) -> str:
    if score >= 80:
        return f"{label} is well supported by the current evidence."
    if gaps:
        return f"{label} is weaker because some context is missing and follow-up prompts were generated."
    return f"{label} is partial and could be sharpened before interview use."


def _interviewer_follow_ups(
    coverage: list[GeneratedStoryCoverageLink],
    gaps: list[GeneratedStoryGapPrompt],
) -> list[str]:
    prompts = [f"Be ready to go deeper on: {item.question}" for item in coverage[:2]]
    prompts.extend(f"Expect follow-up on {item.field_key.replace('_', ' ')}." for item in gaps[:2])
    return _uniq(prompts)


def story_group_id(*, user_id: str, seed_kind: str, seed_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"interview-story-group:{user_id}:{seed_kind}:{seed_id}"))


def _split_lines(value: str) -> list[str]:
    return _uniq([" ".join(part.split()).strip() for part in re.split(r"[.\n]", value) if " ".join(part.split()).strip()])


def _extract_action_lines(summary: str) -> list[str]:
    lines = _split_lines(summary)
    return lines[:2]


def _uniq(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        item = " ".join(str(value).split()).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned
