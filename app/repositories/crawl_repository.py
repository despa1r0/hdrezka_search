from __future__ import annotations

from typing import Any

from psycopg.types.json import Json

from app.database import execute
from app.database import fetch_one


def get_catalog_state(catalog_key: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT catalog_key, last_page, last_movie_url, status, updated_at
        FROM catalog_crawl_state
        WHERE catalog_key = %(catalog_key)s
        """,
        {"catalog_key": catalog_key},
    )


def set_catalog_state(
    catalog_key: str,
    *,
    last_page: int | None = None,
    last_movie_url: str | None = None,
    status: str,
) -> None:
    execute(
        """
        INSERT INTO catalog_crawl_state (
            catalog_key,
            last_page,
            last_movie_url,
            status,
            updated_at
        )
        VALUES (
            %(catalog_key)s,
            COALESCE(%(last_page)s, 0),
            %(last_movie_url)s,
            %(status)s,
            now()
        )
        ON CONFLICT (catalog_key) DO UPDATE SET
            last_page = CASE
                WHEN %(last_page)s IS NULL THEN catalog_crawl_state.last_page
                ELSE EXCLUDED.last_page
            END,
            last_movie_url = COALESCE(EXCLUDED.last_movie_url, catalog_crawl_state.last_movie_url),
            status = EXCLUDED.status,
            updated_at = now()
        """,
        {
            "catalog_key": catalog_key,
            "last_page": last_page,
            "last_movie_url": last_movie_url,
            "status": status,
        },
    )


def log_crawl_event(
    *,
    message: str,
    catalog_key: str | None = None,
    movie_id: int | None = None,
    level: str = "info",
    context: dict[str, Any] | None = None,
) -> None:
    execute(
        """
        INSERT INTO crawl_log (catalog_key, movie_id, level, message, context)
        VALUES (%(catalog_key)s, %(movie_id)s, %(level)s, %(message)s, %(context)s::jsonb)
        """,
        {
            "catalog_key": catalog_key,
            "movie_id": movie_id,
            "level": level,
            "message": message,
            "context": Json(context or {}),
        },
    )
