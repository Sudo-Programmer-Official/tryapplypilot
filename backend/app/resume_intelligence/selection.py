from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.domain import KnowledgeEntity
from app.knowledge_platform.queries import entity_text
from app.knowledge_platform.utils import normalize_name
from app.resume_library import ResumeDocument

from .models import JobRequirement, ResumeIntelligenceJobContext, ResumeSelectionReason, ResumeSelectionResult


@dataclass(frozen=True)
class RequirementPattern:
    label: str
    category: str
    keywords: tuple[str, ...]


_REQUIREMENT_PATTERNS: tuple[RequirementPattern, ...] = (
    RequirementPattern("Python", "technology", ("python",)),
    RequirementPattern("FastAPI", "technology", ("fastapi",)),
    RequirementPattern("PostgreSQL", "technology", ("postgresql", "postgres")),
    RequirementPattern("Kubernetes", "technology", ("kubernetes", "k8s")),
    RequirementPattern("Docker", "technology", ("docker", "container", "containers")),
    RequirementPattern("AWS", "technology", ("aws", "amazon web services")),
    RequirementPattern("Azure", "technology", ("azure",)),
    RequirementPattern("GCP", "technology", ("gcp", "google cloud")),
    RequirementPattern("Terraform", "technology", ("terraform",)),
    RequirementPattern("Kafka", "technology", ("kafka",)),
    RequirementPattern("Redis", "technology", ("redis",)),
    RequirementPattern("MongoDB", "technology", ("mongodb", "mongo")),
    RequirementPattern("SQL", "technology", (" sql ", "mysql", "sql server", "mssql")),
    RequirementPattern("gRPC", "technology", ("grpc",)),
    RequirementPattern("TypeScript", "technology", ("typescript",)),
    RequirementPattern("JavaScript", "technology", ("javascript",)),
    RequirementPattern("React", "technology", ("react", "react.js", "reactjs")),
    RequirementPattern("Go", "technology", (" golang ", " go ", "golang")),
    RequirementPattern("Java", "technology", (" java ",)),
    RequirementPattern("Backend", "capability", ("backend", "api", "microservice", "services")),
    RequirementPattern("Platform", "capability", ("platform",)),
    RequirementPattern("Infrastructure", "capability", ("infrastructure", "infra", "sre", "reliability")),
    RequirementPattern("Distributed Systems", "capability", ("distributed systems", "distributed", "high scale", "scalability")),
    RequirementPattern("Observability", "capability", ("observability", "monitoring", "telemetry")),
    RequirementPattern("Security", "capability", ("security", "secure", "identity", "auth")),
    RequirementPattern("AI", "capability", ("artificial intelligence", "generative ai", " genai ", " ai ")),
    RequirementPattern("LLMs", "capability", ("llm", "large language model", "large language")),
    RequirementPattern("Agents", "capability", ("agentic", " ai agent", "agents")),
    RequirementPattern("ML Platform", "capability", ("ml platform", "mlops", "machine learning platform")),
    RequirementPattern("Payments", "domain", ("payment", "billing", "invoice", "procurement", "fintech")),
    RequirementPattern("Identity", "domain", ("identity", "authentication", "authorization", "iam")),
    RequirementPattern("Healthcare", "domain", ("healthcare", "clinical", "payer", "medical")),
    RequirementPattern("Data", "domain", ("data platform", "data engineering", "analytics", "warehouse")),
    RequirementPattern("Staff", "seniority", ("staff",)),
    RequirementPattern("Senior", "seniority", ("senior",)),
    RequirementPattern("Principal", "seniority", ("principal",)),
)

_ROLE_FOCUS_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AI Platform", ("AI", "LLMs", "Agents", "ML Platform")),
    ("Platform", ("Platform", "Infrastructure", "Kubernetes", "Observability")),
    ("Frontend", ("React", "TypeScript", "JavaScript")),
)


def _normalized_haystack(*values: str) -> str:
    return f" {' '.join(value.strip() for value in values if value).casefold()} "


def extract_job_requirements(job: ResumeIntelligenceJobContext) -> list[JobRequirement]:
    haystack = _normalized_haystack(
        job.company,
        job.title,
        job.location,
        job.remote_policy,
        job.description_text,
        " ".join(job.why),
        " ".join(job.gaps),
        job.recommended_resume,
    )
    requirements: list[JobRequirement] = []
    seen: set[str] = set()
    for pattern in _REQUIREMENT_PATTERNS:
        if pattern.label in seen:
            continue
        if any(keyword.casefold() in haystack for keyword in pattern.keywords):
            requirements.append(JobRequirement(label=pattern.label, category=pattern.category, keywords=pattern.keywords))
            seen.add(pattern.label)
    for label in [*job.why, *job.gaps]:
        normalized = normalize_name(label)
        if not normalized or normalized in seen:
            continue
        requirements.append(JobRequirement(label=normalized, category="signal", keywords=(normalized.casefold(),)))
        seen.add(normalized)
    return requirements


