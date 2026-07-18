from __future__ import annotations

from dataclasses import replace
import json
from uuid import NAMESPACE_URL, uuid5

from app.config import AppSettings, GreenhouseBoard, TargetCompany, get_settings
from app.db.client import connection
from app.domain import CompanyPreference, NotificationChannel, RolePreference, ScoutSettings, Watchlist, WatchlistTerm
from app.job_metadata import normalize_supported_country

DEFAULT_WATCHLISTS: tuple[dict[str, object], ...] = (
    {
        "name": "Priority Teams",
        "terms": (
            {"term": "Azure AI", "company": "Microsoft"},
            {"term": "Copilot", "company": "Microsoft"},
            {"term": "Databricks AI", "company": "Databricks"},
            {"term": "OpenAI Platform", "company": "OpenAI"},
            {"term": "Anthropic Infrastructure", "company": "Anthropic"},
        ),
    },
)

PREFERENCE_DEFAULTS = (
    "primary_connector",
    "apply_now_threshold_score",
    "review_threshold_score",
    "polling_interval_minutes",
    "minimum_match_score",
    "selected_country",
    "alert_freshness_hours",
    "dashboard_freshness_hours",
    "roles",
    "role_families",
    "work_arrangements",
    "experience_levels",
    "excluded_keywords",
)


def _company_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"company:{name.casefold()}"))


def _role_family_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"role-family:{name.casefold()}"))


def _watchlist_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"watchlist:{name.casefold()}"))


def _watchlist_term_id(watchlist_id: str, term: str, company: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"watchlist-term:{watchlist_id}:{company.casefold()}:{term.casefold()}"))


def _company_career_url(*, connector: str, external_identifier: str, existing_url: str) -> str:
    if existing_url.strip():
        return existing_url.strip()
    if connector == "greenhouse" and external_identifier.strip():
        return f"https://boards.greenhouse.io/{external_identifier.strip()}"
    return ""


def _default_role_families(company_name: str) -> list[str]:
    normalized = company_name.casefold()
    role_families = {"Core Engineering", "Backend"}
    if normalized in {
        "openai",
        "anthropic",
        "perplexity",
        "scale ai",
        "mistral ai",
        "cohere",
        "cursor",
        "elevenlabs",
        "together ai",
        "hugging face",
        "weights & biases",
    }:
        role_families.add("AI")
    if normalized in {
        "databricks",
        "snowflake",
        "cloudflare",
        "confluent",
        "mongodb",
        "nvidia",
        "hashicorp",
    }:
        role_families.add("Backend")
    if normalized in {
        "stripe",
        "twilio",
        "github",
        "figma",
        "vercel",
    }:
        role_families.add("Customer-Facing Engineering")
    return sorted(role_families)


def _notifications(settings: AppSettings) -> list[NotificationChannel]:
    return [
        NotificationChannel(
            channel="telegram",
            enabled=settings.telegram.delivery_configured,
            destination=settings.telegram.chat_id or "Telegram not configured",
        ),
        NotificationChannel(channel="email", enabled=False, destination="Primary inbox"),
        NotificationChannel(channel="slack", enabled=False, destination="#job-radar"),
        NotificationChannel(channel="desktop", enabled=False, destination="Local desktop notifications"),
    ]


