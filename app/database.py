from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL

Params = Mapping[str, Any] | Sequence[Any] | None


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=2)


def fetch_one(sql: str, params: Params = None) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row is not None else None


def fetch_all(sql: str, params: Params = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]


def execute(sql: str, params: Params = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount


def execute_many(sql: str, params_seq: Iterable[Params]) -> int:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(sql, params_seq)
            return cursor.rowcount
