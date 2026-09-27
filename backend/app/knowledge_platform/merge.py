from __future__ import annotations

from dataclasses import dataclass

from app.domain import KnowledgeEntityType, KnowledgeMergeAction


@dataclass(frozen=True)
class MergeDecision:
    action: KnowledgeMergeAction
    merged_content: dict[str, object]
    changed_fields: list[str]
    conflict_fields: list[str]
    reason: str


_IDENTITY_FIELDS: dict[KnowledgeEntityType, tuple[str, ...]] = {
    "experience": ("role", "company"),
    "project": ("summary",),
    "education": ("school", "degree"),
    "certification": ("issuer", "credential"),
    "achievement": ("text",),
    "leadership": ("text",),
}


def merge_content(existing: dict[str, object], new: dict[str, object]) -> dict[str, object]:
    merged = dict(existing)
    for key, value in new.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        current = merged.get(key)
        if isinstance(current, list) and isinstance(value, list):
            merged[key] = list(dict.fromkeys([*current, *value]))
            continue
        if isinstance(current, dict) and isinstance(value, dict):
            nested = dict(current)
            nested.update({nested_key: nested_value for nested_key, nested_value in value.items() if nested_value not in {None, "", [], {}}})
            merged[key] = nested
            continue
        if current is None:
            merged[key] = value
            continue
        if isinstance(current, str) and not current.strip():
            merged[key] = value
            continue
        if isinstance(current, (list, dict)) and not current:
            merged[key] = value
            continue
        if isinstance(current, str) and isinstance(value, str):
            merged[key] = value if len(value) > len(current) else current
            continue
        merged[key] = value
    return merged


def classify_merge_change(
    entity_type: KnowledgeEntityType,
    *,
    existing_content: dict[str, object] | None,
    incoming_content: dict[str, object],
) -> MergeDecision:
    if existing_content is None:
        return MergeDecision(
            action="added",
            merged_content=incoming_content,
            changed_fields=sorted(incoming_content.keys()),
            conflict_fields=[],
            reason=f"New canonical {entity_type} detected.",
        )
    merged = merge_content(existing_content, incoming_content)
    changed_fields = sorted([key for key in merged.keys() if merged.get(key) != existing_content.get(key)])
    if not changed_fields:
        return MergeDecision(
            action="unchanged",
            merged_content=existing_content,
            changed_fields=[],
            conflict_fields=[],
            reason=f"Incoming {entity_type} did not add new canonical information.",
        )
    conflict_fields: list[str] = []
    for field_name in _IDENTITY_FIELDS.get(entity_type, ()):
        current = existing_content.get(field_name)
        incoming = incoming_content.get(field_name)
        if isinstance(current, str) and isinstance(incoming, str) and current.strip() and incoming.strip():
            if current.casefold() != incoming.casefold():
                conflict_fields.append(field_name)
    if conflict_fields:
        return MergeDecision(
            action="conflict",
            merged_content=merged,
            changed_fields=changed_fields,
            conflict_fields=conflict_fields,
            reason=f"Incoming {entity_type} conflicts on {', '.join(conflict_fields)} and should be reviewed.",
        )
    return MergeDecision(
        action="updated",
        merged_content=merged,
        changed_fields=changed_fields,
        conflict_fields=[],
        reason=f"Incoming {entity_type} enriched canonical knowledge.",
    )
