from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from app.job_metadata import normalize_supported_country

RuntimeMode = Literal["seed", "postgres"]

DEFAULT_TARGET_ROLES = (
    "Software Engineer",
    "Software Engineer II",
    "Senior Software Engineer",
    "Staff Software Engineer",
    "Principal Software Engineer",
    "Backend Engineer",
    "Platform Engineer",
    "Distributed Systems Engineer",
    "Infrastructure Engineer",
    "Cloud Engineer",
    "AI Engineer",
    "Machine Learning Engineer",
    "Applied AI Engineer",
    "LLM Engineer",
    "AI Platform Engineer",
    "Agent Engineer",
    "Forward Deployed Engineer",
    "Solutions Engineer",
    "Solutions Architect",
    "Developer Advocate",
)

DEFAULT_RESUME_VARIANTS = (
    "Backend_AI_v5.pdf",
    "Platform_v4.pdf",
    "Distributed_Systems_v2.pdf",
)

DEFAULT_ROLE_FAMILIES = (
    "Backend Engineering",
    "AI Platform",
    "AI Infrastructure",
    "Distributed Systems",
    "Platform Engineering",
    "Cloud Infrastructure",
    "Developer Experience",
    "Infrastructure",
    "Data Platform",
    "Machine Learning Platform",
    "Search",
    "Identity",
    "Storage",
    "Networking",
    "Reliability",
    "Observability",
    "Internal Tools",
    "Product Engineering",
    "Full Stack",
    "Forward Deployed Engineering",
)

DEFAULT_WORK_ARRANGEMENTS = (
    "Remote",
    "Hybrid",
    "Onsite",
)

DEFAULT_EXPERIENCE_LEVELS = (
    "Mid-level",
    "Senior",
    "Staff",
)

DEFAULT_EXCLUDED_KEYWORDS = (
    "sales",
    "marketing",
    "human resources",
    "hr",
    "finance",
    "accounting",
    "customer support",
    "support engineer",
    "qa",
    "quality assurance",
    "test automation",
    "it help desk",
    "help desk",
    "desktop support",
    "hardware",
    "silicon",
    "firmware",
    "verification",
)

DEFAULT_TARGET_COMPANY_ROWS = (
    ("Microsoft", 1, 1, "microsoft-careers"),
    ("Google", 1, 2, "google-careers"),
    ("Amazon", 1, 3, "company-api"),
    ("Meta", 1, 4, "company-api"),
    ("Apple", 1, 5, "company-api"),
    ("NVIDIA", 1, 6, "company-api"),
    ("OpenAI", 1, 7, "company-api"),
    ("Anthropic", 1, 8, "company-api"),
    ("Databricks", 1, 9, "company-api"),
    ("Snowflake", 1, 10, "company-api"),
    ("Cloudflare", 1, 11, "company-api"),
    ("Stripe", 1, 12, "company-api"),
    ("Twilio", 1, 13, "company-api"),
    ("GitHub", 1, 14, "company-api"),
    ("MongoDB", 1, 15, "company-api"),
    ("Confluent", 1, 16, "company-api"),
    ("Perplexity", 1, 17, "company-api"),
    ("Scale AI", 1, 18, "company-api"),
    ("Netflix", 2, 19, "company-api"),
    ("Airbnb", 2, 20, "company-api"),
    ("Uber", 2, 21, "company-api"),
    ("Cursor", 3, 22, "company-api"),
    ("Linear", 3, 23, "company-api"),
    ("Ramp", 3, 24, "company-api"),
    ("Rippling", 3, 25, "company-api"),
)


@dataclass(frozen=True)
class DatabaseSettings:
    admin_dsn: str
    dsn: str
    name: str
    app_name: str
    connect_timeout_seconds: int
    schema_path: Path

    @property
    def backend(self) -> str:
        return self.dsn.split(":", 1)[0].split("+", 1)[0]


@dataclass(frozen=True)
class ConnectorSettings:
    request_timeout_seconds: int
    retry_attempts: int
    base_retry_delay_seconds: float
    max_retry_delay_seconds: float
    backoff_multiplier: float
    rate_limit_per_minute: int


@dataclass(frozen=True)
class GreenhouseBoard:
    company: str
    token: str


