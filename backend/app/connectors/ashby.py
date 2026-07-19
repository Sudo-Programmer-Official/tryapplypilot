from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import html
import re

from app.config import ConnectorSettings
from app.connectors.base import ConnectorCursor, ConnectorDefinition, ConnectorRunResult, JobConnector, NormalizedJobRecord
from app.http import HttpTlsSettings, request_json
from app.job_metadata import infer_country_code, matches_country_preference, normalize_supported_country

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
_BROWSER_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = TAG_RE.sub(" ", unescaped)
    return WHITESPACE_RE.sub(" ", without_tags).strip()


def _join_locations(primary_location: str, secondary_locations: object) -> str:
    values: list[str] = []
    if primary_location.strip():
        values.append(primary_location.strip())
    if isinstance(secondary_locations, list):
        for item in secondary_locations:
            if not isinstance(item, dict):
                continue
            secondary_location = str(item.get("location", "")).strip()
            if secondary_location and secondary_location not in values:
                values.append(secondary_location)
    return "; ".join(values) or "Unknown"


def _remote_policy(workplace_type: str, is_remote: bool, location: str, description_text: str) -> str:
    normalized_workplace_type = workplace_type.strip().casefold()
    if normalized_workplace_type == "remote" or is_remote:
        return "Remote"
    if normalized_workplace_type == "hybrid":
        return "Hybrid"
    haystack = f" {location} {description_text} ".casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    return "Onsite"


def _matches_company_country(location: str, description_text: str, company_country: str) -> bool:
    selected_country = normalize_supported_country(company_country)
    inferred_country = infer_country_code(location, description_text)
    return matches_country_preference(inferred_country, selected_country)


@dataclass(frozen=True)
class AshbyBoard:
    company: str
    token: str
    country: str = "US"


@dataclass(frozen=True)
class AshbyJobConnector(JobConnector):
    board: AshbyBoard
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="ashby",
        display_name="Ashby",
        layer="official_ats",
        admin_status="live",
        rollout_stage="live",
        pagination_mode="none",
        supports_incremental_sync=False,
        rate_limit_per_minute=20,
    )

    def collect(self, cursor: ConnectorCursor | None = None) -> ConnectorRunResult:
        del cursor
        payload = request_json(
            "GET",
            f"https://api.ashbyhq.com/posting-api/job-board/{self.board.token}?includeCompensation=true",
            timeout_seconds=self.connector_settings.request_timeout_seconds,
            tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
            headers=_BROWSER_HEADERS,
        )
        if not isinstance(payload, dict):
            raise RuntimeError("Ashby job board returned an unexpected payload.")

        jobs_payload = payload.get("jobs", [])
        jobs: list[NormalizedJobRecord] = []
        latest_seen_at: datetime | None = None
        for item in jobs_payload:
            if not isinstance(item, dict) or not bool(item.get("isListed", True)):
                continue
            title = str(item.get("title", "")).strip()
            location = _join_locations(
                str(item.get("location", "")).strip(),
                item.get("secondaryLocations"),
            )
            description_text = _strip_html(
                str(item.get("descriptionPlain") or item.get("descriptionHtml") or "")
            )
            if not _matches_company_country(location, description_text, self.board.country):
                continue
            published_at = _parse_datetime(str(item.get("publishedAt") or ""))
            if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                latest_seen_at = published_at
            apply_url = str(item.get("applyUrl") or item.get("jobUrl") or "").strip()
            remote_policy = _remote_policy(
                str(item.get("workplaceType") or ""),
                bool(item.get("isRemote")),
                location,
                description_text,
            )
            fingerprint_input = "::".join(
                (
                    self.definition.key,
                    self.board.token,
                    str(item.get("id", "")),
                    self.board.company.casefold(),
                    title.casefold(),
                    location.casefold(),
                    apply_url.casefold(),
                )
            )
            jobs.append(
                NormalizedJobRecord(
                    connector_key=f"{self.definition.key}:{self.board.token}",
                    external_job_id=str(item.get("id", "")).strip(),
                    company=self.board.company,
                    title=title,
                    location=location,
                    remote_policy=remote_policy,
                    published_at=published_at,
                    apply_url=apply_url,
                    description_text=description_text,
                    job_fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
                    raw_payload=item,
                )
            )
        return ConnectorRunResult(
            jobs=jobs,
            next_cursor=ConnectorCursor(cursor=None, last_published_at=latest_seen_at),
            exhausted=True,
            requests_made=1,
            pages_scanned=1,
            expected_pages=1,
        )