def _json_value(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _read_list(value: object, default: tuple[str, ...]) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return list(default)


async def ensure_catalog_seeded(settings: AppSettings | None = None) -> None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return

    board_map = {
        board.company.casefold(): board.token
        for board in resolved_settings.radar.greenhouse_boards
    }

    async with connection() as conn:
        async with conn.transaction():
            for family in resolved_settings.radar.role_families:
                await conn.execute(
                    """
                    INSERT INTO role_families (role_family_id, name)
                    VALUES ($1, $2)
                    ON CONFLICT (role_family_id) DO NOTHING
                    """,
                    _role_family_id(family),
                    family,
                )

            company_count = int(await conn.fetchval("SELECT COUNT(*) FROM companies") or 0)
            if company_count == 0:
                for company in resolved_settings.radar.target_companies:
                    external_identifier = board_map.get(company.name.casefold(), "")
                    career_url = _company_career_url(
                        connector=company.connector,
                        external_identifier=external_identifier,
                        existing_url="",
                    )
                    company_id = _company_id(company.name)
                    await conn.execute(
                        """
                        INSERT INTO companies (
                            company_id,
                            name,
                            connector,
                            external_identifier,
                            priority,
                            tier,
                            enabled,
                            poll_interval_minutes,
                            country,
                            career_url
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (company_id) DO NOTHING
                        """,
                        company_id,
                        company.name,
                        company.connector,
                        external_identifier,
                        company.priority,
                        company.tier,
                        company.enabled,
                        company.poll_interval_minutes,
                        resolved_settings.radar.selected_country,
                        career_url,
                    )
                    for family in _default_role_families(company.name):
                        await conn.execute(
                            """
                            INSERT INTO company_role_families (company_id, role_family_id)
                            VALUES ($1, $2)
                            ON CONFLICT (company_id, role_family_id) DO NOTHING
                            """,
                            company_id,
                            _role_family_id(family),
                        )

            preference_count = int(await conn.fetchval("SELECT COUNT(*) FROM user_preferences") or 0)
            if preference_count == 0:
                defaults: dict[str, object] = {
                    "primary_connector": resolved_settings.radar.primary_connector,
                    "apply_now_threshold_score": resolved_settings.radar.apply_now_threshold_score,
                    "review_threshold_score": resolved_settings.radar.review_threshold_score,
                    "polling_interval_minutes": resolved_settings.radar.polling_interval_minutes,
                    "minimum_match_score": resolved_settings.radar.minimum_match_score,
                    "selected_country": resolved_settings.radar.selected_country,
                    "alert_freshness_hours": resolved_settings.radar.alert_freshness_hours,
                    "dashboard_freshness_hours": resolved_settings.radar.dashboard_freshness_hours,
                    "roles": list(resolved_settings.radar.target_roles),
                    "role_families": list(resolved_settings.radar.role_families),
                    "work_arrangements": list(resolved_settings.radar.preferred_work_arrangements),
                    "experience_levels": list(resolved_settings.radar.preferred_experience_levels),
                    "excluded_keywords": list(resolved_settings.radar.excluded_keywords),
                }
                for key in PREFERENCE_DEFAULTS:
                    await conn.execute(
                        """
                        INSERT INTO user_preferences (preference_key, preference_value)
                        VALUES ($1, $2::jsonb)
                        ON CONFLICT (preference_key) DO NOTHING
                        """,
                        key,
                        json.dumps(defaults[key]),
                    )

            watchlist_count = int(await conn.fetchval("SELECT COUNT(*) FROM watchlists") or 0)
            if watchlist_count == 0:
                for watchlist in DEFAULT_WATCHLISTS:
                    watchlist_name = str(watchlist["name"])
                    watchlist_id = _watchlist_id(watchlist_name)
                    await conn.execute(
                        """
                        INSERT INTO watchlists (watchlist_id, name, enabled)
                        VALUES ($1, $2, TRUE)
                        ON CONFLICT (watchlist_id) DO NOTHING
                        """,
                        watchlist_id,
                        watchlist_name,
                    )
                    for raw_term in watchlist["terms"]:
                        term = str(raw_term["term"])
                        company = str(raw_term.get("company", ""))
                        await conn.execute(
                            """
                            INSERT INTO watchlist_terms (
                                watchlist_term_id,
                                watchlist_id,
                                term,
                                company_name,
                                enabled
                            )
                            VALUES ($1, $2, $3, $4, TRUE)
                            ON CONFLICT (watchlist_term_id) DO NOTHING
                            """,
                            _watchlist_term_id(watchlist_id, term, company),
                            watchlist_id,
                            term,
                            company,
                        )


async def list_companies(settings: AppSettings | None = None) -> list[CompanyPreference]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        from app.data.seed import COMPANIES

        return list(COMPANIES)

    await ensure_catalog_seeded(resolved_settings)
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.company_id,
                c.name,
                c.connector,
                c.external_identifier,
                c.priority,
                c.tier,
                c.enabled,
                c.poll_interval_minutes,
                c.country,
                c.career_url,
                COALESCE(array_agg(rf.name ORDER BY rf.name) FILTER (WHERE rf.name IS NOT NULL), ARRAY[]::text[]) AS role_families
            FROM companies c
            LEFT JOIN company_role_families crf ON crf.company_id = c.company_id
            LEFT JOIN role_families rf ON rf.role_family_id = crf.role_family_id
            GROUP BY
                c.company_id,
                c.name,
                c.connector,
                c.external_identifier,
                c.priority,
                c.tier,
                c.enabled,
                c.poll_interval_minutes,
                c.country,
                c.career_url
            ORDER BY c.tier ASC, c.priority ASC, c.name ASC
            """
        )
    return [
        CompanyPreference(
            id=str(row["company_id"]),
            company=str(row["name"]),
            enabled=bool(row["enabled"]),
            tier=int(row["tier"]),
            priority=int(row["priority"]),
            connector=str(row["connector"]),
            poll_interval_minutes=int(row["poll_interval_minutes"]),
            country=normalize_supported_country(str(row["country"])),
            career_url=str(row["career_url"]),
            external_identifier=str(row["external_identifier"]),
            role_families=[str(item) for item in row["role_families"]],
        )
        for row in rows
    ]


async def upsert_company(company: CompanyPreference, settings: AppSettings | None = None) -> CompanyPreference:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return company

    await ensure_catalog_seeded(resolved_settings)
    company_id = company.id or _company_id(company.company)
    role_families = sorted({family.strip() for family in company.role_families if family.strip()})
    career_url = _company_career_url(
        connector=company.connector,
        external_identifier=company.external_identifier,
        existing_url=company.career_url,
    )
    async with connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO companies (
                    company_id,
                    name,
                    connector,
                    external_identifier,
                    priority,
                    tier,
                    enabled,
                    poll_interval_minutes,
                    country,
                    career_url,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
                ON CONFLICT (company_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    connector = EXCLUDED.connector,
                    external_identifier = EXCLUDED.external_identifier,
                    priority = EXCLUDED.priority,
                    tier = EXCLUDED.tier,
                    enabled = EXCLUDED.enabled,
                    poll_interval_minutes = EXCLUDED.poll_interval_minutes,
                    country = EXCLUDED.country,
                    career_url = EXCLUDED.career_url,
                    updated_at = NOW()
                """,
                company_id,
                company.company.strip(),
                company.connector.strip(),
                company.external_identifier.strip(),
                company.priority,
                company.tier,
                company.enabled,
                company.poll_interval_minutes,
                normalize_supported_country(company.country),
                career_url,
            )
            await conn.execute("DELETE FROM company_role_families WHERE company_id = $1", company_id)
            for family in role_families:
                role_family_id = _role_family_id(family)
                await conn.execute(
                    """
                    INSERT INTO role_families (role_family_id, name, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (role_family_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        updated_at = NOW()
                    """,
                    role_family_id,
                    family,
                )
                await conn.execute(
                    """
                    INSERT INTO company_role_families (company_id, role_family_id)
                    VALUES ($1, $2)
                    ON CONFLICT (company_id, role_family_id) DO NOTHING
                    """,
                    company_id,
                    role_family_id,
                )
    return CompanyPreference(
        id=company_id,
        company=company.company.strip(),
        enabled=company.enabled,
        tier=company.tier,
        priority=company.priority,
        connector=company.connector.strip(),
        poll_interval_minutes=company.poll_interval_minutes,
        country=normalize_supported_country(company.country),
        career_url=career_url,
        external_identifier=company.external_identifier.strip(),
        role_families=role_families,
    )


