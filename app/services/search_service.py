from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from typing import Any

from app.clients.imdb import ImdbClient
from app.clients.rezka import RezkaClient, fetch_page_metadata
from app.config import DEFAULT_RESULT_LIMIT, MAX_RESULT_LIMIT
from app.debug import debug_log
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

        options = self._parse_options(params, query)
        started = time.perf_counter()
        accepted = self._collect_single_pass(query, options)
        accepted = self._sort_items(accepted, options["sort_order"])

        return HTTPStatus.OK, {
            "query": query,
            "count": len(accepted),
            "elapsed": round(time.perf_counter() - started, 2),
            "maxResults": options["max_results"],
            "ratingSource": "IMDb",
            "items": [item.as_dict() for item in accepted[: options["max_results"]]],
        }

    def _parse_options(self, params: dict[str, str], query: str) -> dict[str, Any]:
        rating_min, rating_max = self._parse_rating_range(params)
        return {
            "debug": params.get("debug", "").lower() in {"1", "true", "on", "yes"},
            "include_genres": self._include_genres(params, query),
            "include_countries": split_csv(params.get("include_countries", "")),
            "banned_genres": split_csv(params.get("ban_genres", "")),
            "banned_countries": split_csv(params.get("ban_countries", "")),
            "max_results": self._parse_result_limit(params.get("max_results", "")),
            "rating_min": rating_min,
            "rating_max": rating_max,
            "sort_order": params.get("sort_order", "desc"),
        }

    def _parse_result_limit(self, value: str) -> int:
        try:
            requested = int(value)
        except (TypeError, ValueError):
            requested = DEFAULT_RESULT_LIMIT

        return max(1, min(requested, MAX_RESULT_LIMIT))

    def _parse_rating_range(self, params: dict[str, str]) -> tuple[float | None, float | None]:
        rating_range = params.get("rating_range", "").strip()
        if rating_range:
            parts = [part for part in rating_range.replace(",", ".").split("-") if part.strip()]
            ratings = [parse_rating(part) for part in parts]
            ratings = [rating for rating in ratings if rating is not None]
            if len(ratings) >= 2:
                return min(ratings), max(ratings)
            if len(ratings) == 1:
                return ratings[0], None

        return parse_rating(params.get("min_rating", "")), parse_rating(params.get("max_rating", ""))

    def _include_genres(self, params: dict[str, str], query: str) -> list[str]:
        include_genres = split_csv(params.get("include_genres", ""))
        if include_genres:
            return include_genres

        query_genres = split_csv(query)
        if len(query_genres) > 1 and self.rezka_client.genre_slugs(query):
            return query_genres

        return []

    def _collect_single_pass(self, query: str, options: dict[str, Any]) -> list[SearchItem]:
        accepted: list[SearchItem] = []
        seen_urls: set[str] = set()
        candidate_limit = options["max_results"]

        debug_log(
            f"single-pass search query={query!r} candidate_limit={candidate_limit}",
            options["debug"],
        )
        candidates = self.rezka_client.search(query, candidate_limit)
        new_candidates = [item for item in candidates if item.url not in seen_urls]
        self._enrich_items(new_candidates, options)

        for item in new_candidates:
            seen_urls.add(item.url)
            if self._matches_filters(item, options):
                accepted.append(item)

        debug_log(f"done accepted={len(accepted)} scanned={len(seen_urls)}", options["debug"])
        return accepted

    def _enrich_items(self, items: list[SearchItem], options: dict[str, Any]) -> None:
        if not items:
            return

        workers = min(12, len(items))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda item: self._enrich_item(item, options), items))

    def _enrich_item(self, item: SearchItem, options: dict[str, Any]) -> None:
        self._apply_rezka_metadata(item, options["debug"])
        self._apply_imdb_rating(item, options["debug"])

    def _apply_rezka_metadata(self, item: SearchItem, debug: bool) -> None:
        try:
            metadata = fetch_page_metadata(item.url)
        except Exception as exc:
            debug_log(f"metadata failed url={item.url} error={exc}", debug)
            if item.seed_genres and not item.genres:
                item.genres = item.seed_genres
            return

        item.genres = metadata.get("genres") or item.genres or item.seed_genres
        item.countries = metadata.get("countries") or []
        item.year = item.year or metadata.get("year", "")
        item.description = metadata.get("description", "")
        item.image = item.image or metadata.get("image", "")
        item.original_title = metadata.get("originalTitle", "")
        item.source_rating = item.source_rating or metadata.get("rezkaRating")

    def _apply_imdb_rating(self, item: SearchItem, debug: bool) -> None:
        titles = [
            item.original_title,
            item.title,
            transliterate(item.title),
        ]
        try:
            item.imdb_rating = self.imdb_client.fetch_first_rating(titles, item.year)
        except Exception as exc:
            debug_log(f"imdb failed title={item.title!r} year={item.year!r} error={exc}", debug)
            item.imdb_rating = None

        item.rating = item.imdb_rating
        item.rating_source = "IMDb" if item.imdb_rating is not None else ""

    def _matches_filters(self, item: SearchItem, options: dict[str, Any]) -> bool:
        return (
            self._has_all(item.genres, options["include_genres"])
            and self._has_all(item.countries, options["include_countries"])
            and not self._has_any(item.genres, options["banned_genres"])
            and not self._has_any(item.countries, options["banned_countries"])
            and self._passes_rating_range(item, options["rating_min"], options["rating_max"])
        )

    def _passes_rating_range(
        self,
        item: SearchItem,
        rating_min: float | None,
        rating_max: float | None,
    ) -> bool:
        if rating_min is None and rating_max is None:
            return True
        if item.rating is None:
            return False
        if rating_min is not None and item.rating < rating_min:
            return False
        if rating_max is not None and item.rating > rating_max:
            return False
        return True

    def _sort_items(self, items: list[SearchItem], sort_order: str) -> list[SearchItem]:
        reverse = sort_order != "asc"
        rated = [item for item in items if item.rating is not None]
        unrated = [item for item in items if item.rating is None]
        rated = sorted(rated, key=lambda item: (item.rating or 0.0, item.title), reverse=reverse)
        return rated + sorted(unrated, key=lambda item: item.title)

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
