from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Awaitable, Callable, Protocol
from uuid import NAMESPACE_URL, uuid5

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.resume_intelligence import ResumeVersionRecord, build_resume_version_store
from app.resume_intelligence.versioning import ResumeVersionStore

from .models import (
    ApplicationAnswer,
    ApplicationJobSnapshot,
    ApplicationNote,
    ApplicationPackageArtifact,
    ApplicationRecord,
    ApplicationStructuredMetadata,
    ApplicationSubmissionRecord,
    ApplicationTask,
    ApplicationTimelineEvent,
)

_TERMINAL_APPLICATION_STATUSES = {"accepted", "rejected", "withdrawn"}
_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "ready_to_apply": ("withdrawn",),
    "applied": ("interviewing", "offer", "rejected", "withdrawn"),
    "interviewing": ("offer", "rejected", "withdrawn"),
    "offer": ("accepted", "rejected", "withdrawn"),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return decoded
    return []


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


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_key(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "_" for character in value.strip())
    return "_".join(segment for segment in normalized.split("_") if segment)


def _timeline_item(*, event_type: str, label: str, detail: str = "", occurred_at: str | None = None) -> ApplicationTimelineEvent:
    return ApplicationTimelineEvent(
        event_type=event_type,
        label=label,
        detail=detail,
        occurred_at=occurred_at or _iso_now(),
    )


def _task_status_label(status: str) -> str:
    labels = {
        "pending": "Pending",
        "in_progress": "In progress",
        "completed": "Completed",
        "blocked": "Blocked",
        "skipped": "Skipped",
    }
    return labels.get(status, status.replace("_", " ").title())


def _artifact_kind_label(kind: str) -> str:
    return kind.replace("_", " ").title()


class ApplicationStore(Protocol):
    async def get_by_signature(self, user_id: str, package_signature: str) -> ApplicationRecord | None:
        ...

    async def save(self, record: ApplicationRecord) -> ApplicationRecord:
        ...

    async def get(self, application_id: str, *, user_id: str | None = None) -> ApplicationRecord | None:
        ...

    async def list_for_user(self, user_id: str, *, status: str | None = None) -> list[ApplicationRecord]:
        ...


@dataclass
class InMemoryApplicationStore:
    records: dict[str, ApplicationRecord] | None = None

    def __post_init__(self) -> None:
        self.records = {} if self.records is None else self.records

    async def get_by_signature(self, user_id: str, package_signature: str) -> ApplicationRecord | None:
        assert self.records is not None
        for record in self.records.values():
            if record.user_id == user_id and record.package_signature == package_signature:
                return record
        return None

    async def save(self, record: ApplicationRecord) -> ApplicationRecord:
        assert self.records is not None
        self.records[record.application_id] = record
        return record

    async def get(self, application_id: str, *, user_id: str | None = None) -> ApplicationRecord | None:
        assert self.records is not None
        record = self.records.get(application_id)
        if record is None:
            return None
        if user_id is not None and record.user_id != user_id:
            return None
        return record

    async def list_for_user(self, user_id: str, *, status: str | None = None) -> list[ApplicationRecord]:
        assert self.records is not None
        items = [record for record in self.records.values() if record.user_id == user_id]
        if status is not None:
            items = [record for record in items if record.status == status]
        return sorted(items, key=lambda item: (item.updated_at or "", item.application_id), reverse=True)


def _metadata_from_dict(payload: object) -> ApplicationStructuredMetadata:
    data = _json_object(payload)
    return ApplicationStructuredMetadata(
        recruiter_name=str(data.get("recruiter_name") or ""),
        recruiter_email=str(data.get("recruiter_email") or ""),
        hiring_manager=str(data.get("hiring_manager") or ""),
        application_portal=str(data.get("application_portal") or ""),
        external_application_id=str(data.get("external_application_id") or ""),
        confirmation_number=str(data.get("confirmation_number") or ""),
        submitted_url=str(data.get("submitted_url") or ""),
        submission_timestamp=str(data.get("submission_timestamp")) if data.get("submission_timestamp") else None,
        deadline=str(data.get("deadline")) if data.get("deadline") else None,
        assessment_deadline=str(data.get("assessment_deadline")) if data.get("assessment_deadline") else None,
        follow_up_date=str(data.get("follow_up_date")) if data.get("follow_up_date") else None,
        referral_source=str(data.get("referral_source") or ""),
        referral_contact=str(data.get("referral_contact") or ""),
        salary_range=str(data.get("salary_range") or ""),
        location=str(data.get("location") or ""),
        work_arrangement=str(data.get("work_arrangement") or ""),
        sponsorship_status=str(data.get("sponsorship_status") or ""),
        application_source=str(data.get("application_source") or ""),
    )


def _submission_from_dict(payload: object) -> ApplicationSubmissionRecord:
    data = _json_object(payload)
    return ApplicationSubmissionRecord(
        submitted_at=str(data.get("submitted_at")) if data.get("submitted_at") else None,
        portal=str(data.get("portal") or ""),
        confirmation_number=str(data.get("confirmation_number") or ""),
        external_application_id=str(data.get("external_application_id") or ""),
        submitted_url=str(data.get("submitted_url") or ""),
        resume_version_id=str(data.get("resume_version_id") or ""),
        answer_ids=[str(item) for item in _json_list(data.get("answer_ids"))],
        artifact_ids=[str(item) for item in _json_list(data.get("artifact_ids"))],
    )


