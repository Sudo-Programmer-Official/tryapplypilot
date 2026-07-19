from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import html
import json
import re
from urllib.parse import urljoin, urlsplit

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
_DEFAULT_MAX_DETAIL_REQUESTS_PER_RUN = 40
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9-]+$")
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_JOB_ID_RE = re.compile(r"/job/([^/?#]+)")
_JOB_POSTING_JSON_LD_RE = re.compile(
    r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
    re.S | re.I,
)
_APPLY_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*jv-button-apply[^"]*"[^>]+href="([^"]+)"',
    re.I,
)


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            parsed = datetime.fromisoformat(f"{text}T00:00:00+00:00")
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _remote_policy(location: str, description_text: str) -> str:
    haystack = " ".join((location, description_text)).casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    return "Onsite"


def _matches_company_country(company_country: str, location: str, description_text: str) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _description_text(category: str, location: str, detail_description: str) -> str:
    sections: list[str] = []
    if detail_description:
        sections.append(detail_description)
    if category:
        sections.append(f"Category: {category}")
    if location:
        sections.append(f"Location: {location}")
    return "\n\n".join(section for section in sections if section.strip())


def _extract_job_posting_payload(detail_html: str) -> dict[str, object]:
    for match in _JOB_POSTING_JSON_LD_RE.finditer(detail_html):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and str(payload.get("@type") or "").strip() == "JobPosting":
            return payload
    return {}


def _extract_apply_url(detail_html: str, site_identifier: str, external_job_id: str) -> str:
    match = _APPLY_LINK_RE.search(detail_html)
    if match is not None:
        return urljoin("https://jobs.jobvite.com", match.group(1))
    return urljoin("https://jobs.jobvite.com", f"/{site_identifier}/job/{external_job_id}/apply")


class _JobviteListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.jobs: list[dict[str, str]] = []
        self._pending_category = ""
        self._current_table_category = ""
        self._heading_buffer: list[str] = []
        self._row: dict[str, str] | None = None
        self._field: str | None = None
        self._in_heading = False
        self._in_job_table = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        classes = attributes.get("class", "")
        if tag == "h3" and "h2" in classes:
            self._in_heading = True
            self._heading_buffer = []
            return
        if tag == "table" and "jv-job-list" in classes:
            self._in_job_table = True
            self._current_table_category = self._pending_category
            return
        if not self._in_job_table:
            return
        if tag == "tr":
            self._row = {"category": self._current_table_category}
            return
        if self._row is None:
            return
        if tag == "td" and "jv-job-list-name" in classes:
            self._field = "title"
            return
        if tag == "td" and "jv-job-list-location" in classes:
            self._field = "location"
            return
        if tag == "a" and self._field == "title":
            self._row["href"] = attributes.get("href", "")

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_buffer.append(data)
            return
        if self._row is None or self._field is None:
            return
        self._row[self._field] = f"{self._row.get(self._field, '')}{data}"

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3" and self._in_heading:
            self._in_heading = False
            self._pending_category = _WHITESPACE_RE.sub(" ", "".join(self._heading_buffer)).strip()
            self._heading_buffer = []
            return
        if tag == "table" and self._in_job_table:
            self._in_job_table = False
            self._current_table_category = ""
            return
        if tag == "td":
            self._field = None
            return
        if tag == "tr" and self._row is not None:
            href = self._row.get("href", "").strip()
            title = _WHITESPACE_RE.sub(" ", self._row.get("title", "")).strip()
            location = _WHITESPACE_RE.sub(" ", self._row.get("location", "")).strip()
            if href and title:
                self.jobs.append(
                    {
                        "href": href,
                        "title": title,
                        "location": location or "Unknown",
                        "category": self._row.get("category", "").strip(),
                    }
                )
            self._row = None


def _extract_list_jobs(html_text: str) -> list[dict[str, str]]:
    parser = _JobviteListParser()
    parser.feed(html_text)
    parser.close()
    return parser.jobs


@dataclass(frozen=True)
class JobviteSite:
    company: str
    identifier: str
    career_url: str
    country: str = "US"
    role_families: tuple[str, ...] = ()
    max_detail_requests_per_run: int = _DEFAULT_MAX_DETAIL_REQUESTS_PER_RUN


