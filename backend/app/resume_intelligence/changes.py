from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from app.knowledge_platform import parse_resume_sections
from app.resume_library import ResumeDocument

from .models import EvidenceRetrievalResult, JobRequirement, ResumeChange, ResumeChangeSet, RetrievedRequirementEvidence


@dataclass(frozen=True)
class ResumeEntry:
    section: str
    entry_id: str
    text: str


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split()).strip()


def _split_entries(section_name: str, content: str) -> list[ResumeEntry]:
    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    return [
        ResumeEntry(
            section=section_name,
            entry_id=f"{section_name}_{index}",
            text=block,
        )
        for index, block in enumerate(blocks, start=1)
    ]


def _resume_entries(resume: ResumeDocument) -> list[ResumeEntry]:
    sections = parse_resume_sections(resume.extracted_text)
    entries: list[ResumeEntry] = []
    for section in sections:
        entries.extend(_split_entries(section.name, section.content))
    if entries:
        return entries
    return [ResumeEntry(section="summary", entry_id="summary_1", text=_normalize_whitespace(resume.extracted_text))]


def _best_entry_for_requirement(
    requirement: JobRequirement,
    evidence_item: RetrievedRequirementEvidence,
    entries: list[ResumeEntry],
) -> ResumeEntry | None:
    scored: list[tuple[int, ResumeEntry]] = []
    evidence_terms = [snippet.excerpt for snippet in evidence_item.evidence]
    entity_terms = list(evidence_item.entity_names)
    for entry in entries:
        haystack = f" {entry.section} {entry.text} ".casefold()
        score = 0
        if requirement.label.casefold() in haystack:
            score += 5
        if any(keyword.casefold() in haystack for keyword in requirement.keywords):
            score += 4
        if any(term.casefold() in haystack for term in entity_terms):
            score += 3
        if entry.section in {"experience", "projects"}:
            score += 2
        if any(_normalize_whitespace(term).casefold() in haystack for term in evidence_terms):
            score += 2
        scored.append((score, entry))
    scored.sort(key=lambda item: (item[0], item[1].entry_id), reverse=True)
    best_score, best_entry = scored[0] if scored else (0, None)
    if best_entry is None:
        return None
    if best_score <= 0:
        return next((entry for entry in entries if entry.section in {"experience", "projects"}), best_entry)
    return best_entry


def _suggestion_line(requirement: JobRequirement, evidence_item: RetrievedRequirementEvidence) -> str:
    if evidence_item.evidence:
        excerpt = _normalize_whitespace(evidence_item.evidence[0].excerpt).rstrip(".")
        return f"Relevant to {requirement.label}: {excerpt}."
    joined_entities = ", ".join(evidence_item.entity_names[:3])
    return f"Relevant to {requirement.label}: verified experience exists in {joined_entities}."


def generate_change_set(
    *,
    job_id: str,
    selected_resume: ResumeDocument | None,
    requirements: list[JobRequirement],
    evidence_retrieval: EvidenceRetrievalResult,
) -> ResumeChangeSet:
    if selected_resume is None:
        blocked = list(evidence_retrieval.missing_proof_flags)
        return ResumeChangeSet(
            status="blocked",
            source_resume_id=None,
            source_resume_name="",
            changes=[],
            blocked_requirements=blocked,
            summary="Resume Intelligence cannot generate changes until at least one resume exists.",
        )

    entries = _resume_entries(selected_resume)
    requirement_index = {requirement.label: requirement for requirement in requirements}
    changes: list[ResumeChange] = []
    blocked_requirements = list(evidence_retrieval.missing_proof_flags)

    for evidence_item in evidence_retrieval.items:
        if evidence_item.support_level != "supported" or not evidence_item.evidence:
            continue
        requirement = requirement_index.get(evidence_item.requirement_label)
        if requirement is None:
            continue
        target_entry = _best_entry_for_requirement(requirement, evidence_item, entries)
        if target_entry is None:
            continue
        suggestion_line = _suggestion_line(requirement, evidence_item)
        normalized_original = _normalize_whitespace(target_entry.text).casefold()
        if _normalize_whitespace(suggestion_line).casefold() in normalized_original:
            continue
        suggested_text = f"{target_entry.text.rstrip()}\n- {suggestion_line}"
        change_id = str(uuid5(NAMESPACE_URL, f"{job_id}:{selected_resume.id}:{target_entry.entry_id}:{requirement.label}"))
        changes.append(
            ResumeChange(
                change_id=change_id,
                section=target_entry.section,
                entry_id=target_entry.entry_id,
                operation="modify",
                original_text=target_entry.text,
                suggested_text=suggested_text,
                rationale=f"Expose verified {requirement.label} evidence that already exists in the knowledge platform.",
                job_requirements=[requirement.label],
                evidence=evidence_item.evidence[:3],
                confidence=84,
                risk_level="low",
                status="pending",
            )
        )

    if not changes:
        summary = "The selected resume is already the strongest available version for this job."
        if blocked_requirements:
            summary = (
                "No safe rewrite was generated because unsupported requirements remain blocked: "
                + ", ".join(blocked_requirements[:5])
            )
        return ResumeChangeSet(
            status="no_changes_recommended",
            source_resume_id=selected_resume.id,
            source_resume_name=selected_resume.display_name,
            changes=[],
            blocked_requirements=blocked_requirements,
            summary=summary,
        )

    return ResumeChangeSet(
        status="ready_for_review",
        source_resume_id=selected_resume.id,
        source_resume_name=selected_resume.display_name,
        changes=changes,
        blocked_requirements=blocked_requirements,
        summary=f"Generated {len(changes)} evidence-backed resume change(s) for review.",
    )
