from __future__ import annotations

from app.config import AppSettings
from app.domain import CompanyPreference, NotificationChannel, RolePreference, ScoutSettings
from app.job_metadata import country_display


def build_profile_text(settings: AppSettings) -> str:
    if settings.radar.profile_text:
        return settings.radar.profile_text

    enabled_companies = [company.name for company in settings.radar.target_companies if company.enabled]
    company_summary = ", ".join(enabled_companies[:10])
    if len(enabled_companies) > 10:
        company_summary = f"{company_summary}, and {len(enabled_companies) - 10} more"
    if not company_summary:
        company_summary = "high-quality engineering organizations"

    role_family_summary = ", ".join(settings.radar.role_families)
    role_summary = ", ".join(settings.radar.target_roles)
    work_arrangement_summary = ", ".join(settings.radar.preferred_work_arrangements)
    experience_summary = ", ".join(settings.radar.preferred_experience_levels)
    exclusion_summary = ", ".join(settings.radar.excluded_keywords[:6])
    return (
        "Candidate focus: senior backend, platform, infrastructure, and AI-adjacent software engineering roles. "
        f"Target companies: {company_summary}. "
        f"Preferred job families: {role_family_summary}. "
        f"Role and skill preferences: {role_summary}. "
        f"Work arrangements: {work_arrangement_summary}. "
        f"Experience levels: {experience_summary}. "
        f"Exclude non-target roles like: {exclusion_summary}. "
        f"Country preference: {country_display(settings.radar.selected_country)}."
    )


def build_scout_settings(settings: AppSettings) -> ScoutSettings:
    companies = sorted(
        [
            CompanyPreference(
                company=company.name,
                enabled=company.enabled,
                tier=company.tier,
                priority=company.priority,
                connector=company.connector,
                poll_interval_minutes=company.poll_interval_minutes,
            )
            for company in settings.radar.target_companies
        ],
        key=lambda company: (company.tier, company.priority, company.company.casefold()),
    )

    notifications = [
        NotificationChannel(
            channel="telegram",
            enabled=settings.telegram.delivery_configured,
            destination=(
                f"@{settings.telegram.bot_username}"
                if settings.telegram.bot_username
                else settings.telegram.chat_id or "Telegram bot not configured"
            ),
        ),
        NotificationChannel(channel="email", enabled=False, destination="Primary inbox"),
        NotificationChannel(channel="slack", enabled=False, destination="#job-radar"),
        NotificationChannel(channel="desktop", enabled=False, destination="Local desktop notifications"),
    ]

    return ScoutSettings(
        primary_connector=settings.radar.primary_connector,
        apply_now_threshold_score=settings.radar.apply_now_threshold_score,
        review_threshold_score=settings.radar.review_threshold_score,
        polling_interval_minutes=settings.radar.polling_interval_minutes,
        companies=companies,
        roles=[RolePreference(label=role, enabled=True) for role in settings.radar.target_roles],
        notifications=notifications,
        role_families=[RolePreference(label=family, enabled=True) for family in settings.radar.role_families],
        work_arrangements=[RolePreference(label=value, enabled=True) for value in settings.radar.preferred_work_arrangements],
        experience_levels=[RolePreference(label=value, enabled=True) for value in settings.radar.preferred_experience_levels],
        excluded_keywords=list(settings.radar.excluded_keywords),
        minimum_match_score=settings.radar.minimum_match_score,
        selected_country=settings.radar.selected_country,
        alert_freshness_hours=settings.radar.alert_freshness_hours,
        dashboard_freshness_hours=settings.radar.dashboard_freshness_hours,
    )
