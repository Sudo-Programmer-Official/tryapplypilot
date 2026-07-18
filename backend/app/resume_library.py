from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Iterable
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import ZipFile

from fastapi import UploadFile
from pypdf import PdfReader

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import ResumeAsset, UserAccount
from app.user_accounts import get_user_by_id, update_user_profile_fields

_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
_SKILL_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Python", ("python",)),
    ("FastAPI", ("fastapi",)),
    ("PostgreSQL", ("postgres", "postgresql")),
    ("Distributed Systems", ("distributed systems", "distributed", "scalability")),
    ("Backend", ("backend", "api", "microservice")),
    ("Platform", ("platform",)),
    ("Infrastructure", ("infrastructure", "infra", "sre", "reliability")),
    ("Kubernetes", ("kubernetes", "k8s")),
    ("Docker", ("docker", "containers")),
    ("AWS", ("aws", "amazon web services")),
    ("Azure", ("azure",)),
    ("GCP", ("gcp", "google cloud")),
    ("AI", ("artificial intelligence", "generative ai", "genai", " ai ")),
    ("LLMs", ("llm", "large language")),
    ("Agents", ("agent", "agentic")),
    ("ML Platform", ("ml platform", "mlops", "machine learning platform")),
)


class ResumeUploadError(ValueError):
    pass


@dataclass(frozen=True)
class ResumeExtraction:
    display_name: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    extracted_text: str
    extracted_skills: list[str]
    role_focus: str


def _storage_root() -> Path:
    return Path(__file__).resolve().parents[1] / "uploads" / "resumes"


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned or "resume"


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


def _extract_docx_text(data: bytes) -> str:
    with ZipFile(BytesIO(data)) as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError:
            return ""
    root = ElementTree.fromstring(xml_bytes)
    text_nodes = [node.text.strip() for node in root.iter() if node.text and node.text.strip()]
    return "\n".join(text_nodes).strip()


def _extract_text_from_file(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.casefold()
    if suffix in {".txt", ".md"}:
        return data.decode("utf-8", errors="ignore").strip()
    if suffix == ".pdf":
        return _extract_pdf_text(data)
    if suffix == ".docx":
        return _extract_docx_text(data)
    raise ResumeUploadError(f"Unsupported resume type: {suffix or 'unknown'}")


def _extract_skills(text: str) -> list[str]:
    haystack = f" {text.casefold()} "
    skills = [label for label, needles in _SKILL_PATTERNS if any(needle in haystack for needle in needles)]
    return skills[:10]


def _role_focus(skills: Iterable[str], text: str) -> str:
    skill_set = set(skills)
    haystack = text.casefold()
    if {"AI", "LLMs", "Agents", "ML Platform"} & skill_set:
        return "AI Platform"
    if {"Platform", "Infrastructure", "Kubernetes"} & skill_set:
        return "Platform"
    if "frontend" in haystack or "react" in haystack:
        return "Frontend"
    return "Backend"


def _preview(text: str, limit: int = 320) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def _profile_resume_entry(resume: ResumeAsset) -> dict[str, object]:
    return {
        "resume_id": resume.id,
        "display_name": resume.display_name,
        "original_filename": resume.original_filename,
        "skills": resume.extracted_skills,
        "role_focus": resume.role_focus,
        "created_at": resume.created_at,
    }


def _row_to_resume(row) -> ResumeAsset:
    metadata = row["metadata"]
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    if not isinstance(metadata, dict):
        metadata = {}
    created_at = row["created_at"]
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return ResumeAsset(
        id=str(row["resume_id"]),
        user_id=str(row["user_id"]),
        display_name=str(row["display_name"]),
        original_filename=str(row["original_filename"]),
        storage_path=str(row["storage_path"]),
        mime_type=str(row["mime_type"]),
        file_size_bytes=int(row["file_size_bytes"]),
        extracted_text_preview=_preview(str(row["extracted_text"])),
        extracted_skills=[str(item) for item in metadata.get("skills", [])],
        role_focus=str(metadata.get("role_focus", "Backend")),
        created_at=created_at.isoformat() if created_at is not None else None,
    )


async def _persist_resume_file(user_id: str, original_filename: str, data: bytes) -> tuple[str, Path]:
    resume_id = str(uuid4())
    suffix = Path(original_filename).suffix.casefold()
    storage_dir = _storage_root() / user_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / f"{resume_id}{suffix}"
    storage_path.write_bytes(data)
    return resume_id, storage_path


async def list_user_resumes(user_id: str, settings: AppSettings | None = None) -> list[ResumeAsset]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return []
    async with connection() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM resumes
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id,
        )
    return [_row_to_resume(row) for row in rows]


async def upload_resume_for_user(
    user_id: str,
    file: UploadFile,
    *,
    settings: AppSettings | None = None,
) -> tuple[ResumeAsset, UserAccount]:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        raise ResumeUploadError("Resume uploads are unavailable in seed mode.")
    user = await get_user_by_id(user_id, resolved_settings)
    if user is None:
        raise ResumeUploadError("Unknown user.")

    original_filename = file.filename or "resume"
    suffix = Path(original_filename).suffix.casefold()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise ResumeUploadError("Supported resume types are PDF, DOCX, TXT, and MD.")

    data = await file.read()
    if not data:
        raise ResumeUploadError("Uploaded resume file is empty.")

    extracted_text = _extract_text_from_file(original_filename, data)
    skills = _extract_skills(extracted_text)
    role_focus = _role_focus(skills, extracted_text)
    display_name = Path(original_filename).stem.replace("_", " ").replace("-", " ").strip() or "Resume"
    resume_id, storage_path = await _persist_resume_file(user_id, _safe_filename(original_filename), data)
    metadata = {
        "skills": skills,
        "role_focus": role_focus,
        "file_extension": suffix,
    }
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO resumes (
                resume_id,
                user_id,
                display_name,
                original_filename,
                storage_path,
                mime_type,
                file_size_bytes,
                extracted_text,
                metadata,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, NOW())
            RETURNING *
            """,
            resume_id,
            user_id,
            display_name,
            original_filename,
            str(storage_path),
            file.content_type or "application/octet-stream",
            len(data),
            extracted_text,
            json.dumps(metadata),
        )
    assert row is not None
    resume = _row_to_resume(row)

    existing_library = user.profile.get("resume_library", [])
    if not isinstance(existing_library, list):
        existing_library = []
    retained_entries = [
        entry
        for entry in existing_library
        if isinstance(entry, dict) and str(entry.get("resume_id", "")) != resume.id
    ]
    retained_entries.insert(0, _profile_resume_entry(resume))
    updated_user = await update_user_profile_fields(
        user_id,
        {
            "resume_uploaded": True,
            "resume_library": retained_entries[:10],
            "resume_skill_keywords": sorted({skill for entry in retained_entries if isinstance(entry, dict) for skill in entry.get("skills", [])}),
        },
        settings=resolved_settings,
    )
    if updated_user is None:
        raise ResumeUploadError("Failed to update user resume profile.")
    return resume, updated_user
