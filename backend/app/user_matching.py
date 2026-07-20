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

_COMPANY_PRIORITY_LABELS = {
    "dream": "Dream Companies",
    "high": "High Priority",
    "normal": "Normal Priority",
    "hidden": "Hidden",
}

_JOB_TYPE_LABELS = {
    "full_time": "Full-time",
    "part_time": "Part-time",
    "contract": "Contract",
    "contract_to_hire": "Contract-to-Hire",
    "internship": "Internship",
    "temporary": "Temporary",
}

_COMPANY_SIZE_LABELS = {
    "startup": "Startup (1-50)",
    "growth": "Growth (50-500)",
    "mid_market": "Mid Market (500-2000)",
    "enterprise": "Enterprise (2000+)",
}

_INDUSTRY_LABELS = {
    "artificial_intelligence": "Artificial Intelligence",
    "developer_tools": "Developer Tools",
    "cloud_infrastructure": "Cloud Infrastructure",
    "enterprise_software": "Enterprise Software",
    "cybersecurity": "Cybersecurity",
    "data_platform": "Data Platform",
    "fintech": "FinTech",
    "healthcare": "Healthcare",
    "productivity": "Productivity",
    "robotics": "Robotics",
    "networking": "Networking",
    "consumer": "Consumer",
    "gaming": "Gaming",
    "e_commerce": "E-commerce",
    "infrastructure": "Infrastructure",
    "observability": "Observability",
}

_REMOTE_PREFERENCE_LABELS = {
    "remote_only": "Remote Only",
    "mostly_remote": "Mostly Remote",
    "hybrid": "Hybrid",
    "onsite": "Onsite",
    "no_preference": "No Preference",
}

_TRAVEL_PREFERENCE_LABELS = {
    "no_travel": "No Travel",
    "up_to_10": "Up to 10%",
    "up_to_25": "25%",
    "up_to_50": "50%",
    "any": "Any",
}

_NOTIFICATION_RULE_LABELS = {
    "only_95_plus": "Only 95%+",
    "only_new_jobs": "Only New Jobs",
    "only_dream_companies": "Only Dream Companies",
}

_TRAVEL_LIMITS = {
    "no_travel": 0,
    "up_to_10": 10,
    "up_to_25": 25,
    "up_to_50": 50,
}

_REMOTE_WORK_ARRANGEMENTS = {
    "remote_only": ("Remote",),
    "mostly_remote": ("Remote", "Hybrid"),
    "hybrid": ("Hybrid",),
    "onsite": ("Onsite",),
}

_CITIZENSHIP_MARKERS = (
    "must be a us citizen",
    "must be us citizen",
    "u.s. citizen",
    "us citizen",
    "citizenship required",
    "citizen only",
    "federal clearance",
)

_CLEARANCE_MARKERS = (
    "security clearance",
    "secret clearance",
    "top secret",
    "ts/sci",
    "active clearance",
)

_SPONSORSHIP_DISALLOWED_MARKERS = (
    "no sponsorship",
    "will not sponsor",
    "cannot sponsor",
    "unable to sponsor",
    "without sponsorship",
)

_DEFAULT_JOB_TYPES = ["full_time", "contract", "contract_to_hire"]
_DEFAULT_COMPANY_SIZES = ["growth", "enterprise"]
_DEFAULT_INDUSTRIES = [
    "artificial_intelligence",
    "developer_tools",
    "cloud_infrastructure",
    "enterprise_software",
    "data_platform",
]


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


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, item in value.items():
        normalized_key = str(key).strip()
        normalized_value = str(item).strip()
        if normalized_key and normalized_value:
            cleaned[normalized_key] = normalized_value
    return cleaned


def _display_labels(values: list[str], labels: dict[str, str]) -> list[str]:
    return [labels.get(value, value.replace("_", " ").title()) for value in values if value]


def _normalize_company_priority(value: str) -> str:
    normalized = value.strip().casefold().replace(" ", "_")
    if normalized in {"dream", "dream_company", "dream_companies"}:
        return "dream"
    if normalized in {"high", "high_priority"}:
        return "high"
    if normalized in {"normal", "standard"}:
        return "normal"
    if normalized in {"hidden", "off"}:
        return "hidden"
    return "normal"


