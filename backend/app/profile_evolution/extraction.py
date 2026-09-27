from __future__ import annotations

import re

from .conversation import ExtractedFactCandidate

_TECH_PATTERNS: dict[str, tuple[str, ...]] = {
    "Kubernetes": ("kubernetes", "k8s"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "GCP": ("gcp", "google cloud"),
    "PostgreSQL": ("postgres", "postgresql"),
    "SQL Server": ("sql server", "ms sql", "microsoft sql server"),
    "Redis": ("redis",),
    "Kafka": ("kafka",),
    "Python": ("python",),
    "FastAPI": ("fastapi",),
    "Docker": ("docker",),
    "gRPC": ("grpc",),
}

_LEADERSHIP_PATTERN = re.compile(r"\b(led|managed|mentored|owned|directed|guided|coached)\b", re.IGNORECASE)
_METRIC_PATTERN = re.compile(r"(\d[\d,]*\+?\s*(?:users|requests|jobs|engineers|transactions|ms|seconds|minutes|hours|percent|%))", re.IGNORECASE)


def _first_metric(answer: str) -> str | None:
    match = _METRIC_PATTERN.search(answer)
    return match.group(1).strip() if match else None


def _project_name(answer: str) -> str:
    match = re.search(r"(?:called|named)\s+([A-Z][A-Za-z0-9 _-]{2,80})", answer)
    if match:
        return match.group(1).strip()
    return "Largest System Project"


def _cloud(answer: str) -> str | None:
    lowered = answer.casefold()
    for canonical_name, aliases in _TECH_PATTERNS.items():
        if canonical_name not in {"AWS", "Azure", "GCP", "Kubernetes"}:
            continue
        if any(alias in lowered for alias in aliases):
            return canonical_name
    return None


def _database(answer: str) -> str | None:
    lowered = answer.casefold()
    for canonical_name, aliases in _TECH_PATTERNS.items():
        if canonical_name not in {"PostgreSQL", "SQL Server", "Redis"}:
            continue
        if any(alias in lowered for alias in aliases):
            return canonical_name
    return None


def _technologies(answer: str) -> list[str]:
    lowered = answer.casefold()
    detected: list[str] = []
    for canonical_name, aliases in _TECH_PATTERNS.items():
        if any(alias in lowered for alias in aliases):
            detected.append(canonical_name)
    return detected


def extract_facts_from_answer(
    *,
    topic: str,
    answer: str,
    existing_fields: dict[str, object],
) -> list[ExtractedFactCandidate]:
    stripped = " ".join(answer.split()).strip()
    if not stripped:
        return []
    candidates: list[ExtractedFactCandidate] = []
    project_name = str(existing_fields.get("project_name") or _project_name(answer))
    techs = _technologies(answer)
    detected_fields: dict[str, object] = {"project_name": project_name}
    metric = _first_metric(stripped)
    cloud = _cloud(stripped)
    database = _database(stripped)
    if cloud:
        detected_fields["cloud"] = cloud
    if database:
        detected_fields["database"] = database
    if metric:
        if "ms" in metric.casefold():
            detected_fields["latency"] = metric
        else:
            detected_fields["scale"] = metric
            detected_fields["traffic"] = metric
    lowered = stripped.casefold()
    if "role" not in existing_fields and any(token in lowered for token in ("i built", "i designed", "i led", "i migrated", "i owned")):
        detected_fields["role"] = stripped
    if "problem" not in existing_fields:
        detected_fields["problem"] = stripped
    if "outcome" not in existing_fields and metric:
        detected_fields["outcome"] = stripped
    if topic == "architecture":
        detected_fields["architecture"] = stripped
    if topic == "leadership" and _LEADERSHIP_PATTERN.search(stripped):
        detected_fields["leadership_scope"] = stripped
    if topic == "mentoring" and any(token in lowered for token in ("mentor", "mentored", "coached", "guided")):
        detected_fields["mentoring_scope"] = stripped
    if topic == "ai_ml" and any(token in lowered for token in ("ai", "machine learning", "model", "llm", "rag", "agent")):
        detected_fields["ai_problem"] = stripped
        detected_fields["model_or_workflow"] = stripped
    if topic == "business_impact" and any(token in lowered for token in ("revenue", "customer", "cost", "adoption", "conversion")):
        detected_fields["business_impact"] = stripped
        detected_fields["customer_or_revenue"] = stripped

    candidates.append(
        ExtractedFactCandidate(
            topic=topic,
            entity_type="project",
            canonical_name=project_name,
            content={"topic": topic, **detected_fields, "text": stripped, "technologies": techs},
            reason=f"Conversation answer enriched the {topic} story for a major project.",
            confidence=0.86,
            extracted_fields=detected_fields,
        )
    )
    for technology in techs:
        candidates.append(
            ExtractedFactCandidate(
                topic=topic,
                entity_type="technology",
                canonical_name=technology,
                content={"label": technology, "source_topic": topic},
                reason=f"Conversation answer referenced {technology}.",
                confidence=0.9,
                extracted_fields={technology.casefold(): technology},
            )
        )
    if _LEADERSHIP_PATTERN.search(stripped):
        candidates.append(
            ExtractedFactCandidate(
                topic=topic,
                entity_type="leadership",
                canonical_name=stripped[:100],
                content={"topic": topic, "text": stripped},
                reason="Conversation answer suggested leadership ownership.",
                confidence=0.78,
                extracted_fields={"leadership_scope": stripped},
            )
        )
    if metric:
        candidates.append(
            ExtractedFactCandidate(
                topic=topic,
                entity_type="achievement",
                canonical_name=stripped[:100],
                content={"topic": topic, "text": stripped, "metric": metric},
                reason="Conversation answer contained a quantified result.",
                confidence=0.8,
                extracted_fields={"metric": metric},
            )
        )
    return candidates