async def list_watchlists(settings: AppSettings | None = None) -> list[Watchlist]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        from app.data.seed import WATCHLISTS

        return list(WATCHLISTS)

    await ensure_catalog_seeded(resolved_settings)
    async with connection() as conn:
        watchlist_rows = await conn.fetch(
            """
            SELECT watchlist_id, name, enabled
            FROM watchlists
            ORDER BY name ASC
            """
        )
        term_rows = await conn.fetch(
            """
            SELECT watchlist_term_id, watchlist_id, term, company_name, enabled
            FROM watchlist_terms
            ORDER BY term ASC
            """
        )
    terms_by_watchlist: dict[str, list[WatchlistTerm]] = {}
    for row in term_rows:
        terms_by_watchlist.setdefault(str(row["watchlist_id"]), []).append(
            WatchlistTerm(
                id=str(row["watchlist_term_id"]),
                term=str(row["term"]),
                company=str(row["company_name"]),
                enabled=bool(row["enabled"]),
            )
        )
    return [
        Watchlist(
            id=str(row["watchlist_id"]),
            name=str(row["name"]),
            enabled=bool(row["enabled"]),
            terms=terms_by_watchlist.get(str(row["watchlist_id"]), []),
        )
        for row in watchlist_rows
    ]


async def upsert_watchlist(watchlist: Watchlist, settings: AppSettings | None = None) -> Watchlist:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return watchlist

    await ensure_catalog_seeded(resolved_settings)
    watchlist_id = watchlist.id or _watchlist_id(watchlist.name)
    cleaned_terms = [
        WatchlistTerm(
            id=term.id or _watchlist_term_id(watchlist_id, term.term, term.company),
            term=term.term.strip(),
            company=term.company.strip(),
            enabled=term.enabled,
        )
        for term in watchlist.terms
        if term.term.strip()
    ]
    async with connection() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO watchlists (watchlist_id, name, enabled, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (watchlist_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    enabled = EXCLUDED.enabled,
                    updated_at = NOW()
                """,
                watchlist_id,
                watchlist.name.strip(),
                watchlist.enabled,
            )
            await conn.execute("DELETE FROM watchlist_terms WHERE watchlist_id = $1", watchlist_id)
            for term in cleaned_terms:
                await conn.execute(
                    """
                    INSERT INTO watchlist_terms (
                        watchlist_term_id,
                        watchlist_id,
                        term,
                        company_name,
                        enabled,
                        updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, NOW())
                    ON CONFLICT (watchlist_term_id) DO UPDATE SET
                        term = EXCLUDED.term,
                        company_name = EXCLUDED.company_name,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    term.id,
                    watchlist_id,
                    term.term,
                    term.company,
                    term.enabled,
                )
    return Watchlist(id=watchlist_id, name=watchlist.name.strip(), enabled=watchlist.enabled, terms=cleaned_terms)


async def build_scout_settings(settings: AppSettings | None = None) -> ScoutSettings:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        from app.data.seed import SETTINGS

        return SETTINGS

    await ensure_catalog_seeded(resolved_settings)
    companies = await list_companies(resolved_settings)
    watchlists = await list_watchlists(resolved_settings)
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT preference_key, preference_value
            FROM user_preferences
            """
        )
    values = {str(row["preference_key"]): _json_value(row["preference_value"]) for row in rows}
    roles = _read_list(values.get("roles"), resolved_settings.radar.target_roles)
    role_families = _read_list(values.get("role_families"), resolved_settings.radar.role_families)
    work_arrangements = _read_list(values.get("work_arrangements"), resolved_settings.radar.preferred_work_arrangements)
    experience_levels = _read_list(values.get("experience_levels"), resolved_settings.radar.preferred_experience_levels)
    excluded_keywords = _read_list(values.get("excluded_keywords"), resolved_settings.radar.excluded_keywords)

    return ScoutSettings(
        primary_connector=str(values.get("primary_connector", resolved_settings.radar.primary_connector)),
        apply_now_threshold_score=int(values.get("apply_now_threshold_score", resolved_settings.radar.apply_now_threshold_score)),
        review_threshold_score=int(values.get("review_threshold_score", resolved_settings.radar.review_threshold_score)),
        polling_interval_minutes=int(values.get("polling_interval_minutes", resolved_settings.radar.polling_interval_minutes)),
        companies=companies,
        roles=[RolePreference(label=role, enabled=True) for role in roles],
        notifications=_notifications(resolved_settings),
        role_families=[RolePreference(label=family, enabled=True) for family in role_families],
        work_arrangements=[RolePreference(label=value, enabled=True) for value in work_arrangements],
        experience_levels=[RolePreference(label=value, enabled=True) for value in experience_levels],
        excluded_keywords=excluded_keywords,
        watchlists=watchlists,
        minimum_match_score=int(values.get("minimum_match_score", resolved_settings.radar.minimum_match_score)),
        selected_country=normalize_supported_country(str(values.get("selected_country", resolved_settings.radar.selected_country))),
        alert_freshness_hours=int(values.get("alert_freshness_hours", resolved_settings.radar.alert_freshness_hours)),
        dashboard_freshness_hours=int(values.get("dashboard_freshness_hours", resolved_settings.radar.dashboard_freshness_hours)),
    )


async def update_preference_settings(
    payload: dict[str, object],
    settings: AppSettings | None = None,
) -> ScoutSettings:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        from app.data.seed import SETTINGS

        return SETTINGS

    await ensure_catalog_seeded(resolved_settings)
    cleaned_payload = {
        "primary_connector": str(payload.get("primary_connector", resolved_settings.radar.primary_connector)),
        "apply_now_threshold_score": int(payload.get("apply_now_threshold_score", resolved_settings.radar.apply_now_threshold_score)),
        "review_threshold_score": int(payload.get("review_threshold_score", resolved_settings.radar.review_threshold_score)),
        "polling_interval_minutes": int(payload.get("polling_interval_minutes", resolved_settings.radar.polling_interval_minutes)),
        "minimum_match_score": int(payload.get("minimum_match_score", resolved_settings.radar.minimum_match_score)),
        "selected_country": normalize_supported_country(str(payload.get("selected_country", resolved_settings.radar.selected_country))),
        "alert_freshness_hours": int(payload.get("alert_freshness_hours", resolved_settings.radar.alert_freshness_hours)),
        "dashboard_freshness_hours": int(payload.get("dashboard_freshness_hours", resolved_settings.radar.dashboard_freshness_hours)),
        "roles": [str(value).strip() for value in payload.get("roles", []) if str(value).strip()],
        "role_families": [str(value).strip() for value in payload.get("role_families", []) if str(value).strip()],
        "work_arrangements": [str(value).strip() for value in payload.get("work_arrangements", []) if str(value).strip()],
        "experience_levels": [str(value).strip() for value in payload.get("experience_levels", []) if str(value).strip()],
        "excluded_keywords": [str(value).strip() for value in payload.get("excluded_keywords", []) if str(value).strip()],
    }
    async with connection() as conn:
        async with conn.transaction():
            for key, value in cleaned_payload.items():
                await conn.execute(
                    """
                    INSERT INTO user_preferences (preference_key, preference_value, updated_at)
                    VALUES ($1, $2::jsonb, NOW())
                    ON CONFLICT (preference_key) DO UPDATE SET
                        preference_value = EXCLUDED.preference_value,
                        updated_at = NOW()
                    """,
                    key,
                    json.dumps(value),
                )
    return await build_scout_settings(resolved_settings)


async def build_effective_app_settings(settings: AppSettings | None = None) -> AppSettings:
    resolved_settings = settings or get_settings()
    scout_settings = await build_scout_settings(resolved_settings)
    target_companies = tuple(
        TargetCompany(
            name=company.company,
            enabled=company.enabled,
            tier=company.tier,
            priority=company.priority,
            connector=company.connector,
            poll_interval_minutes=company.poll_interval_minutes,
        )
        for company in scout_settings.companies
    )
    greenhouse_boards = tuple(
        GreenhouseBoard(company=company.company, token=company.external_identifier)
        for company in scout_settings.companies
        if company.enabled and company.connector == "greenhouse" and company.external_identifier
    )
    return replace(
        resolved_settings,
        radar=replace(
            resolved_settings.radar,
            primary_connector=scout_settings.primary_connector,
            polling_interval_minutes=scout_settings.polling_interval_minutes,
            minimum_match_score=scout_settings.minimum_match_score,
            apply_now_threshold_score=scout_settings.apply_now_threshold_score,
            review_threshold_score=scout_settings.review_threshold_score,
            selected_country=scout_settings.selected_country,
            alert_freshness_hours=scout_settings.alert_freshness_hours,
            dashboard_freshness_hours=scout_settings.dashboard_freshness_hours,
            target_companies=target_companies,
            greenhouse_boards=greenhouse_boards,
            target_roles=tuple(role.label for role in scout_settings.roles if role.enabled),
            role_families=tuple(role.label for role in scout_settings.role_families if role.enabled),
            preferred_work_arrangements=tuple(role.label for role in scout_settings.work_arrangements if role.enabled),
            preferred_experience_levels=tuple(role.label for role in scout_settings.experience_levels if role.enabled),
            excluded_keywords=tuple(scout_settings.excluded_keywords),
        ),
    )
