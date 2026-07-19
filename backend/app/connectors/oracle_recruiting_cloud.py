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
_DEFAULT_PAGE_SIZE = 25
_MAX_PAGES_PER_RUN = 4
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_CAREER_PATH_RE = re.compile(r"^/hcmUI/CandidateExperience/(?P<locale>[^/]+)/sites/(?P<site>[^/]+)/")


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _parse_posted_date(value: object) -> datetime | None:
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


def _country_code_from_value(value: object) -> str | None:
    normalized = str(value or "").strip().casefold()
    if not normalized:
        return None
    mapping = {
        "us": "US",
        "usa": "US",
        "united states": "US",
        "canada": "CA",
        "ca": "CA",
        "india": "IN",
        "in": "IN",
    }
    if normalized in mapping:
        return mapping[normalized]
    if len(normalized) == 2 and normalized.isalpha():
        return normalized.upper()
    return "OTHER"


def _location_text(job: dict[str, object]) -> str:
    location = str(job.get("PrimaryLocation") or "").strip()
    if location:
        return location
    country = str(job.get("PrimaryLocationCountry") or "").strip()
    if country:
        return country
    return "Unknown"


def _remote_policy(job: dict[str, object], location: str, description_text: str) -> str:
    workplace_type = str(job.get("WorkplaceType") or "").strip().casefold()
    if "hybrid" in workplace_type:
        return "Hybrid"
    if "remote" in workplace_type or "virtual" in workplace_type:
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
    job_country = _country_code_from_value(job.get("PrimaryLocationCountry"))
    if job_country is not None and job_country != "OTHER":
        return job_country == selected_country
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _description_text(job: dict[str, object], location: str) -> str:
    sections: list[str] = []
    short_description = _strip_html(str(job.get("ShortDescriptionStr") or ""))
    responsibilities = _strip_html(str(job.get("ExternalResponsibilitiesStr") or ""))
    qualifications = _strip_html(str(job.get("ExternalQualificationsStr") or ""))
    if short_description:
        sections.append(short_description)
    if responsibilities:
        sections.append(f"Responsibilities\n{responsibilities}")
    if qualifications:
        sections.append(f"Qualifications\n{qualifications}")
    metadata = [
        ("Location", location),
        ("Workplace Type", str(job.get("WorkplaceType") or "").strip()),
        ("Job Family", str(job.get("JobFamily") or "").strip()),
        ("Job Function", str(job.get("JobFunction") or "").strip()),
        ("Job Type", str(job.get("JobType") or "").strip()),
        ("Job Schedule", str(job.get("JobSchedule") or "").strip()),
    ]
    sections.extend(f"{label}: {value}" for label, value in metadata if value)
    return "\n\n".join(section for section in sections if section.strip())


def _result_container(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    items = payload.get("items")
    if not isinstance(items, list):
        return {}
    for item in items:
        if isinstance(item, dict):
            return item
    return {}


@dataclass(frozen=True)
class OracleRecruitingCloudSite:
    company: str
    identifier: str
    career_url: str
    host: str
    locale: str
    site_path: str
    site_number: str
    country: str = "US"
    role_families: tuple[str, ...] = ()
    page_size: int = _DEFAULT_PAGE_SIZE
    max_pages_per_run: int = _MAX_PAGES_PER_RUN

    @property
    def jobs_url(self) -> str:
        return f"{self.host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"

    @property
    def public_root_url(self) -> str:
        return f"{self.host}/hcmUI/CandidateExperience/{self.locale}/sites/{self.site_path}"


def build_oracle_recruiting_cloud_site(
    *,
    company: str,
    career_url: str,
    external_identifier: str = "",
    country: str = "US",
    role_families: tuple[str, ...] = (),
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_pages_per_run: int = _MAX_PAGES_PER_RUN,
) -> OracleRecruitingCloudSite:
    resolved_url = career_url.strip()
    parsed = urlsplit(resolved_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Oracle Recruiting Cloud career URL must be a valid absolute URL.")
    path_match = _CAREER_PATH_RE.match(parsed.path)
    if path_match is None:
        raise ValueError("Oracle Recruiting Cloud URL must point to a Candidate Experience site.")
    site_number = external_identifier.strip()
    if not site_number:
        raise ValueError("Oracle Recruiting Cloud configuration is missing the public site number.")
    if not re.fullmatch(r"CX_[A-Za-z0-9]+", site_number):
        raise ValueError("Oracle Recruiting Cloud site number must look like CX_12345.")
    return OracleRecruitingCloudSite(
        company=company,
        identifier=site_number,
        career_url=resolved_url,
        host=f"{parsed.scheme}://{parsed.netloc}",
        locale=path_match.group("locale"),
        site_path=path_match.group("site"),
        site_number=site_number,
        country=country,
        role_families=role_families,
        page_size=page_size,
        max_pages_per_run=max_pages_per_run,
    )


@dataclass(frozen=True)
class OracleRecruitingCloudConnector(JobConnector):
    site: OracleRecruitingCloudSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="oracle-recruiting-cloud",
        display_name="Oracle Recruiting Cloud",
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
        seen_job_ids: set[str] = set()
        last_published_cursor = cursor.last_published_at if cursor is not None else None

        for page_number in range(1, self.site.max_pages_per_run + 1):
            offset = (page_number - 1) * self.site.page_size
            payload = request_json(
                "GET",
                (
                    f"{self.site.jobs_url}"
                    f"?finder=findReqs;siteNumber={self.site.site_number},limit={self.site.page_size},offset={offset},sortBy=POSTING_DATES_DESC"
                    "&expand=requisitionList"
                ),
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
            )
            requests_made += 1
            pages_scanned += 1
            container = _result_container(payload)
            total_jobs = int(container.get("TotalJobsCount") or 0)
            if expected_pages is None:
                expected_pages = max(1, ceil(total_jobs / self.site.page_size)) if total_jobs else 1
            requisitions = container.get("requisitionList")
            if not isinstance(requisitions, list):
                requisitions = []
            if not requisitions:
                if total_jobs and page_number <= expected_pages:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break

            for job in requisitions:
                if not isinstance(job, dict):
                    continue
                external_job_id = str(job.get("Id") or "").strip()
                if not external_job_id or external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)
                title = str(job.get("Title") or "").strip()
                location = _location_text(job)
                description_text = _description_text(job, location)
                if not _matches_company_country(self.site.country, job, location, description_text):
                    continue
                published_at = _parse_posted_date(job.get("PostedDate"))
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                if last_published_cursor is not None and published_at is not None and published_at < last_published_cursor:
                    pass
                apply_url = f"{self.site.public_root_url}/job/{external_job_id}/"
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
                        remote_policy=_remote_policy(job, location, description_text),
                        published_at=published_at,
                        apply_url=apply_url,
                        description_text=description_text,
                        job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                        raw_payload={"oracle_requisition": job},
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