def build_jobvite_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    max_detail_requests_per_run: int = _DEFAULT_MAX_DETAIL_REQUESTS_PER_RUN,
) -> JobviteSite:
    resolved_identifier = external_identifier.strip()
    resolved_url = career_url.strip()
    if resolved_url:
        parsed = urlsplit(resolved_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Jobvite career URL must be a valid absolute URL.")
        if "jobvite.com" in parsed.netloc.casefold() and not resolved_identifier:
            path_segments = [segment for segment in parsed.path.split("/") if segment]
            if path_segments[:1] == ["careers"] and len(path_segments) > 1:
                resolved_identifier = path_segments[1]
            elif path_segments:
                resolved_identifier = path_segments[0]
    if not resolved_identifier:
        raise ValueError("Jobvite company configuration is missing the board identifier.")
    if not _IDENTIFIER_RE.fullmatch(resolved_identifier):
        raise ValueError("Jobvite board identifier is invalid.")
    canonical_career_url = f"https://jobs.jobvite.com/careers/{resolved_identifier}/jobs"
    return JobviteSite(
        company=company,
        identifier=resolved_identifier,
        career_url=canonical_career_url,
        country=country,
        role_families=role_families,
        max_detail_requests_per_run=max_detail_requests_per_run,
    )


@dataclass(frozen=True)
class JobviteJobConnector(JobConnector):
    site: JobviteSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="jobvite",
        display_name="Jobvite",
        layer="official_ats",
        admin_status="beta",
        rollout_stage="next",
        pagination_mode="none",
        supports_incremental_sync=False,
        rate_limit_per_minute=8,
    )

    def collect(self, cursor: ConnectorCursor | None = None) -> ConnectorRunResult:
        list_html = request_text(
            "GET",
            self.site.career_url,
            timeout_seconds=self.connector_settings.request_timeout_seconds,
            tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
            headers=_BROWSER_HEADERS,
        )
        requests_made = 1
        jobs: list[NormalizedJobRecord] = []
        latest_seen_at: datetime | None = None
        seen_job_ids: set[str] = set()
        detail_requests_made = 0

        for row in _extract_list_jobs(list_html):
            href_match = _JOB_ID_RE.search(row.get("href", ""))
            if href_match is None:
                continue
            external_job_id = href_match.group(1).strip()
            if not external_job_id or external_job_id in seen_job_ids:
                continue
            seen_job_ids.add(external_job_id)
            detail_url = urljoin("https://jobs.jobvite.com", row["href"])
            apply_url = urljoin("https://jobs.jobvite.com", f"/{self.site.identifier}/job/{external_job_id}/apply")
            detail_description = ""
            detail_payload: dict[str, object] = {}
            published_at: datetime | None = None
            category = row.get("category", "").strip()

            if detail_requests_made < self.site.max_detail_requests_per_run:
                requests_made += 1
                detail_requests_made += 1
                try:
                    detail_html = request_text(
                        "GET",
                        detail_url,
                        timeout_seconds=self.connector_settings.request_timeout_seconds,
                        tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                        headers=_BROWSER_HEADERS,
                    )
                    detail_payload = _extract_job_posting_payload(detail_html)
                    detail_description = _strip_html(str(detail_payload.get("description") or ""))
                    published_at = _parse_datetime(detail_payload.get("datePosted"))
                    if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                        latest_seen_at = published_at
                    category = str(detail_payload.get("industry") or "").strip() or category
                    apply_url = _extract_apply_url(detail_html, self.site.identifier, external_job_id)
                except Exception:  # noqa: BLE001
                    pass

            location = row.get("location", "Unknown").strip() or "Unknown"
            description_text = _description_text(category, location, detail_description)
            if not _matches_company_country(self.site.country, location, description_text):
                continue
            title = row.get("title", "").strip()
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
                        "jobvite_listing": row,
                        "jobvite_detail": detail_payload,
                        "detail_url": detail_url,
                    },
                )
            )

        jobs.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return ConnectorRunResult(
            jobs=jobs,
            next_cursor=ConnectorCursor(cursor=None, last_published_at=latest_seen_at),
            exhausted=True,
            requests_made=requests_made,
            pages_scanned=1,
            expected_pages=1,
            partial_reason=None,
        )
