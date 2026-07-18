from __future__ import annotations

from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=1)
def load_schema_sql() -> str:
    schema_path = get_settings().database.schema_path
    return schema_path.read_text(encoding="utf-8")

