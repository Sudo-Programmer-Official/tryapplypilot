from __future__ import annotations

import re

from app.resume_library import ResumeDocument

from .changes import ResumeEntry, _resume_entries
from .models import CritiqueDimensionScore, JobRequirement, ResumeChange, ResumeChangeSet, ResumeCritiqueResult
from .selection import requirement_matches_text

_ACTION_VERB_PATTERN = re.compile(
    r"\b(designed|built|delivered|implemented|led|scaled|improved|launched|owned|optimized|developed|architected)\b",
    re.IGNORECASE,
)
_METRIC_PATTERN = re.compile(r"\b\d[\d,]*(?:\+|%|x)?\b")


def _apply_change_set(resume: ResumeDocument | None, change_set: ResumeChangeSet) -> str:
    if resume is None:
        return ""
    entry_map = {entry.entry_id: entry for entry in _resume_entries(resume)}
    updated_entries: list[ResumeEntry] = []
    for entry in entry_map.values():
        replacement = next((change for change in change_set.changes if change.entry_id == entry.entry_id), None)
        if replacement is None:
            updated_entries.append(entry)
            continue
        if replacement.operation == "remove":
            continue
        updated_entries.append(ResumeEntry(section=entry.section, entry_id=entry.entry_id, text=replacement.suggested_text))
    for change in change_set.changes:
        if change.operation == "add":
            updated_entries.append(ResumeEntry(section=change.section, entry_id=change.entry_id, text=change.suggested_text))
    return "\n\n".join(entry.text.strip() for entry in updated_entries if entry.text.strip())


def _requirement_coverage_score(text: str, requirements: list[JobRequirement]) -> int:
    if not requirements:
        return 100
    covered = len([requirement for requirement in requirements if requirement_matches_text(requirement, text)])
    return int(round((covered / len(requirements)) * 100))


def _readability_score(text: str) -> int:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 40
    average_length = sum(len(line.split()) for line in lines) / len(lines)
    action_lines = len([line for line in lines if _ACTION_VERB_PATTERN.search(line)])
    action_ratio = action_lines / len(lines)
    score = 78
    if average_length > 32:
        score -= 12
    elif average_length > 24:
        score -= 6
    if action_ratio < 0.35:
        score -= 10
    elif action_ratio > 0.55:
        score += 4
    return max(35, min(96, int(round(score))))


def _evidence_strength_score(text: str, change_set: ResumeChangeSet) -> int:
    if not text.strip():
        return 35
    evidence_backed_changes = len([change for change in change_set.changes if change.evidence])
    metric_mentions = len(_METRIC_PATTERN.findall(text))
    base = 72 + min(evidence_backed_changes * 6, 18) + min(metric_mentions * 2, 8)
    if change_set.blocked_requirements:
        base -= min(len(change_set.blocked_requirements) * 8, 24)
    return max(30, min(98, base))


def _keyword_quality_score(text: str, requirements: list[JobRequirement]) -> int:
    coverage = _requirement_coverage_score(text, requirements)
    metric_bonus = 5 if _METRIC_PATTERN.search(text) else 0
    action_bonus = 4 if _ACTION_VERB_PATTERN.search(text) else 0
    return max(30, min(98, coverage + metric_bonus + action_bonus))


def critique_resume_analysis(
    *,
    selected_resume: ResumeDocument | None,
    requirements: list[JobRequirement],
    change_set: ResumeChangeSet,
) -> ResumeCritiqueResult:
    original_text = selected_resume.extracted_text if selected_resume is not None else ""
    revised_text = _apply_change_set(selected_resume, change_set) if selected_resume is not None else ""
    after_text = revised_text or original_text

    keyword_before = _keyword_quality_score(original_text, requirements)
    keyword_after = _keyword_quality_score(after_text, requirements)
    readability_before = _readability_score(original_text)
    readability_after = _readability_score(after_text)
    evidence_before = _evidence_strength_score(original_text, ResumeChangeSet(status="baseline"))
    evidence_after = _evidence_strength_score(after_text, change_set)
    ats_before = int(round((keyword_before + readability_before + evidence_before) / 3))
    ats_after = int(round((keyword_after + readability_after + evidence_after) / 3))

    dimensions = [
        CritiqueDimensionScore(
            label="ATS compatibility",
            before=ats_before,
            after=ats_after,
            rationale="Combines keyword coverage, readability, and evidence density into a recruiter-facing baseline.",
        ),
        CritiqueDimensionScore(
            label="Keyword coverage",
            before=keyword_before,
            after=keyword_after,
            rationale="Measures how clearly the resume reflects the target job requirements.",
        ),
        CritiqueDimensionScore(
            label="Readability",
            before=readability_before,
            after=readability_after,
            rationale="Rewards concise lines, action verbs, and scannable wording.",
        ),
        CritiqueDimensionScore(
            label="Evidence strength",
            before=evidence_before,
            after=evidence_after,
            rationale="Rewards quantified, provenance-backed claims and penalizes unsupported requirements.",
        ),
    ]
    overall_before = int(round(sum(item.before for item in dimensions) / len(dimensions)))
    overall_after = int(round(sum(item.after for item in dimensions) / len(dimensions)))

    issues: list[str] = []
    strengths: list[str] = []
    if change_set.blocked_requirements:
        issues.append(
            "Unsupported requirements remain blocked: " + ", ".join(change_set.blocked_requirements[:5]) + "."
        )
    if keyword_after < 75:
        issues.append("Keyword coverage is still below the ideal review threshold for this job.")
    if readability_after < 70:
        issues.append("Several resume lines remain dense enough that recruiter scanning could slow down.")
    if change_set.status == "no_changes_recommended":
        strengths.append("The current resume already covers the strongest available requirements cleanly.")
    if overall_after > overall_before:
        strengths.append(f"The proposed draft improves the overall resume score from {overall_before}% to {overall_after}%.")
    if evidence_after >= 85:
        strengths.append("Most proposed claims are backed by strong approved evidence.")

    verdict = "ready_for_review"
    if change_set.status == "blocked":
        verdict = "blocked"
    elif change_set.status == "no_changes_recommended":
        verdict = "strong_current_resume"
    elif change_set.blocked_requirements:
        verdict = "review_with_risks"

    summary = (
        "The selected resume can move forward to change-level review."
        if verdict == "ready_for_review"
        else "Resume review is partially blocked by unsupported requirements."
        if verdict == "review_with_risks"
        else "Resume Intelligence is blocked until a baseline resume exists."
        if verdict == "blocked"
        else "The current resume is already the strongest available version for this job."
    )

    return ResumeCritiqueResult(
        verdict=verdict,
        overall_before=overall_before,
        overall_after=overall_after,
        dimensions=dimensions,
        issues=issues,
        strengths=strengths,
        summary=summary,
    )