def _row_to_application_record(row) -> ApplicationRecord:
    metadata = _json_object(row["metadata"])
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    applied_at = row["applied_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if applied_at is not None and applied_at.tzinfo is None:
        applied_at = applied_at.replace(tzinfo=timezone.utc)
    artifacts = [
        ApplicationPackageArtifact(**item)
        for item in _json_list(metadata.get("artifacts"))
        if isinstance(item, dict)
    ]
    tasks = [ApplicationTask(**item) for item in _json_list(metadata.get("tasks")) if isinstance(item, dict)]
    notes = [ApplicationNote(**item) for item in _json_list(metadata.get("notes")) if isinstance(item, dict)]
    answers = [ApplicationAnswer(**item) for item in _json_list(metadata.get("answers")) if isinstance(item, dict)]
    timeline = [
        ApplicationTimelineEvent(**item)
        for item in _json_list(metadata.get("timeline"))
        if isinstance(item, dict)
    ]
    return ApplicationRecord(
        application_id=str(row["application_id"]),
        user_id=str(row["user_id"]),
        job_id=str(row["job_id"]),
        resume_version_id=str(row["resume_version_id"]),
        status=str(row["status"]),
        package_signature=str(row["package_signature"]),
        company=str(row["company"]),
        title=str(row["title"]),
        apply_url=str(row["apply_url"]),
        match_score=int(row["match_score"]) if row["match_score"] is not None else None,
        decision=str(row["decision"]) if row["decision"] is not None else "",
        artifacts=artifacts,
        tasks=tasks,
        notes=notes,
        answers=answers,
        structured_metadata=_metadata_from_dict(metadata.get("structured_metadata")),
        submission=_submission_from_dict(metadata.get("submission")),
        timeline=timeline,
        metadata=metadata,
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
        applied_at=applied_at.isoformat() if applied_at is not None else None,
    )


class PostgresApplicationStore:
    async def get_by_signature(self, user_id: str, package_signature: str) -> ApplicationRecord | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM applications
                WHERE user_id = $1
                  AND package_signature = $2
                """,
                user_id,
                package_signature,
            )
        return _row_to_application_record(row) if row is not None else None

    async def save(self, record: ApplicationRecord) -> ApplicationRecord:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO applications (
                    application_id,
                    user_id,
                    job_id,
                    resume_version_id,
                    status,
                    package_signature,
                    company,
                    title,
                    apply_url,
                    match_score,
                    decision,
                    metadata,
                    created_at,
                    updated_at,
                    applied_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb, COALESCE($13::timestamptz, NOW()), COALESCE($14::timestamptz, NOW()), $15::timestamptz)
                ON CONFLICT (user_id, package_signature) DO UPDATE SET
                    status = EXCLUDED.status,
                    company = EXCLUDED.company,
                    title = EXCLUDED.title,
                    apply_url = EXCLUDED.apply_url,
                    match_score = EXCLUDED.match_score,
                    decision = EXCLUDED.decision,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW()),
                    applied_at = COALESCE(EXCLUDED.applied_at, applications.applied_at)
                RETURNING *
                """,
                record.application_id,
                record.user_id,
                record.job_id,
                record.resume_version_id,
                record.status,
                record.package_signature,
                record.company,
                record.title,
                record.apply_url,
                record.match_score,
                record.decision,
                json.dumps(record.metadata),
                record.created_at,
                record.updated_at,
                record.applied_at,
            )
        assert row is not None
        return _row_to_application_record(row)

    async def get(self, application_id: str, *, user_id: str | None = None) -> ApplicationRecord | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM applications
                WHERE application_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                application_id,
                user_id,
            )
        return _row_to_application_record(row) if row is not None else None

    async def list_for_user(self, user_id: str, *, status: str | None = None) -> list[ApplicationRecord]:
        async with connection() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM applications
                WHERE user_id = $1
                  AND ($2::text IS NULL OR status = $2)
                ORDER BY updated_at DESC, created_at DESC
                """,
                user_id,
                status,
            )
        return [_row_to_application_record(row) for row in rows]


def build_application_store(settings: AppSettings | None = None) -> ApplicationStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryApplicationStore()
    return PostgresApplicationStore()


def build_application_package_signature(*, job_id: str, resume_version_id: str) -> str:
    payload = {"job_id": job_id, "resume_version_id": resume_version_id}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


async def _default_job_loader(user_id: str, job_id: str) -> ApplicationJobSnapshot | None:
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                j.job_id,
                j.company,
                j.title,
                j.location,
                j.remote_policy,
                j.apply_url,
                j.published_at,
                jm.match_score,
                jm.decision,
                COALESCE(jm.why, '[]'::jsonb) AS effective_why,
                COALESCE(jm.gaps, '[]'::jsonb) AS effective_gaps
            FROM jobs j
            LEFT JOIN job_matches jm
              ON jm.job_id = j.job_id
             AND jm.user_id = $2
            WHERE j.job_id = $1
            """,
            job_id,
            user_id,
        )
    if row is None:
        return None
    published_at = row["published_at"]
    if published_at is not None and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return ApplicationJobSnapshot(
        job_id=str(row["job_id"]),
        company=str(row["company"]),
        title=str(row["title"]),
        location=str(row["location"]),
        remote_policy=str(row["remote_policy"]),
        apply_url=str(row["apply_url"]),
        match_score=int(row["match_score"]) if row["match_score"] is not None else None,
        decision=str(row["decision"]) if row["decision"] is not None else "",
        why=[str(item) for item in _json_list(row["effective_why"])],
        gaps=[str(item) for item in _json_list(row["effective_gaps"])],
        published_at=published_at.isoformat() if published_at is not None else None,
    )


def _application_id(user_id: str, package_signature: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"application:{user_id}:{package_signature}"))


def _artifact_id(application_id: str, kind: str, title: str, source_id: str = "") -> str:
    return str(uuid5(NAMESPACE_URL, f"application-artifact:{application_id}:{kind}:{title}:{source_id}"))


def _answer_id(application_id: str, question: str, answer: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"application-answer:{application_id}:{question}:{answer}"))


def _package_artifacts(job: ApplicationJobSnapshot, resume_version: ResumeVersionRecord) -> list[ApplicationPackageArtifact]:
    now = _iso_now()
    return [
        ApplicationPackageArtifact(
            artifact_id="resume_pdf",
            kind="resume",
            label="Approved resume PDF",
            version=1,
            source="resume_intelligence",
            status="ready",
            url=f"/api/auth/me/resume-intelligence/versions/{resume_version.version_id}/content",
            file_name=resume_version.file_name,
            mime_type="application/pdf",
            detail="Versioned resume artifact selected for this application package.",
            source_id=resume_version.version_id,
            metadata={"resume_version_id": resume_version.version_id},
            created_at=now,
            audit_history=[{"event_type": "ApplicationPackageBuilt", "created_at": now}],
        ),
        ApplicationPackageArtifact(
            artifact_id="job_apply_link",
            kind="external_link",
            label="Application link",
            version=1,
            source="job_connector",
            status="ready",
            url=job.apply_url,
            detail="Official job application URL from the connector source.",
            source_id=job.job_id,
            metadata={"job_id": job.job_id},
            created_at=now,
            audit_history=[{"event_type": "ApplicationPackageBuilt", "created_at": now}],
        ),
    ]


