from __future__ import annotations

from dataclasses import dataclass

from app.connectors.base import ConnectorDefinition


@dataclass(frozen=True)
class ConnectorRegistry:
    connectors: tuple[ConnectorDefinition, ...]

    def list_definitions(self) -> list[ConnectorDefinition]:
        return list(self.connectors)

    def get(self, key: str) -> ConnectorDefinition | None:
        for connector in self.connectors:
            if connector.key == key:
                return connector
        return None


def build_default_registry() -> ConnectorRegistry:
    return ConnectorRegistry(
        connectors=(
            ConnectorDefinition(
                key="greenhouse",
                display_name="Greenhouse",
                rollout_stage="live",
                pagination_mode="none",
                supports_incremental_sync=False,
                rate_limit_per_minute=30,
            ),
            ConnectorDefinition(
                key="lever",
                display_name="Lever",
                rollout_stage="next",
                pagination_mode="page",
                supports_incremental_sync=True,
                rate_limit_per_minute=20,
            ),
            ConnectorDefinition(
                key="ashby",
                display_name="Ashby",
                rollout_stage="next",
                pagination_mode="page",
                supports_incremental_sync=True,
                rate_limit_per_minute=20,
            ),
            ConnectorDefinition(
                key="microsoft-careers",
                display_name="Microsoft Careers",
                rollout_stage="later",
                pagination_mode="page",
                supports_incremental_sync=True,
                rate_limit_per_minute=12,
            ),
            ConnectorDefinition(
                key="google-careers",
                display_name="Google Careers",
                rollout_stage="later",
                pagination_mode="page",
                supports_incremental_sync=True,
                rate_limit_per_minute=12,
            ),
            ConnectorDefinition(
                key="workday",
                display_name="Workday",
                rollout_stage="later",
                pagination_mode="page",
                supports_incremental_sync=False,
                rate_limit_per_minute=10,
            ),
            ConnectorDefinition(
                key="smartrecruiters",
                display_name="SmartRecruiters",
                rollout_stage="later",
                pagination_mode="page",
                supports_incremental_sync=True,
                rate_limit_per_minute=10,
            ),
            ConnectorDefinition(
                key="company-api",
                display_name="Company APIs",
                rollout_stage="later",
                pagination_mode="page",
                supports_incremental_sync=True,
                rate_limit_per_minute=10,
            ),
        )
    )
