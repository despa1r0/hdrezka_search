from __future__ import annotations

from typing import Any

from app.database import execute, fetch_all, fetch_one


def get_all_users() -> list[dict[str, Any]]:
    return fetch_all(
        """
        SELECT id, username, display_name
        FROM users
        ORDER BY username
        """
    )


def get_user_by_username(username: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT id, username, display_name
        FROM users
        WHERE username = %(username)s
        """,
        {"username": username},
    )


def ensure_test_users() -> None:
    execute(
        """
        INSERT INTO users (username, display_name)
        VALUES ('test1', 'test1'), ('test2', 'test2')
        ON CONFLICT (username) DO NOTHING
        """
    )
