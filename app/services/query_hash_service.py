from __future__ import annotations

import hashlib
import json
from typing import Any

from app.utils.text import normalize, split_csv

HASH_FIELDS = (
    "query",
    "include_genres",
    "ban_genres",
    "include_countries",
    "ban_countries",
    "min_imdb",
    "max_imdb",
    "content_type",
    "sort_mode",
)


def build_query_hash(filters: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    for field in HASH_FIELDS:
        value = filters.get(field)
        if field in {
            "include_genres",
            "ban_genres",
            "include_countries",
            "ban_countries",
        }:
            values = value if isinstance(value, list) else split_csv(str(value or ""))
            payload[field] = sorted({normalize(item) for item in values if str(item).strip()})
        elif value is None:
            payload[field] = None
        else:
            payload[field] = normalize(str(value))

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
