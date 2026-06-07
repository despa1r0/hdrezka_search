from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.repositories.user_repository import get_user_by_username
from app.services.query_hash_service import build_query_hash
from app.services.search_service import SearchService
from app.services.user_state_service import apply_movie_state, set_movie_state
from tests_local.reset_test_db import main as reset_db
from tests_local.seed_test_data import main as seed_db


def assert_titles(items: list[dict], expected: list[str]) -> None:
    titles = [item["title"] for item in items]
    assert titles == expected, f"expected {expected}, got {titles}"


def search(service: SearchService, **params: str) -> list[dict]:
    status, payload = service.search({key: str(value) for key, value in params.items()})
    assert status == 200, payload
    return payload["items"]


def main() -> None:
    reset_db()
    seed_db()

    user1 = get_user_by_username("test1")
    user2 = get_user_by_username("test2")
    assert user1 and user2

    service = SearchService()
    user1_id = str(user1["id"])
    user2_id = str(user2["id"])

    items = search(
        service,
        user_id=user1_id,
        include_genres="Фантастика, Драмы",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
    )
    assert_titles(items, ["Фантастика A"])

    items = search(
        service,
        user_id=user1_id,
        include_genres="Фантастика",
        ban_genres="Ужасы, Комедии",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
    )
    assert "Фантастика F" not in [item["title"] for item in items]
    assert "Фантастика E" not in [item["title"] for item in items]

    items = search(
        service,
        user_id=user1_id,
        include_countries="США, Великобритания",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
    )
    assert_titles(items, ["Фантастика D"])

    items = search(
        service,
        user_id=user1_id,
        include_genres="Фантастика",
        ban_countries="Франция, Япония",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
    )
    assert "Фантастика E" not in [item["title"] for item in items]

    items = search(
        service,
        user_id=user1_id,
        include_genres="Фантастика",
        min_imdb="8.0",
        max_imdb="8.6",
        sort_mode="asc",
        limit="10",
        exclude_seen="0",
    )
    assert_titles(items, ["Фантастика D", "Фантастика C"])

    hash_a = build_query_hash({"query": "Фантастика", "limit": 1, "sort_mode": "desc"})
    hash_b = build_query_hash({"query": "Фантастика", "limit": 20, "sort_mode": "desc"})
    assert hash_a == hash_b

    reset_db()
    seed_db()
    user1 = get_user_by_username("test1")
    user2 = get_user_by_username("test2")
    assert user1 and user2
    user1_id = str(user1["id"])
    user2_id = str(user2["id"])

    first = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="5",
    )
    assert_titles(
        first,
        ["Фантастика A", "Фантастика B", "Фантастика C", "Фантастика D", "Фантастика E"],
    )

    second = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="5",
    )
    assert_titles(second, ["Фантастика F"])

    other_user = search(
        service,
        user_id=user2_id,
        query="фантастика",
        sort_mode="desc",
        limit="5",
    )
    assert_titles(
        other_user,
        ["Фантастика A", "Фантастика B", "Фантастика C", "Фантастика D", "Фантастика E"],
    )

    hidden_movie_id = first[0]["movieId"]
    seen_movie_id = first[1]["movieId"]
    favorite_movie_id = first[2]["movieId"]
    set_movie_state(int(user1_id), int(hidden_movie_id), "hidden")
    set_movie_state(int(user1_id), int(hidden_movie_id), "favorite")
    set_movie_state(int(user1_id), int(seen_movie_id), "seen")
    set_movie_state(int(user1_id), int(favorite_movie_id), "favorite")

    user1_visible = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
    )
    assert "Фантастика A" not in [item["title"] for item in user1_visible]
    assert "Фантастика B" not in [item["title"] for item in user1_visible]

    user1_with_seen = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
        include_seen="1",
    )
    assert "Фантастика A" not in [item["title"] for item in user1_with_seen]
    seen_item = next(item for item in user1_with_seen if item["title"] == "Фантастика B")
    assert seen_item["isSeen"] is True
    assert "seen" in seen_item["states"]

    user1_seen = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="10",
        state_filter="seen",
    )
    assert_titles(user1_seen, ["Фантастика B"])
    assert user1_seen[0]["isSeen"] is True

    user1_favorites = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="10",
        state_filter="favorite",
    )
    assert_titles(user1_favorites, ["Фантастика C"])
    assert user1_favorites[0]["isFavorite"] is True

    apply_movie_state(int(user1_id), int(favorite_movie_id), "favorite", "remove")
    user1_favorites_after_remove = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="10",
        state_filter="favorite",
    )
    assert_titles(user1_favorites_after_remove, [])

    apply_movie_state(int(user1_id), int(seen_movie_id), "seen", "remove")
    user1_seen_after_remove = search(
        service,
        user_id=user1_id,
        query="фантастика",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
    )
    assert "Фантастика B" in [item["title"] for item in user1_seen_after_remove]

    user2_visible = search(
        service,
        user_id=user2_id,
        query="фантастика",
        sort_mode="desc",
        limit="10",
        exclude_seen="0",
    )
    assert "Фантастика A" in [item["title"] for item in user2_visible]

    print("All search logic checks passed.")


if __name__ == "__main__":
    main()
