from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
from math import ceil
import re
from urllib.parse import urlencode

from app.config import ConnectorSettings
from app.connectors.base import ConnectorCursor, ConnectorDefinition, ConnectorRunResult, JobConnector, NormalizedJobRecord
from app.http import HttpTlsSettings, request_json
from app.job_metadata import country_label, infer_country_code, matches_country_preference, normalize_supported_country

_BROWSER_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
}
_DEFAULT_PAGE_SIZE = 10
_MAX_PAGES_PER_RUN = 15
_MAX_DETAIL_REQUESTS_PER_RUN = 10
_ENGINEERING_ROLE_FAMILIES = frozenset(
    {
        "backend engineering",
        "distributed systems",
        "platform engineering",
        "cloud infrastructure",
        "infrastructure",
        "ai platform",
        "ai infrastructure",
        "machine learning platform",
        "developer experience",
        "reliability",
    }
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _parse_timestamp(value: object) -> datetime | None:
    if value in {None, ""}:
        return None
    try:
        raw_value = int(value)
    except (TypeError, ValueError):
        return None
    if raw_value > 10_000_000_000:
        raw_value //= 1000
    return datetime.fromtimestamp(raw_value, tz=timezone.utc)


def _remote_policy(work_location_option: str, location_flexibility: str | None, location: str) -> str:
    normalized_option = work_location_option.strip().casefold()
    normalized_flexibility = (location_flexibility or "").strip().casefold()
    haystack = f" {normalized_option} {normalized_flexibility} {location.casefold()} "
    if "remote" in haystack:
        return "Remote"
    if "hybrid" in haystack or "days / week in-office" in haystack:
        return "Hybrid"
    return "Onsite"


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _matches_company_country(
    company_country: str,
    standardized_locations: object,
    location: str,
    description_text: str,
) -> bool:
    selected_country = normalize_supported_country(company_country)
    if isinstance(standardized_locations, list):
        normalized_locations = {str(item).strip().upper() for item in standardized_locations if str(item).strip()}
        if selected_country == "ANY":
            return True
        if normalized_locations:
            return selected_country in normalized_locations
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


def _build_query_params(site: "MicrosoftCareerSite", start: int) -> str:
    params: list[tuple[str, str]] = [("domain", site.domain)]
    selected_country = normalize_supported_country(site.country)
    if selected_country != "ANY":
        params.append(("location", country_label(selected_country)))
    if start > 0:
        params.append(("start", str(start)))
    if any(role_family.casefold() in _ENGINEERING_ROLE_FAMILIES for role_family in site.role_families):
        params.append(("filter_career_discipline", "Software Engineering"))
    return urlencode(params)


def _build_detail_query_params(site: "MicrosoftCareerSite", position_id: str) -> str:
    return urlencode((("domain", site.domain), ("position_id", position_id)))


def _extract_detail_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    detail_payload = payload.get("data")
    if isinstance(detail_payload, dict):
        return detail_payload
    return payload


def _normalize_apply_url(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return ""
    if normalized.startswith("http"):
        return normalized
    return f"https://apply.careers.microsoft.com{normalized}"


def _description_text(item: dict[str, object], detail_payload: dict[str, object], location: str) -> str:
    detailed_description = _strip_html(str(detail_payload.get("jobDescription") or detail_payload.get("description") or ""))
    description_parts = [
        detailed_description,
        f"Department: {str(item.get('department', '')).strip()}",
        f"Location: {location}",
        f"Work location option: {str(item.get('workLocationOption', '')).strip()}",
        f"Location flexibility: {str(item.get('locationFlexibility', '')).strip()}",
        f"Display job id: {str(item.get('displayJobId', '')).strip()}",
        f"ATS job id: {str(item.get('atsJobId', '')).strip()}",
    ]
    return "\n".join(part for part in description_parts if part and (":" not in part or part.split(":", 1)[1].strip()))


def _request_position_detail(
    site: "MicrosoftCareerSite",
    position_id: str,
    connector_settings: ConnectorSettings,
) -> dict[str, object]:
    payload = request_json(
        "GET",
        f"https://apply.careers.microsoft.com/api/pcsx/position_details?{_build_detail_query_params(site, position_id)}",
        timeout_seconds=connector_settings.request_timeout_seconds,
        tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
        headers=_BROWSER_HEADERS,
    )
    return _extract_detail_payload(payload)


@dataclass(frozen=True)
class MicrosoftCareerSite:
    company: str
    domain: str
    country: str = "US"
    role_families: tuple[str, ...] = ()
    max_pages_per_run: int = _MAX_PAGES_PER_RUN
    max_detail_requests_per_run: int = _MAX_DETAIL_REQUESTS_PER_RUN


@dataclass(frozen=True)
class MicrosoftCareersJobConnector(JobConnector):
    site: MicrosoftCareerSite
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="microsoft-careers",
        display_name="Microsoft Careers",
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
        start = 0
        pages_scanned = 0
        expected_pages: int | None = None
        inventory_complete = True
        partial_reason: str | None = None
        seen_job_ids: set[str] = set()
        detail_requests_made = 0
        last_published_cursor = cursor.last_published_at if cursor is not None else None

        while True:
            payload = request_json(
                "GET",
                f"https://apply.careers.microsoft.com/api/pcsx/search?{_build_query_params(self.site, start)}",
                timeout_seconds=self.connector_settings.request_timeout_seconds,
                tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
                headers=_BROWSER_HEADERS,
            )
            requests_made += 1
            pages_scanned += 1
            if not isinstance(payload, dict):
                raise RuntimeError("Microsoft Careers returned an unexpected payload.")
            data = payload.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("Microsoft Careers response did not include a data object.")

            positions = data.get("positions", [])
            if not isinstance(positions, list):
                positions = []
            total_count = int(data.get("count") or 0)
            if expected_pages is None:
                expected_pages = max(1, ceil(total_count / _DEFAULT_PAGE_SIZE)) if total_count else 1

            for item in positions:
                if not isinstance(item, dict):
                    continue
                external_job_id = str(item.get("id", "")).strip()
                if not external_job_id or external_job_id in seen_job_ids:
                    continue
                seen_job_ids.add(external_job_id)
                title = str(item.get("name", "")).strip()
                locations = item.get("locations") if isinstance(item.get("locations"), list) else []
                location = "; ".join(str(entry).strip() for entry in locations if str(entry).strip()) or "Unknown"
                published_at = _parse_timestamp(item.get("postedTs") or item.get("creationTs"))
                if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                    latest_seen_at = published_at
                detail_payload: dict[str, object] = {}
                should_fetch_detail = detail_requests_made < self.site.max_detail_requests_per_run
                if should_fetch_detail and last_published_cursor is not None and published_at is not None:
                    should_fetch_detail = published_at >= last_published_cursor
                if should_fetch_detail:
                    try:
                        detail_payload = _request_position_detail(self.site, external_job_id, self.connector_settings)
                    except Exception:  # noqa: BLE001
                        detail_payload = {}
                    finally:
                        requests_made += 1
                        detail_requests_made += 1
                apply_url = _normalize_apply_url(
                    str(detail_payload.get("publicUrl") or detail_payload.get("positionUrl") or item.get("positionUrl") or "")
                )
                description_text = _description_text(item, detail_payload, location)
                if not _matches_company_country(
                    self.site.country,
                    item.get("standardizedLocations"),
                    location,
                    description_text,
                ):
                    continue
                fingerprint_input = "::".join(
                    (
                        self.definition.key,
                        self.site.domain,
                        external_job_id,
                        self.site.company.casefold(),
                        title.casefold(),
                        location.casefold(),
                        apply_url.casefold(),
                    )
                )
                jobs.append(
                    NormalizedJobRecord(
                        connector_key=f"{self.definition.key}:{self.site.domain}",
                        external_job_id=external_job_id,
                        company=self.site.company,
                        title=title,
                        location=location,
                        remote_policy=_remote_policy(
                            str(item.get("workLocationOption") or ""),
                            (
                                str(item.get("locationFlexibility")).strip()
                                if item.get("locationFlexibility") is not None
                                else None
                            ),
                            location,
                        ),
                        published_at=published_at,
                        apply_url=apply_url,
                        description_text=description_text,
                        job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                        raw_payload={"search": item, "detail": detail_payload},
                    )
                )

            next_start = start + len(positions)
            has_more_results = bool(total_count and next_start < total_count)
            if not positions:
                if has_more_results:
                    inventory_complete = False
                    partial_reason = partial_reason or "empty_page_before_inventory_complete"
                break
            if not has_more_results and len(positions) < _DEFAULT_PAGE_SIZE:
                break
            start = next_start
            if total_count and start >= total_count:
                break
            if pages_scanned >= self.site.max_pages_per_run:
                inventory_complete = False
                partial_reason = "page_limit_reached"
                break

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
