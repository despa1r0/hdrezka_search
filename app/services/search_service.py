from __future__ import annotations

import time
from http import HTTPStatus
from typing import Any

from app.config import DEFAULT_RESULT_LIMIT, MAX_RESULT_LIMIT
from app.database import fetch_all
from app.debug import debug_log
from app.repositories.shown_repository import mark_as_shown
from app.services.query_hash_service import build_query_hash
from app.utils.text import normalize, parse_rating, split_csv

GENRE_ALIASES = {
    "биография": "Биографии",
    "биографии": "Биографии",
    "боевик": "Боевики",
    "боевики": "Боевики",
    "вестерн": "Вестерны",
    "вестерны": "Вестерны",
    "военный": "Военные",
    "военные": "Военные",
    "детектив": "Детективы",
    "детективы": "Детективы",
    "драма": "Драмы",
    "драмы": "Драмы",
    "исторический": "Исторические",
    "исторические": "Исторические",
    "комедия": "Комедии",
    "комедии": "Комедии",
    "криминал": "Криминал",
    "мелодрама": "Мелодрамы",
    "мелодрамы": "Мелодрамы",
    "приключения": "Приключения",
    "семейный": "Семейные",
    "семейные": "Семейные",
    "триллер": "Триллеры",
    "триллеры": "Триллеры",
    "ужасы": "Ужасы",
    "фантастика": "Фантастика",
    "фэнтези": "Фэнтези",
}


