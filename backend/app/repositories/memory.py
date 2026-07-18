from __future__ import annotations

from dataclasses import dataclass

from app.data.seed import ALERTS, JOBS, SETTINGS, SOURCES
from app.domain import AlertEvent, JobOpportunity, ScoutSettings, SourceStatus
from app.repositories.interfaces import RadarRepositories


@dataclass
class InMemoryJobsRepository:
    _jobs: tuple[JobOpportunity, ...]

    async def list(self) -> list[JobOpportunity]:
        return list(self._jobs)

    async def get(self, job_id: str) -> JobOpportunity | None:
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None


@dataclass
class InMemoryAlertsRepository:
    _alerts: tuple[AlertEvent, ...]

    async def list(self) -> list[AlertEvent]:
        return list(self._alerts)


@dataclass
class InMemorySourcesRepository:
    _sources: tuple[SourceStatus, ...]

    async def list(self) -> list[SourceStatus]:
        return list(self._sources)


@dataclass
class InMemorySettingsRepository:
    _settings: ScoutSettings

    async def get(self) -> ScoutSettings:
        return self._settings


def build_seed_repositories() -> RadarRepositories:
    return RadarRepositories(
        jobs=InMemoryJobsRepository(tuple(JOBS)),
        alerts=InMemoryAlertsRepository(tuple(ALERTS)),
        sources=InMemorySourcesRepository(tuple(SOURCES)),
        settings=InMemorySettingsRepository(SETTINGS),
    )
