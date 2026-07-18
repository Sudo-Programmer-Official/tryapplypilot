from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import re

from app.config import ConnectorSettings
from app.connectors.base import ConnectorCursor, ConnectorDefinition, ConnectorRunResult, JobConnector, NormalizedJobRecord
from app.http import HttpTlsSettings, request_json

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def _parse_datetime(value: object) -> datetime | None:
    if value in {None, ""}:
        return None
    if isinstance(value, (int, float)):
        raw_value = float(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            raw_value = float(text)
        else:
            normalized = text.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
    if raw_value > 10_000_000_000:
        raw_value /= 1000.0
    return datetime.fromtimestamp(raw_value, tz=timezone.utc)


def _strip_html(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = TAG_RE.sub(" ", unescaped)
    return WHITESPACE_RE.sub(" ", without_tags).strip()


def _remote_policy(title: str, location: str, description_text: str) -> str:
    haystack = " ".join((title, location, description_text)).casefold()
    if "hybrid" in haystack:
        return "Hybrid"
    if "remote" in haystack:
        return "Remote"
    return "Onsite"


@dataclass(frozen=True)
class LeverBoard:
    company: str
    token: str


@dataclass(frozen=True)
class LeverJobConnector(JobConnector):
    board: LeverBoard
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="lever",
        display_name="Lever",
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
            f"https://api.lever.co/v0/postings/{self.board.token}?mode=json",
            timeout_seconds=self.connector_settings.request_timeout_seconds,
            tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
        )
        jobs_payload = payload if isinstance(payload, list) else payload.get("jobs", [])
        jobs: list[NormalizedJobRecord] = []
        latest_seen_at: datetime | None = None
        for item in jobs_payload:
            if not isinstance(item, dict):
                continue
            title = str(item.get("text", "")).strip()
            categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
            all_locations = categories.get("allLocations") if isinstance(categories.get("allLocations"), list) else []
            location = str(
                categories.get("location")
                or item.get("location")
                or (all_locations[0] if all_locations else "Unknown")
            ).strip()
            apply_url = str(item.get("hostedUrl") or item.get("applyUrl") or "").strip()
            description_text = _strip_html(str(item.get("descriptionPlain") or item.get("description") or ""))
            published_at = _parse_datetime(item.get("updatedAt") or item.get("createdAt"))
            if published_at is not None and (latest_seen_at is None or published_at > latest_seen_at):
                latest_seen_at = published_at
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
                    external_job_id=str(item.get("id", "")),
                    company=self.board.company,
                    title=title,
                    location=location,
                    remote_policy=_remote_policy(title, location, description_text),
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
        )
