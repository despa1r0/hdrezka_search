from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from typing import Any

from app.clients.imdb import ImdbClient
from app.clients.rezka import RezkaClient, fetch_page_metadata
from app.config import DEFAULT_RESULT_LIMIT, MAX_RESULT_LIMIT
from app.models import SearchItem
from app.utils.text import normalize, parse_rating, split_csv, transliterate


class SearchService:
    def __init__(
        self,
        rezka_client: RezkaClient | None = None,
        imdb_client: ImdbClient | None = None,
    ) -> None:
        self.rezka_client = rezka_client or RezkaClient()
        self.imdb_client = imdb_client or ImdbClient()

    def search(self, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
        query = params.get("q", "").strip()
        if not query:
            return HTTPStatus.BAD_REQUEST, {"error": "Введите поисковый запрос."}

        max_results = self._parse_result_limit(params.get("max_results", ""))
        min_rating = parse_rating(params.get("min_rating", ""))
        include_genres = self._include_genres(params, query)
        include_countries = split_csv(params.get("include_countries", ""))
        banned_genres = split_csv(params.get("ban_genres", ""))
        banned_countries = split_csv(params.get("ban_countries", ""))

        started = time.perf_counter()
        items = self.rezka_client.search(query, max_results)
        self._enrich_items(items, query)
        items = self._filter_items(
            items=items,
            include_genres=include_genres,
            include_countries=include_countries,
            banned_genres=banned_genres,
            banned_countries=banned_countries,
            min_rating=min_rating,
        )
        items = items[:max_results]

        return HTTPStatus.OK, {
            "query": query,
            "count": len(items),
            "elapsed": round(time.perf_counter() - started, 2),
            "maxResults": max_results,
            "ratingSource": "IMDb",
            "items": [item.as_dict() for item in items],
        }

    def _parse_result_limit(self, value: str) -> int:
        try:
            requested = int(value)
        except (TypeError, ValueError):
            requested = DEFAULT_RESULT_LIMIT

        return max(1, min(requested, MAX_RESULT_LIMIT))

    def _include_genres(self, params: dict[str, str], query: str) -> list[str]:
        include_genres = split_csv(params.get("include_genres", ""))
        if include_genres:
            return include_genres

        query_genres = split_csv(query)
        if len(query_genres) > 1 and self.rezka_client.genre_slugs(query):
            return query_genres

        return []

    def _enrich_items(self, items: list[SearchItem], fallback_query: str) -> None:
        if not items:
            return

        workers = min(12, len(items))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda item: self._enrich_item(item, fallback_query), items))

    def _enrich_item(self, item: SearchItem, fallback_query: str) -> None:
        self._apply_rezka_metadata(item)
        self._apply_imdb_rating(item, fallback_query)

    def _apply_rezka_metadata(self, item: SearchItem) -> None:
        try:
            metadata = fetch_page_metadata(item.url)
        except Exception:
            return

        item.genres = metadata.get("genres") or []
        item.countries = metadata.get("countries") or []
        item.year = item.year or metadata.get("year", "")
        item.description = metadata.get("description", "")
        item.image = item.image or metadata.get("image", "")
        item.original_title = metadata.get("originalTitle", "")
        item.source_rating = item.source_rating or metadata.get("rezkaRating")

    def _apply_imdb_rating(self, item: SearchItem, fallback_query: str) -> None:
        titles = [
            item.original_title,
            item.title,
            fallback_query,
            transliterate(item.title),
        ]
        item.imdb_rating = self.imdb_client.fetch_first_rating(titles, item.year)
        item.rating = item.imdb_rating
        item.rating_source = "IMDb" if item.imdb_rating is not None else ""

    def _filter_items(
        self,
        items: list[SearchItem],
        include_genres: list[str],
        include_countries: list[str],
        banned_genres: list[str],
        banned_countries: list[str],
        min_rating: float | None,
    ) -> list[SearchItem]:
        filtered = [
            item
            for item in items
            if self._has_all(item.genres, include_genres)
            and self._has_all(item.countries, include_countries)
            and not self._has_any(item.genres, banned_genres)
            and not self._has_any(item.countries, banned_countries)
            and self._passes_min_rating(item, min_rating)
        ]

        return sorted(
            filtered,
            key=lambda item: (item.rating is not None, item.rating or 0.0, item.title),
            reverse=True,
        )

    def _passes_min_rating(self, item: SearchItem, min_rating: float | None) -> bool:
        if min_rating is None:
            return True
        return item.rating is not None and item.rating >= min_rating

    def _has_any(self, values: list[str], needles: list[str]) -> bool:
        normalized_values = [normalize(value) for value in values]
        normalized_needles = [normalize(value) for value in needles if value.strip()]
        return any(
            needle in value
            for needle in normalized_needles
            for value in normalized_values
        )

    def _has_all(self, values: list[str], needles: list[str]) -> bool:
        normalized_values = [normalize(value) for value in values]
        normalized_needles = [normalize(value) for value in needles if value.strip()]
        return all(
            any(needle in value for value in normalized_values)
            for needle in normalized_needles
        )
