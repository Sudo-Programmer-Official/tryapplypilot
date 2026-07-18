from __future__ import annotations

from dataclasses import replace
import re

from app.config import AppSettings
from app.connectors.base import NormalizedJobRecord
from app.domain import UserAccount
from app.job_filters import filter_reason
from app.job_metadata import infer_country_code, matches_country_preference, normalize_supported_country

_SIGNAL_STOP_WORDS = frozenset(
    {
        "engineer",
        "engineering",
        "software",
        "senior",
        "staff",
        "principal",
        "lead",
        "applied",
        "developer",
        "developers",
        "architect",
        "solution",
        "solutions",
        "level",
        "ii",
        "iii",
        "iv",
    }
)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def _user_preferences(user: UserAccount) -> dict[str, object]:
    return dict(user.preferences)


def _user_profile(user: UserAccount) -> dict[str, object]:
    return dict(user.profile)


def preferred_companies(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("preferred_companies"))


def preferred_roles(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("preferred_roles"))


def preferred_skills(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("skills"))


def watchlist_themes(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("watchlists"))


def preferred_locations(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("locations"))


def resume_skill_keywords(user: UserAccount) -> list[str]:
    return _string_list(_user_profile(user).get("resume_skill_keywords"))


def resume_role_focuses(user: UserAccount) -> list[str]:
    profile = _user_profile(user)
    resume_library = profile.get("resume_library")
    if not isinstance(resume_library, list):
        return []
    role_focuses = [
        str(entry.get("role_focus", "")).strip()
        for entry in resume_library
        if isinstance(entry, dict) and str(entry.get("role_focus", "")).strip()
    ]
    return _dedupe_strings(role_focuses)


def domain_interest_signals(user: UserAccount) -> list[str]:
    return _dedupe_strings(
        preferred_roles(user)
        + preferred_skills(user)
        + watchlist_themes(user)
        + resume_skill_keywords(user)
        + resume_role_focuses(user)
    )


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
    if not domain_interest_signals(user):
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


def country_matches(job: NormalizedJobRecord, user: UserAccount, settings: AppSettings) -> bool:
    country_code = infer_country_code(job.location, job.description_text)
    return matches_country_preference(country_code, selected_country(user, settings))


def _contains_word(haystack: str, value: str) -> bool:
    if not value:
        return False
    return re.search(rf"(?<!\w){re.escape(value)}(?!\w)", haystack) is not None


def _signal_tokens(signal: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9]+", signal.casefold())
        if token and token not in _SIGNAL_STOP_WORDS
    ]


def _signal_matches(haystack: str, signal: str) -> bool:
    normalized = signal.strip().casefold()
    if not normalized:
        return False
    if normalized in haystack:
        return True
    tokens = _signal_tokens(normalized)
    if not tokens:
        return False
    return all(_contains_word(haystack, token) for token in tokens)


def domain_interest_matches(job: NormalizedJobRecord, user: UserAccount) -> bool:
    signals = domain_interest_signals(user)
    if not signals:
        return True
    haystack = f" {job.title.strip()} {job.description_text.strip()} {job.company.strip()} ".casefold()
    return any(_signal_matches(haystack, signal) for signal in signals)


def build_user_profile_text(user: UserAccount, settings: AppSettings) -> str:
    profile = _user_profile(user)
    preferences = _user_preferences(user)
    years_of_experience = profile.get("years_of_experience")
    work_arrangements = preferred_work_arrangements(user, settings)
    experience_levels = preferred_experience_levels(user, settings)
    companies = preferred_companies(user)
    roles = preferred_roles(user)
    locations = preferred_locations(user)
    skills = preferred_skills(user)
    watchlists = watchlist_themes(user)
    resume_skills = resume_skill_keywords(user)
    resume_focuses = resume_role_focuses(user)

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
    if resume_skills:
        profile_lines.append(f"Resume skill signals: {', '.join(resume_skills)}.")
    if resume_focuses:
        profile_lines.append(f"Resume role focus: {', '.join(resume_focuses)}.")
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
    merged_target_roles = tuple(_dedupe_strings([*settings.radar.target_roles, *preferred_roles(user)]))
    return replace(
        settings,
        radar=replace(
            settings.radar,
            minimum_match_score=minimum_match_score(user, settings),
            selected_country=selected_country(user, settings),
            alert_freshness_hours=alert_freshness_hours(user, settings),
            target_roles=merged_target_roles,
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

    if not country_matches(job, user, settings):
        return "country"

    if not location_matches(job, user):
        return "location"

    resolved_matching_settings = matching_settings or build_user_matching_settings(settings, user)
    generic_filter_reason = filter_reason(job, resolved_matching_settings)
    if generic_filter_reason is not None:
        return generic_filter_reason

    if not domain_interest_matches(job, user):
        return "domain_interest"

    return None
