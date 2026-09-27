from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

if "asyncpg" not in sys.modules and importlib.util.find_spec("asyncpg") is None:
    asyncpg_stub = types.ModuleType("asyncpg")

    class _UniqueViolationError(Exception):
        pass

    asyncpg_stub.UniqueViolationError = _UniqueViolationError
    asyncpg_stub.Connection = object
    asyncpg_stub.Record = dict
    asyncpg_stub.connect = None
    sys.modules["asyncpg"] = asyncpg_stub

if "fastapi" not in sys.modules and importlib.util.find_spec("fastapi") is None:
    fastapi_stub = types.ModuleType("fastapi")

    class _HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    class _FastAPI:
        def __init__(self, *args, **kwargs):
            self.state = types.SimpleNamespace()

        def add_middleware(self, *args, **kwargs):
            return None

        def get(self, *args, **kwargs):
            return lambda func: func

        def post(self, *args, **kwargs):
            return lambda func: func

        def put(self, *args, **kwargs):
            return lambda func: func

        def patch(self, *args, **kwargs):
            return lambda func: func

        def delete(self, *args, **kwargs):
            return lambda func: func

    class _UploadFile:
        pass

    fastapi_stub.Depends = lambda dependency=None: dependency
    fastapi_stub.FastAPI = _FastAPI
    fastapi_stub.File = lambda default=None: default
    fastapi_stub.HTTPException = _HTTPException
    fastapi_stub.Query = lambda default=None, **kwargs: default
    fastapi_stub.Request = object
    fastapi_stub.UploadFile = _UploadFile
    fastapi_stub.status = types.SimpleNamespace(
        HTTP_400_BAD_REQUEST=400,
        HTTP_401_UNAUTHORIZED=401,
        HTTP_403_FORBIDDEN=403,
        HTTP_404_NOT_FOUND=404,
        HTTP_409_CONFLICT=409,
        HTTP_503_SERVICE_UNAVAILABLE=503,
    )
    sys.modules["fastapi"] = fastapi_stub

    middleware_stub = types.ModuleType("fastapi.middleware")
    cors_stub = types.ModuleType("fastapi.middleware.cors")
    cors_stub.CORSMiddleware = object
    sys.modules["fastapi.middleware"] = middleware_stub
    sys.modules["fastapi.middleware.cors"] = cors_stub

    security_stub = types.ModuleType("fastapi.security")

    class _HTTPAuthorizationCredentials:
        def __init__(self, credentials: str = ""):
            self.credentials = credentials

    class _HTTPBearer:
        def __init__(self, auto_error: bool = False):
            self.auto_error = auto_error

        def __call__(self, *args, **kwargs):
            return None

    security_stub.HTTPAuthorizationCredentials = _HTTPAuthorizationCredentials
    security_stub.HTTPBearer = _HTTPBearer
    sys.modules["fastapi.security"] = security_stub

if "pypdf" not in sys.modules and importlib.util.find_spec("pypdf") is None:
    pypdf_stub = types.ModuleType("pypdf")

    class _PdfReader:
        def __init__(self, stream):
            self.pages = []

    pypdf_stub.PdfReader = _PdfReader
    sys.modules["pypdf"] = pypdf_stub

from app.knowledge_platform import InMemoryKnowledgePlatformStore, KnowledgePlatformService
from app.resume_intelligence import (
    InMemoryResumeVersionStore,
    ResumeBenchmarkExpectation,
    ResumeChangeReviewInput,
    ResumeIntelligenceJobContext,
    ResumeIntelligenceService,
    evaluate_benchmark_result,
)
from app.resume_library import ResumeDocument


class ResumeIntelligenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        async def audit_recorder(**payload):
            return None

        self.temp_dir = tempfile.TemporaryDirectory()
        self.knowledge = KnowledgePlatformService(
            store=InMemoryKnowledgePlatformStore(),
            audit_recorder=audit_recorder,
        )
        self.version_store = InMemoryResumeVersionStore()

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def _approve_entity(
        self,
        *,
        user_id: str = "user-1",
        entity_type: str,
        canonical_name: str,
        content: dict[str, object],
        excerpt: str,
        source_type: str = "project",
    ) -> None:
        evidence = await self.knowledge.add_evidence(
            user_id,
            source_type=source_type,
            source_id=f"{entity_type}-{canonical_name.casefold().replace(' ', '-')}",
            excerpt=excerpt,
            metadata={"seed": True, "confidence": 0.93},
        )
        version = await self.knowledge.stage_change(
            user_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            new_content=content,
            source="tests",
            reason="Seed canonical knowledge for Resume Intelligence tests.",
            evidence_ids=[evidence.id],
            actor_user_id="system",
            confidence=0.93,
            agent_name="tests",
        )
        await self.knowledge.approve_change(version.id, reviewed_by_user_id="admin-1")

    async def test_selection_prefers_resume_with_best_requirement_overlap(self) -> None:
        await self._approve_entity(
            entity_type="project",
            canonical_name="Payments Platform",
            content={
                "summary": "Built payment APIs with gRPC and Python for a distributed billing platform on AWS.",
                "technologies": ["Python", "AWS", "gRPC"],
            },
            excerpt="Built payment APIs with gRPC and Python for a distributed billing platform on AWS.",
        )
        await self._approve_entity(
            entity_type="achievement",
            canonical_name="Payments Throughput",
            content={"text": "Handled 90,000 payment jobs per day across a Kubernetes platform."},
            excerpt="Handled 90,000 payment jobs per day across a Kubernetes platform.",
        )

        job = ResumeIntelligenceJobContext(
            job_id="job-1",
            user_id="user-1",
            company="Ramp",
            title="Staff Platform Engineer, Billing Infrastructure",
            location="New York, NY",
            remote_policy="Hybrid",
            apply_url="https://example.com/jobs/1",
            description_text=(
                "Build Python services for a Kubernetes-based billing platform. "
                "Strong AWS, distributed systems, gRPC, and Terraform experience required."
            ),
            match_score=95,
            decision="APPLY_NOW",
            recommended_resume="Platform_v4.pdf",
            why=["Python", "Platform", "Distributed Systems"],
            gaps=["gRPC", "Terraform"],
        )
        resumes = [
            ResumeDocument(
                id="resume-ai",
                user_id="user-1",
                display_name="AI Platform Resume",
                original_filename="Backend_AI_v5.pdf",
                storage_path="/tmp/resume-ai.pdf",
                mime_type="application/pdf",
                file_size_bytes=1200,
                extracted_text="Built LLM orchestration systems and AI copilots with Python.",
                extracted_skills=["Python", "AI", "LLMs", "Agents"],
                role_focus="AI Platform",
                created_at="2026-07-19T00:00:00+00:00",
            ),
            ResumeDocument(
                id="resume-platform",
                user_id="user-1",
                display_name="Platform Resume",
                original_filename="Platform_v4.pdf",
                storage_path="/tmp/resume-platform.pdf",
                mime_type="application/pdf",
                file_size_bytes=1400,
                extracted_text=(
                    "Staff platform engineer building Python APIs, Kubernetes infrastructure, "
                    "AWS services, and distributed backend systems."
                ),
                extracted_skills=["Python", "Kubernetes", "AWS", "Platform", "Infrastructure", "Distributed Systems"],
                role_focus="Platform",
                created_at="2026-07-20T00:00:00+00:00",
            ),
        ]

        async def job_loader(user_id: str, job_id: str) -> ResumeIntelligenceJobContext | None:
            self.assertEqual(user_id, "user-1")
            self.assertEqual(job_id, "job-1")
            return job

        async def resume_loader(user_id: str) -> list[ResumeDocument]:
            self.assertEqual(user_id, "user-1")
            return resumes

        service = ResumeIntelligenceService(
            knowledge=self.knowledge,
            job_loader=job_loader,
            resume_loader=resume_loader,
        )

        analysis = await service.analyze_job("user-1", "job-1")

        self.assertIsNotNone(analysis)
        assert analysis is not None
        self.assertEqual(analysis.selection.status, "selected")
        self.assertEqual(analysis.selection.resume_id, "resume-platform")
        self.assertIn("Python", analysis.selection.matched_requirements)
        self.assertTrue(any(reason.label == "Existing recommendation" for reason in analysis.selection.reason_summary))

        covered = {item.label for item in analysis.gap_analysis.covered_requirements}
        weak = {item.label for item in analysis.gap_analysis.weak_requirements}
        missing = {item.label for item in analysis.gap_analysis.missing_requirements}

        self.assertIn("Kubernetes", covered)
        self.assertIn("AWS", covered)
        self.assertIn("gRPC", weak)
        self.assertIn("Terraform", missing)
        self.assertIn("gRPC", analysis.gap_analysis.keyword_opportunities)
        self.assertTrue(any("Terraform" in flag for flag in analysis.gap_analysis.risk_flags))

        grpc_gap = next(item for item in analysis.gap_analysis.weak_requirements if item.label == "gRPC")
        self.assertGreater(len(grpc_gap.evidence), 0)
        self.assertEqual(grpc_gap.evidence[0].source_type, "project")
        self.assertTrue(any(item.requirement_label == "gRPC" for item in analysis.evidence_retrieval.items))
        grpc_evidence = next(item for item in analysis.evidence_retrieval.items if item.requirement_label == "gRPC")
        self.assertEqual(grpc_evidence.support_level, "supported")
        self.assertGreater(len(grpc_evidence.evidence), 0)
        self.assertEqual(analysis.change_set.status, "ready_for_review")
        self.assertGreaterEqual(len(analysis.change_set.changes), 1)
        self.assertTrue(any("gRPC" in change.job_requirements for change in analysis.change_set.changes))
        terraform_evidence = next(item for item in analysis.evidence_retrieval.items if item.requirement_label == "Terraform")
        self.assertEqual(terraform_evidence.support_level, "missing_proof")
        self.assertIn("Terraform", analysis.change_set.blocked_requirements)
        self.assertEqual(analysis.critique.verdict, "review_with_risks")
        self.assertGreater(analysis.critique.overall_after, analysis.critique.overall_before)
        self.assertTrue(any(score.label == "ATS compatibility" for score in analysis.critique.dimensions))
        self.assertIsNotNone(analysis.evaluation)
        assert analysis.evaluation is not None
        self.assertEqual(analysis.evaluation.status, "pass")
        self.assertGreaterEqual(analysis.evaluation.score, 90)
        self.assertEqual(analysis.evaluation.metrics["change_explainability_rate"], 100.0)
        self.assertEqual(analysis.evaluation.metrics["evidence_integrity_rate"], 100.0)
        benchmark = evaluate_benchmark_result(
            analysis,
            expectation=ResumeBenchmarkExpectation(
                name="supported-missing-evidence",
                expected_selection_status="selected",
                expected_change_set_status="ready_for_review",
                expected_critique_verdict="review_with_risks",
                min_score=90,
                allowed_scorecard_statuses=("pass",),
                required_covered_requirements=("Kubernetes", "AWS"),
                required_weak_requirements=("gRPC",),
                required_missing_requirements=("Terraform",),
                max_blocked_requirements=1,
            ),
        )
        self.assertTrue(benchmark.passed, msg="; ".join(benchmark.failures))

    async def test_selection_handles_empty_resume_library(self) -> None:
        job = ResumeIntelligenceJobContext(
            job_id="job-2",
            user_id="user-1",
            company="Anthropic",
            title="Backend Engineer",
            location="San Francisco, CA",
            remote_policy="Remote",
            apply_url="https://example.com/jobs/2",
            description_text="Build backend Python services with PostgreSQL and distributed systems experience.",
            match_score=91,
            decision="REVIEW",
            why=["Python", "Backend"],
            gaps=["PostgreSQL"],
        )

        async def job_loader(user_id: str, job_id: str) -> ResumeIntelligenceJobContext | None:
            return job

        async def resume_loader(user_id: str) -> list[ResumeDocument]:
            return []

        service = ResumeIntelligenceService(
            knowledge=self.knowledge,
            job_loader=job_loader,
            resume_loader=resume_loader,
        )

        analysis = await service.analyze_job("user-1", "job-2")

        self.assertIsNotNone(analysis)
        assert analysis is not None
        self.assertEqual(analysis.selection.status, "no_resumes")
        self.assertEqual(analysis.selection.confidence, 0)
        self.assertGreater(len(analysis.gap_analysis.missing_requirements), 0)
        self.assertEqual(analysis.change_set.status, "blocked")
        self.assertEqual(len(analysis.change_set.changes), 0)
        self.assertEqual(analysis.critique.verdict, "blocked")
        self.assertIsNotNone(analysis.evaluation)
        assert analysis.evaluation is not None
        self.assertEqual(analysis.evaluation.status, "fail")
        self.assertLess(analysis.evaluation.score, 70)
        benchmark = evaluate_benchmark_result(
            analysis,
            expectation=ResumeBenchmarkExpectation(
                name="missing-resume-library",
                expected_selection_status="no_resumes",
                expected_change_set_status="blocked",
                expected_critique_verdict="blocked",
                min_score=0,
                allowed_scorecard_statuses=("fail",),
            ),
        )
        self.assertTrue(benchmark.passed, msg="; ".join(benchmark.failures))

    async def test_no_change_outcome_when_resume_already_covers_supported_requirements(self) -> None:
        await self._approve_entity(
            entity_type="project",
            canonical_name="Platform Scheduler",
            content={
                "summary": "Built Python services on Kubernetes and AWS for a distributed scheduling platform.",
                "technologies": ["Python", "Kubernetes", "AWS"],
            },
            excerpt="Built Python services on Kubernetes and AWS for a distributed scheduling platform.",
        )

        job = ResumeIntelligenceJobContext(
            job_id="job-3",
            user_id="user-1",
            company="Linear",
            title="Senior Backend Engineer",
            location="Remote",
            remote_policy="Remote",
            apply_url="https://example.com/jobs/3",
            description_text="Looking for Python, Kubernetes, AWS, and distributed systems experience.",
            match_score=96,
            decision="APPLY_NOW",
            why=["Python", "Kubernetes", "AWS", "Distributed Systems"],
            gaps=[],
        )
        resumes = [
            ResumeDocument(
                id="resume-strong",
                user_id="user-1",
                display_name="Backend Resume",
                original_filename="Backend_v7.pdf",
                storage_path="/tmp/resume-strong.pdf",
                mime_type="application/pdf",
                file_size_bytes=1600,
                extracted_text=(
                    "Summary\n"
                    "Senior backend engineer focused on high-scale platform systems.\n\n"
                    "Experience\n"
                    "- Built Python services on Kubernetes and AWS for a distributed scheduling platform.\n\n"
                    "Projects\n"
                    "- Delivered backend systems with distributed infrastructure and observability."
                ),
                extracted_skills=["Python", "Kubernetes", "AWS", "Backend", "Distributed Systems"],
                role_focus="Backend",
                created_at="2026-07-20T00:00:00+00:00",
            )
        ]

        async def job_loader(user_id: str, job_id: str) -> ResumeIntelligenceJobContext | None:
            return job

        async def resume_loader(user_id: str) -> list[ResumeDocument]:
            return resumes

        service = ResumeIntelligenceService(
            knowledge=self.knowledge,
            job_loader=job_loader,
            resume_loader=resume_loader,
        )

        analysis = await service.analyze_job("user-1", "job-3")

        self.assertIsNotNone(analysis)
        assert analysis is not None
        self.assertEqual(len(analysis.gap_analysis.weak_requirements), 0)
        self.assertEqual(len(analysis.gap_analysis.missing_requirements), 0)
        self.assertEqual(analysis.change_set.status, "no_changes_recommended")
        self.assertEqual(len(analysis.change_set.changes), 0)
        self.assertEqual(analysis.critique.verdict, "strong_current_resume")
        self.assertIsNotNone(analysis.evaluation)
        assert analysis.evaluation is not None
        self.assertEqual(analysis.evaluation.status, "pass")
        self.assertGreaterEqual(analysis.evaluation.score, 90)
        benchmark = evaluate_benchmark_result(
            analysis,
            expectation=ResumeBenchmarkExpectation(
                name="strong-existing-resume",
                expected_selection_status="selected",
                expected_change_set_status="no_changes_recommended",
                expected_critique_verdict="strong_current_resume",
                min_score=90,
                allowed_scorecard_statuses=("pass",),
                required_covered_requirements=("Python", "Kubernetes", "AWS", "Distributed Systems"),
                max_blocked_requirements=0,
            ),
        )
        self.assertTrue(benchmark.passed, msg="; ".join(benchmark.failures))

    async def test_finalize_review_generates_versioned_pdf_and_reuses_same_signature(self) -> None:
        await self._approve_entity(
            entity_type="project",
            canonical_name="Payments Platform",
            content={
                "summary": "Built payment APIs with gRPC and Python for a distributed billing platform on AWS.",
                "technologies": ["Python", "AWS", "gRPC"],
            },
            excerpt="Built payment APIs with gRPC and Python for a distributed billing platform on AWS.",
        )

        job = ResumeIntelligenceJobContext(
            job_id="job-finalize",
            user_id="user-1",
            company="Ramp",
            title="Platform Engineer",
            location="New York, NY",
            remote_policy="Hybrid",
            apply_url="https://example.com/jobs/finalize",
            description_text="Looking for Python, AWS, distributed systems, and gRPC platform experience.",
            match_score=95,
            decision="APPLY_NOW",
            why=["Python", "AWS", "Platform"],
            gaps=["gRPC"],
        )
        resumes = [
            ResumeDocument(
                id="resume-platform",
                user_id="user-1",
                display_name="Platform Resume",
                original_filename="Platform_v4.pdf",
                storage_path="/tmp/resume-platform.pdf",
                mime_type="application/pdf",
                file_size_bytes=1400,
                extracted_text=(
                    "Summary\n"
                    "Staff platform engineer building Python APIs and distributed systems.\n\n"
                    "Experience\n"
                    "- Built Python APIs on AWS for backend platform systems."
                ),
                extracted_skills=["Python", "AWS", "Platform", "Distributed Systems"],
                role_focus="Platform",
                created_at="2026-07-20T00:00:00+00:00",
            )
        ]

        async def job_loader(user_id: str, job_id: str) -> ResumeIntelligenceJobContext | None:
            return job

        async def resume_loader(user_id: str) -> list[ResumeDocument]:
            return resumes

        service = ResumeIntelligenceService(
            knowledge=self.knowledge,
            job_loader=job_loader,
            resume_loader=resume_loader,
            version_store=self.version_store,
            version_storage_root=Path(self.temp_dir.name),
        )

        analysis = await service.analyze_job("user-1", "job-finalize")
        self.assertIsNotNone(analysis)
        assert analysis is not None
        grpc_change = next(change for change in analysis.change_set.changes if "gRPC" in change.job_requirements)

        version = await service.finalize_review(
            "user-1",
            "job-finalize",
            reviews=[
                ResumeChangeReviewInput(
                    change_id=grpc_change.change_id,
                    decision="approved",
                    edited_text=grpc_change.suggested_text,
                )
            ],
        )

        self.assertEqual(version.status, "generated")
        self.assertTrue(Path(version.pdf_storage_path).exists())
        self.assertTrue(Path(version.text_storage_path).exists())
        rendered_text = Path(version.text_storage_path).read_text(encoding="utf-8")
        self.assertIn("Summary", rendered_text)
        self.assertIn("Experience", rendered_text)
        self.assertIn("gRPC", rendered_text)

        content = await service.get_version_content(version.version_id, user_id="user-1")
        self.assertIsNotNone(content)
        assert content is not None
        self.assertEqual(content["mime_type"], "application/pdf")
        self.assertGreater(len(str(content["content_base64"])), 50)
        self.assertIn("evaluation", version.metadata)
        self.assertIsNotNone(version.metadata["evaluation"])

        duplicate = await service.finalize_review(
            "user-1",
            "job-finalize",
            reviews=[
                ResumeChangeReviewInput(
                    change_id=grpc_change.change_id,
                    decision="approved",
                    edited_text=grpc_change.suggested_text,
                )
            ],
        )
        self.assertEqual(duplicate.version_id, version.version_id)


if __name__ == "__main__":
    unittest.main()
