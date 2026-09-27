from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import json
from pathlib import Path
from time import perf_counter
from typing import Awaitable, Callable

from app.config import AppSettings, get_settings
from app.db.client import connection
from app.domain import KnowledgeEntity
from app.knowledge_platform import KnowledgePlatformService, build_knowledge_platform_service
from app.resume_library import ResumeDocument, list_user_resume_documents

from .changes import generate_change_set
from .critic import critique_resume_analysis
from .evidence import retrieve_requirement_evidence
from .evaluation import evaluate_resume_analysis
from .gap_analysis import analyze_resume_gaps
from .models import ResumeChangeReviewInput, ResumeIntelligenceAnalysis, ResumeIntelligenceJobContext, ResumeVersionRecord
from .selection import extract_job_requirements, select_resume_for_job
from .validation import validate_final_resume_text
from .versioning import (
    ResumeVersionStore,
    apply_reviewed_changes,
    build_resume_version_store,
    build_version_signature,
    save_resume_version_artifacts,
)

JobContextLoader = Callable[[str, str], Awaitable[ResumeIntelligenceJobContext | None]]
ResumeLoader = Callable[[str], Awaitable[list[ResumeDocument]]]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


async def _default_job_context_loader(
    user_id: str,
    job_id: str,
    *,
    settings: AppSettings | None = None,
) -> ResumeIntelligenceJobContext | None:
    resolved_settings = settings or get_settings()
    if resolved_settings.radar.mode == "seed":
        return None
    async with connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                j.job_id,
                j.connector_key,
                j.company,
                j.title,
                j.location,
                j.remote_policy,
                j.apply_url,
                j.description_text,
                j.published_at,
                jm.match_score,
                jm.decision,
                COALESCE(jm.recommended_resume, j.recommended_resume) AS effective_recommended_resume,
                COALESCE(jm.why, '[]'::jsonb) AS effective_why,
                COALESCE(jm.gaps, j.metadata->'gaps', '[]'::jsonb) AS effective_gaps
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
    return ResumeIntelligenceJobContext(
        job_id=str(row["job_id"]),
        user_id=user_id,
        company=str(row["company"]),
        title=str(row["title"]),
        location=str(row["location"]),
        remote_policy=str(row["remote_policy"]),
        apply_url=str(row["apply_url"]),
        description_text=str(row["description_text"]),
        connector_key=str(row["connector_key"]),
        published_at=published_at.isoformat() if published_at is not None else None,
        match_score=int(row["match_score"]) if row["match_score"] is not None else None,
        decision=str(row["decision"]) if row["decision"] is not None else "",
        recommended_resume=str(row["effective_recommended_resume"] or ""),
        why=_json_list(row["effective_why"]),
        gaps=_json_list(row["effective_gaps"]),
    )


def _flatten_profile(profile: dict[str, list[KnowledgeEntity]]) -> list[KnowledgeEntity]:
    return [entity for entities in profile.values() for entity in entities]


