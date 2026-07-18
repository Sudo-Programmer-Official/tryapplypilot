from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain import AlertEvent, JobOpportunity, ScoutSettings, SourceStatus


class JobsRepository(Protocol):
    async def list(self) -> list[JobOpportunity]:
        ...

    async def get(self, job_id: str) -> JobOpportunity | None:
        ...


class AlertsRepository(Protocol):
    async def list(self) -> list[AlertEvent]:
        ...


class SourcesRepository(Protocol):
    async def list(self) -> list[SourceStatus]:
        ...


class SettingsRepository(Protocol):
    async def get(self) -> ScoutSettings:
        ...


@dataclass(frozen=True)
class RadarRepositories:
    jobs: JobsRepository
    alerts: AlertsRepository
    sources: SourcesRepository
    settings: SettingsRepository
