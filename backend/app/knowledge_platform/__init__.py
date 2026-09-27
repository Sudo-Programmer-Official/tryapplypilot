from app.domain import KnowledgeEntityVersion

from .events import KnowledgeDomainEvent
from .errors import KnowledgeChangeConflictError, KnowledgeEntityNotFoundError, KnowledgeEvidenceError, KnowledgePlatformError
from .health import build_health_report
from .ingestion import (
    ExtractedKnowledgeItem,
    ResumeIngestionResult,
    ResumeSection,
    compute_knowledge_completeness,
    extract_resume_items,
    ingest_resume_into_knowledge_platform,
    parse_resume_sections,
    sync_profile_snapshot_to_knowledge_platform,
)
from .interfaces import KnowledgePlatformStore
from .linking import LinkResolution, normalize_alias, resolve_entity_alias
from .merge import MergeDecision, classify_merge_change
from .queries import compute_knowledge_completeness_report
from .schema_version import KNOWLEDGE_SCHEMA_VERSION
from .sdk import KnowledgePlatformClient, build_knowledge_platform_client
from .services import KnowledgePlatformService, build_knowledge_platform_service
from .store import InMemoryKnowledgePlatformStore, PostgresKnowledgePlatformStore

__all__ = [
    "KnowledgeChangeConflictError",
    "ExtractedKnowledgeItem",
    "InMemoryKnowledgePlatformStore",
    "KNOWLEDGE_SCHEMA_VERSION",
    "KnowledgeDomainEvent",
    "LinkResolution",
    "MergeDecision",
    "KnowledgeEntityNotFoundError",
    "KnowledgeEntityVersion",
    "KnowledgeEvidenceError",
    "KnowledgePlatformError",
    "KnowledgePlatformService",
    "KnowledgePlatformStore",
    "PostgresKnowledgePlatformStore",
    "ResumeIngestionResult",
    "ResumeSection",
    "KnowledgePlatformClient",
    "build_knowledge_platform_client",
    "build_knowledge_platform_service",
    "build_health_report",
    "classify_merge_change",
    "compute_knowledge_completeness",
    "compute_knowledge_completeness_report",
    "extract_resume_items",
    "ingest_resume_into_knowledge_platform",
    "normalize_alias",
    "parse_resume_sections",
    "resolve_entity_alias",
    "sync_profile_snapshot_to_knowledge_platform",
]
