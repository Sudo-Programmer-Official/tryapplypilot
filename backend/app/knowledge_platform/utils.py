from __future__ import annotations

from datetime import datetime, timezone
import json


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def normalize_name(value: str) -> str:
    return " ".join(value.split()).strip()


def content_search_text(canonical_name: str, content: dict[str, object]) -> str:
    return f"{canonical_name} {json.dumps(content, sort_keys=True, ensure_ascii=True)}".casefold()


def json_object(value: object) -> dict[str, object]:
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


def json_list(value: object) -> list[str]:
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
