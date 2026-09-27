from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Protocol, Sequence

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.knowledge_platform import parse_resume_sections
from app.resume_library import ResumeDocument

from .changes import ResumeEntry, _resume_entries
from .models import ResumeChangeReviewInput, ResumeChangeSet, ResumeVersionRecord
from .pdf import generate_resume_pdf_bytes


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _storage_root() -> Path:
    return Path(__file__).resolve().parents[1] / "uploads" / "resume_versions"


def _safe_segment(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value.strip())
    return cleaned.strip("._") or "resume"


class ResumeVersionStore(Protocol):
    async def get_by_signature(self, user_id: str, version_signature: str) -> ResumeVersionRecord | None:
        ...

    async def save(self, record: ResumeVersionRecord) -> ResumeVersionRecord:
        ...

    async def get(self, version_id: str, *, user_id: str | None = None) -> ResumeVersionRecord | None:
        ...


@dataclass
class InMemoryResumeVersionStore:
    records: dict[str, ResumeVersionRecord] | None = None

    def __post_init__(self) -> None:
        self.records = {} if self.records is None else self.records

    async def get_by_signature(self, user_id: str, version_signature: str) -> ResumeVersionRecord | None:
        for record in self.records.values():
            if record.user_id == user_id and record.version_signature == version_signature:
                return record
        return None

    async def save(self, record: ResumeVersionRecord) -> ResumeVersionRecord:
        assert self.records is not None
        self.records[record.version_id] = record
        return record

    async def get(self, version_id: str, *, user_id: str | None = None) -> ResumeVersionRecord | None:
        assert self.records is not None
        record = self.records.get(version_id)
        if record is None:
            return None
        if user_id is not None and record.user_id != user_id:
            return None
        return record


def _json_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [str(item) for item in decoded]
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


def _row_to_record(row) -> ResumeVersionRecord:
    metadata = _json_object(row["metadata"])
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return ResumeVersionRecord(
        version_id=str(row["resume_version_id"]),
        user_id=str(row["user_id"]),
        job_id=str(row["job_id"]),
        source_resume_id=str(row["source_resume_id"]) if row["source_resume_id"] is not None else None,
        source_resume_name=str(row["source_resume_name"]),
        file_name=str(row["file_name"]),
        pdf_storage_path=str(row["pdf_storage_path"]),
        text_storage_path=str(row["text_storage_path"]),
        status=str(row["status"]),
        version_signature=str(row["version_signature"]),
        accepted_changes=metadata.get("accepted_changes", []) if isinstance(metadata.get("accepted_changes"), list) else [],
        rejected_changes=metadata.get("rejected_changes", []) if isinstance(metadata.get("rejected_changes"), list) else [],
        blocked_requirements=_json_list(metadata.get("blocked_requirements", [])),
        metadata=metadata,
        created_at=created_at.isoformat() if created_at is not None else None,
        updated_at=updated_at.isoformat() if updated_at is not None else None,
    )