def _task(
    *,
    task_id: str,
    label: str,
    status: str,
    detail: str,
    action: str = "",
    action_url: str = "",
    due_at: str | None = None,
    completed_at: str | None = None,
    priority: str = "normal",
    category: str = "workflow",
    source: str = "system",
    generated: bool = True,
    reminder_status: str = "none",
    updated_at: str | None = None,
) -> ApplicationTask:
    return ApplicationTask(
        task_id=task_id,
        label=label,
        status=status,
        detail=detail,
        action=action,
        action_url=action_url,
        due_at=due_at,
        completed_at=completed_at,
        priority=priority,
        category=category,
        source=source,
        generated=generated,
        reminder_status=reminder_status,
        updated_at=updated_at or _iso_now(),
    )


def _package_tasks(job: ApplicationJobSnapshot, resume_version: ResumeVersionRecord) -> list[ApplicationTask]:
    now = _iso_now()
    return [
        _task(
            task_id="resume_ready",
            label="Resume version is finalized",
            status="completed",
            detail=f"{resume_version.file_name} is ready for {job.company}.",
            completed_at=now,
            source="resume_intelligence",
            updated_at=now,
        ),
        _task(
            task_id="open_apply_link",
            label="Open the application form",
            status="pending",
            detail="Use the official apply link to start the submission.",
            action="open_link",
            action_url=job.apply_url,
            updated_at=now,
        ),
        _task(
            task_id="submit_application",
            label="Submit the application",
            status="pending",
            detail="Complete the official form submission with the approved resume package.",
            action="submit_application",
            updated_at=now,
        ),
        _task(
            task_id="capture_confirmation",
            label="Capture confirmation details",
            status="pending",
            detail="Record portal, confirmation, and external application details after submission.",
            action="add_structured_metadata",
            category="confirmation",
            updated_at=now,
        ),
        _task(
            task_id="follow_up_tracker",
            label="Track follow-up and next steps",
            status="pending",
            detail="Keep recruiter follow-up notes and next actions attached to this application.",
            action="add_note",
            category="follow_up",
            updated_at=now,
        ),
    ]


def _status_tasks(tasks: list[ApplicationTask], *, status: str) -> list[ApplicationTask]:
    updated: list[ApplicationTask] = []
    now = _iso_now()
    for task in tasks:
        payload = task.to_dict()
        if task.task_id == "open_apply_link" and status in {"applied", "interviewing", "offer", "accepted", "rejected"}:
            payload.update({"status": "completed", "completed_at": now, "updated_at": now})
            updated.append(ApplicationTask(**payload))
            continue
        if task.task_id == "submit_application" and status in {"applied", "interviewing", "offer", "accepted", "rejected"}:
            payload.update({"status": "completed", "completed_at": now, "updated_at": now})
            updated.append(ApplicationTask(**payload))
            continue
        if task.task_id == "capture_confirmation" and status in {"applied", "interviewing", "offer", "accepted", "rejected"}:
            payload.update({"status": "completed" if status != "applied" else "in_progress", "updated_at": now})
            if payload["status"] == "completed":
                payload["completed_at"] = now
            updated.append(ApplicationTask(**payload))
            continue
        if task.task_id == "follow_up_tracker" and status in {"interviewing", "offer"}:
            payload.update({"status": "in_progress", "updated_at": now})
            updated.append(ApplicationTask(**payload))
            continue
        if task.task_id == "follow_up_tracker" and status in {"accepted", "rejected", "withdrawn"}:
            payload.update({"status": "completed", "completed_at": now, "updated_at": now})
            updated.append(ApplicationTask(**payload))
            continue
        updated.append(task)
    return updated


def _status_label(status: str) -> str:
    labels = {
        "ready_to_apply": "Package ready to apply",
        "applied": "Application submitted",
        "interviewing": "Interview stage reached",
        "offer": "Offer received",
        "accepted": "Offer accepted",
        "rejected": "Application rejected",
        "withdrawn": "Application withdrawn",
    }
    return labels.get(status, status.replace("_", " ").title())


