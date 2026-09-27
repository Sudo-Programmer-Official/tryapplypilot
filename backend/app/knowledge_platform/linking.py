from __future__ import annotations

from dataclasses import dataclass
import re

from app.domain import KnowledgeEntityType

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_COMPANY_SUFFIX_PATTERN = re.compile(r"\b(?:corp(?:oration)?|inc(?:orporated)?|llc|ltd|co|company)\b", re.IGNORECASE)

_DEFAULT_ALIASES: dict[KnowledgeEntityType, dict[str, str]] = {
    "technology": {
        "python": "Python",
        "typescript": "TypeScript",
        "javascript": "JavaScript",
        "node": "Node.js",
        "node js": "Node.js",
        "nodejs": "Node.js",
        "react": "React",
        "reactjs": "React",
        "react js": "React",
        "postgres": "PostgreSQL",
        "postgresql": "PostgreSQL",
        "sql server": "SQL Server",
        "microsoft sql server": "SQL Server",
        "ms sql": "SQL Server",
        "fastapi": "FastAPI",
        "kubernetes": "Kubernetes",
        "k8s": "Kubernetes",
        "aws": "AWS",
        "amazon web services": "AWS",
        "azure": "Azure",
        "gcp": "GCP",
        "google cloud": "GCP",
        "docker": "Docker",
        "grpc": "gRPC",
        "golang": "Go",
        "go": "Go",
    },
    "skill": {
        "backend": "Backend",
        "backend engineering": "Backend",
        "distributed systems": "Distributed Systems",
        "platform": "Platform",
        "infrastructure": "Infrastructure",
        "artificial intelligence": "AI",
        "generative ai": "AI",
        "ai": "AI",
        "machine learning": "Machine Learning",
        "mlops": "MLOps",
    },
    "leadership": {
        "leadership": "Leadership",
        "mentorship": "Mentorship",
        "people management": "Leadership",
    },
}


@dataclass(frozen=True)
class LinkResolution:
    entity_type: KnowledgeEntityType
    raw_name: str
    normalized_alias: str
    canonical_name: str
    confidence: float
    source: str


def normalize_alias(value: str) -> str:
    lowered = value.casefold().replace("&", " and ").replace(".js", " js")
    lowered = lowered.replace("/", " ").replace("-", " ")
    lowered = _COMPANY_SUFFIX_PATTERN.sub("", lowered)
    lowered = _NON_ALNUM_PATTERN.sub(" ", lowered)
    return " ".join(lowered.split()).strip()


def resolve_entity_alias(
    entity_type: KnowledgeEntityType,
    raw_name: str,
    *,
    manual_aliases: dict[str, str] | None = None,
) -> LinkResolution:
    cleaned = " ".join(raw_name.split()).strip()
    normalized_alias = normalize_alias(cleaned)
    if manual_aliases and normalized_alias in manual_aliases:
        return LinkResolution(
            entity_type=entity_type,
            raw_name=cleaned,
            normalized_alias=normalized_alias,
            canonical_name=manual_aliases[normalized_alias],
            confidence=1.0,
            source="manual_override",
        )
    alias_table = _DEFAULT_ALIASES.get(entity_type, {})
    if normalized_alias in alias_table:
        canonical_name = alias_table[normalized_alias]
        confidence = 1.0 if normalize_alias(canonical_name) == normalized_alias else 0.99
        return LinkResolution(
            entity_type=entity_type,
            raw_name=cleaned,
            normalized_alias=normalized_alias,
            canonical_name=canonical_name,
            confidence=confidence,
            source="deterministic_alias",
        )
    title_name = cleaned if cleaned else raw_name.strip()
    return LinkResolution(
        entity_type=entity_type,
        raw_name=cleaned,
        normalized_alias=normalized_alias,
        canonical_name=title_name,
        confidence=0.9 if cleaned and cleaned != raw_name else 0.85 if cleaned else 0.0,
        source="normalized_fallback",
    )
