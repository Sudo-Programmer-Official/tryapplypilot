from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.domain import KnowledgeEntity, KnowledgeEntityType, KnowledgeEntityVersion, ResumeAsset, UserAccount

from .linking import resolve_entity_alias
from .merge import classify_merge_change
from .queries import compute_knowledge_completeness, compute_knowledge_completeness_report
from .services import KnowledgePlatformService

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "about"),
    "experience": ("experience", "work experience", "professional experience", "employment", "employment history"),
    "projects": ("projects", "project experience", "selected projects"),
    "education": ("education", "academic background"),
    "skills": ("skills", "technical skills", "core skills", "technologies", "tech stack"),
    "certifications": ("certifications", "licenses", "licenses & certifications"),
    "awards": ("awards", "honors", "recognition"),
}

_COMPANY_SUFFIX_PATTERN = re.compile(r"\b(?:corp(?:oration)?|inc(?:orporated)?|llc|ltd|co|company)\.?$", re.IGNORECASE)
_SECTION_TOKEN_PATTERN = re.compile(r"[\n,|/•]+")
_BULLET_PREFIX_PATTERN = re.compile(r"^(?:[-*•]\s+|\d+\.\s+)")
_LEADERSHIP_PATTERN = re.compile(r"\b(led|managed|mentored|owned|headed|directed|launched)\b", re.IGNORECASE)
_ACHIEVEMENT_PATTERN = re.compile(r"\b(\d[%+,]|million|billion|latency|throughput|scaled|reduced|increased|saved)\b", re.IGNORECASE)
_KNOWN_TEXT_TERMS: tuple[tuple[KnowledgeEntityType, str], ...] = (
    ("technology", "Python"),
    ("technology", "TypeScript"),
    ("technology", "JavaScript"),
    ("technology", "Node.js"),
    ("technology", "React"),
    ("technology", "PostgreSQL"),
    ("technology", "SQL Server"),
    ("technology", "FastAPI"),
    ("technology", "Kubernetes"),
    ("technology", "AWS"),
    ("technology", "Azure"),
    ("technology", "GCP"),
    ("technology", "Docker"),
    ("technology", "gRPC"),
    ("technology", "Go"),
    ("skill", "Backend"),
    ("skill", "Distributed Systems"),
    ("skill", "Platform"),
    ("skill", "Infrastructure"),
    ("skill", "AI"),
    ("skill", "Machine Learning"),
    ("skill", "MLOps"),
    ("leadership", "Leadership"),
    ("leadership", "Mentorship"),
)


@dataclass(frozen=True)
class ResumeSection:
    name: str
    heading: str
    content: str
    lines: list[str]


@dataclass(frozen=True)
class ExtractedKnowledgeItem:
    entity_type: KnowledgeEntityType
    canonical_name: str
    content: dict[str, object]
    evidence_excerpt: str
    evidence_metadata: dict[str, object] = field(default_factory=dict)
    confidence: float = 0.9


@dataclass(frozen=True)
class ResumeIngestionResult:
    parsed_sections: list[ResumeSection]
    approved_entities: list[KnowledgeEntity]
    staged_versions: list[KnowledgeEntityVersion]
    completeness: dict[str, dict[str, object]]
    completeness_report: dict[str, object]
    entity_counts: dict[str, int]
    merge_summary: dict[str, int]


def _normalize_token(value: str) -> str:
    return " ".join(value.replace("\u2013", "-").replace("\u2014", "-").split()).strip()


def _normalize_company_name(value: str) -> str:
    cleaned = _normalize_token(value)
    cleaned = _COMPANY_SUFFIX_PATTERN.sub("", cleaned).strip(" ,.-")
    return cleaned or value.strip()


def _section_name_for_heading(line: str) -> str | None:
    normalized = _normalize_token(line).strip(":").casefold()
    for section_name, aliases in _SECTION_ALIASES.items():
        if normalized in aliases:
            return section_name
    return None


def parse_resume_sections(text: str) -> list[ResumeSection]:
    sections: list[ResumeSection] = []
    current_name = "summary"
    current_heading = "Summary"
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue
        next_section_name = _section_name_for_heading(line)
        if next_section_name is not None:
            content = "\n".join(item for item in current_lines if item is not None).strip()
            if content:
                lines = [entry for entry in current_lines if entry]
                sections.append(ResumeSection(name=current_name, heading=current_heading, content=content, lines=lines))
            current_name = next_section_name
            current_heading = line.strip(":")
            current_lines = []
            continue
        current_lines.append(line)
    content = "\n".join(item for item in current_lines if item is not None).strip()
    if content:
        lines = [entry for entry in current_lines if entry]
        sections.append(ResumeSection(name=current_name, heading=current_heading, content=content, lines=lines))
    return sections