def _persisted_metadata(
    *,
    record: ApplicationRecord,
    artifacts: list[ApplicationPackageArtifact] | None = None,
    tasks: list[ApplicationTask] | None = None,
    notes: list[ApplicationNote] | None = None,
    answers: list[ApplicationAnswer] | None = None,
    structured_metadata: ApplicationStructuredMetadata | None = None,
    submission: ApplicationSubmissionRecord | None = None,
    timeline: list[ApplicationTimelineEvent] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    metadata = dict(record.metadata)
    metadata["artifacts"] = [item.to_dict() for item in (artifacts if artifacts is not None else record.artifacts)]
    metadata["tasks"] = [item.to_dict() for item in (tasks if tasks is not None else record.tasks)]
    metadata["notes"] = [item.to_dict() for item in (notes if notes is not None else record.notes)]
    metadata["answers"] = [item.to_dict() for item in (answers if answers is not None else record.answers)]
    metadata["structured_metadata"] = (
        structured_metadata.to_dict() if structured_metadata is not None else record.structured_metadata.to_dict()
    )
    metadata["submission"] = submission.to_dict() if submission is not None else record.submission.to_dict()
    metadata["timeline"] = [item.to_dict() for item in (timeline if timeline is not None else record.timeline)]
    if extra:
        metadata.update(extra)
    return metadata


def _apply_deadline_tasks(
    *,
    tasks: list[ApplicationTask],
    structured_metadata: ApplicationStructuredMetadata,
    application_status: str,
) -> list[ApplicationTask]:
    now = _iso_now()
    task_map = {task.task_id: task for task in tasks}

    def upsert_generated_task(
        *,
        task_id: str,
        enabled: bool,
        label: str,
        detail: str,
        due_at: str | None,
        priority: str,
        category: str,
    ) -> None:
        existing = task_map.get(task_id)
        if not enabled:
            if existing is not None and existing.generated:
                task_map.pop(task_id, None)
            return
        status = "pending"
        completed_at = existing.completed_at if existing is not None else None
        reminder_status = existing.reminder_status if existing is not None else "scheduled"
        if task_id == "submission_deadline" and application_status != "ready_to_apply":
            status = "completed"
            completed_at = completed_at or now
        elif existing is not None and existing.status in {"completed", "skipped", "blocked"}:
            status = existing.status
        task_map[task_id] = _task(
            task_id=task_id,
            label=label,
            status=status,
            detail=detail,
            due_at=due_at,
            completed_at=completed_at,
            priority=priority,
            category=category,
            source="structured_metadata",
            generated=True,
            reminder_status=reminder_status,
            updated_at=now,
        )

    upsert_generated_task(
        task_id="submission_deadline",
        enabled=bool(structured_metadata.deadline),
        label="Submit application before deadline",
        detail="Record the official application deadline and submit before it closes.",
        due_at=structured_metadata.deadline,
        priority="high",
        category="deadline",
    )
    upsert_generated_task(
        task_id="assessment_deadline",
        enabled=bool(structured_metadata.assessment_deadline),
        label="Complete assessment before deadline",
        detail="Track the assessment deadline attached to this application.",
        due_at=structured_metadata.assessment_deadline,
        priority="high",
        category="assessment",
    )
    upsert_generated_task(
        task_id="follow_up_due",
        enabled=bool(structured_metadata.follow_up_date),
        label="Follow up with recruiter",
        detail="Follow up using the structured recruiter and submission context for this application.",
        due_at=structured_metadata.follow_up_date,
        priority="normal",
        category="follow_up",
    )
    return list(task_map.values())


def _apply_communication_task(
    *,
    tasks: list[ApplicationTask],
    pending_action: str,
    detail: str,
    due_at: str | None,
    response_overdue: bool,
    updated_at: str,
) -> list[ApplicationTask]:
    task_map = {task.task_id: task for task in tasks}
    existing = task_map.get("recruiter_next_action")
    if not pending_action.strip():
        if existing is not None and existing.generated and existing.source == "recruiter_intelligence":
            task_map.pop("recruiter_next_action", None)
        return list(task_map.values())
    task_map["recruiter_next_action"] = _task(
        task_id="recruiter_next_action",
        label=pending_action.strip(),
        status="pending",
        detail=detail.strip() or "Review the latest recruiter communication attached to this application.",
        due_at=due_at,
        priority="high" if response_overdue or due_at else "normal",
        category="communication",
        source="recruiter_intelligence",
        generated=True,
        reminder_status="overdue" if response_overdue else ("scheduled" if due_at else "none"),
        updated_at=updated_at,
    )
    return list(task_map.values())


def _build_record(
    *,
    record: ApplicationRecord,
    status: str | None = None,
    artifacts: list[ApplicationPackageArtifact] | None = None,
    tasks: list[ApplicationTask] | None = None,
    notes: list[ApplicationNote] | None = None,
    answers: list[ApplicationAnswer] | None = None,
    structured_metadata: ApplicationStructuredMetadata | None = None,
    submission: ApplicationSubmissionRecord | None = None,
    timeline: list[ApplicationTimelineEvent] | None = None,
    metadata: dict[str, object] | None = None,
    updated_at: str | None = None,
    applied_at: str | None = None,
) -> ApplicationRecord:
    return ApplicationRecord(
        application_id=record.application_id,
        user_id=record.user_id,
        job_id=record.job_id,
        resume_version_id=record.resume_version_id,
        status=status or record.status,
        package_signature=record.package_signature,
        company=record.company,
        title=record.title,
        apply_url=record.apply_url,
        match_score=record.match_score,
        decision=record.decision,
        artifacts=artifacts if artifacts is not None else record.artifacts,
        tasks=tasks if tasks is not None else record.tasks,
        notes=notes if notes is not None else record.notes,
        answers=answers if answers is not None else record.answers,
        structured_metadata=structured_metadata if structured_metadata is not None else record.structured_metadata,
        submission=submission if submission is not None else record.submission,
        timeline=timeline if timeline is not None else record.timeline,
        metadata=metadata if metadata is not None else record.metadata,
        created_at=record.created_at,
        updated_at=updated_at or record.updated_at,
        applied_at=applied_at if applied_at is not None else record.applied_at,
    )


@dataclass
class ApplicationIntelligenceService:
    settings: AppSettings | None = None
    application_store: ApplicationStore | None = None
    version_store: ResumeVersionStore | None = None
    job_loader: object | None = None

    def _store(self) -> ApplicationStore:
        if self.application_store is not None:
            return self.application_store
        return build_application_store(self.settings)

    def _version_store(self) -> ResumeVersionStore:
        if self.version_store is not None:
            return self.version_store
        return build_resume_version_store(self.settings)

    async def _load_job(self, user_id: str, job_id: str) -> ApplicationJobSnapshot | None:
        if callable(self.job_loader):
            return await self.job_loader(user_id, job_id)
        return await _default_job_loader(user_id, job_id)

    async def _load_record(self, user_id: str, application_id: str) -> ApplicationRecord:
        record = await self._store().get(application_id, user_id=user_id)
        if record is None:
            raise ValueError("Unknown application package.")
        return record

    async def list_applications(self, user_id: str, *, status: str | None = None) -> list[ApplicationRecord]:
        return await self._store().list_for_user(user_id, status=status)

    async def get_application(self, user_id: str, application_id: str) -> ApplicationRecord | None:
        return await self._store().get(application_id, user_id=user_id)

    async def track_job_application(
        self,
        user_id: str,
        job_id: str,
        *,
        resume_version_factory: Callable[[], Awaitable[ResumeVersionRecord]],
    ) -> tuple[ApplicationRecord, bool]:
        """Track a job the user is applying to; returns (application, created).

        Reuses any existing application for the job so a tailored package is never
        duplicated; otherwise packages the version produced by resume_version_factory.
        """
        existing = next(
            (application for application in await self.list_applications(user_id) if application.job_id == job_id),
            None,
        )
        if existing is not None:
            return existing, False
        resume_version = await resume_version_factory()
        record = await self.build_application_package(
            user_id,
            job_id,
            resume_version_id=resume_version.version_id,
            notes="Tracked when the apply link was opened.",
        )
        return record, True

    async def record_recruiter_communication(
        self,
        user_id: str,
        application_id: str,
        *,
        message_id: str,
        thread_id: str,
        recruiter_name: str,
        recruiter_email: str,
        occurred_at: str,
        event_type: str,
        label: str,
        detail: str,
        summary: dict[str, object],
        pending_action: str,
        suggested_actions: list[str],
        due_at: str | None = None,
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        metadata = dict(record.metadata)
        known_message_ids = {str(item) for item in _json_list(metadata.get("communication_message_ids"))}
        is_new_message = message_id not in known_message_ids
        if is_new_message:
            known_message_ids.add(message_id)

        current_summary = _json_object(metadata.get("communication_summary"))
        current_summary_at = _parse_datetime(str(current_summary.get("last_contact_date") or "")) if current_summary else None
        incoming_summary_at = _parse_datetime(occurred_at)
        is_latest_message = incoming_summary_at is not None and (
            current_summary_at is None or incoming_summary_at >= current_summary_at
        )
        if not current_summary:
            is_latest_message = True

        structured_metadata = record.structured_metadata
        recruiter_changed = False
        if recruiter_name.strip() and not structured_metadata.recruiter_name.strip():
            structured_metadata = ApplicationStructuredMetadata(
                recruiter_name=recruiter_name.strip(),
                recruiter_email=structured_metadata.recruiter_email or recruiter_email.strip(),
                hiring_manager=structured_metadata.hiring_manager,
                application_portal=structured_metadata.application_portal,
                external_application_id=structured_metadata.external_application_id,
                confirmation_number=structured_metadata.confirmation_number,
                submitted_url=structured_metadata.submitted_url,
                submission_timestamp=structured_metadata.submission_timestamp,
                deadline=structured_metadata.deadline,
                assessment_deadline=structured_metadata.assessment_deadline,
                follow_up_date=structured_metadata.follow_up_date,
                referral_source=structured_metadata.referral_source,
                referral_contact=structured_metadata.referral_contact,
                salary_range=structured_metadata.salary_range,
                location=structured_metadata.location,
                work_arrangement=structured_metadata.work_arrangement,
                sponsorship_status=structured_metadata.sponsorship_status,
                application_source=structured_metadata.application_source,
            )
            recruiter_changed = True
        elif recruiter_email.strip() and not structured_metadata.recruiter_email.strip():
            structured_metadata = ApplicationStructuredMetadata(
                recruiter_name=structured_metadata.recruiter_name,
                recruiter_email=recruiter_email.strip(),
                hiring_manager=structured_metadata.hiring_manager,
                application_portal=structured_metadata.application_portal,
                external_application_id=structured_metadata.external_application_id,
                confirmation_number=structured_metadata.confirmation_number,
                submitted_url=structured_metadata.submitted_url,
                submission_timestamp=structured_metadata.submission_timestamp,
                deadline=structured_metadata.deadline,
                assessment_deadline=structured_metadata.assessment_deadline,
                follow_up_date=structured_metadata.follow_up_date,
                referral_source=structured_metadata.referral_source,
                referral_contact=structured_metadata.referral_contact,
                salary_range=structured_metadata.salary_range,
                location=structured_metadata.location,
                work_arrangement=structured_metadata.work_arrangement,
                sponsorship_status=structured_metadata.sponsorship_status,
                application_source=structured_metadata.application_source,
            )
            recruiter_changed = True

        communication_contacts = [
            item for item in _json_list(metadata.get("communication_contacts")) if isinstance(item, dict)
        ]
        if recruiter_name.strip() or recruiter_email.strip():
            deduped_contacts = {
                str(item.get("email") or "").strip().casefold(): item
                for item in communication_contacts
                if str(item.get("email") or "").strip()
            }
            key = recruiter_email.strip().casefold() or recruiter_name.strip().casefold()
            if key:
                deduped_contacts[key] = {
                    "name": recruiter_name.strip(),
                    "email": recruiter_email.strip(),
                    "updated_at": occurred_at,
                }
            communication_contacts = list(deduped_contacts.values())

        timeline = list(record.timeline)
        if recruiter_changed:
            timeline.append(
                _timeline_item(
                    event_type="RecruiterAdded",
                    label="Recruiter context added",
                    detail=recruiter_name.strip() or recruiter_email.strip(),
                    occurred_at=occurred_at,
                )
            )
        if is_new_message:
            timeline.append(
                _timeline_item(
                    event_type=event_type,
                    label=label,
                    detail=detail,
                    occurred_at=occurred_at,
                )
            )

        tasks = list(record.tasks)
        if is_latest_message:
            summary_payload = dict(summary)
            summary_payload["suggested_actions"] = [str(item) for item in suggested_actions if str(item).strip()]
            summary_payload["last_message_id"] = message_id
            summary_payload["last_thread_id"] = thread_id
            summary_payload["last_contact_date"] = occurred_at
            summary_payload["recruiter_name"] = recruiter_name.strip() or summary_payload.get("recruiter_name", "")
            summary_payload["recruiter_email"] = recruiter_email.strip() or summary_payload.get("recruiter_email", "")
            metadata["communication_summary"] = summary_payload
            detail_text = detail.strip() or f"Latest recruiter message: {summary_payload.get('last_message_subject') or label}"
            tasks = _apply_communication_task(
                tasks=tasks,
                pending_action=pending_action,
                detail=detail_text,
                due_at=due_at,
                response_overdue=bool(summary_payload.get("response_overdue")),
                updated_at=_iso_now(),
            )

        metadata_updates = {
            "communication_message_ids": sorted(known_message_ids),
            "communication_contacts": communication_contacts,
        }
        if is_latest_message or not current_summary:
            metadata_updates["communication_thread_id"] = thread_id
        if "communication_summary" in metadata:
            metadata_updates["communication_summary"] = metadata["communication_summary"]
        persisted_metadata = _persisted_metadata(
            record=record,
            tasks=tasks,
            structured_metadata=structured_metadata,
            timeline=timeline,
            extra=metadata_updates,
        )
        updated = _build_record(
            record=record,
            tasks=tasks,
            structured_metadata=structured_metadata,
            timeline=timeline,
            metadata=persisted_metadata,
            updated_at=_iso_now(),
        )
        return await self._store().save(updated)

    async def record_interview_activity(
        self,
        user_id: str,
        application_id: str,
        *,
        interview_id: str,
        event_type: str,
        label: str,
        detail: str,
        occurred_at: str,
        remove: bool = False,
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        metadata = dict(record.metadata)
        interview_ids = {str(item) for item in _json_list(metadata.get("interview_ids")) if str(item).strip()}
        if remove:
            interview_ids.discard(interview_id)
        else:
            interview_ids.add(interview_id)
        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type=event_type,
                label=label,
                detail=detail,
                occurred_at=occurred_at,
            )
        )
        persisted_metadata = _persisted_metadata(
            record=record,
            timeline=timeline,
            extra={"interview_ids": sorted(interview_ids)},
        )
        updated = _build_record(
            record=record,
            timeline=timeline,
            metadata=persisted_metadata,
            updated_at=_iso_now(),
        )
        return await self._store().save(updated)

    async def list_application_artifacts(self, user_id: str, application_id: str) -> list[ApplicationPackageArtifact]:
        return (await self._load_record(user_id, application_id)).artifacts

    async def list_application_answers(self, user_id: str, application_id: str) -> list[ApplicationAnswer]:
        return (await self._load_record(user_id, application_id)).answers

    async def list_reusable_answers(self, user_id: str, *, include_sensitive: bool = False) -> list[ApplicationAnswer]:
        applications = await self._store().list_for_user(user_id)
        answers: list[ApplicationAnswer] = []
        for application in applications:
            for answer in application.answers:
                if not answer.reusable or not answer.user_approved:
                    continue
                if answer.sensitive_data and not include_sensitive:
                    continue
                answers.append(answer)
        return sorted(answers, key=lambda item: (item.last_used_at or item.created_at or "", item.answer_id), reverse=True)

    async def build_application_package(
        self,
        user_id: str,
        job_id: str,
        *,
        resume_version_id: str,
        notes: str = "",
    ) -> ApplicationRecord:
        job = await self._load_job(user_id, job_id)
        if job is None:
            raise ValueError("Unknown job for application package.")
        resume_version = await self._version_store().get(resume_version_id, user_id=user_id)
        if resume_version is None:
            raise ValueError("Unknown resume version for application package.")
        if resume_version.job_id != job_id:
            raise ValueError("Resume version does not belong to the requested job.")

        package_signature = build_application_package_signature(job_id=job_id, resume_version_id=resume_version_id)
        existing = await self._store().get_by_signature(user_id, package_signature)
        if existing is not None:
            return existing

        now = _iso_now()
        artifacts = _package_artifacts(job, resume_version)
        structured_metadata = ApplicationStructuredMetadata(
            application_portal=job.apply_url,
            location=job.location,
            work_arrangement=job.remote_policy,
            application_source=job.decision,
        )
        tasks = _apply_deadline_tasks(
            tasks=_package_tasks(job, resume_version),
            structured_metadata=structured_metadata,
            application_status="ready_to_apply",
        )
        timeline = [
            _timeline_item(
                event_type="ApplicationPackageBuilt",
                label="Application package built",
                detail=f"Prepared a submission package for {job.company} using {resume_version.file_name}.",
                occurred_at=now,
            )
        ]
        submission = ApplicationSubmissionRecord(resume_version_id=resume_version_id)
        metadata = {
            "job": job.to_dict(),
            "resume_version": resume_version.to_dict(),
            "package_notes": notes.strip(),
            "resume_evaluation": resume_version.metadata.get("evaluation"),
            "resume_critique": resume_version.metadata.get("critique"),
            "blocked_requirements": resume_version.metadata.get("blocked_requirements", []),
            "artifacts": [item.to_dict() for item in artifacts],
            "tasks": [item.to_dict() for item in tasks],
            "notes": [],
            "answers": [],
            "structured_metadata": structured_metadata.to_dict(),
            "submission": submission.to_dict(),
            "timeline": [item.to_dict() for item in timeline],
        }
        record = ApplicationRecord(
            application_id=_application_id(user_id, package_signature),
            user_id=user_id,
            job_id=job_id,
            resume_version_id=resume_version_id,
            status="ready_to_apply",
            package_signature=package_signature,
            company=job.company,
            title=job.title,
            apply_url=job.apply_url,
            match_score=job.match_score,
            decision=job.decision,
            artifacts=artifacts,
            tasks=tasks,
            notes=[],
            answers=[],
            structured_metadata=structured_metadata,
            submission=submission,
            timeline=timeline,
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )
        return await self._store().save(record)

    async def update_application_status(
        self,
        user_id: str,
        application_id: str,
        *,
        status: str,
        notes: str = "",
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        if record.status == status:
            return record
        if record.status in _TERMINAL_APPLICATION_STATUSES:
            raise ValueError("Application is already terminal and cannot transition again.")
        allowed = _ALLOWED_TRANSITIONS.get(record.status, ())
        if status not in allowed:
            raise ValueError(f"Invalid application transition from {record.status} to {status}.")

        now = _iso_now()
        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type="StatusChanged",
                label=_status_label(status),
                detail=notes.strip(),
                occurred_at=now,
            )
        )
        tasks = _apply_deadline_tasks(
            tasks=_status_tasks(record.tasks, status=status),
            structured_metadata=record.structured_metadata,
            application_status=status,
        )
        metadata = _persisted_metadata(record=record, tasks=tasks, timeline=timeline)
        if notes.strip():
            status_notes = metadata.get("status_notes", [])
            if not isinstance(status_notes, list):
                status_notes = []
            status_notes.append({"status": status, "note": notes.strip(), "recorded_at": now})
            metadata["status_notes"] = status_notes
        updated = _build_record(
            record=record,
            status=status,
            tasks=tasks,
            timeline=timeline,
            metadata=metadata,
            updated_at=now,
            applied_at=record.applied_at,
        )
        return await self._store().save(updated)

    async def update_application_task(
        self,
        user_id: str,
        application_id: str,
        *,
        task_id: str,
        status: str,
        detail: str = "",
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        allowed_statuses = {"pending", "in_progress", "completed", "blocked", "skipped"}
        if status not in allowed_statuses:
            raise ValueError("Invalid task status.")
        target = next((task for task in record.tasks if task.task_id == task_id), None)
        if target is None:
            raise ValueError("Unknown application task.")

        now = _iso_now()
        tasks: list[ApplicationTask] = []
        for task in record.tasks:
            if task.task_id != task_id:
                tasks.append(task)
                continue
            tasks.append(
                ApplicationTask(
                    task_id=task.task_id,
                    label=task.label,
                    status=status,
                    detail=detail.strip() or task.detail,
                    action=task.action,
                    action_url=task.action_url,
                    due_at=task.due_at,
                    completed_at=now if status == "completed" else task.completed_at,
                    priority=task.priority,
                    category=task.category,
                    source=task.source,
                    generated=task.generated,
                    reminder_status=task.reminder_status,
                    updated_at=now,
                )
            )
        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type="TaskCompleted" if status == "completed" else "TaskUpdated",
                label=f"{target.label}: {_task_status_label(status)}",
                detail=detail.strip(),
                occurred_at=now,
            )
        )
        metadata = _persisted_metadata(record=record, tasks=tasks, timeline=timeline)
        updated = _build_record(
            record=record,
            tasks=tasks,
            timeline=timeline,
            metadata=metadata,
            updated_at=now,
        )
        return await self._store().save(updated)

    async def add_application_note(
        self,
        user_id: str,
        application_id: str,
        *,
        body: str,
        note_type: str = "general",
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        normalized_body = body.strip()
        if not normalized_body:
            raise ValueError("Application note cannot be empty.")
        normalized_note_type = note_type.strip() or "general"
        now = _iso_now()
        note = ApplicationNote(
            note_id=str(uuid5(NAMESPACE_URL, f"application-note:{application_id}:{len(record.notes) + 1}:{normalized_body}")),
            note_type=normalized_note_type,
            body=normalized_body,
            created_at=now,
            created_by_user_id=user_id,
        )
        notes = [*record.notes, note]
        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type="NoteAdded",
                label=f"Added {normalized_note_type} note",
                detail=normalized_body,
                occurred_at=now,
            )
        )
        metadata = _persisted_metadata(record=record, notes=notes, timeline=timeline)
        updated = _build_record(
            record=record,
            notes=notes,
            timeline=timeline,
            metadata=metadata,
            updated_at=now,
        )
        return await self._store().save(updated)

    async def add_application_artifact(
        self,
        user_id: str,
        application_id: str,
        *,
        kind: str,
        title: str,
        source: str,
        status: str = "ready",
        url: str = "",
        file_name: str = "",
        mime_type: str = "",
        detail: str = "",
        source_id: str = "",
        metadata: dict[str, object] | None = None,
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        normalized_kind = kind.strip()
        normalized_title = title.strip()
        if not normalized_kind or not normalized_title:
            raise ValueError("Artifact kind and title are required.")
        now = _iso_now()
        artifact = ApplicationPackageArtifact(
            artifact_id=_artifact_id(application_id, normalized_kind, normalized_title, source_id),
            kind=normalized_kind,
            label=normalized_title,
            version=1,
            source=source.strip() or "manual",
            status=status.strip() or "ready",
            url=url.strip(),
            file_name=file_name.strip(),
            mime_type=mime_type.strip(),
            detail=detail.strip(),
            source_id=source_id.strip(),
            metadata=dict(metadata or {}),
            created_at=now,
            audit_history=[{"event_type": "ArtifactAttached", "created_at": now}],
        )
        artifacts = [*record.artifacts, artifact]
        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type="ArtifactAttached",
                label=f"Attached {_artifact_kind_label(normalized_kind)} artifact",
                detail=normalized_title,
                occurred_at=now,
            )
        )
        metadata_payload = _persisted_metadata(record=record, artifacts=artifacts, timeline=timeline)
        updated = _build_record(
            record=record,
            artifacts=artifacts,
            timeline=timeline,
            metadata=metadata_payload,
            updated_at=now,
        )
        return await self._store().save(updated)

    async def add_application_answer(
        self,
        user_id: str,
        application_id: str,
        *,
        question: str,
        answer: str,
        source: str,
        reusable: bool = False,
        sensitive_data: bool = False,
        user_approved: bool = True,
        question_key: str = "",
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        normalized_question = question.strip()
        normalized_answer = answer.strip()
        if not normalized_question or not normalized_answer:
            raise ValueError("Application answers require both a question and an answer.")
        now = _iso_now()
        normalized_question_key = question_key.strip() or _normalize_key(normalized_question)
        answer_record = ApplicationAnswer(
            answer_id=_answer_id(application_id, normalized_question, normalized_answer),
            application_id=application_id,
            question=normalized_question,
            normalized_question_key=normalized_question_key,
            answer=normalized_answer,
            source=source.strip() or "manual",
            created_at=now,
            last_used_at=now,
            reusable=reusable,
            sensitive_data=sensitive_data,
            user_approved=user_approved,
            status="approved" if user_approved else "draft",
        )
        answers = [*record.answers, answer_record]
        artifacts = [*record.artifacts]
        artifacts.append(
            ApplicationPackageArtifact(
                artifact_id=_artifact_id(application_id, "application_answer", normalized_question, answer_record.answer_id),
                kind="application_answer",
                label=normalized_question,
                version=1,
                source=answer_record.source,
                status="ready",
                detail="Structured application answer preserved for later review and reuse.",
                source_id=answer_record.answer_id,
                metadata={
                    "normalized_question_key": normalized_question_key,
                    "reusable": reusable,
                    "sensitive_data": sensitive_data,
                    "user_approved": user_approved,
                },
                created_at=now,
                audit_history=[{"event_type": "AnswerSaved", "created_at": now}],
            )
        )
        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type="AnswerSaved",
                label=f"Saved answer for {normalized_question}",
                detail=normalized_answer,
                occurred_at=now,
            )
        )
        metadata = _persisted_metadata(record=record, artifacts=artifacts, answers=answers, timeline=timeline)
        updated = _build_record(
            record=record,
            artifacts=artifacts,
            answers=answers,
            timeline=timeline,
            metadata=metadata,
            updated_at=now,
        )
        return await self._store().save(updated)

    async def update_application_metadata(
        self,
        user_id: str,
        application_id: str,
        *,
        updates: dict[str, object],
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        merged = {**record.structured_metadata.to_dict(), **{key: value for key, value in updates.items() if value is not None}}
        structured_metadata = _metadata_from_dict(merged)
        tasks = _apply_deadline_tasks(
            tasks=record.tasks,
            structured_metadata=structured_metadata,
            application_status=record.status,
        )
        now = _iso_now()
        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type="MetadataUpdated",
                label="Application metadata updated",
                detail=", ".join(sorted(updates.keys())),
                occurred_at=now,
            )
        )
        if structured_metadata.recruiter_name and structured_metadata.recruiter_name != record.structured_metadata.recruiter_name:
            timeline.append(
                _timeline_item(
                    event_type="RecruiterAdded",
                    label="Recruiter context added",
                    detail=structured_metadata.recruiter_name,
                    occurred_at=now,
                )
            )
        for field_name, label in (
            ("deadline", "Application deadline added"),
            ("assessment_deadline", "Assessment deadline added"),
            ("follow_up_date", "Follow-up date added"),
        ):
            new_value = getattr(structured_metadata, field_name)
            old_value = getattr(record.structured_metadata, field_name)
            if new_value and new_value != old_value:
                timeline.append(
                    _timeline_item(
                        event_type="DeadlineAdded",
                        label=label,
                        detail=str(new_value),
                        occurred_at=now,
                    )
                )
        metadata = _persisted_metadata(
            record=record,
            tasks=tasks,
            structured_metadata=structured_metadata,
            timeline=timeline,
        )
        updated = _build_record(
            record=record,
            tasks=tasks,
            structured_metadata=structured_metadata,
            timeline=timeline,
            metadata=metadata,
            updated_at=now,
        )
        return await self._store().save(updated)

    async def submit_application(
        self,
        user_id: str,
        application_id: str,
        *,
        submitted_at: str | None = None,
        portal: str = "",
        confirmation_number: str = "",
        external_application_id: str = "",
        submitted_url: str = "",
        answer_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        notes: str = "",
    ) -> ApplicationRecord:
        record = await self._load_record(user_id, application_id)
        if record.status in _TERMINAL_APPLICATION_STATUSES:
            raise ValueError("Application is already terminal and cannot be submitted again.")
        if record.status not in {"ready_to_apply", "applied"}:
            raise ValueError(f"Invalid application transition from {record.status} to applied.")

        resolved_submitted_at = submitted_at or record.submission.submitted_at or _iso_now()
        resolved_answer_ids = [str(item) for item in (answer_ids or record.submission.answer_ids)]
        resolved_artifact_ids = [str(item) for item in (artifact_ids or record.submission.artifact_ids)]
        known_answer_ids = {answer.answer_id for answer in record.answers}
        unknown_answers = [item for item in resolved_answer_ids if item not in known_answer_ids]
        if unknown_answers:
            raise ValueError("Submission references unknown application answers.")
        known_artifact_ids = {artifact.artifact_id for artifact in record.artifacts}
        unknown_artifacts = [item for item in resolved_artifact_ids if item not in known_artifact_ids]
        if unknown_artifacts:
            raise ValueError("Submission references unknown application artifacts.")

        structured_metadata = ApplicationStructuredMetadata(
            recruiter_name=record.structured_metadata.recruiter_name,
            recruiter_email=record.structured_metadata.recruiter_email,
            hiring_manager=record.structured_metadata.hiring_manager,
            application_portal=portal.strip() or record.structured_metadata.application_portal,
            external_application_id=external_application_id.strip() or record.structured_metadata.external_application_id,
            confirmation_number=confirmation_number.strip() or record.structured_metadata.confirmation_number,
            submitted_url=submitted_url.strip() or record.structured_metadata.submitted_url,
            submission_timestamp=resolved_submitted_at,
            deadline=record.structured_metadata.deadline,
            assessment_deadline=record.structured_metadata.assessment_deadline,
            follow_up_date=record.structured_metadata.follow_up_date,
            referral_source=record.structured_metadata.referral_source,
            referral_contact=record.structured_metadata.referral_contact,
            salary_range=record.structured_metadata.salary_range,
            location=record.structured_metadata.location,
            work_arrangement=record.structured_metadata.work_arrangement,
            sponsorship_status=record.structured_metadata.sponsorship_status,
            application_source=record.structured_metadata.application_source,
        )
        submission = ApplicationSubmissionRecord(
            submitted_at=resolved_submitted_at,
            portal=structured_metadata.application_portal,
            confirmation_number=structured_metadata.confirmation_number,
            external_application_id=structured_metadata.external_application_id,
            submitted_url=structured_metadata.submitted_url,
            resume_version_id=record.resume_version_id,
            answer_ids=resolved_answer_ids,
            artifact_ids=resolved_artifact_ids,
        )

        if record.status == "applied" and submission == record.submission:
            return record

        now = _iso_now()
        artifacts = list(record.artifacts)
        if structured_metadata.confirmation_number or structured_metadata.external_application_id or structured_metadata.submitted_url:
            confirmation_artifact = ApplicationPackageArtifact(
                artifact_id=_artifact_id(application_id, "confirmation", "Submission confirmation", structured_metadata.confirmation_number or structured_metadata.external_application_id),
                kind="confirmation",
                label="Submission confirmation",
                version=1,
                source="user_submission",
                status="recorded",
                detail="Structured submission confirmation recorded by the user.",
                source_id=application_id,
                metadata={
                    "portal": structured_metadata.application_portal,
                    "confirmation_number": structured_metadata.confirmation_number,
                    "external_application_id": structured_metadata.external_application_id,
                    "submitted_url": structured_metadata.submitted_url,
                },
                created_at=now,
                audit_history=[{"event_type": "ConfirmationRecorded", "created_at": now}],
            )
            if confirmation_artifact.artifact_id not in {artifact.artifact_id for artifact in artifacts}:
                artifacts.append(confirmation_artifact)
                if confirmation_artifact.artifact_id not in resolved_artifact_ids:
                    resolved_artifact_ids.append(confirmation_artifact.artifact_id)
                submission = ApplicationSubmissionRecord(
                    submitted_at=submission.submitted_at,
                    portal=submission.portal,
                    confirmation_number=submission.confirmation_number,
                    external_application_id=submission.external_application_id,
                    submitted_url=submission.submitted_url,
                    resume_version_id=submission.resume_version_id,
                    answer_ids=list(submission.answer_ids),
                    artifact_ids=list(resolved_artifact_ids),
                )

        timeline = list(record.timeline)
        timeline.append(
            _timeline_item(
                event_type="ApplicationSubmitted",
                label="Application submitted",
                detail=notes.strip() or structured_metadata.application_portal or structured_metadata.submitted_url,
                occurred_at=resolved_submitted_at,
            )
        )
        if structured_metadata.confirmation_number or structured_metadata.external_application_id:
            timeline.append(
                _timeline_item(
                    event_type="ConfirmationRecorded",
                    label="Submission confirmation recorded",
                    detail=structured_metadata.confirmation_number or structured_metadata.external_application_id,
                    occurred_at=resolved_submitted_at,
                )
            )
        tasks = _apply_deadline_tasks(
            tasks=_status_tasks(record.tasks, status="applied"),
            structured_metadata=structured_metadata,
            application_status="applied",
        )
        metadata = _persisted_metadata(
            record=record,
            artifacts=artifacts,
            tasks=tasks,
            structured_metadata=structured_metadata,
            submission=submission,
            timeline=timeline,
        )
        if notes.strip():
            submit_notes = metadata.get("submission_notes", [])
            if not isinstance(submit_notes, list):
                submit_notes = []
            submit_notes.append({"note": notes.strip(), "recorded_at": now})
            metadata["submission_notes"] = submit_notes
        updated = _build_record(
            record=record,
            status="applied",
            artifacts=artifacts,
            tasks=tasks,
            structured_metadata=structured_metadata,
            submission=submission,
            timeline=timeline,
            metadata=metadata,
            updated_at=now,
            applied_at=resolved_submitted_at,
        )
        return await self._store().save(updated)


def build_application_intelligence_service(settings: AppSettings | None = None) -> ApplicationIntelligenceService:
    resolved_settings = settings or get_settings()
    return ApplicationIntelligenceService(
        settings=resolved_settings,
        application_store=build_application_store(resolved_settings),
        version_store=build_resume_version_store(resolved_settings),
    )
