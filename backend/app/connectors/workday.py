from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import html
from math import ceil
import re
from urllib.parse import urlsplit

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
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGES_PER_RUN = 8
_MAX_DETAIL_REQUESTS_PER_RUN = 10
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")
_POSTED_DAYS_RE = re.compile(r"posted\s+(\d+)\+?\s+days?\s+ago", re.IGNORECASE)
_POSTED_HOURS_RE = re.compile(r"posted\s+(\d+)\+?\s+hours?\s+ago", re.IGNORECASE)
_POSTED_MINUTES_RE = re.compile(r"posted\s+(\d+)\+?\s+minutes?\s+ago", re.IGNORECASE)


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
        "canada": "CA",
        "in": "IN",
        "india": "IN",
    }
    return mapping.get(normalized, "OTHER")


def _parse_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_posted_label(value: object, *, now: datetime) -> datetime | None:
    label = str(value or "").strip()
    if not label:
        return None
    normalized = label.casefold()
    if normalized == "posted today":
        return now
    if normalized == "posted yesterday":
        return now - timedelta(days=1)
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


def _remote_policy(title: str, location: str, description_text: str) -> str:
    haystack = " ".join((title, location, description_text)).casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    return "Onsite"


def _description_text(item: dict[str, object], detail_payload: dict[str, object], location: str) -> str:
    job_posting = detail_payload.get("jobPostingInfo")
    if isinstance(job_posting, dict):
        detailed_description = _strip_html(str(job_posting.get("jobDescription") or ""))
    else:
        detailed_description = ""
    bullet_fields = item.get("bulletFields") if isinstance(item.get("bulletFields"), list) else []
    bullet_summary = ", ".join(str(field).strip() for field in bullet_fields if str(field).strip())
    time_type = ""
    if isinstance(job_posting, dict):
        time_type = str(job_posting.get("timeType") or "").strip()
    description_parts = [
        detailed_description,
        f"Location: {location}",
        f"Posted: {str(item.get('postedOn') or '').strip()}",
        f"Time Type: {time_type}",
        f"Reference: {bullet_summary}",
    ]
    return "\n".join(part for part in description_parts if part and (":" not in part or part.split(":", 1)[1].strip()))


def _location_text(item: dict[str, object], detail_payload: dict[str, object]) -> str:
    job_posting = detail_payload.get("jobPostingInfo")
    if isinstance(job_posting, dict):
        location = str(job_posting.get("location") or "").strip()
        if location:
            return location
    requisition_location = detail_payload.get("jobRequisitionLocation")
    if isinstance(requisition_location, dict):
        location = str(requisition_location.get("descriptor") or "").strip()
        if location:
            return location
    return str(item.get("locationsText") or "").strip() or "Unknown"


def _published_at(item: dict[str, object], detail_payload: dict[str, object], *, now: datetime) -> datetime | None:
    job_posting = detail_payload.get("jobPostingInfo")
    if isinstance(job_posting, dict):
        published_at = _parse_date(job_posting.get("startDate"))
        if published_at is not None:
            return published_at
    published_at = _parse_date(item.get("startDate"))
    if published_at is not None:
        return published_at
    return _parse_posted_label(item.get("postedOn"), now=now)


def _matches_company_country(
    company_country: str,
    location: str,
    description_text: str,
    detail_payload: dict[str, object],
) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    requisition_location = detail_payload.get("jobRequisitionLocation")
    if isinstance(requisition_location, dict):
        country = requisition_location.get("country")
        if isinstance(country, dict):
            detail_country = _country_code_from_value(country.get("alpha2Code") or country.get("descriptor"))
            if detail_country is not None:
                return detail_country == selected_country
    job_posting = detail_payload.get("jobPostingInfo")
    if isinstance(job_posting, dict):
        country = job_posting.get("country")
        if isinstance(country, dict):
            detail_country = _country_code_from_value(country.get("alpha2Code") or country.get("descriptor"))
            if detail_country is not None:
                return detail_country == selected_country
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _normalize_external_path(value: object) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""
    return raw_value if raw_value.startswith("/") else f"/{raw_value}"


def _detail_payload(payload: object) -> dict[str, object]:
    return payload if isinstance(payload, dict) else {}


@dataclass(frozen=True)
class WorkdayCareerSite:
    company: str
    host: str
    tenant: str
    site: str
    career_url: str
    country: str = "US"
    locale: str = "en-US"
    role_families: tuple[str, ...] = ()
    page_size: int = _DEFAULT_PAGE_SIZE
    max_pages_per_run: int = _MAX_PAGES_PER_RUN
    max_detail_requests_per_run: int = _MAX_DETAIL_REQUESTS_PER_RUN

    @property
    def identifier(self) -> str:
        return f"{self.tenant}/{self.site}"

    @property
    def jobs_url(self) -> str:
        return f"{self.host}/wday/cxs/{self.tenant}/{self.site}/jobs"

    @property
    def detail_base_url(self) -> str:
        return f"{self.host}/wday/cxs/{self.tenant}/{self.site}"

    @property
    def public_root_url(self) -> str:
        return f"{self.host}/{self.site}"


