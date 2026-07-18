from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json

from app.config import AppSettings, get_settings
from app.connectors.base import NormalizedJobRecord
from app.http import HttpClientError, HttpTlsSettings, request_json
from app.preferences import build_profile_text

KEYWORD_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Python", ("python",)),
    ("Backend", ("backend", "api", "service", "microservice")),
    ("Platform", ("platform",)),
    ("Infrastructure", ("infrastructure", "infra", "reliability", "sre")),
    ("Distributed Systems", ("distributed", "scalability", "high scale")),
    ("AI", (" ai ", "artificial intelligence", "genai", "generative ai")),
    ("LLMs", ("llm", "large language", "foundation model")),
    ("Agents", ("agent", "agents", "agentic")),
    ("ML Platform", ("ml platform", "machine learning platform", "mlops")),
    ("Remote", ("remote",)),
    ("Hybrid", ("hybrid",)),
)

DEFAULT_GAP_LABELS = (
    "Backend",
    "Platform",
    "Infrastructure",
    "Distributed Systems",
    "AI",
    "LLMs",
    "Agents",
    "ML Platform",
)


@dataclass(frozen=True)
class MatchResult:
    score: int
    decision: str
    top_strengths: list[str]
    gaps: list[str]
    recommended_resume: str
    provider: str


def _decision_for_score(score: int, settings: AppSettings) -> str:
    if score >= settings.radar.apply_now_threshold_score:
        return "APPLY_NOW"
    if score >= settings.radar.review_threshold_score:
        return "REVIEW"
    return "IGNORE"


def _recommended_resume(matched_labels: list[str], settings: AppSettings) -> str:
    variants = list(settings.radar.resume_variants)
    if not variants:
        return "General_Backend_Resume"
    if any(label in {"AI", "LLMs", "Agents", "ML Platform"} for label in matched_labels):
        for variant in variants:
            if "ai" in variant.casefold():
                return variant
    if any(label in {"Platform", "Infrastructure"} for label in matched_labels):
        for variant in variants:
            if "platform" in variant.casefold():
                return variant
    if any(label == "Distributed Systems" for label in matched_labels):
        for variant in variants:
            if "distributed" in variant.casefold():
                return variant
    return variants[0]


def heuristic_score_job(job: NormalizedJobRecord, settings: AppSettings) -> MatchResult:
    haystack = f" {job.title} {job.location} {job.remote_policy} {job.description_text} ".casefold()
    matched_labels: list[str] = []
    for label, keywords in KEYWORD_MAP:
        if any(keyword in haystack for keyword in keywords):
            matched_labels.append(label)
    matched_labels = matched_labels[:4]

    score = 55 + len(matched_labels) * 9
    if job.remote_policy == "Remote" and any(value.casefold() == "remote" for value in settings.radar.preferred_work_arrangements):
        score += 4
    if job.remote_policy == "Hybrid" and any(value.casefold() == "hybrid" for value in settings.radar.preferred_work_arrangements):
        score += 2
    score = min(score, 99)
    gaps = [
        label
        for label in DEFAULT_GAP_LABELS
        if label not in matched_labels
    ][:3]
    return MatchResult(
        score=score,
        decision=_decision_for_score(score, settings),
        top_strengths=matched_labels or ["General backend overlap"],
        gaps=gaps,
        recommended_resume=_recommended_resume(matched_labels, settings),
        provider="heuristic",
    )


def _extract_output_text(payload: dict[str, object]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text
    output = payload.get("output", [])
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content_items = item.get("content", [])
            if not isinstance(content_items, list):
                continue
            for content in content_items:
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text
                if isinstance(text, dict):
                    value = text.get("value")
                    if isinstance(value, str) and value.strip():
                        return value
    raise HttpClientError("OpenAI response did not include output text.")


def _normalize_resume_choice(choice: str, settings: AppSettings, fallback: str) -> str:
    for variant in settings.radar.resume_variants:
        if choice.casefold() == variant.casefold():
            return variant
    return fallback


def _request_openai_match(
    job: NormalizedJobRecord,
    settings: AppSettings,
    heuristic: MatchResult,
    *,
    profile_text: str | None = None,
) -> MatchResult:
    resolved_profile_text = (profile_text or "").strip() or build_profile_text(settings)
    body = {
        "model": settings.openai.model,
        "store": False,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You score job descriptions against a candidate profile for job search triage. "
                            "Return only structured JSON that follows the schema."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"Candidate profile:\n{resolved_profile_text}\n\n"
                            f"Preferred roles: {', '.join(settings.radar.target_roles)}\n"
                            f"Allowed resume variants: {', '.join(settings.radar.resume_variants)}\n\n"
                            f"Job company: {job.company}\n"
                            f"Job title: {job.title}\n"
                            f"Job location: {job.location}\n"
                            f"Remote policy: {job.remote_policy}\n"
                            f"Job description:\n{job.description_text}\n\n"
                            "Return a strict score from 0 to 100."
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "job_match",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "decision": {"type": "string", "enum": ["APPLY_NOW", "REVIEW", "IGNORE"]},
                        "top_strengths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": 5,
                        },
                        "gaps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 5,
                        },
                        "recommended_resume": {
                            "type": "string",
                            "enum": list(settings.radar.resume_variants),
                        },
                    },
                    "required": [
                        "score",
                        "decision",
                        "top_strengths",
                        "gaps",
                        "recommended_resume",
                    ],
                },
            }
        },
    }
    payload = request_json(
        "POST",
        f"{settings.openai.api_base_url.rstrip('/')}/responses",
        timeout_seconds=settings.openai.timeout_seconds,
        tls=HttpTlsSettings(
            ca_bundle_path=settings.openai.ca_bundle_path,
            skip_ssl_verify=settings.openai.skip_ssl_verify,
        ),
        headers={"Authorization": f"Bearer {settings.openai.api_key}"},
        body=body,
    )
    structured = json.loads(_extract_output_text(payload))
    score = int(structured["score"])
    normalized_score = max(0, min(100, score))
    return MatchResult(
        score=normalized_score,
        decision=structured.get("decision") or _decision_for_score(normalized_score, settings),
        top_strengths=list(structured.get("top_strengths", heuristic.top_strengths))[:5],
        gaps=list(structured.get("gaps", heuristic.gaps))[:5],
        recommended_resume=_normalize_resume_choice(
            str(structured.get("recommended_resume", heuristic.recommended_resume)),
            settings,
            heuristic.recommended_resume,
        ),
        provider="openai",
    )


async def score_job(
    job: NormalizedJobRecord,
    settings: AppSettings | None = None,
    *,
    prefer_openai: bool = True,
    profile_text: str | None = None,
) -> MatchResult:
    resolved_settings = settings or get_settings()
    heuristic = heuristic_score_job(job, resolved_settings)
    minimum_openai_score = max(resolved_settings.radar.review_threshold_score - 10, 60)
    if not prefer_openai or not resolved_settings.openai.enabled or heuristic.score < minimum_openai_score:
        return heuristic

    try:
        return await asyncio.to_thread(
            _request_openai_match,
            job,
            resolved_settings,
            heuristic,
            profile_text=profile_text,
        )
    except Exception:  # noqa: BLE001
        return heuristic
