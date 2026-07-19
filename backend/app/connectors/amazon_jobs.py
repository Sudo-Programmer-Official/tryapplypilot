from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
from math import ceil
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
_DEFAULT_BASE_QUERY = "software development engineer"
_DEFAULT_PAGE_SIZE = 10
_MAX_PAGES_PER_RUN = 8
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_POSTED_DAYS_RE = re.compile(r"(\d+)\s+days?", re.IGNORECASE)
_POSTED_HOURS_RE = re.compile(r"(\d+)\s+hours?", re.IGNORECASE)
_POSTED_MINUTES_RE = re.compile(r"(\d+)\s+minutes?", re.IGNORECASE)
_COUNTRY_QUERY_BY_CODE = {
    "US": "USA",
    "CA": "CAN",
    "IN": "IND",
}


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _country_code_from_value(value: object) -> str | None:
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return None
    mapping = {
        "us": "US",
        "usa": "US",
        "united states": "US",
        "ca": "CA",
        "can": "CA",
        "canada": "CA",
        "in": "IN",
        "ind": "IN",
        "india": "IN",
    }
    return mapping.get(normalized, "OTHER")


def _parse_posted_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%B %d, %Y")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _parse_updated_time(value: object, *, now: datetime) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.casefold()
    if normalized in {"today", "0 day", "0 days"}:
        return now
    match = _POSTED_MINUTES_RE.fullmatch(normalized)
    if match is not None:
        return now - timedelta(minutes=int(match.group(1)))
    match = _POSTED_HOURS_RE.fullmatch(normalized)
    if match is not None:
        return now - timedelta(hours=int(match.group(1)))
    match = _POSTED_DAYS_RE.fullmatch(normalized)
    if match is not None:
        return now - timedelta(days=int(match.group(1)))
    return None


def _decoded_locations(item: dict[str, object]) -> list[dict[str, object]]:
    raw_locations = item.get("locations")
    if not isinstance(raw_locations, list):
        return []
    locations: list[dict[str, object]] = []
    for entry in raw_locations:
        if isinstance(entry, dict):
            locations.append(entry)
            continue
        if isinstance(entry, str):
            try:
                decoded = json.loads(entry)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                locations.append(decoded)
    return locations


def _remote_policy(item: dict[str, object], decoded_locations: list[dict[str, object]], description_text: str) -> str:
    location_types = {
        str(location.get("type") or "").strip().casefold()
        for location in decoded_locations
        if str(location.get("type") or "").strip()
    }
    if "remote" in location_types or "virtual" in location_types:
        return "Remote"
    if "hybrid" in location_types:
        return "Hybrid"
    haystack = " ".join(
        (
            str(item.get("normalized_location") or ""),
            str(item.get("location") or ""),
            description_text,
        )
    ).casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack or "virtual" in haystack:
        return "Remote"
    return "Onsite"


def _location_text(item: dict[str, object], decoded_locations: list[dict[str, object]]) -> str:
    normalized_location = str(item.get("normalized_location") or "").strip()
    if normalized_location:
        return normalized_location
    labels = [
        str(location.get("normalizedLocation") or location.get("location") or "").strip()
        for location in decoded_locations
    ]
    labels = [label for label in labels if label]
    if labels:
        return "; ".join(dict.fromkeys(labels))
    return str(item.get("location") or "").strip() or "Unknown"


def _description_text(item: dict[str, object], location: str) -> str:
    parts = [
        _strip_html(str(item.get("description") or "")),
        f"Location: {location}",
        f"Business Category: {str(item.get('business_category') or '').strip()}",
        f"Job Category: {str(item.get('job_category') or '').strip()}",
        f"Schedule: {str(item.get('job_schedule_type') or '').strip()}",
        f"Basic Qualifications: {_strip_html(str(item.get('basic_qualifications') or ''))}",
        f"Preferred Qualifications: {_strip_html(str(item.get('preferred_qualifications') or ''))}",
    ]
    return "\n".join(part for part in parts if part and (":" not in part or part.split(":", 1)[1].strip()))


def _matches_company_country(
    company_country: str,
    item: dict[str, object],
    decoded_locations: list[dict[str, object]],
    location: str,
    description_text: str,
) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    country_candidates = {
        _country_code_from_value(item.get("country_code")),
        *(
            _country_code_from_value(location_payload.get("countryIso2a") or location_payload.get("countryIso3a"))
            for location_payload in decoded_locations
        ),
    }
    normalized_candidates = {candidate for candidate in country_candidates if candidate is not None}
    if normalized_candidates:
        return selected_country in normalized_candidates
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _normalize_url(value: object, *, root_url: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized
    return f"{root_url.rstrip('/')}/{normalized.lstrip('/')}"


@dataclass(frozen=True)
class AmazonCareerSite:
    company: str
    identifier: str
    career_url: str
    root_url: str
    locale: str
    base_query: str
    country: str = "US"
    search_country: str | None = None
    sort: str = "recent"
    extra_query: tuple[tuple[str, str], ...] = ()
    role_families: tuple[str, ...] = ()
    page_size: int = _DEFAULT_PAGE_SIZE
    max_pages_per_run: int = _MAX_PAGES_PER_RUN

    @property
    def search_url(self) -> str:
        return f"{self.root_url}/{self.locale}/search.json"


def build_amazon_career_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_pages_per_run: int = _MAX_PAGES_PER_RUN,
) -> AmazonCareerSite:
    resolved_url = career_url.strip() or "https://www.amazon.jobs/en/search"
    parsed = urlsplit(resolved_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Amazon Jobs URL must be a valid absolute URL.")
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    locale = path_segments[0] if path_segments else "en"
    query_pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=False)]
    query_map = {key: value for key, value in query_pairs}
    base_query = query_map.get("base_query", "").strip() or _DEFAULT_BASE_QUERY
    selected_country = normalize_supported_country(country)
    search_country = query_map.get("country", "").strip() or _COUNTRY_QUERY_BY_CODE.get(selected_country)
    if selected_country == "ANY" and not query_map.get("country"):
        search_country = None
    extra_query = tuple(
        (key, value)
        for key, value in query_pairs
        if key not in {"base_query", "country", "sort", "offset", "result_limit"}
    )
    return AmazonCareerSite(
        company=company,
        identifier=external_identifier.strip() or company.casefold().replace(" ", "-"),
        career_url=resolved_url,
        root_url=f"{parsed.scheme}://{parsed.netloc}",
        locale=locale,
        base_query=base_query,
        country=country,
        search_country=search_country or None,
        sort=query_map.get("sort", "").strip() or "recent",
        extra_query=extra_query,
        role_families=role_families,
        page_size=page_size,
        max_pages_per_run=max_pages_per_run,
    )