def _split_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _canonicalize_skill_or_technology(token: str) -> tuple[KnowledgeEntityType, str] | None:
    normalized = _normalize_token(token).casefold().strip(".")
    if not normalized:
        return None
    tech = resolve_entity_alias("technology", token)
    if tech.source == "deterministic_alias":
        return ("technology", tech.canonical_name)
    skill = resolve_entity_alias("skill", token)
    if skill.source == "deterministic_alias":
        return ("skill", skill.canonical_name)
    leadership = resolve_entity_alias("leadership", token)
    if leadership.source == "deterministic_alias":
        return ("leadership", leadership.canonical_name)
    return None


def _extract_skill_items(section: ResumeSection, *, source_resume_id: str) -> list[ExtractedKnowledgeItem]:
    seen: set[tuple[KnowledgeEntityType, str]] = set()
    items: list[ExtractedKnowledgeItem] = []
    for token in _SECTION_TOKEN_PATTERN.split(section.content):
        cleaned = _normalize_token(token)
        canonical = _canonicalize_skill_or_technology(cleaned)
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        items.append(
            ExtractedKnowledgeItem(
                entity_type=canonical[0],
                canonical_name=canonical[1],
                content={"label": canonical[1], "section": section.name, "resume_id": source_resume_id},
                evidence_excerpt=cleaned,
                evidence_metadata={"section": section.name, "resume_id": source_resume_id},
                confidence=0.98,
            )
        )
    return items


def _entry_name_from_block(lines: list[str], *, fallback_prefix: str) -> str:
    first_line = _BULLET_PREFIX_PATTERN.sub("", lines[0]).strip()
    if "|" in first_line:
        first_line = first_line.split("|", 1)[0].strip()
    if " at " in first_line.casefold():
        first_line = first_line.split(" at ", 1)[0].strip()
    return _normalize_token(first_line)[:120] or fallback_prefix


def _extract_entry_items(
    section: ResumeSection,
    *,
    entity_type: KnowledgeEntityType,
    source_resume_id: str,
) -> list[ExtractedKnowledgeItem]:
    items: list[ExtractedKnowledgeItem] = []
    for index, block in enumerate(_split_blocks(section.content), start=1):
        canonical_name = _entry_name_from_block(block, fallback_prefix=f"{section.name.title()} {index}")
        content = {
            "section": section.name,
            "lines": block,
            "text": "\n".join(block),
            "resume_id": source_resume_id,
        }
        first_line = block[0]
        if entity_type == "experience" and ("|" in first_line or " at " in first_line.casefold()):
            parts = [part.strip() for part in re.split(r"\s+\|\s+|\sat\s", first_line, maxsplit=1, flags=re.IGNORECASE) if part.strip()]
            if len(parts) >= 2:
                content["role"] = parts[0]
                content["company"] = _normalize_company_name(parts[1])
        items.append(
            ExtractedKnowledgeItem(
                entity_type=entity_type,
                canonical_name=canonical_name,
                content=content,
                evidence_excerpt="\n".join(block[:4])[:500],
                evidence_metadata={"section": section.name, "resume_id": source_resume_id},
                confidence=0.9,
            )
        )
    return items


def _extract_achievement_items(
    section: ResumeSection,
    *,
    source_resume_id: str,
) -> list[ExtractedKnowledgeItem]:
    items: list[ExtractedKnowledgeItem] = []
    for line in section.lines:
        cleaned = _BULLET_PREFIX_PATTERN.sub("", line).strip()
        if not cleaned:
            continue
        if _ACHIEVEMENT_PATTERN.search(cleaned):
            items.append(
                ExtractedKnowledgeItem(
                    entity_type="achievement",
                    canonical_name=cleaned[:120],
                    content={"section": section.name, "text": cleaned, "resume_id": source_resume_id},
                    evidence_excerpt=cleaned,
                    evidence_metadata={"section": section.name, "resume_id": source_resume_id},
                    confidence=0.88,
                )
            )
        if _LEADERSHIP_PATTERN.search(cleaned):
            items.append(
                ExtractedKnowledgeItem(
                    entity_type="leadership",
                    canonical_name=cleaned[:120],
                    content={"section": section.name, "text": cleaned, "resume_id": source_resume_id},
                    evidence_excerpt=cleaned,
                    evidence_metadata={"section": section.name, "resume_id": source_resume_id},
                    confidence=0.86,
                )
            )
    return items