class SearchService:
    def search(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        started = time.perf_counter()
        try:
            options = self._parse_options(params)
        except ValueError as exc:
            return HTTPStatus.BAD_REQUEST, {"error": str(exc)}

        try:
            rows = self._search_rows(options)
            movie_ids = [int(row["id"]) for row in rows]
            mark_as_shown(options["user_id"], options["query_hash"], movie_ids)
        except Exception as exc:
            debug_log(f"db search failed error={exc}", options["debug"])
            return HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": (
                    "PostgreSQL недоступен или схема не применена. "
                    f"Обычный поиск не падает обратно на Rezka/IMDb. Детали: {exc}"
                )
            }

        return HTTPStatus.OK, {
            "query": options["original_query"],
            "queryHash": options["query_hash"],
            "count": len(rows),
            "elapsed": round(time.perf_counter() - started, 2),
            "limit": options["limit"],
            "ratingSource": "IMDb",
            "items": [self._row_to_item(row) for row in rows],
        }

    def _parse_options(self, params: dict[str, str]) -> dict[str, Any]:
        user_id = self._parse_positive_int(params.get("user_id", ""), "user_id")
        query = params.get("query", params.get("q", "")).strip()
        include_genres = self._canonical_genres(split_csv(params.get("include_genres", "")))
        text_query = query

        if query and not include_genres:
            query_genres = self._genres_from_query(query)
            if query_genres:
                include_genres = query_genres
                text_query = ""

        min_imdb, max_imdb = self._parse_rating_bounds(params)
        options = {
            "user_id": user_id,
            "original_query": query,
            "query": text_query,
            "include_genres": include_genres,
            "ban_genres": self._canonical_genres(split_csv(params.get("ban_genres", ""))),
            "include_countries": split_csv(params.get("include_countries", "")),
            "ban_countries": split_csv(params.get("ban_countries", "")),
            "min_imdb": min_imdb,
            "max_imdb": max_imdb,
            "content_type": self._content_type(params.get("content_type", "")),
            "sort_mode": params.get("sort_mode", params.get("sort_order", "desc")).strip().lower(),
            "limit": self._parse_limit(params.get("limit", params.get("max_results", ""))),
            "exclude_seen": self._parse_bool(params.get("exclude_seen", "1")),
            "debug": self._parse_bool(params.get("debug", "")),
        }
        options["query_hash"] = build_query_hash(options)
        return options

    def _search_rows(self, options: dict[str, Any]) -> list[dict[str, Any]]:
        where = ["1 = 1"]
        sql_params: dict[str, Any] = {
            "user_id": options["user_id"],
            "query_hash": options["query_hash"],
            "limit": options["limit"],
        }

        if options["query"]:
            where.append(
                """
                (
                    m.title_ru ILIKE %(query_like)s
                    OR COALESCE(m.title_original, '') ILIKE %(query_like)s
                    OR COALESCE(m.description, '') ILIKE %(query_like)s
                )
                """
            )
            sql_params["query_like"] = f"%{options['query']}%"

        if options["content_type"]:
            where.append("m.content_type = %(content_type)s")
            sql_params["content_type"] = options["content_type"]

        if options["min_imdb"] is not None:
            where.append("m.imdb_rating >= %(min_imdb)s")
            sql_params["min_imdb"] = options["min_imdb"]

        if options["max_imdb"] is not None:
            where.append("m.imdb_rating <= %(max_imdb)s")
            sql_params["max_imdb"] = options["max_imdb"]

        self._append_include_filter(
            where,
            sql_params,
            table="movie_genres",
            column="genre",
            option_name="include_genres",
            values=options["include_genres"],
        )
        self._append_include_filter(
            where,
            sql_params,
            table="movie_countries",
            column="country",
            option_name="include_countries",
            values=options["include_countries"],
        )
        self._append_ban_filter(
            where,
            sql_params,
            table="movie_genres",
            column="genre",
            option_name="ban_genres",
            values=options["ban_genres"],
        )
        self._append_ban_filter(
            where,
            sql_params,
            table="movie_countries",
            column="country",
            option_name="ban_countries",
            values=options["ban_countries"],
        )

        if options["exclude_seen"]:
            where.append(
                """
                NOT EXISTS (
                    SELECT 1
                    FROM shown_items si
                    WHERE si.movie_id = m.id
                      AND si.user_id = %(user_id)s
                      AND si.query_hash = %(query_hash)s
                )
                """
            )

        where.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM user_movie_state ums
                WHERE ums.movie_id = m.id
                  AND ums.user_id = %(user_id)s
                  AND ums.state IN ('seen', 'hidden')
            )
            """
        )

        order_by = self._order_by(options["sort_mode"])
        sql = f"""
            SELECT
                m.id,
                m.rezka_url,
                m.title_ru,
                m.title_original,
                m.year,
                m.content_type,
                m.imdb_rating,
                m.poster_url,
                m.description,
                COALESCE(
                    array_agg(DISTINCT mg.genre) FILTER (WHERE mg.genre IS NOT NULL),
                    '{{}}'
                ) AS genres,
                COALESCE(
                    array_agg(DISTINCT mc.country) FILTER (WHERE mc.country IS NOT NULL),
                    '{{}}'
                ) AS countries
            FROM movies m
            LEFT JOIN movie_genres mg ON mg.movie_id = m.id
            LEFT JOIN movie_countries mc ON mc.movie_id = m.id
            WHERE {" AND ".join(where)}
            GROUP BY m.id
            {order_by}
            LIMIT %(limit)s
        """
        debug_log(f"sql search params={sql_params}", options["debug"])
        return fetch_all(sql, sql_params)

    def _append_include_filter(
        self,
        where: list[str],
        params: dict[str, Any],
        *,
        table: str,
        column: str,
        option_name: str,
        values: list[str],
    ) -> None:
        normalized = self._normalize_list(values)
        if not normalized:
            return
        params[option_name] = normalized
        params[f"{option_name}_count"] = len(normalized)
        where.append(
            f"""
            m.id IN (
                SELECT movie_id
                FROM {table}
                WHERE lower({column}) = ANY(%({option_name})s)
                GROUP BY movie_id
                HAVING COUNT(DISTINCT lower({column})) = %({option_name}_count)s
            )
            """
        )

    def _append_ban_filter(
        self,
        where: list[str],
        params: dict[str, Any],
        *,
        table: str,
        column: str,
        option_name: str,
        values: list[str],
    ) -> None:
        normalized = self._normalize_list(values)
        if not normalized:
            return
        params[option_name] = normalized
        where.append(
            f"""
            NOT EXISTS (
                SELECT 1
                FROM {table} banned
                WHERE banned.movie_id = m.id
                  AND lower(banned.{column}) = ANY(%({option_name})s)
            )
            """
        )

    def _row_to_item(self, row: dict[str, Any]) -> dict[str, Any]:
        rating = float(row["imdb_rating"]) if row["imdb_rating"] is not None else None
        return {
            "id": row["id"],
            "movieId": row["id"],
            "title": row["title_ru"],
            "url": row["rezka_url"],
            "originalTitle": row["title_original"] or "",
            "image": row["poster_url"] or "",
            "category": row["content_type"] or "",
            "contentType": row["content_type"] or "",
            "sourceRating": None,
            "imdbRating": rating,
            "rating": rating,
            "ratingSource": "IMDb" if rating is not None else "",
            "genres": list(row["genres"] or []),
            "countries": list(row["countries"] or []),
            "year": str(row["year"] or ""),
            "description": row["description"] or "",
        }

    def _genres_from_query(self, query: str) -> list[str]:
        parts = split_csv(query)
        if not parts:
            return []
        genres: list[str] = []
        for part in parts:
            genre = GENRE_ALIASES.get(normalize(part))
            if not genre:
                return []
            genres.append(genre)
        return genres

    def _canonical_genres(self, values: list[str]) -> list[str]:
        return [GENRE_ALIASES.get(normalize(value), value.strip()) for value in values if value.strip()]

    def _parse_rating_bounds(self, params: dict[str, str]) -> tuple[float | None, float | None]:
        min_imdb = parse_rating(params.get("min_imdb", params.get("min_rating", "")))
        max_imdb = parse_rating(params.get("max_imdb", params.get("max_rating", "")))
        rating_range = params.get("rating_range", "").strip()

        if rating_range and (min_imdb is None and max_imdb is None):
            parts = [part for part in rating_range.replace(",", ".").split("-") if part.strip()]
            ratings = [parse_rating(part) for part in parts]
            ratings = [rating for rating in ratings if rating is not None]
            if len(ratings) >= 2:
                return min(ratings), max(ratings)
            if len(ratings) == 1:
                return ratings[0], None

        return min_imdb, max_imdb

    def _parse_limit(self, value: str) -> int:
        try:
            requested = int(value)
        except (TypeError, ValueError):
            requested = DEFAULT_RESULT_LIMIT
        return max(1, min(requested, MAX_RESULT_LIMIT))

    def _parse_positive_int(self, value: str, field_name: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} is required") from exc
        if parsed <= 0:
            raise ValueError(f"{field_name} must be positive")
        return parsed

    def _parse_bool(self, value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _content_type(self, value: str) -> str:
        clean = value.strip().lower()
        return "" if clean in {"", "all", "any"} else clean

    def _normalize_list(self, values: list[str]) -> list[str]:
        return sorted({normalize(value) for value in values if value.strip()})

    def _order_by(self, sort_mode: str) -> str:
        if sort_mode == "asc":
            return "ORDER BY m.imdb_rating ASC NULLS LAST, m.title_ru ASC"
        if sort_mode == "title":
            return "ORDER BY m.title_ru ASC"
        if sort_mode == "random":
            return "ORDER BY random()"
        return "ORDER BY m.imdb_rating DESC NULLS LAST, m.title_ru ASC"
