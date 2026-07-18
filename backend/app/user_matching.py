from __future__ import annotations

from dataclasses import replace

from app.config import AppSettings
from app.connectors.base import NormalizedJobRecord
from app.domain import UserAccount
from app.job_filters import filter_reason
from app.job_metadata import normalize_supported_country


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned


def _user_preferences(user: UserAccount) -> dict[str, object]:
    return dict(user.preferences)


def _user_profile(user: UserAccount) -> dict[str, object]:
    return dict(user.profile)


def preferred_companies(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("preferred_companies"))


def preferred_roles(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("preferred_roles"))


def preferred_locations(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("locations"))


def preferred_work_arrangements(user: UserAccount, settings: AppSettings) -> tuple[str, ...]:
    values = _string_list(_user_preferences(user).get("work_arrangements"))
    return tuple(values) or settings.radar.preferred_work_arrangements


def preferred_experience_levels(user: UserAccount, settings: AppSettings) -> tuple[str, ...]:
    values = _string_list(_user_preferences(user).get("experience_levels"))
    return tuple(values) or settings.radar.preferred_experience_levels


def selected_country(user: UserAccount, settings: AppSettings) -> str:
    preferences = _user_preferences(user)
    return normalize_supported_country(str(preferences.get("country", user.country or settings.radar.selected_country)))


def alert_freshness_hours(user: UserAccount, settings: AppSettings) -> int:
    preferences = _user_preferences(user)
    raw_value = preferences.get("freshness_hours", settings.radar.alert_freshness_hours)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return settings.radar.alert_freshness_hours
    return max(1, min(168, value))


def minimum_match_score(user: UserAccount, settings: AppSettings) -> int:
    preferences = _user_preferences(user)
    raw_value = preferences.get("minimum_match_score", settings.radar.minimum_match_score)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return settings.radar.minimum_match_score
    return max(0, min(100, value))


def telegram_connected(user: UserAccount) -> bool:
    return bool(user.telegram_chat_id and user.telegram_chat_id.strip())


def required_preferences_reason(user: UserAccount) -> str | None:
    if not preferred_companies(user):
        return "preferred_companies_missing"
    if not preferred_roles(user):
        return "preferred_roles_missing"
    return None


def company_matches(job: NormalizedJobRecord, user: UserAccount) -> bool:
    companies = preferred_companies(user)
    if not companies:
        return False
    return job.company.casefold() in {company.casefold() for company in companies}


def location_matches(job: NormalizedJobRecord, user: UserAccount) -> bool:
    locations = preferred_locations(user)
    if not locations:
        return True

    haystack = f" {job.location.strip().casefold()} {job.description_text.strip().casefold()} "
    remote_policy = job.remote_policy.strip().casefold()
    for location in locations:
        normalized = location.casefold()
        if normalized in {"remote", "anywhere"} and remote_policy.startswith("remote"):
            return True
        if normalized and normalized in haystack:
            return True
    return False


def build_user_profile_text(user: UserAccount, settings: AppSettings) -> str:
    profile = _user_profile(user)
    preferences = _user_preferences(user)
    years_of_experience = profile.get("years_of_experience")
    work_arrangements = preferred_work_arrangements(user, settings)
    experience_levels = preferred_experience_levels(user, settings)
    companies = preferred_companies(user)
    roles = preferred_roles(user)
    locations = preferred_locations(user)
    skills = _string_list(preferences.get("skills"))
    watchlists = _string_list(preferences.get("watchlists"))

    profile_lines = [
        "Candidate profile for personalized job triage.",
        f"Name: {user.full_name or user.email}.",
        f"Country preference: {selected_country(user, settings)}.",
    ]
    if years_of_experience not in {None, ""}:
        profile_lines.append(f"Years of experience: {years_of_experience}.")
    if roles:
        profile_lines.append(f"Preferred roles: {', '.join(roles)}.")
    if companies:
        profile_lines.append(f"Preferred companies: {', '.join(companies)}.")
    if locations:
        profile_lines.append(f"Preferred locations: {', '.join(locations)}.")
    if work_arrangements:
        profile_lines.append(f"Preferred work arrangements: {', '.join(work_arrangements)}.")
    if experience_levels:
        profile_lines.append(f"Preferred experience levels: {', '.join(experience_levels)}.")
    if skills:
        profile_lines.append(f"Core skills: {', '.join(skills)}.")
    if watchlists:
        profile_lines.append(f"Watchlist themes: {', '.join(watchlists)}.")
    if profile.get("resume_uploaded"):
        profile_lines.append("A resume has been uploaded for this user.")
    if profile.get("linkedin_url"):
        profile_lines.append(f"LinkedIn: {profile['linkedin_url']}.")
    if profile.get("github_url"):
        profile_lines.append(f"GitHub: {profile['github_url']}.")
    if profile.get("portfolio_url"):
        profile_lines.append(f"Portfolio: {profile['portfolio_url']}.")
    return " ".join(profile_lines)


def build_user_matching_settings(settings: AppSettings, user: UserAccount) -> AppSettings:
    return replace(
        settings,
        radar=replace(
            settings.radar,
            minimum_match_score=minimum_match_score(user, settings),
            selected_country=selected_country(user, settings),
            alert_freshness_hours=alert_freshness_hours(user, settings),
            target_roles=tuple(preferred_roles(user)),
            preferred_work_arrangements=preferred_work_arrangements(user, settings),
            preferred_experience_levels=preferred_experience_levels(user, settings),
            profile_text=build_user_profile_text(user, settings),
        ),
    )


def filter_reason_for_user(
    job: NormalizedJobRecord,
    user: UserAccount,
    settings: AppSettings,
    *,
    matching_settings: AppSettings | None = None,
) -> str | None:
    missing_reason = required_preferences_reason(user)
    if missing_reason is not None:
        return missing_reason

    if not company_matches(job, user):
        return "company"

    if not location_matches(job, user):
        return "location"

    return filter_reason(job, matching_settings or build_user_matching_settings(settings, user))
