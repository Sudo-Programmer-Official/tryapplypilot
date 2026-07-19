from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.logging_utils import get_logger


@dataclass(frozen=True)
class MaintenanceStatusSnapshot:
    running: bool
    cycle_state: str
    interval_minutes: int
    started_at: str | None
    last_run_started_at: str | None
    last_run: str | None
    next_run: str | None
    last_duration_seconds: float | None
    archived_jobs: int
    deleted_jobs: int
    company_backfills: int
    errors: int
    last_error: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MaintenanceRunSummary:
    archived_jobs: int
    deleted_jobs: int
    company_backfills: int
    inventory_counts: dict[str, int]
    estimated_storage_bytes: int | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_maintenance_service: MaintenanceService | None = None


def set_maintenance_service(service: MaintenanceService | None) -> None:
    global _maintenance_service
    _maintenance_service = service


def get_maintenance_service() -> MaintenanceService | None:
    return _maintenance_service


class MaintenanceService:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.logger = get_logger("app.maintenance")
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._run_lock = asyncio.Lock()
        self._started_at: datetime | None = None
        self._last_run_started_at: datetime | None = None
        self._last_run_finished_at: datetime | None = None
        self._next_run_at: datetime | None = None
        self._last_duration_seconds: float | None = None
        self._archived_jobs = 0
        self._deleted_jobs = 0
        self._company_backfills = 0
        self._errors = 0
        self._last_error: str | None = None
        self._cycle_state = "stopped"

    async def start(self) -> None:
        if self.settings.radar.mode == "seed":
            self._cycle_state = "stopped"
            return
        if self._task is not None and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._started_at = datetime.now(timezone.utc)
        self._next_run_at = self._started_at
        self._cycle_state = "idle"
        self.logger.info(
            "Maintenance service configured",
            extra={
                "operation_name": "maintenance.config",
                "maintenance_interval_minutes": self.settings.maintenance.interval_minutes,
                "cleanup_batch_size": self.settings.maintenance.cleanup_batch_size,
                "stale_after_missed_syncs": self.settings.lifecycle.stale_after_missed_syncs,
                "closed_after_missed_syncs": self.settings.lifecycle.closed_after_missed_syncs,
                "archive_after_days": self.settings.lifecycle.archive_after_days,
                "delete_after_days": self.settings.lifecycle.delete_after_days,
            },
        )
        self._task = asyncio.create_task(self._run_forever(), name="job-radar-maintenance")

    async def stop(self) -> None:
        if self._task is None:
            self._cycle_state = "stopped"
            self._next_run_at = None
            return
        self._stop_event.set()
        await self._task
        self._task = None
        self._cycle_state = "stopped"
        self._next_run_at = None

    async def run_cycle(self, *, trigger: str = "manual") -> MaintenanceStatusSnapshot:
        if self.settings.radar.mode == "seed":
            return self.status()
        async with self._run_lock:
            started_at = datetime.now(timezone.utc)
            self._last_run_started_at = started_at
            self._cycle_state = "running"
            self._last_error = None
            try:
                summary = await self._apply_lifecycle_maintenance()
                finished_at = datetime.now(timezone.utc)
                self._last_run_finished_at = finished_at
                self._last_duration_seconds = (finished_at - started_at).total_seconds()
                self._archived_jobs = summary.archived_jobs
                self._deleted_jobs = summary.deleted_jobs
                self._company_backfills = summary.company_backfills
                self._next_run_at = finished_at + timedelta(minutes=self.settings.maintenance.interval_minutes)
                self.logger.info(
                    "Lifecycle maintenance completed",
                    extra={
                        "operation_name": "maintenance.cycle.finish",
                        "trigger": trigger,
                        "summary": summary.to_dict(),
                        "duration_seconds": self._last_duration_seconds,
                    },
                )
                return self.status()
            except Exception as exc:  # noqa: BLE001
                finished_at = datetime.now(timezone.utc)
                self._last_run_finished_at = finished_at
                self._last_duration_seconds = (finished_at - started_at).total_seconds()
                self._errors += 1
                self._last_error = str(exc)[:1000]
                self._next_run_at = finished_at + timedelta(minutes=self.settings.maintenance.interval_minutes)
                self.logger.exception(
                    "Lifecycle maintenance failed",
                    extra={"operation_name": "maintenance.cycle.failed", "trigger": trigger},
                )
                raise
            finally:
                if not self._stop_event.is_set():
                    self._cycle_state = "idle"

    def status(self) -> MaintenanceStatusSnapshot:
        running = self._task is not None and not self._task.done() and self.settings.radar.mode != "seed"
        return MaintenanceStatusSnapshot(
            running=running,
            cycle_state=self._cycle_state,
            interval_minutes=self.settings.maintenance.interval_minutes,
            started_at=_isoformat(self._started_at),
            last_run_started_at=_isoformat(self._last_run_started_at),
            last_run=_isoformat(self._last_run_finished_at),
            next_run=_isoformat(self._next_run_at),
            last_duration_seconds=self._last_duration_seconds,
            archived_jobs=self._archived_jobs,
            deleted_jobs=self._deleted_jobs,
            company_backfills=self._company_backfills,
            errors=self._errors,
            last_error=self._last_error,
        )

    async def _run_forever(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    await self.run_cycle(trigger="scheduled")
                except Exception:  # noqa: BLE001
                    pass

                if self._stop_event.is_set():
                    break

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.settings.maintenance.interval_minutes * 60,
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            self._cycle_state = "stopped"

    async def _apply_lifecycle_maintenance(self) -> MaintenanceRunSummary:
        async with connection() as conn:
            async with conn.transaction():
                company_backfills = await conn.fetchval(
                    """
                    WITH updated AS (
                        UPDATE jobs j
                        SET company_id = c.company_id
                        FROM companies c
                        WHERE j.company_id IS NULL
                          AND lower(j.company) = lower(c.name)
                        RETURNING 1
                    )
                    SELECT COUNT(*) FROM updated
                    """
                )
                archive_cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.lifecycle.archive_after_days)
                delete_cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.lifecycle.delete_after_days)
                archived_jobs = await conn.fetchval(
                    """
                    WITH archived AS (
                        UPDATE jobs
                        SET lifecycle_status = 'archived',
                            source_status = 'archived',
                            archived_at = COALESCE(archived_at, NOW()),
                            last_changed_at = NOW()
                        WHERE lifecycle_status IN ('closed', 'expired')
                          AND closed_at IS NOT NULL
                          AND closed_at <= $1
                        RETURNING 1
                    )
                    SELECT COUNT(*) FROM archived
                    """,
                    archive_cutoff,
                )
                deleted_jobs = await conn.fetchval(
                    """
                    WITH deletable AS (
                        SELECT j.job_id
                        FROM jobs j
                        WHERE j.lifecycle_status = 'archived'
                          AND COALESCE(j.archived_at, j.closed_at, j.last_seen_at) <= $1
                          AND NOT EXISTS (
                              SELECT 1 FROM saved_jobs sj WHERE sj.job_id = j.job_id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM alerts a WHERE a.job_id = j.job_id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM user_alerts ua WHERE ua.job_id = j.job_id
                          )
                        ORDER BY COALESCE(j.archived_at, j.closed_at, j.last_seen_at) ASC
                        LIMIT $2
                    ),
                    deleted AS (
                        DELETE FROM jobs j
                        USING deletable d
                        WHERE j.job_id = d.job_id
                        RETURNING 1
                    )
                    SELECT COUNT(*) FROM deleted
                    """,
                    delete_cutoff,
                    self.settings.maintenance.cleanup_batch_size,
                )
                inventory_row = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE lifecycle_status = 'active') AS active,
                        COUNT(*) FILTER (WHERE lifecycle_status = 'stale') AS stale,
                        COUNT(*) FILTER (WHERE lifecycle_status = 'closed') AS closed,
                        COUNT(*) FILTER (WHERE lifecycle_status = 'expired') AS expired,
                        COUNT(*) FILTER (WHERE lifecycle_status = 'archived') AS archived,
                        COUNT(*) AS total_rows
                    FROM jobs
                    """
                )
                try:
                    estimated_storage_bytes = await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(pg_total_relation_size(oid)), 0)
                        FROM pg_class
                        WHERE relname = ANY($1::text[])
                        """,
                        [
                            "jobs",
                            "connector_runs",
                            "saved_jobs",
                            "job_matches",
                            "alerts",
                            "user_alerts",
                        ],
                    )
                except Exception:  # noqa: BLE001
                    estimated_storage_bytes = None
        inventory_counts = {
            "active": int(inventory_row["active"] or 0),
            "stale": int(inventory_row["stale"] or 0),
            "closed": int(inventory_row["closed"] or 0),
            "expired": int(inventory_row["expired"] or 0),
            "archived": int(inventory_row["archived"] or 0),
            "deleted": int(deleted_jobs or 0),
            "total_rows": int(inventory_row["total_rows"] or 0),
        }
        return MaintenanceRunSummary(
            archived_jobs=int(archived_jobs or 0),
            deleted_jobs=int(deleted_jobs or 0),
            company_backfills=int(company_backfills or 0),
            inventory_counts=inventory_counts,
            estimated_storage_bytes=int(estimated_storage_bytes) if estimated_storage_bytes is not None else None,
        )


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
