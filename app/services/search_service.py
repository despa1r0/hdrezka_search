from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from typing import Any

from app.clients.imdb import ImdbClient
from app.clients.rezka import RezkaClient, fetch_page_metadata
from app.models import SearchItem
from app.utils.text import normalize, split_csv, transliterate


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
            return HTTPStatus.BAD_REQUEST, {
                "error": "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u043e\u0438\u0441\u043a\u043e\u0432\u044b\u0439 \u0437\u0430\u043f\u0440\u043e\u0441."
            }

        banned_genres = split_csv(params.get("ban_genres", ""))
        banned_countries = split_csv(params.get("ban_countries", ""))

        started = time.perf_counter()
        items = self.rezka_client.search(query)
        self._enrich_items(items, query)
        items = self._filter_items(items, banned_genres, banned_countries)

        return HTTPStatus.OK, {
            "query": query,
            "count": len(items),
            "elapsed": round(time.perf_counter() - started, 2),
            "items": [item.as_dict() for item in items],
        }

    def _enrich_items(self, items: list[SearchItem], fallback_query: str) -> None:
        if not items:
            return

        workers = min(12, len(items))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda item: self._enrich_item(item, fallback_query), items))

    def _enrich_item(self, item: SearchItem, fallback_query: str) -> None:
        self._apply_rezka_metadata(item)
        self._apply_imdb_fallback(item, fallback_query)

    def _apply_rezka_metadata(self, item: SearchItem) -> None:
        try:
            metadata = fetch_page_metadata(item.url)
        except Exception:
            return

        item.genres = metadata.get("genres") or []
        item.countries = metadata.get("countries") or []
        item.year = item.year or metadata.get("year", "")
        item.description = metadata.get("description", "")
        item.imdb_rating = metadata.get("imdbRating")
        item.image = item.image or metadata.get("image", "")
        item.original_title = metadata.get("originalTitle", "")

        rezka_rating = metadata.get("rezkaRating")
        if item.source_rating is None and rezka_rating is not None:
            item.source_rating = rezka_rating
            item.rating = rezka_rating
            item.rating_source = "Rezka"

    def _apply_imdb_fallback(self, item: SearchItem, fallback_query: str) -> None:
        if item.rating is not None:
            return

        titles = [
            item.original_title,
            item.title,
            fallback_query,
            transliterate(item.title),
        ]
        item.imdb_rating = item.imdb_rating or self.imdb_client.fetch_first_rating(titles, item.year)
        item.rating = item.imdb_rating
        item.rating_source = "IMDb" if item.imdb_rating is not None else ""

    def _filter_items(
        self,
        items: list[SearchItem],
        banned_genres: list[str],
        banned_countries: list[str],
    ) -> list[SearchItem]:
        filtered = [
            item
            for item in items
            if not self._banned_match(item.genres, banned_genres)
            and not self._banned_match(item.countries, banned_countries)
        ]

        return sorted(
            filtered,
            key=lambda item: (item.rating is not None, item.rating or 0.0, item.title),
            reverse=True,
        )

    def _banned_match(self, values: list[str], banned: list[str]) -> bool:
        normalized_values = [normalize(value) for value in values]
        normalized_banned = [normalize(value) for value in banned if value.strip()]
        return any(
            banned_value in item_value
            for banned_value in normalized_banned
            for item_value in normalized_values
        )