def infer_role_focus(requirements: Iterable[JobRequirement]) -> str:
    labels = {requirement.label for requirement in requirements}
    for role_focus, hints in _ROLE_FOCUS_HINTS:
        if any(hint in labels for hint in hints):
            return role_focus
    return "Backend"


def requirement_matches_text(requirement: JobRequirement, text: str) -> bool:
    haystack = _normalized_haystack(text)
    normalized_label = requirement.label.casefold()
    if normalized_label in haystack:
        return True
    return any(keyword.casefold() in haystack for keyword in requirement.keywords)


def requirement_matches_resume(requirement: JobRequirement, resume: ResumeDocument) -> bool:
    if requirement.label in resume.extracted_skills:
        return True
    return requirement_matches_text(
        requirement,
        " ".join(
            [
                resume.display_name,
                resume.original_filename,
                resume.role_focus,
                resume.extracted_text,
            ]
        ),
    )


def requirement_matches_entity(requirement: JobRequirement, entity: KnowledgeEntity) -> bool:
    return requirement_matches_text(requirement, entity_text(entity))


def select_resume_for_job(
    job: ResumeIntelligenceJobContext,
    resumes: list[ResumeDocument],
    *,
    requirements: list[JobRequirement],
    knowledge_entities: list[KnowledgeEntity],
) -> ResumeSelectionResult:
    if not resumes:
        return ResumeSelectionResult(
            status="no_resumes",
            confidence=0,
            fallback_behavior="No resume library is available yet. Resume Intelligence needs at least one uploaded resume.",
        )

    inferred_role_focus = infer_role_focus(requirements)
    recommended_hint = normalize_name(job.recommended_resume)
    knowledge_requirement_labels = {
        requirement.label
        for requirement in requirements
        if any(requirement_matches_entity(requirement, entity) for entity in knowledge_entities)
    }
    ranked: list[tuple[int, ResumeDocument, list[str], list[ResumeSelectionReason]]] = []
    for resume in resumes:
        matched = [requirement.label for requirement in requirements if requirement_matches_resume(requirement, resume)]
        overlap = len(matched)
        skill_overlap = len(set(resume.extracted_skills) & {requirement.label for requirement in requirements})
        score = 30 + (overlap * 12) + (skill_overlap * 6)
        reasons: list[ResumeSelectionReason] = []
        if matched:
            reasons.append(
                ResumeSelectionReason(
                    label="Requirement overlap",
                    detail=f"Matches {', '.join(matched[:4])}.",
                )
            )
        if resume.role_focus == inferred_role_focus:
            score += 14
            reasons.append(
                ResumeSelectionReason(
                    label="Role focus alignment",
                    detail=f"Resume focus already matches this {inferred_role_focus.casefold()} role family.",
                )
            )
        resume_name_haystack = _normalized_haystack(resume.display_name, resume.original_filename, resume.role_focus)
        if recommended_hint and recommended_hint.casefold() in resume_name_haystack:
            score += 12
            reasons.append(
                ResumeSelectionReason(
                    label="Existing recommendation",
                    detail=f"Current match scoring already points to {job.recommended_resume}.",
                )
            )
        if knowledge_requirement_labels & set(matched):
            score += 6
            reasons.append(
                ResumeSelectionReason(
                    label="Evidence support",
                    detail=f"Approved knowledge already supports {', '.join(sorted(knowledge_requirement_labels & set(matched))[:3])}.",
                )
            )
        ranked.append((min(score, 99), resume, matched, reasons[:3]))

    ranked.sort(
        key=lambda item: (
            item[0],
            len(item[2]),
            item[1].created_at or "",
            item[1].id,
        ),
        reverse=True,
    )
    best_score, best_resume, matched_requirements, reasons = ranked[0]
    status = "selected" if best_score >= 55 else "low_confidence"
    fallback_behavior = ""
    if status == "low_confidence":
        fallback_behavior = "Selection confidence is low, so the newest resume was chosen as the safest starting point."
        if not reasons:
            reasons = [
                ResumeSelectionReason(
                    label="Fallback selection",
                    detail="No resume showed strong overlap with the job, so Resume Intelligence picked the safest available baseline.",
                )
            ]
    return ResumeSelectionResult(
        status=status,
        confidence=best_score,
        resume_id=best_resume.id,
        display_name=best_resume.display_name,
        original_filename=best_resume.original_filename,
        role_focus=best_resume.role_focus,
        matched_requirements=matched_requirements,
        reason_summary=reasons[:3],
        fallback_behavior=fallback_behavior,
    )