def _normalize_skill_priorities(value: object) -> list[tuple[str, int]]:
    if not isinstance(value, list):
        return []
    normalized: list[tuple[str, int]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill", "")).strip()
        if not skill or skill.casefold() in seen:
            continue
        seen.add(skill.casefold())
        try:
            weight = int(item.get("weight", 3))
        except (TypeError, ValueError):
            weight = 3
        normalized.append((skill, max(1, min(5, weight))))
    return normalized


def _user_preferences(user: UserAccount) -> dict[str, object]:
    return dict(user.preferences)


def _user_profile(user: UserAccount) -> dict[str, object]:
    return dict(user.profile)


def preferred_companies(user: UserAccount) -> list[str]:
    priorities = company_priorities(user)
    prioritized_companies = [company for company, priority in priorities.items() if priority != "hidden"]
    if prioritized_companies:
        return prioritized_companies
    return _string_list(_user_preferences(user).get("preferred_companies"))


def company_priorities(user: UserAccount) -> dict[str, str]:
    raw_priorities = _string_dict(_user_preferences(user).get("company_priorities"))
    normalized = {company: _normalize_company_priority(priority) for company, priority in raw_priorities.items()}
    if normalized:
        return normalized
    return {
        company: "normal"
        for company in _string_list(_user_preferences(user).get("preferred_companies"))
    }


def company_priority_for(user: UserAccount, company_name: str) -> str:
    return company_priorities(user).get(company_name, "hidden")


def preferred_roles(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("preferred_roles"))


def preferred_skills(user: UserAccount) -> list[str]:
    weighted_skills = [skill for skill, _weight in skill_priorities(user)]
    return _dedupe_strings(weighted_skills + _string_list(_user_preferences(user).get("skills")))


def skill_priorities(user: UserAccount) -> list[tuple[str, int]]:
    weighted_skills = _normalize_skill_priorities(_user_preferences(user).get("skill_priorities"))
    if weighted_skills:
        return weighted_skills
    return [(skill, 3) for skill in _string_list(_user_preferences(user).get("skills"))]


def watchlist_themes(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("watchlists"))


def preferred_locations(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("locations"))


def preferred_job_types(user: UserAccount) -> list[str]:
    values = _string_list(_user_preferences(user).get("job_types"))
    return values or list(_DEFAULT_JOB_TYPES)


def preferred_company_sizes(user: UserAccount) -> list[str]:
    values = _string_list(_user_preferences(user).get("company_sizes"))
    return values or list(_DEFAULT_COMPANY_SIZES)


def preferred_industries(user: UserAccount) -> list[str]:
    values = _string_list(_user_preferences(user).get("industries"))
    return values or list(_DEFAULT_INDUSTRIES)


def excluded_keywords(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("excluded_keywords"))


def notification_rules(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("notification_rules"))


def notification_frequency(user: UserAccount) -> str:
    return str(_user_preferences(user).get("notification_frequency", "instant")).strip() or "instant"


def remote_preference(user: UserAccount) -> str:
    return str(_user_preferences(user).get("remote_preference", "")).strip()


def travel_preference(user: UserAccount) -> str:
    return str(_user_preferences(user).get("travel_preference", "")).strip()


def resume_strategy(user: UserAccount) -> str:
    return str(_user_preferences(user).get("resume_strategy", "auto")).strip() or "auto"


def preferred_resume_variants(user: UserAccount) -> list[str]:
    return _string_list(_user_preferences(user).get("preferred_resume_variants"))


def user_visa_status(user: UserAccount) -> str:
    preferences = _user_preferences(user)
    profile = _user_profile(user)
    return str(preferences.get("visa_status", profile.get("visa_status", ""))).strip()


def years_of_experience(user: UserAccount) -> int | None:
    preferences = _user_preferences(user)
    profile = _user_profile(user)
    raw_value = preferences.get("years_of_experience", profile.get("years_of_experience"))
    try:
        return int(raw_value) if raw_value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


def minimum_salary(user: UserAccount) -> int | None:
    raw_value = _user_preferences(user).get("minimum_salary")
    try:
        return int(raw_value) if raw_value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


def desired_salary(user: UserAccount) -> int | None:
    raw_value = _user_preferences(user).get("desired_salary")
    try:
        return int(raw_value) if raw_value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


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
    remote_value = remote_preference(user)
    if remote_value in _REMOTE_WORK_ARRANGEMENTS:
        return _REMOTE_WORK_ARRANGEMENTS[remote_value]
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


def search_window_hours(user: UserAccount) -> int:
    preferences = _user_preferences(user)
    raw_value = preferences.get("search_window_hours", 24 * 7)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return 24 * 7
    return max(1, min(24 * 30, value))


def minimum_match_score(user: UserAccount, settings: AppSettings) -> int:
    preferences = _user_preferences(user)
    raw_value = preferences.get("minimum_match_score", settings.radar.minimum_match_score)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return settings.radar.minimum_match_score
    if "only_95_plus" in notification_rules(user):
        value = max(value, 95)
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


def _job_haystack(job: NormalizedJobRecord) -> str:
    return f" {job.title.strip()} {job.location.strip()} {job.remote_policy.strip()} {job.description_text.strip()} ".casefold()


def _infer_job_type(job: NormalizedJobRecord) -> str:
    haystack = _job_haystack(job)
    if "contract-to-hire" in haystack or "contract to hire" in haystack:
        return "contract_to_hire"
    if re.search(r"(?<!\w)intern(ship)?(?!\w)", haystack) is not None:
        return "internship"
    if re.search(r"(?<!\w)temporary(?!\w)", haystack) is not None or "temp role" in haystack:
        return "temporary"
    if "part-time" in haystack or "part time" in haystack:
        return "part_time"
    if re.search(r"(?<!\w)contract(?!\w)", haystack) is not None or re.search(r"(?<!\w)consultant(?!\w)", haystack) is not None:
        return "contract"
    return "full_time"


def job_type_matches(job: NormalizedJobRecord, user: UserAccount) -> bool:
    allowed_job_types = set(preferred_job_types(user))
    if not allowed_job_types:
        return True
    return _infer_job_type(job) in allowed_job_types


def visa_matches(job: NormalizedJobRecord, user: UserAccount) -> bool:
    visa_status = user_visa_status(user).casefold()
    if not visa_status:
        return True
    haystack = _job_haystack(job)
    if visa_status in {"opt", "stem_opt", "need_sponsorship"}:
        if any(marker in haystack for marker in _CITIZENSHIP_MARKERS):
            return False
        if any(marker in haystack for marker in _CLEARANCE_MARKERS):
            return False
        if any(marker in haystack for marker in _SPONSORSHIP_DISALLOWED_MARKERS):
            return False
    if visa_status in {"us_citizen", "green_card"} and any(marker in haystack for marker in _CLEARANCE_MARKERS):
        return True
    return True


def _job_travel_requirement(job: NormalizedJobRecord) -> int | None:
    haystack = _job_haystack(job)
    if "no travel" in haystack or "travel not required" in haystack:
        return 0
    for pattern in (
        r"up to\s*(\d{1,2})\s*%",
        r"(\d{1,2})\s*%\s*travel",
        r"travel.*?(\d{1,2})\s*%",
    ):
        match = re.search(pattern, haystack)
        if match is not None:
            try:
                return int(match.group(1))
            except (TypeError, ValueError):
                return None
    if "travel required" in haystack:
        return 25
    return None


def travel_matches(job: NormalizedJobRecord, user: UserAccount) -> bool:
    preference = travel_preference(user)
    if preference == "any":
        return True
    limit = _TRAVEL_LIMITS.get(preference)
    if limit is None:
        return True
    required = _job_travel_requirement(job)
    if required is None:
        return True
    return required <= limit


def alert_rule_allows_job(job: NormalizedJobRecord, user: UserAccount) -> bool:
    rules = set(notification_rules(user))
    if "only_dream_companies" in rules and company_priority_for(user, job.company) != "dream":
        return False
    return True


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
    experience_years = years_of_experience(user)
    work_arrangements = preferred_work_arrangements(user, settings)
    experience_levels = preferred_experience_levels(user, settings)
    companies = preferred_companies(user)
    roles = preferred_roles(user)
    locations = preferred_locations(user)
    skills = preferred_skills(user)
    weighted_skills = skill_priorities(user)
    watchlists = watchlist_themes(user)
    resume_skills = resume_skill_keywords(user)
    resume_focuses = resume_role_focuses(user)
    company_priority_map = company_priorities(user)
    job_types = _display_labels(preferred_job_types(user), _JOB_TYPE_LABELS)
    company_sizes = _display_labels(preferred_company_sizes(user), _COMPANY_SIZE_LABELS)
    industries = _display_labels(preferred_industries(user), _INDUSTRY_LABELS)
    remote_value = remote_preference(user)
    travel_value = travel_preference(user)
    alert_rules = _display_labels(notification_rules(user), _NOTIFICATION_RULE_LABELS)
    minimum_salary_value = minimum_salary(user)
    desired_salary_value = desired_salary(user)
    visa_status = user_visa_status(user)
    manual_resume_variants = preferred_resume_variants(user)

    profile_lines = [
        "Candidate profile for personalized job triage.",
        f"Name: {user.full_name or user.email}.",
        f"Country preference: {selected_country(user, settings)}.",
    ]
    if experience_years is not None:
        profile_lines.append(f"Years of experience: {experience_years}.")
    if roles:
        profile_lines.append(f"Preferred roles: {', '.join(roles)}.")
    if companies:
        profile_lines.append(f"Preferred companies: {', '.join(companies)}.")
    if company_priority_map:
        dream_companies = [company for company, priority in company_priority_map.items() if priority == "dream"]
        high_priority_companies = [company for company, priority in company_priority_map.items() if priority == "high"]
        hidden_companies = [company for company, priority in company_priority_map.items() if priority == "hidden"]
        if dream_companies:
            profile_lines.append(f"{_COMPANY_PRIORITY_LABELS['dream']}: {', '.join(dream_companies)}.")
        if high_priority_companies:
            profile_lines.append(f"{_COMPANY_PRIORITY_LABELS['high']}: {', '.join(high_priority_companies)}.")
        if hidden_companies:
            profile_lines.append(f"{_COMPANY_PRIORITY_LABELS['hidden']}: {', '.join(hidden_companies)}.")
    if locations:
        profile_lines.append(f"Preferred locations: {', '.join(locations)}.")
    if work_arrangements:
        profile_lines.append(f"Preferred work arrangements: {', '.join(work_arrangements)}.")
    if remote_value:
        profile_lines.append(f"Remote preference: {_REMOTE_PREFERENCE_LABELS.get(remote_value, remote_value)}.")
    if experience_levels:
        profile_lines.append(f"Preferred experience levels: {', '.join(experience_levels)}.")
    if job_types:
        profile_lines.append(f"Preferred job types: {', '.join(job_types)}.")
    if company_sizes:
        profile_lines.append(f"Preferred company sizes: {', '.join(company_sizes)}.")
    if industries:
        profile_lines.append(f"Preferred industries: {', '.join(industries)}.")
    if skills:
        profile_lines.append(f"Core skills: {', '.join(skills)}.")
    if weighted_skills:
        profile_lines.append(
            "Skill priorities: "
            + ", ".join(f"{skill} ({weight}/5)" for skill, weight in weighted_skills)
            + "."
        )
    if watchlists:
        profile_lines.append(f"Watchlist themes: {', '.join(watchlists)}.")
    if resume_skills:
        profile_lines.append(f"Resume skill signals: {', '.join(resume_skills)}.")
    if resume_focuses:
        profile_lines.append(f"Resume role focus: {', '.join(resume_focuses)}.")
    if minimum_salary_value is not None or desired_salary_value is not None:
        salary_parts = []
        if minimum_salary_value is not None:
            salary_parts.append(f"minimum ${minimum_salary_value:,}")
        if desired_salary_value is not None:
            salary_parts.append(f"desired ${desired_salary_value:,}")
        profile_lines.append(f"Salary expectations: {', '.join(salary_parts)}.")
    if visa_status:
        profile_lines.append(f"Visa status: {visa_status}.")
    if travel_value:
        profile_lines.append(f"Travel preference: {_TRAVEL_PREFERENCE_LABELS.get(travel_value, travel_value)}.")
    if alert_rules:
        profile_lines.append(f"Notification rules: {', '.join(alert_rules)}.")
    if excluded_keywords(user):
        profile_lines.append(f"Excluded keywords: {', '.join(excluded_keywords(user))}.")
    if resume_strategy(user) == "selected_only" and manual_resume_variants:
        profile_lines.append(f"Resume strategy: use only {', '.join(manual_resume_variants)}.")
    else:
        profile_lines.append("Resume strategy: auto-select the best resume.")
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
    user_excluded_keywords = tuple(_dedupe_strings([*settings.radar.excluded_keywords, *excluded_keywords(user)]))
    manual_resume_variants = tuple(preferred_resume_variants(user))
    effective_resume_variants = settings.radar.resume_variants
    if resume_strategy(user) == "selected_only" and manual_resume_variants:
        effective_resume_variants = manual_resume_variants
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
            excluded_keywords=user_excluded_keywords,
            resume_variants=effective_resume_variants,
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

    if not job_type_matches(job, user):
        return "job_type"

    resolved_matching_settings = matching_settings or build_user_matching_settings(settings, user)
    generic_filter_reason = filter_reason(job, resolved_matching_settings)
    if generic_filter_reason is not None:
        return generic_filter_reason

    if not visa_matches(job, user):
        return "visa"

    if not travel_matches(job, user):
        return "travel"

    if not domain_interest_matches(job, user):
        return "domain_interest"

    return None
