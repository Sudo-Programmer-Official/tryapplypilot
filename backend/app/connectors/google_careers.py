from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
from math import ceil
import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from app.config import ConnectorSettings
from app.connectors.base import ConnectorCursor, ConnectorDefinition, ConnectorRunResult, JobConnector, NormalizedJobRecord
from app.http import HttpTlsSettings, request_text
from app.job_metadata import infer_country_code, matches_country_preference, normalize_supported_country

_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
}
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGES_PER_RUN = 10
_AF_DATA_PATTERN = re.compile(
    r"AF_initDataCallback\(\{key: 'ds:1',.*?data:(\[.*?\]), sideChannel: \{\}\}\);</script>",
    re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _parse_timestamp_pair(value: object) -> datetime | None:
    if not isinstance(value, list) or not value:
        return None
    try:
        seconds = int(value[0])
    except (TypeError, ValueError, IndexError):
        return None
    nanos = 0
    if len(value) > 1:
        try:
            nanos = int(value[1])
        except (TypeError, ValueError):
            nanos = 0
    return datetime.fromtimestamp(seconds + nanos / 1_000_000_000, tz=timezone.utc)


def _latest_timestamp(job_payload: list[object]) -> datetime | None:
    timestamps = [
        parsed
        for parsed in (
            _parse_timestamp_pair(job_payload[12] if len(job_payload) > 12 else None),
            _parse_timestamp_pair(job_payload[13] if len(job_payload) > 13 else None),
            _parse_timestamp_pair(job_payload[14] if len(job_payload) > 14 else None),
        )
        if parsed is not None
    ]
    return max(timestamps) if timestamps else None


def _remote_policy(title: str, location: str, description_text: str) -> str:
    haystack = " ".join((title, location, description_text)).casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    return "Onsite"


def _description_text(job_payload: list[object]) -> str:
    sections = []
    for index in (3, 4, 10, 15, 18, 19):
        if len(job_payload) <= index:
            continue
        section = job_payload[index]
        if isinstance(section, list) and len(section) > 1 and section[1]:
            sections.append(_strip_html(str(section[1])))
    return "\n\n".join(section for section in sections if section)


def _location_entries(job_payload: list[object]) -> list[list[object]]:
    locations = job_payload[9] if len(job_payload) > 9 else []
    if not isinstance(locations, list):
        return []
    return [entry for entry in locations if isinstance(entry, list)]


def _location_text(job_payload: list[object]) -> str:
    labels = [str(entry[0]).strip() for entry in _location_entries(job_payload) if entry and str(entry[0]).strip()]
    return "; ".join(dict.fromkeys(labels)) or "Unknown"


def _matches_company_country(company_country: str, job_payload: list[object], location: str, description_text: str) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    country_codes = {
        str(entry[5]).strip().upper()
        for entry in _location_entries(job_payload)
        if len(entry) > 5 and str(entry[5]).strip()
    }
    if country_codes:
        return selected_country in country_codes
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _extract_jobs_payload(html_text: str) -> tuple[list[list[object]], int, int]:
    match = _AF_DATA_PATTERN.search(html_text)
    if match is None:
        raise RuntimeError("Google Careers page did not include an embedded jobs payload.")
    payload = json.loads(match.group(1))
    if not isinstance(payload, list) or len(payload) < 4 or not isinstance(payload[0], list):
        raise RuntimeError("Google Careers embedded jobs payload was malformed.")
    jobs = [job for job in payload[0] if isinstance(job, list)]
    total_jobs = int(payload[2] or 0)
    page_size = int(payload[3] or _DEFAULT_PAGE_SIZE)
    return jobs, total_jobs, page_size


@dataclass(frozen=True)
class GoogleCareerSite:
    company: str
    identifier: str
    career_url: str
    country: str = "US"
    locale: str = "en_US"
    role_families: tuple[str, ...] = ()
    max_pages_per_run: int = _MAX_PAGES_PER_RUN


def build_google_career_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    max_pages_per_run: int = _MAX_PAGES_PER_RUN,
) -> GoogleCareerSite:
    resolved_url = career_url.strip() or "https://www.google.com/about/careers/applications/jobs/results/"
    parsed = urlsplit(resolved_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Google career URL must be a valid absolute URL.")
    query = parse_qs(parsed.query)
    locale = str(query.get("hl", ["en_US"])[0]).strip() or "en_US"
    return GoogleCareerSite(
        company=company,
        identifier=external_identifier.strip() or "google",
        career_url=f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        country=country,
        locale=locale,
        role_families=role_families,
        max_pages_per_run=max_pages_per_run,
    )


@dataclass(frozen=True)
class GoogleCareersJobConnector(JobConnector):
    site: GoogleCareerSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="google-careers",
        display_name="Google Careers",
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

        for page_number in range(1, self.site.max_pages_per_run + 1):
            query = {"hl": self.site.locale}
            if page_number > 1:
                query["page"] = str(page_number)
            url = f"{self.site.career_url}?{urlencode(query)}"
            html_text = request_text(
                "GET",
                url,
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
            )
            requests_made += 1
            pages_scanned += 1
            jobs_payload, total_jobs, page_size = _extract_jobs_payload(html_text)
            if expected_pages is None:
                expected_pages = max(1, ceil(total_jobs / page_size)) if total_jobs else 1

            if not jobs_payload:
                if total_jobs and page_number <= expected_pages:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break

            for job_payload in jobs_payload:
                external_job_id = str(job_payload[0]).strip() if len(job_payload) > 0 else ""
                if not external_job_id or external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)
                title = str(job_payload[1]).strip() if len(job_payload) > 1 else ""
                apply_url = str(job_payload[2]).strip() if len(job_payload) > 2 else ""
                location = _location_text(job_payload)
                description_text = _description_text(job_payload)
                if not _matches_company_country(self.site.country, job_payload, location, description_text):
                    continue
                published_at = _latest_timestamp(job_payload)
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                if last_published_cursor is not None and published_at is not None and published_at < last_published_cursor:
                    # Older records remain useful for dashboard inventory, so keep them.
                    pass
                company_name = str(job_payload[7]).strip() if len(job_payload) > 7 and str(job_payload[7]).strip() else self.site.company
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
                        remote_policy=_remote_policy(title, location, description_text),
                        published_at=published_at,
                        apply_url=apply_url,
                        description_text=description_text,
                        job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                        raw_payload={"google_job": job_payload},
                    )
                )

            if expected_pages is not None and page_number >= expected_pages:
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
