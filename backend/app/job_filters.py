from __future__ import annotations

from app.config import AppSettings
from app.connectors.base import NormalizedJobRecord

JUNIOR_LEVEL_MARKERS = (
    "intern",
    "internship",
    "new grad",
    "graduate",
    "junior",
    "entry level",
    "apprentice",
)

STAFF_LEVEL_MARKERS = (
    "staff",
    "principal",
)

SENIOR_LEVEL_MARKERS = (
    "senior",
    " sr ",
    "sr.",
    "lead",
)


def _normalize_experience_level(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized in {"mid", "mid-level", "mid level", "software engineer ii", "engineer ii"}:
        return "mid-level"
    if normalized in {"senior", "sr", "lead"}:
        return "senior"
    if normalized in {"staff", "principal"}:
        return "staff"
    return normalized


def _normalize_work_arrangement(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized.startswith("remote"):
        return "remote"
    if normalized.startswith("hybrid"):
        return "hybrid"
    if normalized.startswith("onsite") or normalized.startswith("on-site") or normalized.startswith("on site"):
        return "onsite"
    return normalized


def _infer_experience_level(title: str) -> str | None:
    normalized_title = f" {title.strip().casefold()} "
    if any(marker in normalized_title for marker in JUNIOR_LEVEL_MARKERS):
        return "junior"
    if any(marker in normalized_title for marker in STAFF_LEVEL_MARKERS):
        return "staff"
    if any(marker in normalized_title for marker in SENIOR_LEVEL_MARKERS):
        return "senior"
    if "engineer" in normalized_title or "architect" in normalized_title:
        return "mid-level"
    return None


def filter_reason(job: NormalizedJobRecord, settings: AppSettings) -> str | None:
    title_haystack = f" {job.title.strip().casefold()} "

    if settings.radar.target_roles and not any(role.casefold() in title_haystack for role in settings.radar.target_roles):
        return "title_mismatch"

    if settings.radar.excluded_keywords and any(keyword.casefold() in title_haystack for keyword in settings.radar.excluded_keywords):
        return "excluded_keyword"

    allowed_work_arrangements = {
        _normalize_work_arrangement(value)
        for value in settings.radar.preferred_work_arrangements
        if value.strip()
    }
    job_work_arrangement = _normalize_work_arrangement(job.remote_policy)
    if allowed_work_arrangements and job_work_arrangement and job_work_arrangement not in allowed_work_arrangements:
        return "work_arrangement"

    allowed_experience_levels = {
        _normalize_experience_level(value)
        for value in settings.radar.preferred_experience_levels
        if value.strip()
    }
    inferred_experience_level = _infer_experience_level(job.title)
    if (
        inferred_experience_level is not None
        and inferred_experience_level != "junior"
        and allowed_experience_levels
        and inferred_experience_level not in allowed_experience_levels
    ):
        return "experience_level"
    if inferred_experience_level == "junior" and "junior" not in allowed_experience_levels:
        return "experience_level"

    return None
