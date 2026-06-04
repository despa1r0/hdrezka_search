from __future__ import annotations

from app.database import execute_many, fetch_all


def mark_as_shown(user_id: int, query_hash: str, movie_ids: list[int]) -> None:
    if not movie_ids:
        return
    execute_many(
        """
        INSERT INTO shown_items (user_id, movie_id, query_hash)
        VALUES (%(user_id)s, %(movie_id)s, %(query_hash)s)
        ON CONFLICT (user_id, movie_id, query_hash) DO NOTHING
        """,
        [
            {"user_id": user_id, "movie_id": movie_id, "query_hash": query_hash}
            for movie_id in movie_ids
        ],
    )


def get_shown_movie_ids(user_id: int, query_hash: str) -> set[int]:
    rows = fetch_all(
        """
        SELECT movie_id
        FROM shown_items
        WHERE user_id = %(user_id)s AND query_hash = %(query_hash)s
        """,
        {"user_id": user_id, "query_hash": query_hash},
    )
    return {int(row["movie_id"]) for row in rows}
