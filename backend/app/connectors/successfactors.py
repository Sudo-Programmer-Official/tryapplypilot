from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import html
from math import ceil
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

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
_DEFAULT_PAGE_SIZE = 25
_MAX_PAGES_PER_RUN = 2
_MAX_DETAIL_REQUESTS_PER_RUN = 30
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_RESULTS_RE = re.compile(
    r"Results\s+\d+\s*[–-]\s*\d+\s+of\s+(?P<total>\d+)\s+Page\s+\d+\s+of\s+(?P<pages>\d+)",
    re.I,
)
_DETAIL_ID_RE = re.compile(r"/job/[^/]+/(?P<id>\d+)/?$")
_APPLY_RE = re.compile(r'<a[^>]+href="([^"]*talentcommunity/apply/[^"]+)"[^>]*>\s*Apply now', re.I)
_POSTED_DATE_RE = re.compile(r"Posted Date:\s*(?P<date>[A-Za-z]{3}\s+\d{1,2},\s+\d{4})", re.I)
_LOCATION_RE = re.compile(
    r"Location:\s*(?P<location>.+?)\s*(?:Job alert|share|Job Segment:|Requisition ID:|$)",
    re.I,
)
_DETAIL_END_MARKERS = ("Find similar jobs:", "Job Segment:", "Quick links")


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _parse_posted_date(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%b %d, %Y")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _remote_policy(location: str, description_text: str) -> str:
    haystack = " ".join((location, description_text)).casefold()
    if "#li-hybrid" in haystack or "hybrid" in haystack:
        return "Hybrid"
    if "#li-remote" in haystack or "remote" in haystack:
        return "Remote"
    return "Onsite"


def _matches_company_country(company_country: str, location: str, description_text: str) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _extract_detail_job_id(url: str) -> str:
    match = _DETAIL_ID_RE.search(urlsplit(url).path)
    return match.group("id") if match is not None else ""


def _detail_description_text(detail_html: str, title: str) -> str:
    detail_text = _strip_html(detail_html)
    if title and title in detail_text:
        detail_text = detail_text[detail_text.index(title) :]
    for marker in _DETAIL_END_MARKERS:
        marker_index = detail_text.find(marker)
        if marker_index > 0:
            detail_text = detail_text[:marker_index].strip()
            break
    return detail_text


class _SuccessFactorsSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jobs: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_title_buffer: list[str] = []
        self._pending_job: dict[str, str] | None = None
        self._seen_hrefs: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag == "a":
            href = attributes.get("href", "")
            if "/job/" in href:
                self._current_href = href
                self._current_title_buffer = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_title_buffer.append(data)
            return
        if self._pending_job is None:
            return
        candidate = _WHITESPACE_RE.sub(" ", data).strip()
        if not candidate:
            return
        if candidate == self._pending_job["title"]:
            return
        if "," not in candidate and "Remote" not in candidate:
            return
        job = {
            "href": self._pending_job["href"],
            "title": self._pending_job["title"],
            "location": candidate,
        }
        self.jobs.append(job)
        self._seen_hrefs.add(job["href"])
        self._pending_job = None

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        title = _WHITESPACE_RE.sub(" ", "".join(self._current_title_buffer)).strip()
        href = self._current_href
        if href not in self._seen_hrefs and title:
            self._pending_job = {"href": href, "title": title}
        self._current_href = None
        self._current_title_buffer = []


def _extract_jobs(html_text: str) -> list[dict[str, str]]:
    parser = _SuccessFactorsSearchParser()
    parser.feed(html_text)
    parser.close()
    deduped: dict[str, dict[str, str]] = {}
    for job in parser.jobs:
        deduped.setdefault(job["href"], job)
    return list(deduped.values())


@dataclass(frozen=True)
class SuccessFactorsSite:
    company: str
    identifier: str
    career_url: str
    root_url: str
    locale: str = "en_US"
    country: str = "US"
    role_families: tuple[str, ...] = ()
    page_size: int = _DEFAULT_PAGE_SIZE
    max_pages_per_run: int = _MAX_PAGES_PER_RUN
    max_detail_requests_per_run: int = _MAX_DETAIL_REQUESTS_PER_RUN
    extra_query: tuple[tuple[str, str], ...] = ()


def build_successfactors_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_pages_per_run: int = _MAX_PAGES_PER_RUN,
    max_detail_requests_per_run: int = _MAX_DETAIL_REQUESTS_PER_RUN,
) -> SuccessFactorsSite:
    resolved_url = career_url.strip()
    parsed = urlsplit(resolved_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("SuccessFactors career URL must be a valid absolute URL.")
    query_pairs = tuple(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key not in {"q", "sortColumn", "sortDirection", "startrow"}
    )
    locale = "en_US"
    for key, value in query_pairs:
        if key == "locale" and value.strip():
            locale = value.strip()
            break
    return SuccessFactorsSite(
        company=company,
        identifier=external_identifier.strip() or (parsed.hostname or parsed.netloc),
        career_url=f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        root_url=f"{parsed.scheme}://{parsed.netloc}",
        locale=locale,
        country=country,
        role_families=role_families,
        page_size=page_size,
        max_pages_per_run=max_pages_per_run,
        max_detail_requests_per_run=max_detail_requests_per_run,
        extra_query=query_pairs,
    )


@dataclass(frozen=True)
class SuccessFactorsJobConnector(JobConnector):
    site: SuccessFactorsSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="successfactors",
        display_name="SuccessFactors",
        layer="official_ats",
        admin_status="beta",
        rollout_stage="next",
        pagination_mode="page",
        supports_incremental_sync=True,
        rate_limit_per_minute=8,
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
        last_published_cursor = cursor.last_published_at if cursor is not None else None

        for page_number in range(1, self.site.max_pages_per_run + 1):
            query = dict(self.site.extra_query)
            query.update(
                {
                    "q": "",
                    "sortColumn": "referencedate",
                    "sortDirection": "desc",
                    "startrow": str((page_number - 1) * self.site.page_size),
                }
            )
            html_text = request_text(
                "GET",
                f"{self.site.career_url}?{urlencode(query)}",
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
            )
            requests_made += 1
            pages_scanned += 1
            page_jobs = _extract_jobs(html_text)
            results_match = _RESULTS_RE.search(_strip_html(html_text))
            total_jobs = int(results_match.group("total")) if results_match is not None else 0
            if expected_pages is None:
                parsed_pages = int(results_match.group("pages")) if results_match is not None else 0
                expected_pages = parsed_pages or (max(1, ceil(total_jobs / self.site.page_size)) if total_jobs else 1)
            if not page_jobs:
                if total_jobs and page_number <= expected_pages:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break

            for page_job in page_jobs:
                detail_url = urljoin(self.site.root_url, page_job["href"])
                external_job_id = _extract_detail_job_id(detail_url)
                if not external_job_id or external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)
                title = page_job["title"]
                listing_location = page_job["location"]
                detail_html = ""
                if detail_requests_made < self.site.max_detail_requests_per_run:
                    detail_html = request_text(
                        "GET",
                        detail_url,
                        timeout_seconds=self.connector_settings.request_timeout_seconds,
                        tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                        headers=_BROWSER_HEADERS,
                    )
                    requests_made += 1
                    detail_requests_made += 1
                description_text = _detail_description_text(detail_html, title) if detail_html else f"{title}\n\nLocation: {listing_location}"
                location_match = _LOCATION_RE.search(description_text) if detail_html else None
                location = location_match.group("location").strip() if location_match is not None else listing_location
                if not _matches_company_country(self.site.country, location, description_text):
                    continue
                posted_at_match = _POSTED_DATE_RE.search(description_text) if detail_html else None
                published_at = _parse_posted_date(posted_at_match.group("date")) if posted_at_match is not None else None
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                if last_published_cursor is not None and published_at is not None and published_at < last_published_cursor:
                    pass
                apply_url_match = _APPLY_RE.search(detail_html) if detail_html else None
                if apply_url_match is not None:
                    apply_url = urljoin(self.site.root_url, apply_url_match.group(1))
                else:
                    apply_url = detail_url
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
                        remote_policy=_remote_policy(location, description_text),
                        published_at=published_at,
                        apply_url=apply_url,
                        description_text=description_text,
                        job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                        raw_payload={
                            "successfactors_listing": page_job,
                            "successfactors_detail_url": detail_url,
                        },
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
