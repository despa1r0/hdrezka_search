from __future__ import annotations

from typing import Any

from app.database import execute, execute_many, fetch_one


MOVIE_COLUMNS = (
    "rezka_url",
    "title_ru",
    "title_original",
    "year",
    "content_type",
    "imdb_id",
    "imdb_rating",
    "imdb_match_confidence",
    "poster_url",
    "description",
    "source_catalog",
)


def get_movie_by_rezka_url(rezka_url: str) -> dict[str, Any] | None:
    return fetch_one(
        """
        SELECT *
        FROM movies
        WHERE rezka_url = %(rezka_url)s
        """,
        {"rezka_url": rezka_url},
    )


def upsert_movie(movie: dict[str, Any]) -> int:
    values = {column: movie.get(column) for column in MOVIE_COLUMNS}
    row = fetch_one(
        """
        INSERT INTO movies (
            rezka_url,
            title_ru,
            title_original,
            year,
            content_type,
            imdb_id,
            imdb_rating,
            imdb_match_confidence,
            poster_url,
            description,
            source_catalog
        )
        VALUES (
            %(rezka_url)s,
            %(title_ru)s,
            %(title_original)s,
            %(year)s,
            %(content_type)s,
            %(imdb_id)s,
            %(imdb_rating)s,
            %(imdb_match_confidence)s,
            %(poster_url)s,
            %(description)s,
            %(source_catalog)s
        )
        ON CONFLICT (rezka_url) DO UPDATE SET
            title_ru = EXCLUDED.title_ru,
            title_original = EXCLUDED.title_original,
            year = EXCLUDED.year,
            content_type = EXCLUDED.content_type,
            imdb_id = EXCLUDED.imdb_id,
            imdb_rating = EXCLUDED.imdb_rating,
            imdb_match_confidence = EXCLUDED.imdb_match_confidence,
            poster_url = EXCLUDED.poster_url,
            description = EXCLUDED.description,
            source_catalog = EXCLUDED.source_catalog,
            updated_at = now()
        RETURNING id
        """,
        values,
    )
    if row is None:
        raise RuntimeError("Movie upsert did not return id")
    return int(row["id"])


def replace_movie_genres(movie_id: int, genres: list[str]) -> None:
    execute("DELETE FROM movie_genres WHERE movie_id = %(movie_id)s", {"movie_id": movie_id})
    clean = _clean_values(genres)
    if clean:
        execute_many(
            """
            INSERT INTO movie_genres (movie_id, genre)
            VALUES (%(movie_id)s, %(genre)s)
            ON CONFLICT DO NOTHING
            """,
            [{"movie_id": movie_id, "genre": genre} for genre in clean],
        )


def replace_movie_countries(movie_id: int, countries: list[str]) -> None:
    execute(
        "DELETE FROM movie_countries WHERE movie_id = %(movie_id)s",
        {"movie_id": movie_id},
    )
    clean = _clean_values(countries)
    if clean:
        execute_many(
            """
            INSERT INTO movie_countries (movie_id, country)
            VALUES (%(movie_id)s, %(country)s)
            ON CONFLICT DO NOTHING
            """,
            [{"movie_id": movie_id, "country": country} for country in clean],
        )


def upsert_movie_with_relations(movie: dict[str, Any]) -> int:
    movie_id = upsert_movie(movie)
    replace_movie_genres(movie_id, movie.get("genres") or [])
    replace_movie_countries(movie_id, movie.get("countries") or [])
    return movie_id


def _clean_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    clean: list[str] = []
    for value in values:
        item = str(value).strip()
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            clean.append(item)
    return clean
