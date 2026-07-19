from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
_DEFAULT_PAGE_SIZE = 100
_MAX_PAGES_PER_RUN = 5
_MAX_DETAIL_REQUESTS_PER_RUN = 12
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _remote_policy(item: dict[str, object]) -> str:
    location = item.get("location")
    if isinstance(location, dict):
        if bool(location.get("hybrid")):
            return "Hybrid"
        if bool(location.get("remote")):
            return "Remote"
    return "Onsite"


def _location_text(item: dict[str, object]) -> str:
    location = item.get("location")
    if isinstance(location, dict):
        full_location = str(location.get("fullLocation") or "").strip()
        if full_location:
            return full_location
        city = str(location.get("city") or "").strip()
        country = str(location.get("country") or "").strip()
        if city and country:
            return f"{city}, {country.upper()}"
        if city:
            return city
    return "Unknown"


def _country_from_item(item: dict[str, object]) -> str | None:
    location = item.get("location")
    if isinstance(location, dict):
        country = str(location.get("country") or "").strip()
        if country:
            return country.upper()
    for field in item.get("customField") if isinstance(item.get("customField"), list) else []:
        if not isinstance(field, dict):
            continue
        field_label = str(field.get("fieldLabel") or "").strip().casefold()
        if field_label in {"country", "country/region"}:
            value = str(field.get("valueId") or field.get("valueLabel") or "").strip()
            if value:
                return value.upper()
    return None


def _matches_company_country(company_country: str, item: dict[str, object], location: str, description_text: str) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    country = _country_from_item(item)
    if country:
        if country in {"US", "CA", "IN"}:
            return country == selected_country
        if country in {"USA", "CAN", "IND"}:
            return {"USA": "US", "CAN": "CA", "IND": "IN"}[country] == selected_country
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _description_text(detail_payload: dict[str, object], location: str, remote_policy: str) -> str:
    job_ad = detail_payload.get("jobAd")
    sections = {}
    if isinstance(job_ad, dict):
        sections = job_ad.get("sections") if isinstance(job_ad.get("sections"), dict) else {}
    content_parts: list[str] = []
    for section_key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"):
        section = sections.get(section_key)
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        text = _strip_html(str(section.get("text") or ""))
        if title and text:
            content_parts.append(f"{title}\n{text}")
        elif text:
            content_parts.append(text)
    content_parts.append(f"Location: {location}")
    content_parts.append(f"Remote Policy: {remote_policy}")
    return "\n\n".join(part for part in content_parts if part.strip())


@dataclass(frozen=True)
class SmartRecruitersSite:
    company: str
    identifier: str
    career_url: str
    country: str = "US"
    role_families: tuple[str, ...] = ()
    page_size: int = _DEFAULT_PAGE_SIZE
    max_pages_per_run: int = _MAX_PAGES_PER_RUN
    max_detail_requests_per_run: int = _MAX_DETAIL_REQUESTS_PER_RUN

    @property
    def postings_url(self) -> str:
        return f"https://api.smartrecruiters.com/v1/companies/{self.identifier}/postings"


