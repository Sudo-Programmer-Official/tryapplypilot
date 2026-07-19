from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
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
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGES_PER_RUN = 5
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+$")


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _location_text(job: dict[str, object]) -> str:
    location_name = str(job.get("location_name") or "").strip()
    if location_name:
        return location_name
    full_location = str(job.get("full_location") or "").strip()
    if full_location:
        return full_location
    short_location = str(job.get("short_location") or "").strip()
    if short_location:
        return short_location
    country = str(job.get("country") or "").strip()
    if country:
        return country
    return "Unknown"


def _category_labels(job: dict[str, object]) -> list[str]:
    labels = [
        str(item.get("name") or "").strip()
        for item in job.get("categories", [])
        if isinstance(item, dict)
    ] if isinstance(job.get("categories"), list) else []
    if labels:
        return labels
    return _string_list(job.get("category"))


def _remote_policy(job: dict[str, object], location: str, description_text: str) -> str:
    tags = {tag.casefold() for tag in _string_list(job.get("tags2"))}
    if "hybrid" in tags:
        return "Hybrid"
    if "remote" in tags:
        return "Remote"
    haystack = " ".join((location, description_text)).casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    return "Onsite"


def _matches_company_country(company_country: str, job: dict[str, object], location: str, description_text: str) -> bool:
    selected_country = normalize_supported_country(company_country)
    if selected_country == "ANY":
        return True
    country_code = str(job.get("country_code") or "").strip().upper()
    if country_code in {"US", "CA", "IN"}:
        return country_code == selected_country
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _description_text(job: dict[str, object], location: str, remote_policy: str) -> str:
    sections: list[str] = []
    description = _strip_html(str(job.get("description") or ""))
    if description:
        sections.append(description)
    responsibilities = _strip_html(str(job.get("responsibilities") or ""))
    if responsibilities:
        sections.append(f"Responsibilities\n{responsibilities}")
    qualifications = _strip_html(str(job.get("qualifications") or ""))
    if qualifications:
        sections.append(f"Qualifications\n{qualifications}")
    categories = ", ".join(_category_labels(job))
    employment_type = str(job.get("employment_type") or "").strip().replace("_", " ").title()
    if location:
        sections.append(f"Location: {location}")
    if remote_policy:
        sections.append(f"Remote Policy: {remote_policy}")
    if categories:
        sections.append(f"Categories: {categories}")
    if employment_type:
        sections.append(f"Employment Type: {employment_type}")
    return "\n\n".join(section for section in sections if section.strip())


@dataclass(frozen=True)
class ICIMSCareerSite:
    company: str
    identifier: str
    career_url: str
    root_url: str
    country: str = "US"
    role_families: tuple[str, ...] = ()
    page_size: int = _DEFAULT_PAGE_SIZE
    max_pages_per_run: int = _MAX_PAGES_PER_RUN
    extra_query: tuple[tuple[str, str], ...] = ()

    @property
    def jobs_url(self) -> str:
        return f"{self.root_url}/api/jobs"


def build_icims_career_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_pages_per_run: int = _MAX_PAGES_PER_RUN,
) -> ICIMSCareerSite:
    resolved_source = career_url.strip() or external_identifier.strip()
    if not resolved_source:
        raise ValueError("iCIMS company configuration is missing the career URL or site identifier.")
    if "://" not in resolved_source:
        if not _HOST_RE.fullmatch(resolved_source):
            raise ValueError("iCIMS site identifier must be a valid host name.")
        resolved_source = f"https://{resolved_source}"
    parsed = urlsplit(resolved_source)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("iCIMS career URL must be a valid absolute URL.")
    query_pairs = tuple(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key not in {"page", "limit", "sortBy", "descending"}
    )
    return ICIMSCareerSite(
        company=company,
        identifier=external_identifier.strip() or (parsed.hostname or parsed.netloc),
        career_url=resolved_source,
        root_url=f"{parsed.scheme}://{parsed.netloc}",
        country=country,
        role_families=role_families,
        page_size=page_size,
        max_pages_per_run=max_pages_per_run,
        extra_query=query_pairs,
    )


@dataclass(frozen=True)
class ICIMSJobConnector(JobConnector):
    site: ICIMSCareerSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="icims",
        display_name="iCIMS",
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
        last_published_cursor = cursor.last_published_at if cursor is not None else None

        for page_number in range(1, self.site.max_pages_per_run + 1):
            query = dict(self.site.extra_query)
            query.update(
                {
                    "page": str(page_number),
                    "limit": str(self.site.page_size),
                    "sortBy": "posted_date",
                    "descending": "true",
                }
            )
            payload = request_json(
                "GET",
                f"{self.site.jobs_url}?{urlencode(query)}",
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
            )
            requests_made += 1
            pages_scanned += 1
            if not isinstance(payload, dict):
                raise RuntimeError("iCIMS returned an unexpected payload.")
            raw_jobs = payload.get("jobs")
            if not isinstance(raw_jobs, list):
                raise RuntimeError("iCIMS response did not include a jobs list.")
            total_count = int(payload.get("totalCount") or 0)
            if expected_pages is None:
                expected_pages = max(1, ceil(total_count / self.site.page_size)) if total_count else 1
            if not raw_jobs:
                if total_count and page_number <= expected_pages:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break

            for row in raw_jobs:
                if not isinstance(row, dict):
                    continue
                job = row.get("data") if isinstance(row.get("data"), dict) else row
                if not isinstance(job, dict):
                    continue
                external_job_id = str(job.get("slug") or job.get("req_id") or "").strip()
                if not external_job_id or external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)
                location = _location_text(job)
                remote_policy = _remote_policy(job, location, "")
                description_text = _description_text(job, location, remote_policy)
                if not _matches_company_country(self.site.country, job, location, description_text):
                    continue
                published_at = _parse_datetime(job.get("posted_date")) or _parse_datetime(job.get("update_date"))
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                if last_published_cursor is not None and published_at is not None and published_at < last_published_cursor:
                    pass
                title = str(job.get("title") or "").strip()
                apply_url = str(job.get("apply_url") or "").strip()
                if not apply_url:
                    canonical_url = (
                        str(((job.get("meta_data") or {}) if isinstance(job.get("meta_data"), dict) else {}).get("canonical_url") or "")
                        .strip()
                    )
                    if canonical_url:
                        apply_url = canonical_url
                if not apply_url:
                    apply_url = f"{self.site.root_url}/jobs/{external_job_id}"
                company_name = self.site.company
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
                        raw_payload={"icims_job": job},
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