@dataclass(frozen=True)
class TargetCompany:
    name: str
    enabled: bool
    tier: int
    priority: int
    connector: str
    poll_interval_minutes: int


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str | None
    chat_id: str | None
    bot_username: str | None
    api_base_url: str
    ca_bundle_path: Path | None
    skip_ssl_verify: bool

    @property
    def bot_configured(self) -> bool:
        return bool(self.bot_token)

    @property
    def delivery_configured(self) -> bool:
        return bool(self.bot_token)


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str | None
    model: str
    api_base_url: str
    timeout_seconds: int
    ca_bundle_path: Path | None
    skip_ssl_verify: bool

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class AuthSettings:
    jwt_secret: str
    jwt_issuer: str
    access_token_minutes: int
    refresh_token_days: int
    super_admin_email: str | None
    super_admin_password: str | None
    super_admin_name: str


@dataclass(frozen=True)
class RadarSettings:
    mode: RuntimeMode
    primary_connector: str
    enabled_connectors: tuple[str, ...]
    polling_interval_minutes: int
    minimum_match_score: int
    apply_now_threshold_score: int
    review_threshold_score: int
    selected_country: str
    alert_freshness_hours: int
    dashboard_freshness_hours: int
    alert_decisions: tuple[str, ...]
    greenhouse_boards: tuple[GreenhouseBoard, ...]
    target_companies: tuple[TargetCompany, ...]
    role_families: tuple[str, ...]
    target_roles: tuple[str, ...]
    preferred_work_arrangements: tuple[str, ...]
    preferred_experience_levels: tuple[str, ...]
    excluded_keywords: tuple[str, ...]
    profile_text: str
    resume_variants: tuple[str, ...]
    initial_alert_window_hours: int
    initial_sync_openai_job_limit: int
    initial_sync_max_alerts: int

    def is_connector_enabled(self, connector_key: str) -> bool:
        return connector_key.casefold() in {value.casefold() for value in self.enabled_connectors}


@dataclass(frozen=True)
class AppSettings:
    environment: str
    log_level: str
    database: DatabaseSettings
    connectors: ConnectorSettings
    telegram: TelegramSettings
    openai: OpenAISettings
    auth: AuthSettings
    radar: RadarSettings


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return int(raw_value)


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return float(raw_value)


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return _parse_bool_value(raw_value, default)


def _parse_bool_value(raw_value: str, default: bool) -> bool:
    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _read_path(name: str) -> Path | None:
    raw_value = os.getenv(name)
    if not raw_value:
        return None
    return Path(raw_value)


def _read_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    values = tuple(part.strip() for part in raw_value.split(",") if part.strip())
    return values or default


def _read_connector_keys(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.casefold() for value in _read_csv(name, default))


def _read_greenhouse_boards(name: str) -> tuple[GreenhouseBoard, ...]:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return ()

    boards: list[GreenhouseBoard] = []
    for part in raw_value.split(","):
        entry = part.strip()
        if not entry or "=" not in entry:
            continue
        company, token = entry.split("=", 1)
        company = company.strip()
        token = token.strip()
        if not company or not token:
            continue
        boards.append(GreenhouseBoard(company=company, token=token))
    return tuple(boards)


def _default_target_companies(polling_interval_minutes: int) -> tuple[TargetCompany, ...]:
    return tuple(
        TargetCompany(
            name=name,
            enabled=True,
            tier=tier,
            priority=priority,
            connector=connector,
            poll_interval_minutes=polling_interval_minutes,
        )
        for name, tier, priority, connector in DEFAULT_TARGET_COMPANY_ROWS
    )


def _read_target_companies(
    name: str,
    *,
    default: tuple[TargetCompany, ...],
    polling_interval_minutes: int,
) -> tuple[TargetCompany, ...]:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    companies: list[TargetCompany] = []
    for index, raw_entry in enumerate(raw_value.split(";"), start=1):
        entry = raw_entry.strip()
        if not entry:
            continue
        parts = [part.strip() for part in entry.split("|")]
        if not parts or not parts[0]:
            continue
        tier = int(parts[2]) if len(parts) > 2 and parts[2] else 3
        priority = int(parts[3]) if len(parts) > 3 and parts[3] else index
        enabled = _parse_bool_value(parts[4], True) if len(parts) > 4 and parts[4] else True
        poll_interval = int(parts[5]) if len(parts) > 5 and parts[5] else polling_interval_minutes
        companies.append(
            TargetCompany(
                name=parts[0],
                connector=parts[1] if len(parts) > 1 and parts[1] else "company-api",
                tier=tier,
                priority=priority,
                enabled=enabled,
                poll_interval_minutes=poll_interval,
            )
        )
    return tuple(companies) or default