def build_workday_career_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_pages_per_run: int = _MAX_PAGES_PER_RUN,
    max_detail_requests_per_run: int = _MAX_DETAIL_REQUESTS_PER_RUN,
) -> WorkdayCareerSite:
    parsed = urlsplit(career_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Workday career URL must be a valid absolute URL.")
    path_segments = [segment for segment in parsed.path.split("/") if segment]
    locale = "en-US"
    if path_segments and _LOCALE_SEGMENT_RE.fullmatch(path_segments[0]):
        locale = path_segments[0]
    site = path_segments[-1] if path_segments else ""
    tenant = parsed.hostname.split(".", 1)[0] if parsed.hostname else ""
    identifier_parts = [part.strip() for part in external_identifier.split("/") if part.strip()]
    if len(identifier_parts) >= 2:
        tenant = identifier_parts[0]
        site = identifier_parts[1]
    elif len(identifier_parts) == 1:
        site = identifier_parts[0]
    if not tenant or not site:
        raise ValueError("Workday company configuration is missing a tenant or site identifier.")
    return WorkdayCareerSite(
        company=company,
        host=f"{parsed.scheme}://{parsed.netloc}",
        tenant=tenant,
        site=site,
        career_url=career_url.strip(),
        country=country,
        locale=locale,
        role_families=role_families,
        page_size=page_size,
        max_pages_per_run=max_pages_per_run,
        max_detail_requests_per_run=max_detail_requests_per_run,
    )


@dataclass(frozen=True)
class WorkdayJobConnector(JobConnector):
    site: WorkdayCareerSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="workday",
        display_name="Workday",
        layer="official_ats",
        admin_status="beta",
        rollout_stage="next",
        pagination_mode="page",
        supports_incremental_sync=True,
        rate_limit_per_minute=10,
    )

    def collect(self, cursor: ConnectorCursor | None = None) -> ConnectorRunResult:
        jobs: list[NormalizedJobRecord] = []
        latest_seen_at: datetime | None = None
        requests_made = 0
        pages_scanned = 0
        expected_pages: int | None = None
        inventory_complete = True
        partial_reason: str | None = None
        detail_requests_made = 0
        seen_job_ids: set[str] = set()
        offset = 0
        now = datetime.now(timezone.utc)
        last_published_cursor = cursor.last_published_at if cursor is not None else None

        while True:
            payload = request_json(
                "POST",
                self.site.jobs_url,
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
                body={
                    "appliedFacets": {},
                    "limit": self.site.page_size,
                    "offset": offset,
                    "searchText": "",
                },
            )
            requests_made += 1
            pages_scanned += 1
            if not isinstance(payload, dict):
                raise RuntimeError("Workday returned an unexpected payload.")

            total_count = int(payload.get("total") or 0)
            if expected_pages is None:
                expected_pages = max(1, ceil(total_count / self.site.page_size)) if total_count else 1
            postings = payload.get("jobPostings", [])
            if not isinstance(postings, list):
                postings = []

            if not postings:
                if total_count and offset < total_count:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break

            for item in postings:
                if not isinstance(item, dict):
                    continue
                external_path = _normalize_external_path(item.get("externalPath"))
                if not external_path:
                    continue
                external_job_id = external_path.lstrip("/")
                if external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)

                title = str(item.get("title") or "").strip()
                listing_location = str(item.get("locationsText") or "").strip() or "Unknown"
                detail_payload: dict[str, object] = {}
                published_hint = _published_at(item, {}, now=now)
                should_fetch_detail = detail_requests_made < self.site.max_detail_requests_per_run
                if should_fetch_detail and last_published_cursor is not None and published_hint is not None:
                    should_fetch_detail = published_hint >= last_published_cursor
                if should_fetch_detail:
                    try:
                        detail_payload = _detail_payload(
                            request_json(
                                "GET",
                                f"{self.site.detail_base_url}{external_path}",
                                timeout_seconds=self.connector_settings.request_timeout_seconds,
                                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                                headers=_BROWSER_HEADERS,
                            )
                        )
                    except Exception:  # noqa: BLE001
                        detail_payload = {}
                    finally:
                        requests_made += 1
                        detail_requests_made += 1

                location = _location_text(item, detail_payload) or listing_location
                description_text = _description_text(item, detail_payload, location)
                if not _matches_company_country(self.site.country, location, description_text, detail_payload):
                    continue
                published_at = _published_at(item, detail_payload, now=now)
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                job_posting = detail_payload.get("jobPostingInfo")
                detail_external_url = (
                    str(job_posting.get("externalUrl") or "").strip()
                    if isinstance(job_posting, dict)
                    else ""
                )
                apply_url = detail_external_url or f"{self.site.public_root_url}{external_path}"
                fingerprint_input = "::".join(
                    (
                        self.definition.key,
                        self.site.identifier,
                        external_job_id,
                        self.site.company.casefold(),
                        title.casefold(),
                        location.casefold(),
                        apply_url.casefold(),
                    )
                )
                jobs.append(
                    NormalizedJobRecord(
                        connector_key=f"{self.definition.key}:{self.site.identifier}",
                        external_job_id=external_job_id,
                        company=self.site.company,
                        title=title,
                        location=location,
                        remote_policy=_remote_policy(title, location, description_text),
                        published_at=published_at,
                        apply_url=apply_url,
                        description_text=description_text,
                        job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                        raw_payload={"search": item, "detail": detail_payload},
                    )
                )

            next_offset = offset + len(postings)
            has_more_results = bool(total_count and next_offset < total_count)
            if not has_more_results:
                break
            if pages_scanned >= self.site.max_pages_per_run:
                inventory_complete = False
                partial_reason = "page_limit_reached"
                break
            offset = next_offset

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
