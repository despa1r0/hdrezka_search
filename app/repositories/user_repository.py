from __future__ import annotations

from typing import Any

from app.config import APP_USERS
from app.database import execute, fetch_all, fetch_one, get_connection


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


def rename_existing_users_from_app_users() -> list[dict[str, Any]]:
    users = _parse_app_users(APP_USERS)
    if not users:
        raise ValueError("APP_USERS must contain at least one user")
    if len({username for username, _ in users}) != len(users):
        raise ValueError("APP_USERS contains duplicate usernames")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, display_name
                FROM users
                ORDER BY id
                """
            )
            existing = [dict(row) for row in cursor.fetchall()]
            if len(existing) != len(users):
                raise ValueError(
                    "APP_USERS count must match existing users count for safe rename "
                    f"({len(users)} APP_USERS, {len(existing)} existing users)"
                )

            for row in existing:
                cursor.execute(
                    """
                    UPDATE users
                    SET username = %(username)s
                    WHERE id = %(id)s
                    """,
                    {
                        "id": row["id"],
                        "username": f"__renaming_user_{row['id']}",
                    },
                )

            renamed: list[dict[str, Any]] = []
            for row, (username, display_name) in zip(existing, users):
                cursor.execute(
                    """
                    UPDATE users
                    SET username = %(username)s,
                        display_name = %(display_name)s
                    WHERE id = %(id)s
                    RETURNING id, username, display_name
                    """,
                    {
                        "id": row["id"],
                        "username": username,
                        "display_name": display_name,
                    },
                )
                updated = cursor.fetchone()
                if updated is not None:
                    renamed.append(dict(updated))
            return renamed


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
