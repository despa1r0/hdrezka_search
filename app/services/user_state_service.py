from __future__ import annotations

from app.database import execute

VALID_STATES = {"seen", "hidden", "favorite", "watchlist"}


def set_movie_state(user_id: int, movie_id: int, state: str) -> None:
    _validate_state(state)
    execute(
        """
        INSERT INTO user_movie_state (user_id, movie_id, state)
        VALUES (%(user_id)s, %(movie_id)s, %(state)s)
        ON CONFLICT (user_id, movie_id, state) DO UPDATE SET
            updated_at = now()
        """,
        {"user_id": user_id, "movie_id": movie_id, "state": state},
    )


def remove_movie_state(user_id: int, movie_id: int, state: str) -> None:
    _validate_state(state)
    execute(
        """
        DELETE FROM user_movie_state
        WHERE user_id = %(user_id)s
          AND movie_id = %(movie_id)s
          AND state = %(state)s
        """,
        {"user_id": user_id, "movie_id": movie_id, "state": state},
    )


def apply_movie_state(user_id: int, movie_id: int, state: str, action: str) -> None:
    if action == "set":
        set_movie_state(user_id, movie_id, state)
        return
    if action == "remove":
        remove_movie_state(user_id, movie_id, state)
        return
    raise ValueError("action must be 'set' or 'remove'")


def _validate_state(state: str) -> None:
    if state not in VALID_STATES:
        raise ValueError(f"Unknown movie state: {state}")