class PostgresResumeVersionStore:
    async def get_by_signature(self, user_id: str, version_signature: str) -> ResumeVersionRecord | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM resume_versions
                WHERE user_id = $1
                  AND version_signature = $2
                """,
                user_id,
                version_signature,
            )
        return _row_to_record(row) if row is not None else None

    async def save(self, record: ResumeVersionRecord) -> ResumeVersionRecord:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO resume_versions (
                    resume_version_id,
                    user_id,
                    job_id,
                    source_resume_id,
                    source_resume_name,
                    file_name,
                    pdf_storage_path,
                    text_storage_path,
                    status,
                    version_signature,
                    metadata,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, COALESCE($12::timestamptz, NOW()), COALESCE($13::timestamptz, NOW()))
                ON CONFLICT (version_signature) DO UPDATE SET
                    file_name = EXCLUDED.file_name,
                    pdf_storage_path = EXCLUDED.pdf_storage_path,
                    text_storage_path = EXCLUDED.text_storage_path,
                    status = EXCLUDED.status,
                    metadata = EXCLUDED.metadata,
                    updated_at = COALESCE(EXCLUDED.updated_at, NOW())
                RETURNING *
                """,
                record.version_id,
                record.user_id,
                record.job_id,
                record.source_resume_id,
                record.source_resume_name,
                record.file_name,
                record.pdf_storage_path,
                record.text_storage_path,
                record.status,
                record.version_signature,
                json.dumps(record.metadata),
                record.created_at,
                record.updated_at,
            )
        assert row is not None
        return _row_to_record(row)

    async def get(self, version_id: str, *, user_id: str | None = None) -> ResumeVersionRecord | None:
        async with connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM resume_versions
                WHERE resume_version_id = $1
                  AND ($2::text IS NULL OR user_id = $2)
                """,
                version_id,
                user_id,
            )
        return _row_to_record(row) if row is not None else None


def build_resume_version_store(settings: AppSettings | None = None) -> ResumeVersionStore:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return InMemoryResumeVersionStore()
    return PostgresResumeVersionStore()


def build_version_signature(
    *,
    job_id: str,
    source_resume_id: str | None,
    accepted_reviews: Sequence[ResumeChangeReviewInput],
    rejected_reviews: Sequence[ResumeChangeReviewInput],
) -> str:
    payload = {
        "job_id": job_id,
        "source_resume_id": source_resume_id,
        "accepted": [
            {"change_id": item.change_id, "edited_text": item.edited_text}
            for item in sorted(accepted_reviews, key=lambda review: review.change_id)
        ],
        "rejected": [item.change_id for item in sorted(rejected_reviews, key=lambda review: review.change_id)],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def apply_reviewed_changes(
    *,
    resume: ResumeDocument,
    change_set: ResumeChangeSet,
    reviews: Sequence[ResumeChangeReviewInput],
) -> tuple[str, list[dict[str, object]], list[dict[str, object]]]:
    review_map = {review.change_id: review for review in reviews}
    entry_map = {entry.entry_id: entry for entry in _resume_entries(resume)}
    resume_sections = parse_resume_sections(resume.extracted_text)
    accepted_changes: list[dict[str, object]] = []
    rejected_changes: list[dict[str, object]] = []
    rendered_entries: dict[str, list[ResumeEntry]] = {section.name: [] for section in resume_sections}

    for entry in entry_map.values():
        change = next((candidate for candidate in change_set.changes if candidate.entry_id == entry.entry_id), None)
        if change is None:
            rendered_entries.setdefault(entry.section, []).append(entry)
            continue
        review = review_map.get(change.change_id)
        if review is None or review.decision == "pending":
            rejected_changes.append({"change_id": change.change_id, "decision": "pending"})
            rendered_entries.setdefault(entry.section, []).append(entry)
            continue
        if review.decision == "rejected":
            rejected_changes.append({"change_id": change.change_id, "decision": "rejected"})
            rendered_entries.setdefault(entry.section, []).append(entry)
            continue
        final_text = review.edited_text.strip() or change.suggested_text
        accepted_changes.append(
            {
                "change_id": change.change_id,
                "decision": "approved",
                "original_text": change.original_text,
                "final_text": final_text,
                "job_requirements": list(change.job_requirements),
            }
        )
        if change.operation != "remove":
            rendered_entries.setdefault(entry.section, []).append(
                ResumeEntry(section=entry.section, entry_id=entry.entry_id, text=final_text)
            )

    for change in change_set.changes:
        if change.operation != "add":
            continue
        review = review_map.get(change.change_id)
        if review is None or review.decision != "approved":
            if review is None or review.decision == "pending":
                rejected_changes.append({"change_id": change.change_id, "decision": "pending"})
            else:
                rejected_changes.append({"change_id": change.change_id, "decision": review.decision})
            continue
        final_text = review.edited_text.strip() or change.suggested_text
        accepted_changes.append(
            {
                "change_id": change.change_id,
                "decision": "approved",
                "original_text": change.original_text,
                "final_text": final_text,
                "job_requirements": list(change.job_requirements),
            }
        )
        rendered_entries.setdefault(change.section, []).append(
            ResumeEntry(section=change.section, entry_id=change.entry_id, text=final_text)
        )

    section_blocks: list[str] = []
    seen_sections: set[str] = set()
    for section in resume_sections:
        seen_sections.add(section.name)
        entries = rendered_entries.get(section.name, [])
        if not entries:
            continue
        section_body = "\n\n".join(entry.text.strip() for entry in entries if entry.text.strip())
        if not section_body.strip():
            continue
        section_blocks.append(f"{section.heading}\n{section_body}".strip())
    for section_name, entries in rendered_entries.items():
        if section_name in seen_sections or not entries:
            continue
        section_body = "\n\n".join(entry.text.strip() for entry in entries if entry.text.strip())
        if section_body.strip():
            section_blocks.append(f"{section_name.title()}\n{section_body}".strip())

    final_text = "\n\n".join(block for block in section_blocks if block.strip())
    return final_text, accepted_changes, rejected_changes


async def save_resume_version_artifacts(
    *,
    user_id: str,
    file_stem: str,
    final_text: str,
    storage_root: Path | None = None,
) -> tuple[str, str, str]:
    root = storage_root or _storage_root()
    user_dir = root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = _safe_segment(file_stem)
    text_path = user_dir / f"{safe_stem}.txt"
    pdf_path = user_dir / f"{safe_stem}.pdf"
    text_path.write_text(final_text, encoding="utf-8")
    pdf_path.write_bytes(generate_resume_pdf_bytes(final_text))
    return str(pdf_path), str(text_path), pdf_path.name
