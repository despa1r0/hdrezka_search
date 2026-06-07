from __future__ import annotations

from typing import Any

from app.config import APP_USERS
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


def ensure_app_users() -> None:
    users = _parse_app_users(APP_USERS)
    if not users:
        users = [("test1", "test1"), ("test2", "test2")]

    values_sql = ", ".join(["(%s, %s)"] * len(users))
    params: list[str] = []
    for username, display_name in users:
        params.extend([username, display_name])

    execute(
        f"""
        INSERT INTO users (username, display_name)
        VALUES {values_sql}
        ON CONFLICT (username) DO UPDATE SET
            display_name = EXCLUDED.display_name
        """,
        params,
    )


def replace_app_users() -> None:
    users = _parse_app_users(APP_USERS)
    if not users:
        raise ValueError("APP_USERS must contain at least one user")

    execute("DELETE FROM users")
    ensure_app_users()


def _parse_app_users(value: str) -> list[tuple[str, str]]:
    users: list[tuple[str, str]] = []
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        username, separator, display_name = item.partition(":")
        username = username.strip()
        display_name = display_name.strip() if separator else username
        if username:
            users.append((username, display_name or username))
    return users
