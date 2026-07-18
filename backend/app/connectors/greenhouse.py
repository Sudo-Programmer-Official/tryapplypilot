from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import html
import re

from app.config import ConnectorSettings, GreenhouseBoard
from app.connectors.base import ConnectorCursor, ConnectorDefinition, ConnectorRunResult, JobConnector, NormalizedJobRecord
from app.http import HttpTlsSettings, request_json

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


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
class GreenhouseJobConnector(JobConnector):
    board: GreenhouseBoard
    connector_settings: ConnectorSettings
    definition: ConnectorDefinition = ConnectorDefinition(
        key="greenhouse",
        display_name="Greenhouse",
        rollout_stage="live",
        pagination_mode="none",
        supports_incremental_sync=False,
        rate_limit_per_minute=30,
    )

    def collect(self, cursor: ConnectorCursor | None = None) -> ConnectorRunResult:
        del cursor
        payload = request_json(
            "GET",
            f"https://boards-api.greenhouse.io/v1/boards/{self.board.token}/jobs?content=true",
            timeout_seconds=self.connector_settings.request_timeout_seconds,
            tls=HttpTlsSettings(ca_bundle_path=None, skip_ssl_verify=False),
        )
        jobs_payload = payload.get("jobs", [])
        jobs: list[NormalizedJobRecord] = []
        latest_seen_at: datetime | None = None
        for item in jobs_payload:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            location = str((item.get("location") or {}).get("name", "Unknown")).strip()
            apply_url = str(item.get("absolute_url", "")).strip()
            description_text = _strip_html(str(item.get("content", "")))
            published_at = _parse_datetime(str(item.get("updated_at", "")))
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
