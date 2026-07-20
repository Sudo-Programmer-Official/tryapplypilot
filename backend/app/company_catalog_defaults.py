from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable

from app.domain import CompanyPreference

# Keep defaults aligned with live ATS connectors so database reconciliation can
# expand coverage without requiring more environment changes.
ENABLED_COMPANY_NAMES: set[str] = set()


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
    _company("OpenAI", "company-api", "openai", "https://openai.com/careers/search/", 1, 1),
    _company("Anthropic", "greenhouse", "anthropic", "https://job-boards.greenhouse.io/anthropic", 1, 2),
    _company("Databricks", "greenhouse", "databricks", "https://job-boards.greenhouse.io/databricks", 1, 3),
    _company("Microsoft", "microsoft-careers", "microsoft.com", "https://jobs.careers.microsoft.com/", 1, 4),
    _company("IBM", "ibm-careers", "ibm.com", "https://www.ibm.com/careers/search", 1, 5),
    _company("Stripe", "greenhouse", "stripe", "https://job-boards.greenhouse.io/stripe", 1, 5),
    _company("Cloudflare", "greenhouse", "cloudflare", "https://job-boards.greenhouse.io/cloudflare", 1, 6),
    _company("Snowflake", "company-api", "snowflake", "https://careers.snowflake.com/", 1, 7),
    _company("Confluent", "company-api", "confluent", "https://careers.confluent.io/", 1, 8),
    _company("MongoDB", "greenhouse", "mongodb", "https://job-boards.greenhouse.io/mongodb", 1, 9),
    _company("GitHub", "company-api", "github", "https://www.github.careers/careers-home", 1, 10),
    _company("Ramp", "ashby", "ramp", "https://jobs.ashbyhq.com/ramp", 1, 11),
    _company("Perplexity", "company-api", "perplexity", "https://www.perplexity.ai/careers", 1, 12),
    _company("Scale AI", "greenhouse", "scaleai", "https://job-boards.greenhouse.io/scaleai", 1, 13),
    _company("Cursor", "company-api", "cursor", "https://www.cursor.com/careers", 1, 14),
    _company("Linear", "ashby", "linear", "https://jobs.ashbyhq.com/linear", 1, 15),
    _company(
        "Google",
        "google-careers",
        "google",
        "https://www.google.com/about/careers/applications/jobs/results/",
        2,
        16,
    ),
    _company(
        "Amazon",
        "amazon-jobs",
        "amazon",
        "https://www.amazon.jobs/en/search?base_query=software+development+engineer&country=USA&sort=recent",
        2,
        17,
    ),
    _company("Meta", "company-api", "meta", "https://www.metacareers.com/jobs/", 2, 18),
    _company("Apple", "company-api", "apple", "https://jobs.apple.com/", 2, 19),
    _company(
        "NVIDIA",
        "workday",
        "nvidia/NVIDIAExternalCareerSite",
        "https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite",
        2,
        20,
    ),
    _company("Netflix", "company-api", "netflix", "https://jobs.netflix.com/", 2, 21),
    _company("Airbnb", "company-api", "airbnb", "https://careers.airbnb.com/", 2, 22),
    _company("Uber", "company-api", "uber", "https://www.uber.com/global/en/careers/list/", 2, 23),
    _company("Twilio", "company-api", "twilio", "https://www.twilio.com/company/jobs", 2, 24),
    _company("Salesforce", "company-api", "salesforce", "https://careers.salesforce.com/en/jobs/", 2, 25),
    _company(
        "Oracle",
        "oracle-recruiting-cloud",
        "CX_45001",
        "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/jobs",
        2,
        26,
    ),
    _company("ServiceNow", "smartrecruiters", "ServiceNow", "https://careers.smartrecruiters.com/ServiceNow", 2, 27),
    _company("HashiCorp", "company-api", "hashicorp", "https://www.hashicorp.com/careers", 2, 28),
    _company("Elastic", "greenhouse", "elastic", "https://job-boards.greenhouse.io/elastic", 2, 29),
    _company("Grafana Labs", "greenhouse", "grafanalabs", "https://job-boards.greenhouse.io/grafanalabs", 2, 30),
    _company("DigitalOcean", "company-api", "digitalocean", "https://www.digitalocean.com/careers", 2, 31),
    _company("Supabase", "company-api", "supabase", "https://supabase.com/careers", 2, 32),
    _company("Vercel", "greenhouse", "vercel", "https://job-boards.greenhouse.io/vercel", 2, 33),
    _company("GitLab", "greenhouse", "gitlab", "https://job-boards.greenhouse.io/gitlab", 2, 34),
    _company("Mercury", "greenhouse", "mercury", "https://job-boards.greenhouse.io/mercury", 2, 35),
    _company("Flex", "greenhouse", "flex", "https://job-boards.greenhouse.io/flex", 3, 36),
    _company("Brex", "greenhouse", "brex", "https://job-boards.greenhouse.io/brex", 3, 37),
    _company("Plaid", "company-api", "plaid", "https://plaid.com/careers", 3, 38),
    _company("Robinhood", "greenhouse", "robinhood", "https://job-boards.greenhouse.io/robinhood", 3, 39),
    _company("Figma", "greenhouse", "figma", "https://job-boards.greenhouse.io/figma", 3, 40),
    _company("Notion", "ashby", "notion", "https://jobs.ashbyhq.com/notion", 3, 41),
    _company("Airtable", "greenhouse", "airtable", "https://job-boards.greenhouse.io/airtable", 3, 42),
    _company("Canva", "company-api", "canva", "https://www.canva.com/careers/", 3, 43),
    _company("Discord", "greenhouse", "discord", "https://job-boards.greenhouse.io/discord", 3, 44),
    _company("Roblox", "company-api", "roblox", "https://careers.roblox.com/", 3, 45),
    _company("Rippling", "company-api", "rippling", "https://www.rippling.com/careers", 3, 46),
    _company("Retool", "company-api", "retool", "https://retool.com/careers", 3, 47),
    _company("Replit", "company-api", "replit", "https://replit.com/careers", 3, 48),
    _company("Render", "company-api", "render", "https://render.com/careers", 3, 49),
    _company("Netlify", "greenhouse", "netlify", "https://job-boards.greenhouse.io/netlify", 3, 50),
    _company("PlanetScale", "greenhouse", "planetscale", "https://job-boards.greenhouse.io/planetscale", 3, 51),
    _company("Neon", "lever", "neon", "https://jobs.lever.co/neon", 3, 52),
    _company("ElevenLabs", "company-api", "elevenlabs", "https://elevenlabs.io/careers", 3, 53),
    _company("Cohere", "company-api", "cohere", "https://cohere.com/careers", 3, 54),
    _company("Mistral AI", "company-api", "mistralai", "https://mistral.ai/careers", 3, 55),
    _company("Sierra", "company-api", "sierra", "https://sierra.ai/careers", 3, 56),
    _company("Glean", "company-api", "glean", "https://www.glean.com/careers", 3, 57),
    _company("Harvey", "company-api", "harvey", "https://www.harvey.ai/careers", 3, 58),
    _company("Windsurf", "company-api", "windsurf", "https://windsurf.com/careers", 3, 59),
    _company("Together AI", "greenhouse", "togetherai", "https://job-boards.greenhouse.io/togetherai", 3, 60),
    _company("Runway", "company-api", "runway", "https://runwayml.com/careers/", 3, 61),
    _company("Hugging Face", "company-api", "huggingface", "https://huggingface.co/jobs", 3, 62),
    _company("Weights and Biases", "company-api", "wandb", "https://wandb.ai/site/careers", 3, 63),
    _company("Adobe", "company-api", "adobe", "https://careers.adobe.com/", 3, 64),
    _company("Cisco", "company-api", "cisco", "https://jobs.cisco.com/", 3, 65),
    _company("Intel", "company-api", "intel", "https://jobs.intel.com/", 3, 66),
    _company("Qualcomm", "company-api", "qualcomm", "https://careers.qualcomm.com/", 3, 67),
    _company("Coinbase", "greenhouse", "coinbase", "https://job-boards.greenhouse.io/coinbase", 3, 68),
    _company("Reddit", "greenhouse", "reddit", "https://job-boards.greenhouse.io/reddit", 3, 69),
    _company("Pinterest", "greenhouse", "pinterest", "https://job-boards.greenhouse.io/pinterest", 3, 70),
    _company("Dropbox", "greenhouse", "dropbox", "https://job-boards.greenhouse.io/dropbox", 3, 71),
    _company("Slack", "company-api", "slack", "https://slack.com/careers", 3, 72),
    _company("DoorDash", "company-api", "doordash", "https://careersatdoordash.com/", 3, 73),
    _company("Palantir", "lever", "palantir", "https://jobs.lever.co/palantir", 3, 74),
    _company("PostHog", "company-api", "posthog", "https://posthog.com/careers", 3, 75),
    _company("Snyk", "company-api", "snyk", "https://snyk.io/careers/", 3, 76),
    _company("Cockroach Labs", "greenhouse", "cockroachlabs", "https://job-boards.greenhouse.io/cockroachlabs", 2, 77),
    _company("Sourcegraph", "greenhouse", "sourcegraph91", "https://job-boards.greenhouse.io/sourcegraph91", 2, 78),
    _company("ClickHouse", "greenhouse", "clickhouse", "https://job-boards.greenhouse.io/clickhouse", 2, 79),
    _company("AssemblyAI", "greenhouse", "assemblyai", "https://job-boards.greenhouse.io/assemblyai", 2, 80),
    _company(
        "Anduril",
        "greenhouse",
        "andurilindustries",
        "https://job-boards.greenhouse.io/andurilindustries",
        2,
        81,
    ),
    _company("iCIMS", "icims", "careers.icims.com", "https://careers.icims.com/careers-home", 3, 82),
    _company("Progress", "jobvite", "progress", "https://jobs.jobvite.com/careers/progress/jobs", 3, 83),
    _company("SAP", "successfactors", "sap", "https://jobs.sap.com/search/?sortColumn=referencedate&sortDirection=desc", 2, 84),
)

