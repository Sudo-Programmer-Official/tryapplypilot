from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

from app.config import ConnectorSettings
from app.connectors.base import ConnectorCursor, ConnectorDefinition, ConnectorRunResult, JobConnector, NormalizedJobRecord
from app.http import HttpTlsSettings, request_json
from app.job_metadata import infer_country_code, matches_country_preference, normalize_supported_country

_BROWSER_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
}
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_API_PATH_RE = re.compile(r"^/careers-api/2\.0/company/(?P<uid>[^/]+)/positions(?:/[^/]+)?/?$")
_HOSTED_PATH_RE = re.compile(r"^/jobs/[^/]+/(?P<uid>[A-Za-z0-9.]+)/")
_UID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")
_TOKEN_RE = re.compile(r"^[A-Fa-f0-9]{20,}$")


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _category_labels(position: dict[str, object]) -> list[str]:
    raw_categories = position.get("categories")
    if not isinstance(raw_categories, list):
        return []
    labels: list[str] = []
    for item in raw_categories:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if name and value:
            labels.append(f"{name}: {value}")
        elif value:
            labels.append(value)
        elif name:
            labels.append(name)
    return labels


def _detail_sections(position: dict[str, object]) -> list[str]:
    raw_details = position.get("details")
    if not isinstance(raw_details, list):
        return []
    normalized_details = sorted(
        [item for item in raw_details if isinstance(item, dict)],
        key=lambda item: int(item.get("order") or 0),
    )
    sections: list[str] = []
    for item in normalized_details:
        name = str(item.get("name") or "").strip()
        value = _strip_html(str(item.get("value") or ""))
        if not value:
            continue
        if name:
            sections.append(f"{name}\n{value}")
        else:
            sections.append(value)
    return sections


def _location_text(position: dict[str, object]) -> str:
    location = position.get("location")
    if isinstance(location, dict):
        name = str(location.get("name") or "").strip()
        if name:
            return name
        city = str(location.get("city") or "").strip()
        state = str(location.get("state") or "").strip()
        country = str(location.get("country") or "").strip().upper()
        parts = [part for part in (city, state, country) if part]
        if parts:
            return ", ".join(parts)
    return "Unknown"


def _remote_policy(position: dict[str, object], location: str, description_text: str) -> str:
    workplace_type = str(position.get("workplace_type") or "").strip().casefold()
    if "hybrid" in workplace_type:
        return "Hybrid"
    if "remote" in workplace_type:
        return "Remote"
    location_payload = position.get("location")
    if isinstance(location_payload, dict) and bool(location_payload.get("is_remote")):
        return "Remote"
    haystack = " ".join((location, description_text)).casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    return "Onsite"


def _matches_company_country(company_country: str, position: dict[str, object], location: str, description_text: str) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    location_payload = position.get("location")
    if isinstance(location_payload, dict):
        country = str(location_payload.get("country") or "").strip().upper()
        if country in {"US", "CA", "IN"}:
            return country == selected_country
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _description_text(position: dict[str, object], location: str) -> str:
    sections = _detail_sections(position)
    department = str(position.get("department") or "").strip()
    employment_type = str(position.get("employment_type") or "").strip()
    experience_level = str(position.get("experience_level") or "").strip()
    categories = ", ".join(_category_labels(position))
    metadata = [
        ("Department", department),
        ("Employment Type", employment_type),
        ("Experience Level", experience_level),
        ("Location", location),
        ("Categories", categories),
    ]
    sections.extend(f"{label}: {value}" for label, value in metadata if value)
    return "\n\n".join(section for section in sections if section.strip())