def build_smartrecruiters_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_pages_per_run: int = _MAX_PAGES_PER_RUN,
    max_detail_requests_per_run: int = _MAX_DETAIL_REQUESTS_PER_RUN,
) -> SmartRecruitersSite:
    identifier = external_identifier.strip()
    resolved_url = career_url.strip()
    if not identifier and resolved_url:
        parsed = urlsplit(resolved_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("SmartRecruiters career URL must be a valid absolute URL.")
        if "smartrecruiters.com" not in parsed.netloc.casefold():
            raise ValueError("SmartRecruiters career URL must point to a smartrecruiters.com host.")
        path_segments = [segment for segment in parsed.path.split("/") if segment]
        if not path_segments:
            raise ValueError("SmartRecruiters career URL is missing the company identifier.")
        identifier = path_segments[0]
    if not identifier:
        raise ValueError("SmartRecruiters company configuration is missing the company identifier.")
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError("SmartRecruiters company identifier is invalid.")
    if not resolved_url:
        resolved_url = f"https://careers.smartrecruiters.com/{identifier}"
    return SmartRecruitersSite(
        company=company,
        identifier=identifier,
        career_url=resolved_url,
        country=country,
        role_families=role_families,
        page_size=page_size,
        max_pages_per_run=max_pages_per_run,
        max_detail_requests_per_run=max_detail_requests_per_run,
    )


@dataclass(frozen=True)
class SmartRecruitersJobConnector(JobConnector):
    site: SmartRecruitersSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="smartrecruiters",
        display_name="SmartRecruiters",
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
        seen_job_ids: set[str] = set()
        detail_requests_made = 0
        last_published_cursor = cursor.last_published_at if cursor is not None else None

        for page_index in range(self.site.max_pages_per_run):
            offset = page_index * self.site.page_size
            payload = request_json(
                "GET",
                f"{self.site.postings_url}?limit={self.site.page_size}&offset={offset}",
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
            )
            requests_made += 1
            pages_scanned += 1
            if not isinstance(payload, dict):
                raise RuntimeError("SmartRecruiters returned an unexpected payload.")
            postings = payload.get("content")
            if not isinstance(postings, list):
                raise RuntimeError("SmartRecruiters response did not include a postings list.")
            total_found = int(payload.get("totalFound") or 0)
            if expected_pages is None:
                expected_pages = max(1, ceil(total_found / self.site.page_size)) if total_found else 1
            if not postings:
                if total_found and page_index + 1 <= expected_pages:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break

            for item in postings:
                if not isinstance(item, dict):
                    continue
                external_job_id = str(item.get("id") or item.get("uuid") or "").strip()
                if not external_job_id or external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)
                location = _location_text(item)
                remote_policy = _remote_policy(item)
                detail_payload: dict[str, object] = {}
                published_at = _parse_datetime(item.get("releasedDate"))
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                should_fetch_detail = detail_requests_made < self.site.max_detail_requests_per_run
                if should_fetch_detail and last_published_cursor is not None and published_at is not None:
                    should_fetch_detail = published_at >= last_published_cursor
                if should_fetch_detail:
                    detail_response = request_json(
                        "GET",
                        f"{self.site.postings_url}/{external_job_id}",
                        timeout_seconds=self.connector_settings.request_timeout_seconds,
                        tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                        headers=_BROWSER_HEADERS,
                    )
                    requests_made += 1
                    detail_requests_made += 1
                    if isinstance(detail_response, dict):
                        detail_payload = detail_response
                description_text = _description_text(detail_payload, location, remote_policy)
                if not _matches_company_country(self.site.country, item, location, description_text):
                    continue
                apply_url = str(detail_payload.get("applyUrl") or item.get("ref") or "").strip()
                if not apply_url:
                    apply_url = str(detail_payload.get("postingUrl") or "").strip()
                if not apply_url:
                    apply_url = f"https://jobs.smartrecruiters.com/{self.site.identifier}/{external_job_id}"
                title = str(item.get("name") or "").strip()
                company_name = (
                    str((item.get("company") or {}).get("name") or "").strip()
                    if isinstance(item.get("company"), dict)
                    else ""
                ) or self.site.company
                fingerprint_input = "::".join(
                    (
                        self.definition.key,
                        self.site.identifier,
                        external_job_id,
                        company_name.casefold(),
                        title.casefold(),
                        location.casefold(),
                        apply_url.casefold(),
                    )
                )
                jobs.append(
                    NormalizedJobRecord(
                        connector_key=f"{self.definition.key}:{self.site.identifier}",
                        external_job_id=external_job_id,
                        company=company_name,
                        title=title,
                        location=location,
                        remote_policy=remote_policy,
                        published_at=published_at,
                        apply_url=apply_url,
                        description_text=description_text,
                        job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                        raw_payload={"smartrecruiters_job": item, "smartrecruiters_detail": detail_payload},
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
