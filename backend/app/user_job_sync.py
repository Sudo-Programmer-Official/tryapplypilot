from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from html import escape
import json
from uuid import NAMESPACE_URL, uuid5

from app.config import AppSettings, get_settings
from app.connectors.base import NormalizedJobRecord
from app.db.client import connection
from app.domain import UserAccount
from app.job_metadata import country_display, freshness_label, infer_country_code, recommendation_label
from app.logging_utils import get_logger
from app.notification_delivery import NotificationDecisionSnapshot, evaluate_notification_decision
from app.notifications.telegram import send_message
from app.retry import RetryPolicy, retry_sync
from app.scoring import score_job
from app.user_matching import (
    alert_freshness_hours,
    build_user_profile_text,
    build_user_matching_settings,
    filter_reason_for_user,
    minimum_match_score,
)

BACKFILL_ALERT_BUDGET = 5


def _json_object(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
    return {}


def _format_alert_message(
    job: NormalizedJobRecord,
    *,
    score: int,
    decision: str,
    why: list[str],
    gaps: list[str],
    recommended_resume: str,
    posted_minutes_ago: int,
    country_code: str | None,
    settings: AppSettings,
) -> str:
    strengths = "\n".join(f"• {escape(reason)}" for reason in why[:4])
    missing = "\n".join(f"⚠ {escape(reason)}" for reason in gaps[:3])
    apply_link = f'<a href="{escape(job.apply_url, quote=True)}">Apply Now</a>'
    return "\n".join(
        [
            "🚨 <b>High-Match Job</b>",
            "<b>Company</b>",
            escape(job.company),
            "<b>Role</b>",
            escape(job.title),
            escape(country_display(country_code)),
            "<b>🟢 Match</b>",
            f"{score}%",
            "<b>🕒 Freshness</b>",
            escape(
                freshness_label(
                    posted_minutes_ago,
                    alert_freshness_hours=settings.radar.alert_freshness_hours,
                    dashboard_freshness_hours=settings.radar.dashboard_freshness_hours,
                )
            ),
            "<b>🟢 Recommendation</b>",
            escape(recommendation_label(decision)),
            "<b>Why it matched</b>",
            strengths or "• General overlap",
            "<b>Missing</b>",
            missing or "• No critical gaps detected",
            "<b>Recommended Resume</b>",
            escape(recommended_resume),
            f"🔗 {apply_link}",
        ]
    )


def _job_record_from_row(row) -> NormalizedJobRecord:
    metadata = _json_object(row["metadata"])
    raw_payload = _json_object(metadata.get("raw_payload"))
    return NormalizedJobRecord(
        connector_key=str(row["connector_key"]),
        external_job_id=str(row["external_job_id"]),
        company=str(row["company"]),
        title=str(row["title"]),
        location=str(row["location"]),
        remote_policy=str(row["remote_policy"]),
        published_at=row["published_at"],
        apply_url=str(row["apply_url"]),
        description_text=str(row["description_text"]),
        job_fingerprint=str(row["job_fingerprint"]),
        raw_payload=raw_payload,
    )


async def _upsert_user_alert(
    conn,
    *,
    job_id: str,
    user_id: str,
    decision: str,
    notification_type: str,
    reason_code: str,
    payload: dict[str, object],
) -> str | None:
    alert_id = str(uuid5(NAMESPACE_URL, f"{job_id}:{user_id}:telegram:{decision}"))
    return await conn.fetchval(
        """
        INSERT INTO user_alerts (
            user_alert_id,
            job_id,
            user_id,
            channel,
            decision,
            alert_status,
            notification_type,
            reason_code,
            evaluated_at,
            payload
        )
        VALUES ($1, $2, $3, 'telegram', $4, 'pending', $5, $6, NOW(), $7::jsonb)
        ON CONFLICT (user_id, job_id, channel, decision)
        DO UPDATE SET
            alert_status = 'pending',
            notification_type = EXCLUDED.notification_type,
            reason_code = EXCLUDED.reason_code,
            evaluated_at = NOW(),
            payload = EXCLUDED.payload,
            sent_at = CASE WHEN user_alerts.alert_status = 'sent' THEN user_alerts.sent_at ELSE NULL END,
            failure_reason = CASE WHEN user_alerts.alert_status = 'sent' THEN user_alerts.failure_reason ELSE NULL END
        WHERE user_alerts.alert_status <> 'sent'
        RETURNING user_alert_id
        """,
        alert_id,
        job_id,
        user_id,
        decision,
        notification_type,
        reason_code,
        json.dumps(payload),
    )


async def _set_job_match_notification_state(
    conn,
    *,
    user_id: str,
    job_id: str,
    notification_status: str,
    notification_reason: str,
    notification_type: str,
    mark_alerted: bool = False,
    increment_attempts: bool = False,
) -> None:
    await conn.execute(
        """
        UPDATE job_matches
        SET notification_status = $3,
            notification_reason = $4,
            notification_type = $5,
            notification_evaluated_at = NOW(),
            notification_attempts = CASE
                WHEN $6 THEN COALESCE(notification_attempts, 0) + 1
                ELSE COALESCE(notification_attempts, 0)
            END,
            alerted_at = CASE
                WHEN $7 THEN COALESCE(alerted_at, NOW())
                ELSE alerted_at
            END,
            updated_at = NOW()
        WHERE user_id = $1
          AND job_id = $2
        """,
        user_id,
        job_id,
        notification_status,
        notification_reason,
        notification_type,
        increment_attempts,
        mark_alerted,
    )


async def sync_recent_jobs_for_user(user: UserAccount, settings: AppSettings | None = None) -> None:
    resolved_settings = settings or get_settings()
    matching_settings = build_user_matching_settings(resolved_settings, user)
    matching_profile_text = build_user_profile_text(user, resolved_settings)
    freshness_hours = alert_freshness_hours(user, resolved_settings)
    threshold = minimum_match_score(user, resolved_settings)
    now = datetime.now(timezone.utc)
    retry_policy = RetryPolicy(
        max_attempts=resolved_settings.connectors.retry_attempts,
        base_delay_seconds=resolved_settings.connectors.base_retry_delay_seconds,
        max_delay_seconds=resolved_settings.connectors.max_retry_delay_seconds,
        backoff_multiplier=resolved_settings.connectors.backoff_multiplier,
    )
    logger = get_logger("app.user_job_sync")
    remaining_alert_budget = BACKFILL_ALERT_BUDGET

    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM jobs
            WHERE COALESCE(published_at, first_seen_at) >= NOW() - INTERVAL '14 days'
            ORDER BY COALESCE(published_at, first_seen_at) DESC
            LIMIT 100
            """
        )

        for row in rows:
            job = _job_record_from_row(row)
            skip_reason = filter_reason_for_user(job, user, resolved_settings, matching_settings=matching_settings)
            if skip_reason is not None:
                continue

            match = await score_job(job, matching_settings, prefer_openai=True, profile_text=matching_profile_text)
            country_code = infer_country_code(job.location, job.description_text)
            match_id = str(uuid5(NAMESPACE_URL, f"{row['job_id']}:{user.id}"))
            await conn.execute(
                """
                INSERT INTO job_matches (
                    match_id,
                    job_id,
                    user_id,
                    match_score,
                    decision,
                    recommended_resume,
                    match_status,
                    why,
                    gaps,
                    provider,
                    country_code,
                    notification_status,
                    notification_reason,
                    notification_type,
                    notification_evaluated_at,
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, 'new', $7::jsonb, $8::jsonb, $9, $10, 'pending', 'collected', 'recovery_alert', NOW(), NOW()
                )
                ON CONFLICT (user_id, job_id) DO UPDATE SET
                    match_score = EXCLUDED.match_score,
                    decision = EXCLUDED.decision,
                    recommended_resume = EXCLUDED.recommended_resume,
                    why = EXCLUDED.why,
                    gaps = EXCLUDED.gaps,
                    provider = EXCLUDED.provider,
                    country_code = EXCLUDED.country_code,
                    notification_status = EXCLUDED.notification_status,
                    notification_reason = EXCLUDED.notification_reason,
                    notification_type = EXCLUDED.notification_type,
                    notification_evaluated_at = EXCLUDED.notification_evaluated_at,
                    updated_at = NOW()
                """,
                match_id,
                str(row["job_id"]),
                user.id,
                match.score,
                match.decision,
                match.recommended_resume,
                json.dumps(match.top_strengths),
                json.dumps(match.gaps),
                match.provider,
                country_code,
            )

            published_at = row["published_at"] or row["first_seen_at"] or now
            notification_decision = evaluate_notification_decision(
                job=job,
                match=match,
                user=user,
                settings=resolved_settings,
                published_at=published_at,
                now=now,
                initial_sync=False,
                remaining_initial_alert_budget=0,
                delivery_phase="recovery",
                minimum_match_score_override=threshold,
                freshness_hours_override=freshness_hours,
            )
            if remaining_alert_budget <= 0 and notification_decision.should_send:
                notification_decision = NotificationDecisionSnapshot(
                    should_send=False,
                    notification_status="suppressed",
                    reason_code="recovery_backfill_budget_exhausted",
                    notification_type="recovery_alert",
                )
            await _set_job_match_notification_state(
                conn,
                user_id=user.id,
                job_id=str(row["job_id"]),
                notification_status=notification_decision.notification_status,
                notification_reason=notification_decision.reason_code,
                notification_type=notification_decision.notification_type,
            )
            if not notification_decision.should_send:
                continue

            inserted_alert = await _upsert_user_alert(
                conn,
                job_id=str(row["job_id"]),
                user_id=user.id,
                decision=match.decision,
                notification_type=notification_decision.notification_type,
                reason_code=notification_decision.reason_code,
                payload={
                    "why": match.top_strengths,
                    "gaps": match.gaps,
                    "recommended_resume": match.recommended_resume,
                    "country_code": country_code,
                },
            )
            if inserted_alert is None:
                await _set_job_match_notification_state(
                    conn,
                    user_id=user.id,
                    job_id=str(row["job_id"]),
                    notification_status="sent",
                    notification_reason="already_alerted",
                    notification_type=notification_decision.notification_type,
                    mark_alerted=True,
                )
                continue

            posted_minutes_ago = max(0, int((now - published_at).total_seconds() // 60))
            try:
                await asyncio.to_thread(
                    retry_sync,
                    send_message,
                    resolved_settings,
                    _format_alert_message(
                        job,
                        score=match.score,
                        decision=match.decision,
                        why=match.top_strengths,
                        gaps=match.gaps,
                        recommended_resume=match.recommended_resume,
                        posted_minutes_ago=posted_minutes_ago,
                        country_code=country_code,
                        settings=matching_settings,
                    ),
                    chat_id=user.telegram_chat_id,
                    policy=retry_policy,
                    logger=logger,
                    operation_name=f"user_backfill.telegram.{user.id}.{job.company}",
                    parse_mode="HTML",
                )
                await conn.execute(
                    """
                    UPDATE user_alerts
                    SET alert_status = 'sent',
                        sent_at = NOW(),
                        reason_code = $2
                    WHERE user_alert_id = $1
                    """,
                    inserted_alert,
                    notification_decision.reason_code,
                )
                await _set_job_match_notification_state(
                    conn,
                    user_id=user.id,
                    job_id=str(row["job_id"]),
                    notification_status="sent",
                    notification_reason=notification_decision.reason_code,
                    notification_type=notification_decision.notification_type,
                    mark_alerted=True,
                    increment_attempts=True,
                )
                remaining_alert_budget -= 1
            except Exception as exc:  # noqa: BLE001
                await conn.execute(
                    """
                    UPDATE user_alerts
                    SET alert_status = 'failed',
                        failure_reason = $2,
                        reason_code = 'telegram_delivery_failed'
                    WHERE user_alert_id = $1
                    """,
                    inserted_alert,
                    str(exc)[:1000],
                )
                await _set_job_match_notification_state(
                    conn,
                    user_id=user.id,
                    job_id=str(row["job_id"]),
                    notification_status="failed",
                    notification_reason="telegram_delivery_failed",
                    notification_type=notification_decision.notification_type,
                    increment_attempts=True,
                )