def _merge_greenhouse_companies(
    companies: tuple[TargetCompany, ...],
    boards: tuple[GreenhouseBoard, ...],
    *,
    polling_interval_minutes: int,
) -> tuple[TargetCompany, ...]:
    ordered_companies = list(companies)
    index_by_name = {
        company.name.casefold(): position
        for position, company in enumerate(ordered_companies)
    }
    next_priority = max((company.priority for company in ordered_companies), default=0) + 1

    for board in boards:
        key = board.company.casefold()
        updated_company = TargetCompany(
            name=board.company,
            enabled=True,
            tier=1,
            priority=next_priority,
            connector="greenhouse",
            poll_interval_minutes=polling_interval_minutes,
        )
        if key in index_by_name:
            current = ordered_companies[index_by_name[key]]
            ordered_companies[index_by_name[key]] = TargetCompany(
                name=current.name,
                enabled=current.enabled,
                tier=current.tier,
                priority=current.priority,
                connector="greenhouse",
                poll_interval_minutes=current.poll_interval_minutes,
            )
            continue
        ordered_companies.append(updated_company)
        index_by_name[key] = len(ordered_companies) - 1
        next_priority += 1

    return tuple(ordered_companies)


def _database_name_from_dsn(dsn: str) -> str:
    parsed = urlsplit(dsn)
    path = parsed.path.lstrip("/")
    return path or "postgres"


def _replace_database_name(dsn: str, database_name: str) -> str:
    parsed = urlsplit(dsn)
    new_path = f"/{database_name}"
    return urlunsplit((parsed.scheme, parsed.netloc, new_path, parsed.query, parsed.fragment))