def _extract_known_terms_from_text(text: str, *, source_resume_id: str) -> list[ExtractedKnowledgeItem]:
    haystack = f" {text.casefold()} "
    seen: set[tuple[KnowledgeEntityType, str]] = set()
    items: list[ExtractedKnowledgeItem] = []
    for entity_type, canonical_name in _KNOWN_TEXT_TERMS:
        resolution = resolve_entity_alias(entity_type, canonical_name)
        alias_key = resolution.normalized_alias
        if not alias_key or f" {alias_key} " not in haystack:
            continue
        key = (entity_type, resolution.canonical_name)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            ExtractedKnowledgeItem(
                entity_type=entity_type,
                canonical_name=resolution.canonical_name,
                content={"label": resolution.canonical_name, "resume_id": source_resume_id},
                evidence_excerpt=resolution.canonical_name,
                evidence_metadata={"resume_id": source_resume_id, "source": "full_text"},
                confidence=0.9 if entity_type == "technology" else 0.88,
            )
        )
    return items


def extract_resume_items(
    resume: ResumeAsset,
    *,
    extracted_text: str,
) -> tuple[list[ResumeSection], list[ExtractedKnowledgeItem]]:
    sections = parse_resume_sections(extracted_text)
    items: list[ExtractedKnowledgeItem] = [
        ExtractedKnowledgeItem(
            entity_type="resume",
            canonical_name=resume.display_name,
            content={
                "resume_id": resume.id,
                "display_name": resume.display_name,
                "role_focus": resume.role_focus,
                "skills": resume.extracted_skills,
                "original_filename": resume.original_filename,
                "text_preview": resume.extracted_text_preview,
                "section_names": [section.name for section in sections],
            },
            evidence_excerpt=resume.extracted_text_preview,
            evidence_metadata={"resume_id": resume.id, "entity_type": "resume"},
            confidence=1.0,
        )
    ]
    for section in sections:
        if section.name == "skills":
            items.extend(_extract_skill_items(section, source_resume_id=resume.id))
        elif section.name == "experience":
            items.extend(_extract_entry_items(section, entity_type="experience", source_resume_id=resume.id))
            items.extend(_extract_achievement_items(section, source_resume_id=resume.id))
        elif section.name == "projects":
            items.extend(_extract_entry_items(section, entity_type="project", source_resume_id=resume.id))
            items.extend(_extract_achievement_items(section, source_resume_id=resume.id))
        elif section.name == "education":
            items.extend(_extract_entry_items(section, entity_type="education", source_resume_id=resume.id))
        elif section.name == "certifications":
            items.extend(_extract_entry_items(section, entity_type="certification", source_resume_id=resume.id))
        elif section.name == "awards":
            items.extend(_extract_entry_items(section, entity_type="award", source_resume_id=resume.id))
    items.extend(_extract_known_terms_from_text(extracted_text, source_resume_id=resume.id))
    deduped: dict[tuple[KnowledgeEntityType, str], ExtractedKnowledgeItem] = {}
    for item in items:
        key = (item.entity_type, item.canonical_name.casefold())
        existing = deduped.get(key)
        if existing is None or len(str(item.content)) > len(str(existing.content)):
            deduped[key] = item
    return sections, list(deduped.values())


def _entity_signature(entity: KnowledgeEntity) -> tuple[KnowledgeEntityType, str]:
    return (entity.entity_type, entity.canonical_name.casefold())