@dataclass
class ResumeIntelligenceService:
    knowledge: KnowledgePlatformService
    settings: AppSettings | None = None
    job_loader: JobContextLoader | None = None
    resume_loader: ResumeLoader | None = None
    version_store: ResumeVersionStore | None = None
    version_storage_root: Path | None = None

    async def _load_job(self, user_id: str, job_id: str) -> ResumeIntelligenceJobContext | None:
        if self.job_loader is not None:
            return await self.job_loader(user_id, job_id)
        return await _default_job_context_loader(user_id, job_id, settings=self.settings)

    async def _load_resumes(self, user_id: str) -> list[ResumeDocument]:
        if self.resume_loader is not None:
            return await self.resume_loader(user_id)
        return await list_user_resume_documents(user_id, settings=self.settings)

    def _version_store(self) -> ResumeVersionStore:
        if self.version_store is not None:
            return self.version_store
        return build_resume_version_store(self.settings)

    async def load_job_context(self, user_id: str, job_id: str) -> ResumeIntelligenceJobContext | None:
        return await self._load_job(user_id, job_id)

    async def analyze_job(self, user_id: str, job_id: str) -> ResumeIntelligenceAnalysis | None:
        started_at = perf_counter()
        job = await self.load_job_context(user_id, job_id)
        if job is None:
            return None
        resumes = await self._load_resumes(user_id)
        profile = await self.knowledge.get_user_profile(user_id)
        knowledge_entities = _flatten_profile(profile)
        requirements = extract_job_requirements(job)
        selection = select_resume_for_job(
            job,
            resumes,
            requirements=requirements,
            knowledge_entities=knowledge_entities,
        )
        selected_resume = next((resume for resume in resumes if resume.id == selection.resume_id), None)
        gap_analysis = await analyze_resume_gaps(
            knowledge=self.knowledge,
            user_id=user_id,
            job=job,
            requirements=requirements,
            selected_resume=selected_resume,
            knowledge_entities=knowledge_entities,
        )
        evidence_retrieval = await retrieve_requirement_evidence(
            knowledge=self.knowledge,
            user_id=user_id,
            requirements=[
                requirement
                for requirement in requirements
                if requirement.label in {item.label for item in [*gap_analysis.weak_requirements, *gap_analysis.missing_requirements]}
            ],
            knowledge_entities=knowledge_entities,
        )
        change_set = generate_change_set(
            job_id=job.job_id,
            selected_resume=selected_resume,
            requirements=requirements,
            evidence_retrieval=evidence_retrieval,
        )
        critique = critique_resume_analysis(
            selected_resume=selected_resume,
            requirements=requirements,
            change_set=change_set,
        )
        elapsed_ms = int(round((perf_counter() - started_at) * 1000))
        analysis = ResumeIntelligenceAnalysis(
            generated_at=_iso_now(),
            job=job,
            requirements=requirements,
            selection=selection,
            gap_analysis=gap_analysis,
            evidence_retrieval=evidence_retrieval,
            change_set=change_set,
            critique=critique,
        )
        evaluation = evaluate_resume_analysis(analysis, elapsed_ms=elapsed_ms)
        return ResumeIntelligenceAnalysis(
            generated_at=analysis.generated_at,
            job=analysis.job,
            requirements=analysis.requirements,
            selection=analysis.selection,
            gap_analysis=analysis.gap_analysis,
            evidence_retrieval=analysis.evidence_retrieval,
            change_set=analysis.change_set,
            critique=analysis.critique,
            evaluation=evaluation,
        )

    async def finalize_review(
        self,
        user_id: str,
        job_id: str,
        *,
        reviews: list[ResumeChangeReviewInput],
    ) -> ResumeVersionRecord:
        analysis = await self.analyze_job(user_id, job_id)
        if analysis is None:
            raise ValueError("Unknown job for resume finalization.")
        resumes = await self._load_resumes(user_id)
        selected_resume = next((resume for resume in resumes if resume.id == analysis.selection.resume_id), None)
        if selected_resume is None:
            raise ValueError("Resume finalization requires a selected source resume.")

        accepted_reviews = [review for review in reviews if review.decision == "approved"]
        rejected_reviews = [review for review in reviews if review.decision == "rejected"]
        if analysis.change_set.status == "blocked":
            raise ValueError("Resume finalization is blocked until the user uploads a baseline resume.")

        final_text, accepted_changes, rejected_changes = apply_reviewed_changes(
            resume=selected_resume,
            change_set=analysis.change_set,
            reviews=reviews,
        )
        if analysis.change_set.status == "no_changes_recommended" and not accepted_changes:
            final_text = selected_resume.extracted_text

        validation_errors = validate_final_resume_text(
            analysis=analysis,
            final_text=final_text,
            accepted_reviews=accepted_reviews,
        )
        if validation_errors:
            raise ValueError(" ".join(validation_errors))

        version_signature = build_version_signature(
            job_id=job_id,
            source_resume_id=selected_resume.id,
            accepted_reviews=accepted_reviews,
            rejected_reviews=rejected_reviews,
        )
        store = self._version_store()
        existing = await store.get_by_signature(user_id, version_signature)
        if existing is not None:
            return existing

        file_stem = f"{selected_resume.display_name}_{job_id}_{version_signature[:8]}"
        pdf_storage_path, text_storage_path, file_name = await save_resume_version_artifacts(
            user_id=user_id,
            file_stem=file_stem,
            final_text=final_text,
            storage_root=self.version_storage_root,
        )
        now = _iso_now()
        record = ResumeVersionRecord(
            version_id=f"rv_{version_signature}",
            user_id=user_id,
            job_id=job_id,
            source_resume_id=selected_resume.id,
            source_resume_name=selected_resume.display_name,
            file_name=file_name,
            pdf_storage_path=pdf_storage_path,
            text_storage_path=text_storage_path,
            status="generated",
            version_signature=version_signature,
            accepted_changes=accepted_changes,
            rejected_changes=rejected_changes,
            blocked_requirements=list(analysis.change_set.blocked_requirements),
            metadata={
                "analysis_generated_at": analysis.generated_at,
                "selection": analysis.selection.to_dict(),
                "critique": analysis.critique.to_dict(),
                "evaluation": analysis.evaluation.to_dict() if analysis.evaluation is not None else None,
                "accepted_changes": accepted_changes,
                "rejected_changes": rejected_changes,
                "blocked_requirements": list(analysis.change_set.blocked_requirements),
            },
            created_at=now,
            updated_at=now,
        )
        return await store.save(record)

    async def get_version(self, version_id: str, *, user_id: str) -> ResumeVersionRecord | None:
        return await self._version_store().get(version_id, user_id=user_id)

    async def get_version_content(self, version_id: str, *, user_id: str) -> dict[str, object] | None:
        record = await self.get_version(version_id, user_id=user_id)
        if record is None:
            return None
        pdf_path = Path(record.pdf_storage_path)
        if not pdf_path.exists():
            return None
        return {
            "version_id": record.version_id,
            "file_name": record.file_name,
            "mime_type": "application/pdf",
            "content_base64": base64.b64encode(pdf_path.read_bytes()).decode("ascii"),
        }


def build_resume_intelligence_service(settings: AppSettings | None = None) -> ResumeIntelligenceService:
    resolved_settings = settings or get_settings()
    return ResumeIntelligenceService(
        knowledge=build_knowledge_platform_service(resolved_settings),
        settings=resolved_settings,
        version_store=build_resume_version_store(resolved_settings),
    )
