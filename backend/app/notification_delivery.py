from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config import AppSettings
from app.connectors.base import NormalizedJobRecord
from app.domain import UserAccount
from app.scoring import MatchResult
from app.user_matching import (
    alert_freshness_hours,
    alert_rule_allows_job,
    minimum_match_score,
    notification_frequency,
    telegram_connected,
)


@dataclass(frozen=True)
class NotificationDecisionSnapshot:
    should_send: bool
    notification_status: str
    reason_code: str
    notification_type: str


def evaluate_notification_decision(
    *,
    job: NormalizedJobRecord,
    match: MatchResult,
    user: UserAccount,
    settings: AppSettings,
    published_at: datetime,
    first_seen_at: datetime | None,
    last_changed_at: datetime | None,
    now: datetime,
    initial_sync: bool,
    remaining_initial_alert_budget: int,
    delivery_phase: str,
    minimum_match_score_override: int | None = None,
    freshness_hours_override: int | None = None,
) -> NotificationDecisionSnapshot:
    notification_mode = notification_frequency(user)
    if notification_mode in {"morning_digest", "evening_digest"}:
        return NotificationDecisionSnapshot(
            should_send=False,
            notification_status="digest_pending",
            reason_code="daily_digest_scheduled",
            notification_type="daily_digest",
        )

    minimum_score = minimum_match_score_override if minimum_match_score_override is not None else minimum_match_score(user, settings)
    freshness_hours = freshness_hours_override if freshness_hours_override is not None else alert_freshness_hours(user, settings)
    discovery_reference_time = first_seen_at or last_changed_at or published_at
    recovery_reference_time = last_changed_at or first_seen_at or published_at

    if not telegram_connected(user):
        return NotificationDecisionSnapshot(
            should_send=False,
            notification_status="suppressed",
            reason_code="telegram_not_connected",
            notification_type="recovery_alert" if delivery_phase == "recovery" else "fresh_alert",
        )
    if match.score < minimum_score:
        return NotificationDecisionSnapshot(
            should_send=False,
            notification_status="suppressed",
            reason_code="below_match_threshold",
            notification_type="recovery_alert" if delivery_phase == "recovery" else "fresh_alert",
        )
    if not alert_rule_allows_job(job, user):
        return NotificationDecisionSnapshot(
            should_send=False,
            notification_status="suppressed",
            reason_code="notification_rule_filtered",
            notification_type="recovery_alert" if delivery_phase == "recovery" else "fresh_alert",
        )
    if initial_sync and remaining_initial_alert_budget <= 0:
        return NotificationDecisionSnapshot(
            should_send=False,
            notification_status="suppressed",
            reason_code="initial_sync_suppressed",
            notification_type="fresh_alert",
        )
    if initial_sync and published_at < now - timedelta(hours=settings.radar.initial_alert_window_hours):
        return NotificationDecisionSnapshot(
            should_send=False,
            notification_status="suppressed",
            reason_code="initial_sync_stale",
            notification_type="fresh_alert",
        )
    if published_at < now - timedelta(hours=freshness_hours):
        return NotificationDecisionSnapshot(
            should_send=False,
            notification_status="suppressed",
            reason_code="freshness_expired",
            notification_type="recovery_alert" if delivery_phase == "recovery" else "fresh_alert",
        )
    if delivery_phase == "fresh":
        return NotificationDecisionSnapshot(
            should_send=True,
            notification_status="pending",
            reason_code="fresh_match",
            notification_type="fresh_alert",
        )
    if discovery_reference_time >= now - timedelta(hours=settings.radar.discovery_alert_freshness_hours):
        return NotificationDecisionSnapshot(
            should_send=True,
            notification_status="pending",
            reason_code="discovery_match",
            notification_type="discovery_alert",
        )
    if (
        match.score >= settings.radar.high_priority_discovery_match_score
        and discovery_reference_time >= now - timedelta(hours=settings.radar.high_priority_discovery_window_hours)
    ):
        return NotificationDecisionSnapshot(
            should_send=True,
            notification_status="pending",
            reason_code="high_priority_discovery_match",
            notification_type="discovery_alert",
        )
    if (
        delivery_phase == "recovery"
        and recovery_reference_time >= now - timedelta(hours=settings.radar.recovery_alert_freshness_hours)
    ):
        return NotificationDecisionSnapshot(
            should_send=True,
            notification_status="pending",
            reason_code="recovery_match",
            notification_type="recovery_alert",
        )
    return NotificationDecisionSnapshot(
        should_send=False,
        notification_status="suppressed",
        reason_code="freshness_expired",
        notification_type="recovery_alert" if delivery_phase == "recovery" else "fresh_alert",
    )