async def ingest_resume_into_knowledge_platform(
    *,
    service: KnowledgePlatformService,
    user_id: str,
    resume: ResumeAsset,
    extracted_text: str,
    actor_user_id: str,
) -> ResumeIngestionResult:
    sections, items = extract_resume_items(resume, extracted_text=extracted_text)
    approved_profile = await service.get_user_profile(user_id)
    approved_entities = [entity for entities in approved_profile.values() for entity in entities]
    approved_signatures = {_entity_signature(entity): entity for entity in approved_entities}
    seen_signatures: set[tuple[KnowledgeEntityType, str]] = set()
    approved_results: list[KnowledgeEntity] = []
    staged_results: list[KnowledgeEntityVersion] = []
    merge_summary = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0, "conflict": 0}

    for item in items:
        evidence = await service.add_evidence(
            user_id,
            source_type="resume",
            source_id=resume.id,
            excerpt=item.evidence_excerpt,
            metadata=item.evidence_metadata,
        )
        signature = (item.entity_type, item.canonical_name.casefold())
        seen_signatures.add(signature)
        existing = approved_signatures.get(signature)
        merge_decision = classify_merge_change(
            item.entity_type,
            existing_content=existing.content if existing is not None else None,
            incoming_content=item.content,
        )
        merge_summary[merge_decision.action] = merge_summary.get(merge_decision.action, 0) + 1
        if existing is None:
            entity = await service.upsert_approved_entity(
                user_id,
                entity_type=item.entity_type,
                canonical_name=item.canonical_name,
                new_content=item.content,
                source="resume_upload",
                reason=merge_decision.reason,
                evidence_ids=[evidence.id],
                actor_user_id=actor_user_id,
                confidence=item.confidence,
                agent_name="resume_ingestion",
            )
            approved_results.append(entity)
            approved_signatures[signature] = entity
            continue
        if merge_decision.action == "unchanged":
            updated = await service.add_entity_evidence(existing.id, [evidence.id])
            if updated is not None:
                approved_signatures[signature] = updated
            continue

        version = await service.stage_resume_changes(
            user_id,
            entity_type=item.entity_type,
            canonical_name=item.canonical_name,
            new_content=merge_decision.merged_content,
            source="resume_upload",
            reason=merge_decision.reason,
            evidence_ids=[evidence.id],
            actor_user_id=actor_user_id,
            confidence=item.confidence,
            agent_name="resume_ingestion",
        )
        staged_results.append(version)

    for signature, entity in approved_signatures.items():
        if entity.source != "resume_upload":
            continue
        if signature in seen_signatures:
            continue
        merge_summary["removed"] += 1
        version = await service.stage_resume_changes(
            user_id,
            entity_type=entity.entity_type,
            canonical_name=entity.canonical_name,
            new_content={**entity.content, "resume_presence": "missing_from_latest_upload"},
            source="resume_upload",
            reason="Latest resume upload did not include this previously approved resume-derived entity.",
            evidence_ids=entity.evidence_ids,
            actor_user_id=actor_user_id,
            confidence=entity.confidence,
            agent_name="resume_ingestion",
        )
        staged_results.append(version)

    final_profile = await service.get_user_profile(user_id)
    final_entities = [entity for entities in final_profile.values() for entity in entities]
    completeness = compute_knowledge_completeness(final_entities)
    report = compute_knowledge_completeness_report(final_entities)
    entity_counts = {entity_type: len(entities) for entity_type, entities in final_profile.items()}
    await service._emit_event(
        user_id=user_id,
        event_type="ResumeUploaded",
        title=f"Resume uploaded: {resume.display_name}",
        payload={"resume_id": resume.id, "merge_summary": merge_summary},
    )
    await service._emit_profile_completed_if_needed(user_id)
    return ResumeIngestionResult(
        parsed_sections=sections,
        approved_entities=approved_results,
        staged_versions=staged_results,
        completeness=completeness,
        completeness_report={"overall_score": report.overall_score, "areas": report.areas},
        entity_counts=entity_counts,
        merge_summary=merge_summary,
    )


async def sync_profile_snapshot_to_knowledge_platform(
    *,
    service: KnowledgePlatformService,
    user: UserAccount,
) -> KnowledgeEntity:
    profile = dict(user.profile)
    excerpt_parts = [
        user.full_name.strip(),
        str(profile.get("linkedin_url", "")).strip(),
        str(profile.get("portfolio_url", "")).strip(),
        str(profile.get("github_url", "")).strip(),
        str(profile.get("years_of_experience", "")).strip(),
        str(profile.get("visa_status", "")).strip(),
        str(profile.get("work_authorization", "")).strip(),
    ]
    excerpt = " | ".join(part for part in excerpt_parts if part)
    evidence = await service.add_evidence(
        user.id,
        source_type="profile",
        source_id=user.id,
        excerpt=excerpt or user.email,
        metadata={"source": "profile_snapshot"},
    )
    return await service.upsert_approved_entity(
        user.id,
        entity_type="user",
        canonical_name="Profile",
        new_content={
            "full_name": user.full_name,
            "email": user.email,
            "country": user.country,
            "linkedin_url": str(profile.get("linkedin_url", "")).strip(),
            "portfolio_url": str(profile.get("portfolio_url", "")).strip(),
            "github_url": str(profile.get("github_url", "")).strip(),
            "years_of_experience": profile.get("years_of_experience"),
            "visa_status": str(profile.get("visa_status", "")).strip(),
            "work_authorization": str(profile.get("work_authorization", "")).strip(),
            "resume_uploaded": bool(profile.get("resume_uploaded", False)),
        },
        source="profile_update",
        reason="Canonical profile snapshot updated from user profile.",
        evidence_ids=[evidence.id],
        actor_user_id=user.id,
        confidence=1.0,
        agent_name="profile_sync",
    )