@dataclass(frozen=True)
class AmazonJobsConnector(JobConnector):
    site: AmazonCareerSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="amazon-jobs",
        display_name="Amazon Jobs",
        layer="company_careers",
        admin_status="beta",
        rollout_stage="next",
        pagination_mode="page",
        supports_incremental_sync=True,
        rate_limit_per_minute=12,
    )

    def collect(self, cursor: ConnectorCursor | None = None) -> ConnectorRunResult:
        jobs: list[NormalizedJobRecord] = []
        latest_seen_at: datetime | None = None
        requests_made = 0
        pages_scanned = 0
        expected_pages: int | None = None
        inventory_complete = True
        partial_reason: str | None = None
        seen_job_ids: set[str] = set()
        last_published_cursor = cursor.last_published_at if cursor is not None else None
        now = datetime.now(timezone.utc)

        for page_index in range(self.site.max_pages_per_run):
            offset = page_index * self.site.page_size
            query: list[tuple[str, str]] = [
                ("base_query", self.site.base_query),
                ("sort", self.site.sort),
                ("offset", str(offset)),
                ("result_limit", str(self.site.page_size)),
            ]
            if self.site.search_country is not None:
                query.append(("country", self.site.search_country))
            query.extend(self.site.extra_query)
            payload = request_json(
                "GET",
                f"{self.site.search_url}?{urlencode(query)}",
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
            )
            requests_made += 1
            pages_scanned += 1
            if not isinstance(payload, dict):
                raise RuntimeError("Amazon Jobs returned an unexpected payload.")
            jobs_payload = payload.get("jobs")
            if not isinstance(jobs_payload, list):
                raise RuntimeError("Amazon Jobs response did not include a jobs array.")
            total_jobs = int(payload.get("hits") or 0)
            if expected_pages is None:
                expected_pages = max(1, ceil(total_jobs / self.site.page_size)) if total_jobs else 1
            if not jobs_payload:
                if total_jobs and page_index + 1 <= expected_pages:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break

            for item in jobs_payload:
                if not isinstance(item, dict):
                    continue
                external_job_id = str(item.get("id_icims") or item.get("id") or item.get("job_path") or "").strip()
                if not external_job_id or external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)
                decoded_locations = _decoded_locations(item)
                location = _location_text(item, decoded_locations)
                description_text = _description_text(item, location)
                if not _matches_company_country(self.site.country, item, decoded_locations, location, description_text):
                    continue
                published_at = _parse_posted_date(item.get("posted_date")) or _parse_updated_time(
                    item.get("updated_time"),
                    now=now,
                )
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                if last_published_cursor is not None and published_at is not None and published_at < last_published_cursor:
                    # Older jobs remain useful for inventory and deduplication.
                    pass
                company_name = str(item.get("company_name") or "").strip() or self.site.company
                apply_url = _normalize_url(item.get("url_next_step"), root_url=self.site.root_url)
                if not apply_url:
                    apply_url = _normalize_url(item.get("job_path"), root_url=self.site.root_url)
                fingerprint_input = "::".join(
                    (
                        self.definition.key,
                        self.site.identifier,
                        external_job_id,
                        company_name.casefold(),
                        str(item.get("title") or "").strip().casefold(),
                        location.casefold(),
                        apply_url.casefold(),
                    )
                )
                jobs.append(
                    NormalizedJobRecord(
                        connector_key=f"{self.definition.key}:{self.site.identifier}",
                        external_job_id=external_job_id,
                        company=company_name,
                        title=str(item.get("title") or "").strip(),
                        location=location,
                        remote_policy=_remote_policy(item, decoded_locations, description_text),
                        published_at=published_at,
                        apply_url=apply_url,
                        description_text=description_text,
                        job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                        raw_payload={"amazon_job": item},
                    )
                )

            if expected_pages is not None and page_index + 1 >= expected_pages:
                break

        if expected_pages is not None and pages_scanned < expected_pages:
            inventory_complete = False
            partial_reason = partial_reason or "page_limit_reached"

        jobs.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return ConnectorRunResult(
            jobs=jobs,
            next_cursor=ConnectorCursor(cursor=None, last_published_at=latest_seen_at),
            exhausted=inventory_complete,
            requests_made=requests_made,
            pages_scanned=pages_scanned,
            expected_pages=expected_pages,
            partial_reason=partial_reason,
        )
