from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.domain import CompanyPreference

# V1 keeps default enablement limited to connectors the runtime can actually poll today.
ENABLED_COMPANY_NAMES = {
    "OpenAI",
    "Anthropic",
    "Databricks",
    "Stripe",
    "Scale AI",
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


def _tier_poll_interval_minutes(tier: int) -> int:
    if tier == 1:
        return 5
    if tier == 2:
        return 10
    return 15


def _company(
    name: str,
    connector: str,
    external_identifier: str,
    career_url: str,
    tier: int,
    priority: int,
    *,
    country: str = "US",
    poll_interval_minutes: int | None = None,
) -> CompanyCatalogDefault:
    return CompanyCatalogDefault(
        name=name,
        connector=connector,
        external_identifier=external_identifier,
        career_url=career_url,
        tier=tier,
        priority=priority,
        country=country,
        poll_interval_minutes=poll_interval_minutes or _tier_poll_interval_minutes(tier),
    )


RECOMMENDED_COMPANY_DEFAULTS: tuple[CompanyCatalogDefault, ...] = (
    _company("OpenAI", "greenhouse", "openai", "https://job-boards.greenhouse.io/openai", 1, 1),
    _company("Anthropic", "greenhouse", "anthropic", "https://job-boards.greenhouse.io/anthropic", 1, 2),
    _company("Databricks", "greenhouse", "databricks", "https://job-boards.greenhouse.io/databricks", 1, 3),
    _company("Microsoft", "microsoft-careers", "microsoft", "https://jobs.careers.microsoft.com/", 1, 4),
    _company("Stripe", "greenhouse", "stripe", "https://job-boards.greenhouse.io/stripe", 1, 5),
    _company("Cloudflare", "company-api", "cloudflare", "https://www.cloudflare.com/careers/jobs/", 1, 6),
    _company("Snowflake", "company-api", "snowflake", "https://careers.snowflake.com/", 1, 7),
    _company("Confluent", "company-api", "confluent", "https://careers.confluent.io/", 1, 8),
    _company("MongoDB", "company-api", "mongodb", "https://www.mongodb.com/company/careers", 1, 9),
    _company("GitHub", "company-api", "github", "https://www.github.careers/careers-home", 1, 10),
    _company("Ramp", "company-api", "ramp", "https://ramp.com/careers", 1, 11),
    _company("Perplexity", "company-api", "perplexity", "https://www.perplexity.ai/careers", 1, 12),
    _company("Scale AI", "greenhouse", "scaleai", "https://job-boards.greenhouse.io/scaleai", 1, 13),
    _company("Cursor", "company-api", "cursor", "https://www.cursor.com/careers", 1, 14),
    _company("Linear", "company-api", "linear", "https://linear.app/careers", 1, 15),
    _company(
        "Google",
        "google-careers",
        "google",
        "https://www.google.com/about/careers/applications/jobs/results/",
        2,
        16,
    ),
    _company("Amazon", "company-api", "amazon", "https://www.amazon.jobs/", 2, 17),
    _company("Meta", "company-api", "meta", "https://www.metacareers.com/jobs/", 2, 18),
    _company("Apple", "company-api", "apple", "https://jobs.apple.com/", 2, 19),
    _company("NVIDIA", "company-api", "nvidia", "https://www.nvidia.com/en-us/about-nvidia/careers/", 2, 20),
    _company("Netflix", "company-api", "netflix", "https://jobs.netflix.com/", 2, 21),
    _company("Airbnb", "company-api", "airbnb", "https://careers.airbnb.com/", 2, 22),
    _company("Uber", "company-api", "uber", "https://www.uber.com/global/en/careers/list/", 2, 23),
    _company("Twilio", "company-api", "twilio", "https://www.twilio.com/company/jobs", 2, 24),
    _company("Salesforce", "company-api", "salesforce", "https://careers.salesforce.com/en/jobs/", 2, 25),
    _company("Oracle", "company-api", "oracle", "https://careers.oracle.com/", 2, 26),
    _company("ServiceNow", "company-api", "servicenow", "https://careers.servicenow.com/", 2, 27),
    _company("HashiCorp", "company-api", "hashicorp", "https://www.hashicorp.com/careers", 2, 28),
    _company("Elastic", "company-api", "elastic", "https://www.elastic.co/careers", 2, 29),
    _company("Grafana Labs", "company-api", "grafanalabs", "https://grafana.com/about/careers/", 2, 30),
    _company("DigitalOcean", "company-api", "digitalocean", "https://www.digitalocean.com/careers", 2, 31),
    _company("Supabase", "company-api", "supabase", "https://supabase.com/careers", 2, 32),
    _company("Vercel", "company-api", "vercel", "https://vercel.com/careers", 2, 33),
    _company("GitLab", "company-api", "gitlab", "https://about.gitlab.com/jobs/", 2, 34),
    _company("Mercury", "company-api", "mercury", "https://mercury.com/careers", 2, 35),
    _company("Brex", "company-api", "brex", "https://www.brex.com/careers", 3, 36),
    _company("Plaid", "company-api", "plaid", "https://plaid.com/careers", 3, 37),
    _company("Robinhood", "company-api", "robinhood", "https://careers.robinhood.com/", 3, 38),
    _company("Figma", "company-api", "figma", "https://www.figma.com/careers/", 3, 39),
    _company("Notion", "company-api", "notion", "https://www.notion.so/careers", 3, 40),
    _company("Airtable", "company-api", "airtable", "https://airtable.com/careers", 3, 41),
    _company("Canva", "company-api", "canva", "https://www.canva.com/careers/", 3, 42),
    _company("Discord", "company-api", "discord", "https://discord.com/jobs", 3, 43),
    _company("Roblox", "company-api", "roblox", "https://careers.roblox.com/", 3, 44),
    _company("Rippling", "company-api", "rippling", "https://www.rippling.com/careers", 3, 45),
    _company("Retool", "company-api", "retool", "https://retool.com/careers", 3, 46),
    _company("Replit", "company-api", "replit", "https://replit.com/careers", 3, 47),
    _company("Render", "company-api", "render", "https://render.com/careers", 3, 48),
    _company("Netlify", "company-api", "netlify", "https://www.netlify.com/careers/", 3, 49),
    _company("PlanetScale", "company-api", "planetscale", "https://planetscale.com/careers", 3, 50),
    _company("Neon", "company-api", "neon", "https://neon.tech/careers", 3, 51),
    _company("ElevenLabs", "company-api", "elevenlabs", "https://elevenlabs.io/careers", 3, 52),
    _company("Cohere", "company-api", "cohere", "https://cohere.com/careers", 3, 53),
    _company("Mistral AI", "company-api", "mistralai", "https://mistral.ai/careers", 3, 54),
    _company("Sierra", "company-api", "sierra", "https://sierra.ai/careers", 3, 55),
    _company("Glean", "company-api", "glean", "https://www.glean.com/careers", 3, 56),
    _company("Harvey", "company-api", "harvey", "https://www.harvey.ai/careers", 3, 57),
    _company("Windsurf", "company-api", "windsurf", "https://windsurf.com/careers", 3, 58),
    _company("Together AI", "company-api", "togetherai", "https://www.together.ai/careers", 3, 59),
    _company("Runway", "company-api", "runway", "https://runwayml.com/careers/", 3, 60),
    _company("Hugging Face", "company-api", "huggingface", "https://huggingface.co/jobs", 3, 61),
    _company("Weights and Biases", "company-api", "wandb", "https://wandb.ai/site/careers", 3, 62),
    _company("Adobe", "company-api", "adobe", "https://careers.adobe.com/", 3, 63),
    _company("Cisco", "company-api", "cisco", "https://jobs.cisco.com/", 3, 64),
    _company("Intel", "company-api", "intel", "https://jobs.intel.com/", 3, 65),
    _company("Qualcomm", "company-api", "qualcomm", "https://careers.qualcomm.com/", 3, 66),
    _company("Coinbase", "company-api", "coinbase", "https://www.coinbase.com/careers", 3, 67),
    _company("Reddit", "company-api", "reddit", "https://www.redditinc.com/careers", 3, 68),
    _company("Pinterest", "company-api", "pinterest", "https://www.pinterestcareers.com/", 3, 69),
    _company("Dropbox", "company-api", "dropbox", "https://jobs.dropbox.com/", 3, 70),
    _company("Slack", "company-api", "slack", "https://slack.com/careers", 3, 71),
    _company("DoorDash", "company-api", "doordash", "https://careersatdoordash.com/", 3, 72),
    _company("Palantir", "company-api", "palantir", "https://www.palantir.com/careers/", 3, 73),
    _company("PostHog", "company-api", "posthog", "https://posthog.com/careers", 3, 74),
    _company("Snyk", "company-api", "snyk", "https://snyk.io/careers/", 3, 75),
)

AI_PLATFORM_COMPANIES = {
    "openai",
    "anthropic",
    "perplexity",
    "scale ai",
    "cursor",
    "elevenlabs",
    "cohere",
    "mistral ai",
    "sierra",
    "glean",
    "harvey",
    "windsurf",
    "together ai",
    "runway",
    "hugging face",
    "weights and biases",
    "replit",
    "palantir",
}

DATA_PLATFORM_COMPANIES = {
    "databricks",
    "snowflake",
    "confluent",
    "mongodb",
    "elastic",
    "supabase",
    "planetscale",
    "neon",
}

DISTRIBUTED_SYSTEMS_COMPANIES = {
    "databricks",
    "stripe",
    "cloudflare",
    "snowflake",
    "confluent",
    "mongodb",
    "ramp",
    "amazon",
    "google",
    "microsoft",
    "meta",
    "netflix",
    "uber",
    "twilio",
    "elastic",
    "digitalocean",
    "coinbase",
}

PLATFORM_ENGINEERING_COMPANIES = {
    "databricks",
    "cloudflare",
    "snowflake",
    "confluent",
    "mongodb",
    "github",
    "microsoft",
    "google",
    "amazon",
    "nvidia",
    "hashicorp",
    "digitalocean",
    "supabase",
    "vercel",
    "gitlab",
    "render",
    "netlify",
    "planetscale",
    "neon",
}

CLOUD_INFRASTRUCTURE_COMPANIES = {
    "microsoft",
    "google",
    "amazon",
    "cloudflare",
    "hashicorp",
    "digitalocean",
    "render",
    "netlify",
    "vercel",
    "supabase",
    "nvidia",
}

DEVELOPER_EXPERIENCE_COMPANIES = {
    "github",
    "gitlab",
    "cursor",
    "linear",
    "replit",
    "render",
    "netlify",
    "vercel",
    "supabase",
    "planetscale",
    "retool",
    "posthog",
    "snyk",
}

PRODUCT_ENGINEERING_COMPANIES = {
    "figma",
    "notion",
    "airtable",
    "canva",
    "discord",
    "roblox",
    "reddit",
    "pinterest",
    "dropbox",
    "slack",
    "doordash",
    "airbnb",
    "uber",
    "twilio",
    "salesforce",
    "servicenow",
    "adobe",
    "mercury",
    "brex",
    "plaid",
    "robinhood",
    "rippling",
}

FULL_STACK_COMPANIES = {
    "figma",
    "notion",
    "airtable",
    "canva",
    "discord",
    "roblox",
    "retool",
    "replit",
    "reddit",
    "pinterest",
    "slack",
}

SEARCH_COMPANIES = {
    "perplexity",
    "glean",
    "elastic",
}

STORAGE_COMPANIES = {
    "snowflake",
    "mongodb",
    "planetscale",
    "neon",
}

NETWORKING_COMPANIES = {
    "cloudflare",
    "cisco",
}

RELIABILITY_COMPANIES = {
    "cloudflare",
    "databricks",
    "confluent",
    "mongodb",
    "grafana labs",
    "digitalocean",
    "stripe",
    "servicenow",
}

OBSERVABILITY_COMPANIES = {
    "grafana labs",
    "posthog",
}

FORWARD_DEPLOYED_COMPANIES = {
    "palantir",
    "harvey",
}


def default_role_families_for_company(company_name: str) -> list[str]:
    normalized = company_name.casefold()
    role_families = {"Backend Engineering"}
    if normalized in PLATFORM_ENGINEERING_COMPANIES:
        role_families.add("Platform Engineering")
    if normalized in DISTRIBUTED_SYSTEMS_COMPANIES:
        role_families.add("Distributed Systems")
    if normalized in AI_PLATFORM_COMPANIES:
        role_families.update({"AI Platform", "AI Infrastructure", "Machine Learning Platform"})
    if normalized in DATA_PLATFORM_COMPANIES:
        role_families.add("Data Platform")
    if normalized in CLOUD_INFRASTRUCTURE_COMPANIES:
        role_families.update({"Cloud Infrastructure", "Infrastructure"})
    if normalized in DEVELOPER_EXPERIENCE_COMPANIES:
        role_families.update({"Developer Experience", "Internal Tools"})
    if normalized in PRODUCT_ENGINEERING_COMPANIES:
        role_families.add("Product Engineering")
    if normalized in FULL_STACK_COMPANIES:
        role_families.add("Full Stack")
    if normalized in SEARCH_COMPANIES:
        role_families.add("Search")
    if normalized in STORAGE_COMPANIES:
        role_families.add("Storage")
    if normalized in NETWORKING_COMPANIES:
        role_families.add("Networking")
    if normalized in RELIABILITY_COMPANIES:
        role_families.add("Reliability")
    if normalized in OBSERVABILITY_COMPANIES:
        role_families.add("Observability")
    if normalized in FORWARD_DEPLOYED_COMPANIES:
        role_families.add("Forward Deployed Engineering")
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