def _apply_url(position: dict[str, object]) -> str:
    for key in ("url_active_page", "url_comeet_hosted_page", "url_recruit_hosted_page", "url_detected_page", "position_url"):
        value = str(position.get(key) or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return ""


def _parse_company_uid_and_token(external_identifier: str, career_url: str) -> tuple[str, str]:
    company_uid = ""
    token = ""
    resolved_identifier = external_identifier.strip()
    if resolved_identifier:
        for separator in ("|", ":"):
            if separator in resolved_identifier:
                left, right = resolved_identifier.split(separator, 1)
                company_uid = left.strip()
                token = right.strip()
                break
        if not company_uid:
            company_uid = resolved_identifier

    resolved_url = career_url.strip()
    if resolved_url:
        parsed = urlsplit(resolved_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Comeet career URL must be a valid absolute URL.")
        path_match = _API_PATH_RE.match(parsed.path)
        if path_match is not None and not company_uid:
            company_uid = path_match.group("uid").strip()
        if not company_uid:
            hosted_match = _HOSTED_PATH_RE.match(parsed.path)
            if hosted_match is not None:
                company_uid = hosted_match.group("uid").strip()
        if not token:
            query = dict(parse_qsl(parsed.query, keep_blank_values=False))
            token = str(query.get("token") or "").strip()

    if not company_uid:
        raise ValueError("Comeet configuration is missing the company UID.")
    if not _UID_RE.fullmatch(company_uid):
        raise ValueError("Comeet company UID format is invalid.")
    if not token:
        raise ValueError("Comeet configuration is missing the public company token.")
    if not _TOKEN_RE.fullmatch(token):
        raise ValueError("Comeet company token format is invalid.")
    return company_uid, token


@dataclass(frozen=True)
class ComeetSite:
    company: str
    identifier: str
    company_uid: str
    token: str
    career_url: str
    country: str = "US"
    role_families: tuple[str, ...] = ()
    host: str = "https://www.comeet.co"

    @property
    def positions_url(self) -> str:
        query = urlencode({"token": self.token, "details": "true"})
        return f"{self.host}/careers-api/2.0/company/{self.company_uid}/positions?{query}"


def build_comeet_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
) -> ComeetSite:
    company_uid, token = _parse_company_uid_and_token(external_identifier, career_url)
    resolved_url = career_url.strip() or f"https://www.comeet.co/careers-api/2.0/company/{company_uid}/positions"
    return ComeetSite(
        company=company,
        identifier=company_uid,
        company_uid=company_uid,
        token=token,
        career_url=resolved_url,
        country=country,
        role_families=role_families,
    )


@dataclass(frozen=True)
class ComeetJobConnector(JobConnector):
    site: ComeetSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="comeet",
        display_name="Comeet",
        layer="official_ats",
        admin_status="beta",
        rollout_stage="next",
        pagination_mode="none",
        supports_incremental_sync=False,
        rate_limit_per_minute=8,
    )

    def collect(self, cursor: ConnectorCursor | None = None) -> ConnectorRunResult:
        del cursor
        payload = request_json(
            "GET",
            self.site.positions_url,
            timeout_seconds=self.connector_settings.request_timeout_seconds,
            tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
            headers=_BROWSER_HEADERS,
        )
        if not isinstance(payload, list):
            raise RuntimeError("Comeet returned an unexpected payload.")

        jobs: list[NormalizedJobRecord] = []
        latest_seen_at: datetime | None = None
        seen_job_ids: set[str] = set()
        for position in payload:
            if not isinstance(position, dict):
                continue
            external_job_id = str(position.get("uid") or "").strip()
            title = str(position.get("name") or "").strip()
            if not external_job_id or not title or external_job_id in seen_job_ids:
                continue
            seen_job_ids.add(external_job_id)
            location = _location_text(position)
            description_text = _description_text(position, location)
            if not _matches_company_country(self.site.country, position, location, description_text):
                continue
            apply_url = _apply_url(position)
            if not apply_url:
                continue
            published_at = _parse_datetime(position.get("time_updated"))
            if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                latest_seen_at = published_at
            remote_policy = _remote_policy(position, location, description_text)
            jobs.append(
                NormalizedJobRecord(
                    connector_key=f"comeet:{self.site.identifier}",
                    external_job_id=external_job_id,
                    company=str(position.get("company_name") or "").strip() or self.site.company,
                    title=title,
                    location=location,
                    remote_policy=remote_policy,
                    published_at=published_at,
                    apply_url=apply_url,
                    description_text=description_text,
                    job_fingerprint=hashlib.sha1(f"comeet:{self.site.identifier}:{external_job_id}".encode("utf-8")).hexdigest(),
                    raw_payload=position,
                )
            )

        return ConnectorRunResult(
            jobs=jobs,
            next_cursor=ConnectorCursor(last_published_at=latest_seen_at),
            exhausted=True,
            requests_made=1,
            pages_scanned=1,
            expected_pages=1,
            partial_reason=None,
        )
