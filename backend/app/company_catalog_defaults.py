from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.domain import CompanyPreference

ENABLED_COMPANY_NAMES = {
    "Microsoft",
    "OpenAI",
    "Databricks",
    "Anthropic",
    "Stripe",
}


@dataclass(frozen=True)
class CompanyCatalogDefault:
    name: str
    connector: str
    external_identifier: str
    career_url: str
    tier: int
    priority: int
    country: str = "US"
    poll_interval_minutes: int = 5


RECOMMENDED_COMPANY_DEFAULTS: tuple[CompanyCatalogDefault, ...] = (
    CompanyCatalogDefault("Microsoft", "microsoft-careers", "microsoft", "https://jobs.careers.microsoft.com/", 1, 1),
    CompanyCatalogDefault(
        "Google",
        "google-careers",
        "google",
        "https://www.google.com/about/careers/applications/jobs/results/",
        1,
        2,
    ),
    CompanyCatalogDefault("Amazon", "company-api", "amazon", "https://www.amazon.jobs/", 1, 3),
    CompanyCatalogDefault("Meta", "company-api", "meta", "https://www.metacareers.com/jobs/", 1, 4),
    CompanyCatalogDefault("Apple", "company-api", "apple", "https://jobs.apple.com/", 1, 5),
    CompanyCatalogDefault(
        "NVIDIA",
        "company-api",
        "nvidia",
        "https://www.nvidia.com/en-us/about-nvidia/careers/",
        1,
        6,
    ),
    CompanyCatalogDefault("OpenAI", "greenhouse", "openai", "https://job-boards.greenhouse.io/openai", 1, 7),
    CompanyCatalogDefault("Anthropic", "greenhouse", "anthropic", "https://job-boards.greenhouse.io/anthropic", 1, 8),
    CompanyCatalogDefault("Databricks", "greenhouse", "databricks", "https://job-boards.greenhouse.io/databricks", 1, 9),
    CompanyCatalogDefault("Snowflake", "company-api", "snowflake", "https://careers.snowflake.com/us/en", 1, 10),
    CompanyCatalogDefault("Cloudflare", "company-api", "cloudflare", "https://www.cloudflare.com/careers/jobs/", 1, 11),
    CompanyCatalogDefault("Stripe", "greenhouse", "stripe", "https://job-boards.greenhouse.io/stripe", 1, 12),
    CompanyCatalogDefault("Twilio", "company-api", "twilio", "https://www.twilio.com/company/jobs", 1, 13),
    CompanyCatalogDefault("GitHub", "company-api", "github", "https://www.github.careers/careers-home/jobs", 1, 14),
    CompanyCatalogDefault("MongoDB", "company-api", "mongodb", "https://www.mongodb.com/company/careers/teams", 1, 15),
    CompanyCatalogDefault("Confluent", "company-api", "confluent", "https://careers.confluent.io/", 1, 16),
    CompanyCatalogDefault("Perplexity", "company-api", "perplexity", "https://www.perplexity.ai/careers", 1, 17),
    CompanyCatalogDefault("Scale AI", "greenhouse", "scaleai", "https://job-boards.greenhouse.io/scaleai", 1, 18),
    CompanyCatalogDefault("Netflix", "company-api", "netflix", "https://jobs.netflix.com/", 2, 19),
    CompanyCatalogDefault("Airbnb", "company-api", "airbnb", "https://careers.airbnb.com/positions/", 2, 20),
    CompanyCatalogDefault("Uber", "company-api", "uber", "https://www.uber.com/us/en/careers/list/", 2, 21),
    CompanyCatalogDefault("Cursor", "company-api", "cursor", "https://www.cursor.com/careers", 3, 22),
    CompanyCatalogDefault("Linear", "company-api", "linear", "https://linear.app/careers", 3, 23),
    CompanyCatalogDefault("Ramp", "company-api", "ramp", "https://ramp.com/careers", 3, 24),
)


def default_role_families_for_company(company_name: str) -> list[str]:
    normalized = company_name.casefold()
    role_families = {"Core Engineering", "Backend"}
    if normalized in {
        "openai",
        "anthropic",
        "perplexity",
        "scale ai",
        "cursor",
    }:
        role_families.add("AI")
    if normalized in {
        "databricks",
        "snowflake",
        "cloudflare",
        "confluent",
        "mongodb",
        "nvidia",
    }:
        role_families.add("Backend")
    if normalized in {
        "stripe",
        "twilio",
        "github",
    }:
        role_families.add("Customer-Facing Engineering")
    return sorted(role_families)


def build_recommended_company_preferences(
    role_family_resolver: Callable[[str], list[str]] = default_role_families_for_company,
) -> list[CompanyPreference]:
    return [
        CompanyPreference(
            id=spec.name.casefold().replace(" ", "-"),
            company=spec.name,
            enabled=spec.name in ENABLED_COMPANY_NAMES,
            tier=spec.tier,
            priority=spec.priority,
            connector=spec.connector,
            poll_interval_minutes=spec.poll_interval_minutes,
            country=spec.country,
            career_url=spec.career_url,
            external_identifier=spec.external_identifier,
            role_families=sorted(role_family_resolver(spec.name)),
        )
        for spec in RECOMMENDED_COMPANY_DEFAULTS
    ]
