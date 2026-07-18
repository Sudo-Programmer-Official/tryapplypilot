from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from app.config import AppSettings, get_settings
from app.logging_utils import get_logger
from app.market_scout import MarketScoutAgent, MarketScoutRunSummary


class SchedulerBusyError(RuntimeError):
    pass


@dataclass(frozen=True)
class SchedulerStatusSnapshot:
    running: bool
    cycle_state: str
    polling_interval_minutes: int
    started_at: str | None
    last_run_started_at: str | None
    last_run: str | None
    next_run: str | None
    last_duration_seconds: float | None
    jobs_collected: int
    jobs_inserted: int
    jobs_matched: int
    notifications_sent: int
    errors: int
    current_connector: str | None
    last_error: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_scheduler_service: SchedulerService | None = None


def set_scheduler_service(service: SchedulerService | None) -> None:
    global _scheduler_service
    _scheduler_service = service


def get_scheduler_service() -> SchedulerService | None:
    return _scheduler_service


class SchedulerService:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.logger = get_logger("app.scheduler")
        self.agent = MarketScoutAgent(self.settings)
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._run_lock = asyncio.Lock()
        self._started_at: datetime | None = None
        self._last_run_started_at: datetime | None = None
        self._last_run_finished_at: datetime | None = None
        self._next_run_at: datetime | None = None
        self._last_duration_seconds: float | None = None
        self._jobs_collected = 0
        self._jobs_inserted = 0
        self._jobs_matched = 0
        self._notifications_sent = 0
        self._errors = 0
        self._current_connector: str | None = None
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
        self._task = asyncio.create_task(self._run_forever(), name="job-radar-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            self._cycle_state = "stopped"
            self._next_run_at = None
            return

        self._stop_event.set()
        await self._task
        self._task = None
        self._current_connector = None
        self._cycle_state = "stopped"
        self._next_run_at = None

    async def run_poll_cycle(self, *, trigger: str = "manual") -> SchedulerStatusSnapshot:
        if self.settings.radar.mode == "seed":
            return self.status()
        if self._run_lock.locked():
            raise SchedulerBusyError("Scheduler is already running a poll cycle.")

        async with self._run_lock:
            started_at = datetime.now(timezone.utc)
            self._last_run_started_at = started_at
            self._cycle_state = "running"
            self._current_connector = self.settings.radar.primary_connector
            self._last_error = None

            self.logger.info(
                "Scheduler cycle started",
                extra={
                    "operation_name": "scheduler.cycle.start",
                    "connector_key": self.settings.radar.primary_connector,
                    "trigger": trigger,
                },
            )

            try:
                summary = await self.agent.run_once()
                self._update_metrics_from_summary(summary)
                finished_at = datetime.now(timezone.utc)
                self._last_run_finished_at = finished_at
                self._last_duration_seconds = (finished_at - started_at).total_seconds()
                self._next_run_at = finished_at + timedelta(minutes=self.settings.radar.polling_interval_minutes)
                self.logger.info(
                    "Scheduler cycle finished",
                    extra={
                        "operation_name": "scheduler.cycle.finish",
                        "connector_key": self.settings.radar.primary_connector,
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
                self._next_run_at = finished_at + timedelta(minutes=self.settings.radar.polling_interval_minutes)
                self.logger.exception(
                    "Scheduler cycle failed",
                    extra={
                        "operation_name": "scheduler.cycle.failed",
                        "connector_key": self.settings.radar.primary_connector,
                        "trigger": trigger,
                    },
                )
                raise
            finally:
                self._current_connector = None
                if not self._stop_event.is_set():
                    self._cycle_state = "idle"

    def status(self) -> SchedulerStatusSnapshot:
        running = self._task is not None and not self._task.done() and self.settings.radar.mode != "seed"
        return SchedulerStatusSnapshot(
            running=running,
            cycle_state=self._cycle_state,
            polling_interval_minutes=self.settings.radar.polling_interval_minutes,
            started_at=_isoformat(self._started_at),
            last_run_started_at=_isoformat(self._last_run_started_at),
            last_run=_isoformat(self._last_run_finished_at),
            next_run=_isoformat(self._next_run_at),
            last_duration_seconds=self._last_duration_seconds,
            jobs_collected=self._jobs_collected,
            jobs_inserted=self._jobs_inserted,
            jobs_matched=self._jobs_matched,
            notifications_sent=self._notifications_sent,
            errors=self._errors,
            current_connector=self._current_connector or self.settings.radar.primary_connector,
            last_error=self._last_error,
        )

    async def _run_forever(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    await self.run_poll_cycle(trigger="scheduled")
                except SchedulerBusyError:
                    self.logger.warning(
                        "Skipping scheduled cycle because another poll is already running",
                        extra={
                            "operation_name": "scheduler.cycle.busy",
                            "connector_key": self.settings.radar.primary_connector,
                        },
                    )
                except Exception:  # noqa: BLE001
                    # The cycle already logged the failure; keep the scheduler alive.
                    pass

                if self._stop_event.is_set():
                    break

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.settings.radar.polling_interval_minutes * 60,
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            self._cycle_state = "stopped"
            self._current_connector = None

    def _update_metrics_from_summary(self, summary: MarketScoutRunSummary) -> None:
        self._jobs_collected = summary.jobs_collected
        self._jobs_inserted = summary.jobs_inserted
        self._jobs_matched = summary.jobs_matched
        self._notifications_sent = summary.alerts_sent
        self._errors = summary.connector_failures + summary.alerts_failed


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