ENABLED_COMPANY_NAMES = {
    spec.name
    for spec in RECOMMENDED_COMPANY_DEFAULTS
    if spec.connector in {
        "greenhouse",
        "lever",
        "ashby",
        "microsoft-careers",
        "workday",
        "smartrecruiters",
        "icims",
        "jobvite",
        "comeet",
        "oracle-recruiting-cloud",
        "successfactors",
        "google-careers",
        "amazon-jobs",
    }
}

AI_PLATFORM_COMPANIES = {
    "openai",
    "anthropic",
    "perplexity",
    "scale ai",
    "assemblyai",
    "anduril",
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
    "cockroach labs",
    "clickhouse",
    "elastic",
    "supabase",
    "planetscale",
    "neon",
}

DISTRIBUTED_SYSTEMS_COMPANIES = {
    "databricks",
    "stripe",
    "cloudflare",
    "cockroach labs",
    "clickhouse",
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
    "cockroach labs",
    "clickhouse",
    "github",
    "microsoft",
    "google",
    "amazon",
    "oracle",
    "sap",
    "nvidia",
    "progress",
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
    "oracle",
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
    "sourcegraph",
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
    "icims",
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
    "sourcegraph",
    "elastic",
}

STORAGE_COMPANIES = {
    "snowflake",
    "mongodb",
    "cockroach labs",
    "clickhouse",
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
    "cockroach labs",
    "clickhouse",
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

AI_COMPANY_COLLECTIONS: dict[str, frozenset[str]] = {
    "Foundation Models": frozenset(
        {
            "openai",
            "anthropic",
            "cohere",
            "mistral ai",
            "together ai",
            "hugging face",
        }
    ),
    "AI Infrastructure": frozenset(
        {
            "databricks",
            "scale ai",
            "snowflake",
            "confluent",
            "mongodb",
            "weights and biases",
        }
    ),
    "AI Agents": frozenset(
        {
            "openai",
            "anthropic",
            "perplexity",
            "cursor",
            "glean",
            "harvey",
            "sierra",
            "windsurf",
            "runway",
        }
    ),
    "Developer Tools": frozenset(
        {
            "cursor",
            "linear",
            "github",
            "gitlab",
            "sourcegraph",
            "vercel",
            "netlify",
            "render",
            "replit",
        }
    ),
    "Robotics": frozenset(
        {
            "anduril",
            "nvidia",
        }
    ),
    "FinTech AI": frozenset(
        {
            "stripe",
            "ramp",
            "mercury",
            "brex",
            "plaid",
            "robinhood",
            "coinbase",
        }
    ),
    "Security AI": frozenset(
        {
            "cloudflare",
            "snyk",
            "palantir",
        }
    ),
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


def ai_company_collections_for_company(company_name: str) -> list[str]:
    normalized = company_name.casefold()
    return sorted(
        collection_name
        for collection_name, company_names in AI_COMPANY_COLLECTIONS.items()
        if normalized in company_names
    )


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


def recommended_company_catalog_fingerprint(
    role_family_resolver: Callable[[str], list[str]] = default_role_families_for_company,
) -> str:
    payload = [
        {
            "name": spec.name,
            "connector": spec.connector,
            "external_identifier": spec.external_identifier,
            "career_url": spec.career_url,
            "tier": spec.tier,
            "priority": spec.priority,
            "country": spec.country,
            "poll_interval_minutes": spec.poll_interval_minutes,
            "enabled": spec.name in ENABLED_COMPANY_NAMES,
            "role_families": sorted(role_family_resolver(spec.name)),
        }
        for spec in RECOMMENDED_COMPANY_DEFAULTS
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