def _resolve_runtime_mode(explicit_dsn: str | None, template_dsn: str | None) -> RuntimeMode:
    raw_mode = os.getenv("JOB_RADAR_RUNTIME_MODE")
    if raw_mode is not None:
        normalized = raw_mode.strip().casefold()
        if normalized in {"seed", "postgres"}:
            return normalized  # type: ignore[return-value]
    return "postgres" if explicit_dsn is not None or template_dsn is not None else "seed"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    _load_env_file()
    schema_path = Path(__file__).with_name("db").joinpath("schema.sql")
    explicit_dsn = os.getenv("JOB_RADAR_DATABASE_URL")
    template_dsn = os.getenv("JOB_RADAR_DATABASE_TEMPLATE_URL")
    database_name = os.getenv("JOB_RADAR_DATABASE_NAME", "job_hunter_app")
    runtime_mode = _resolve_runtime_mode(explicit_dsn, template_dsn)
    polling_interval_minutes = _read_int("JOB_RADAR_POLLING_INTERVAL_MINUTES", 5)
    greenhouse_boards = _read_greenhouse_boards("JOB_RADAR_GREENHOUSE_BOARDS")
    target_companies = _merge_greenhouse_companies(
        _read_target_companies(
            "JOB_RADAR_TARGET_COMPANIES",
            default=_default_target_companies(polling_interval_minutes),
            polling_interval_minutes=polling_interval_minutes,
        ),
        greenhouse_boards,
        polling_interval_minutes=polling_interval_minutes,
    )

    if explicit_dsn is not None:
        resolved_dsn = explicit_dsn
        resolved_name = _database_name_from_dsn(explicit_dsn)
        admin_dsn = _replace_database_name(explicit_dsn, "postgres")
    elif template_dsn is not None:
        resolved_dsn = _replace_database_name(template_dsn, database_name)
        resolved_name = database_name
        admin_dsn = template_dsn
    else:
        resolved_dsn = "postgresql://job_radar:job_radar@localhost:5432/job_radar"
        resolved_name = _database_name_from_dsn(resolved_dsn)
        admin_dsn = _replace_database_name(resolved_dsn, "postgres")

    return AppSettings(
        environment=os.getenv("JOB_RADAR_ENV", "development"),
        log_level=os.getenv("JOB_RADAR_LOG_LEVEL", "INFO").upper(),
        database=DatabaseSettings(
            admin_dsn=admin_dsn,
            dsn=resolved_dsn,
            name=resolved_name,
            app_name=os.getenv("JOB_RADAR_DB_APP_NAME", "ai-job-radar"),
            connect_timeout_seconds=_read_int("JOB_RADAR_DB_CONNECT_TIMEOUT_SECONDS", 5),
            schema_path=schema_path,
        ),
        connectors=ConnectorSettings(
            request_timeout_seconds=_read_int("JOB_RADAR_CONNECTOR_TIMEOUT_SECONDS", 20),
            retry_attempts=_read_int("JOB_RADAR_CONNECTOR_RETRY_ATTEMPTS", 3),
            base_retry_delay_seconds=_read_float("JOB_RADAR_CONNECTOR_BASE_RETRY_DELAY_SECONDS", 0.5),
            max_retry_delay_seconds=_read_float("JOB_RADAR_CONNECTOR_MAX_RETRY_DELAY_SECONDS", 8.0),
            backoff_multiplier=_read_float("JOB_RADAR_CONNECTOR_BACKOFF_MULTIPLIER", 2.0),
            rate_limit_per_minute=_read_int("JOB_RADAR_CONNECTOR_RATE_LIMIT_PER_MINUTE", 30),
        ),
        telegram=TelegramSettings(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            bot_username=os.getenv("TELEGRAM_BOT_USERNAME"),
            api_base_url=os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org"),
            ca_bundle_path=_read_path("TELEGRAM_CA_BUNDLE_PATH"),
            skip_ssl_verify=_read_bool("TELEGRAM_SKIP_SSL_VERIFY", False),
        ),
        openai=OpenAISettings(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("JOB_RADAR_OPENAI_MODEL", "gpt-5"),
            api_base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=_read_int("JOB_RADAR_OPENAI_TIMEOUT_SECONDS", 30),
            ca_bundle_path=_read_path("OPENAI_CA_BUNDLE_PATH"),
            skip_ssl_verify=_read_bool("OPENAI_SKIP_SSL_VERIFY", False),
        ),
        auth=AuthSettings(
            jwt_secret=os.getenv("JOB_RADAR_JWT_SECRET", "dev-only-change-me"),
            jwt_issuer=os.getenv("JOB_RADAR_JWT_ISSUER", "ai-job-radar"),
            access_token_minutes=_read_int("JOB_RADAR_ACCESS_TOKEN_MINUTES", 30),
            refresh_token_days=_read_int("JOB_RADAR_REFRESH_TOKEN_DAYS", 30),
            super_admin_email=os.getenv("JOB_RADAR_SUPER_ADMIN_EMAIL"),
            super_admin_password=os.getenv("JOB_RADAR_SUPER_ADMIN_PASSWORD"),
            super_admin_name=os.getenv("JOB_RADAR_SUPER_ADMIN_NAME", "Super Admin"),
        ),
        radar=RadarSettings(
            mode=runtime_mode,
            primary_connector=os.getenv("JOB_RADAR_PRIMARY_CONNECTOR", "Greenhouse"),
            enabled_connectors=_read_connector_keys("JOB_RADAR_ENABLED_CONNECTORS", ("greenhouse",)),
            polling_interval_minutes=polling_interval_minutes,
            minimum_match_score=_read_int("JOB_RADAR_MINIMUM_MATCH_SCORE", 90),
            apply_now_threshold_score=_read_int("JOB_RADAR_APPLY_NOW_THRESHOLD", 90),
            review_threshold_score=_read_int("JOB_RADAR_REVIEW_THRESHOLD", 75),
            selected_country=normalize_supported_country(os.getenv("JOB_RADAR_COUNTRY")),
            alert_freshness_hours=_read_int("JOB_RADAR_ALERT_FRESHNESS_HOURS", 6),
            dashboard_freshness_hours=_read_int("JOB_RADAR_DASHBOARD_FRESHNESS_HOURS", 24),
            alert_decisions=_read_csv("JOB_RADAR_ALERT_DECISIONS", ("APPLY_NOW",)),
            greenhouse_boards=greenhouse_boards,
            target_companies=target_companies,
            role_families=_read_csv("JOB_RADAR_ROLE_FAMILIES", DEFAULT_ROLE_FAMILIES),
            target_roles=_read_csv("JOB_RADAR_TARGET_ROLES", DEFAULT_TARGET_ROLES),
            preferred_work_arrangements=_read_csv("JOB_RADAR_WORK_ARRANGEMENTS", DEFAULT_WORK_ARRANGEMENTS),
            preferred_experience_levels=_read_csv("JOB_RADAR_EXPERIENCE_LEVELS", DEFAULT_EXPERIENCE_LEVELS),
            excluded_keywords=_read_csv("JOB_RADAR_EXCLUDED_KEYWORDS", DEFAULT_EXCLUDED_KEYWORDS),
            profile_text=os.getenv("JOB_RADAR_PROFILE_TEXT", "").strip(),
            resume_variants=_read_csv("JOB_RADAR_RESUME_VARIANTS", DEFAULT_RESUME_VARIANTS),
            initial_alert_window_hours=_read_int("JOB_RADAR_INITIAL_ALERT_WINDOW_HOURS", 24),
            initial_sync_openai_job_limit=_read_int("JOB_RADAR_INITIAL_SYNC_OPENAI_JOB_LIMIT", 20),
            initial_sync_max_alerts=_read_int("JOB_RADAR_INITIAL_SYNC_MAX_ALERTS", 5),
        ),
    )
