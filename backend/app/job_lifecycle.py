from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from app.config import AppSettings
from app.connectors.base import NormalizedJobRecord

JobLifecycleStatus = str
JobSourceStatus = str


def content_hash_for_job(job: NormalizedJobRecord) -> str:
    payload = {
        "title": job.title,
        "location": job.location,
        "remote_policy": job.remote_policy,
        "apply_url": job.apply_url,
        "description_text": job.description_text,
        "published_at": job.published_at.isoformat() if job.published_at is not None else None,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LifecycleTransition:
    lifecycle_status: JobLifecycleStatus
    source_status: JobSourceStatus
    closed_at: datetime | None
    archived_at: datetime | None
    changed: bool


def lifecycle_for_missed_syncs(
    *,
    current_status: JobLifecycleStatus,
    consecutive_missed_syncs: int,
    current_closed_at: datetime | None,
    current_archived_at: datetime | None,
    settings: AppSettings,
    now: datetime,
) -> LifecycleTransition:
    lifecycle_status = current_status
    source_status: JobSourceStatus = "observed"
    closed_at = current_closed_at
    archived_at = current_archived_at

    if consecutive_missed_syncs >= settings.lifecycle.closed_after_missed_syncs:
        lifecycle_status = "closed"
        source_status = "missing"
        closed_at = current_closed_at or now
    elif consecutive_missed_syncs >= settings.lifecycle.stale_after_missed_syncs:
        lifecycle_status = "stale"
        source_status = "missing"
        closed_at = None
    else:
        lifecycle_status = "active"
        source_status = "observed"
        closed_at = None
        archived_at = None

    changed = (
        lifecycle_status != current_status
        or source_status != ("observed" if consecutive_missed_syncs == 0 else "missing")
        or closed_at != current_closed_at
        or archived_at != current_archived_at
    )
    return LifecycleTransition(
        lifecycle_status=lifecycle_status,
        source_status=source_status,
        closed_at=closed_at,
        archived_at=archived_at,
        changed=changed,
    )
