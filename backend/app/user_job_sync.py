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
from app.notifications.telegram import send_message
from app.retry import RetryPolicy, retry_sync
from app.scoring import score_job
from app.user_matching import (
    alert_freshness_hours,
    build_user_matching_settings,
    filter_reason_for_user,
    minimum_match_score,
    telegram_connected,
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


async def sync_recent_jobs_for_user(user: UserAccount, settings: AppSettings | None = None) -> None:
    resolved_settings = settings or get_settings()
    matching_settings = build_user_matching_settings(resolved_settings, user)
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
            WHERE COALESCE(published_at, first_seen_at) >= NOW() - ($1::interval)
            ORDER BY COALESCE(published_at, first_seen_at) DESC
            LIMIT 100
            """,
            f"{resolved_settings.radar.dashboard_freshness_hours} hours",
        )

        for row in rows:
            job = _job_record_from_row(row)
            skip_reason = filter_reason_for_user(job, user, resolved_settings, matching_settings=matching_settings)
            if skip_reason is not None:
                continue

            match = await score_job(job, matching_settings, prefer_openai=True)
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
                    updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, 'new', $7::jsonb, $8::jsonb, $9, $10, NOW()
                )
                ON CONFLICT (user_id, job_id) DO UPDATE SET
                    match_score = EXCLUDED.match_score,
                    decision = EXCLUDED.decision,
                    recommended_resume = EXCLUDED.recommended_resume,
                    why = EXCLUDED.why,
                    gaps = EXCLUDED.gaps,
                    provider = EXCLUDED.provider,
                    country_code = EXCLUDED.country_code,
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
            if (
                not telegram_connected(user)
                or match.score < threshold
                or published_at < now - timedelta(hours=freshness_hours)
                or remaining_alert_budget <= 0
            ):
                continue

            alert_id = str(uuid5(NAMESPACE_URL, f"{row['job_id']}:{user.id}:telegram:{match.decision}"))
            inserted_alert = await conn.fetchval(
                """
                INSERT INTO user_alerts (
                    user_alert_id,
                    job_id,
                    user_id,
                    channel,
                    decision,
                    alert_status,
                    payload
                )
                VALUES ($1, $2, $3, 'telegram', $4, 'pending', $5::jsonb)
                ON CONFLICT DO NOTHING
                RETURNING user_alert_id
                """,
                alert_id,
                str(row["job_id"]),
                user.id,
                match.decision,
                json.dumps(
                    {
                        "why": match.top_strengths,
                        "gaps": match.gaps,
                        "recommended_resume": match.recommended_resume,
                        "country_code": country_code,
                    }
                ),
            )
            if inserted_alert is None:
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
                        sent_at = NOW()
                    WHERE user_alert_id = $1
                    """,
                    alert_id,
                )
                await conn.execute(
                    """
                    UPDATE job_matches
                    SET alerted_at = NOW(),
                        updated_at = NOW()
                    WHERE user_id = $1
                      AND job_id = $2
                    """,
                    user.id,
                    str(row["job_id"]),
                )
                remaining_alert_budget -= 1
            except Exception as exc:  # noqa: BLE001
                await conn.execute(
                    """
                    UPDATE user_alerts
                    SET alert_status = 'failed',
                        failure_reason = $2
                    WHERE user_alert_id = $1
                    """,
                    alert_id,
                    str(exc)[:1000],
                )
