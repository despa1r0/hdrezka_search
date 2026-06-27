from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from app.clients.imdb import ImdbClient
from app.clients.rezka import GENRE_NAMES, RezkaClient, fetch_page_metadata
from app.config import (
    CRAWLER_IMDB_ENABLED,
    CRAWLER_IMDB_ITEM_LIMIT,
    CRAWLER_ITEM_LIMIT,
    CRAWLER_PAGE_LIMIT,
    CRAWLER_SLEEP_SECONDS,
    CRAWLER_SOURCE,
)
from app.notifier import notify_exception
from app.repositories.crawl_repository import get_catalog_state, log_crawl_event, set_catalog_state
from app.repositories.movie_repository import get_movie_by_rezka_url, upsert_movie_with_relations
from app.services.search_service import GENRE_ALIASES
from app.utils.text import normalize, parse_rating, parse_year, split_csv

REZKA_SECTIONS = {"films", "series", "cartoons", "animation"}
CRAWL_STATE_FILTER_FIELDS = (
    "query",
    "include_genres",
    "ban_genres",
    "include_countries",
    "ban_countries",
    "content_type",
    "min_imdb",
    "max_imdb",
)


@dataclass
class CrawlStats:
    catalogs: int = 0
    pages: int = 0
    seen: int = 0
    saved: int = 0
    skipped: int = 0
    existing: int = 0
    imdb_checked: int = 0
    errors: int = 0
    last_error: str = ""


@dataclass
class CrawlFilters:
    include_genres: list[str] = field(default_factory=list)
    ban_genres: list[str] = field(default_factory=list)
    include_countries: list[str] = field(default_factory=list)
    ban_countries: list[str] = field(default_factory=list)
    content_type: str = ""
    min_imdb: float | None = None
    max_imdb: float | None = None


class RezkaCrawler:
    def __init__(
        self,
        *,
        page_limit: int = CRAWLER_PAGE_LIMIT,
        item_limit: int = CRAWLER_ITEM_LIMIT,
        sleep_seconds: float = CRAWLER_SLEEP_SECONDS,
        source: str = CRAWLER_SOURCE,
        imdb_enabled: bool = CRAWLER_IMDB_ENABLED,
        imdb_item_limit: int = CRAWLER_IMDB_ITEM_LIMIT,
        resume: bool = False,
        genre_slugs: list[str] | None = None,
        best_slugs: list[str] | None = None,
        section: str = "films",
        filters: CrawlFilters | None = None,
        state_scope: str = "",
        progress_callback: Callable[..., None] | None = None,
    ) -> None:
        self.page_limit = max(1, page_limit)
        self.item_limit = max(1, item_limit)
        self.sleep_seconds = max(0.0, sleep_seconds)
        self.source = source if source in {"new", "popular", "genres", "best"} else "new"
        self.imdb_enabled = imdb_enabled
        self.imdb_item_limit = max(0, imdb_item_limit)
        self.resume = resume
        self.genre_slugs = genre_slugs or []
        self.best_slugs = best_slugs or []
        self.section = section if section in REZKA_SECTIONS else "films"
        self.filters = filters or CrawlFilters()
        self.state_scope = normalize_state_scope(state_scope)
        self.rezka = RezkaClient()
        self.imdb = ImdbClient()
        self.stats = CrawlStats()
        self._seen_urls: set[str] = set()
        self._current_catalog_url = ""
        self.progress_callback = progress_callback

    def run(self) -> CrawlStats:
        if self.source in {"new", "popular"}:
            self._crawl_listing(self.source)
            log_crawl_event(
                message="crawl finished",
                context=self.stats.__dict__,
            )
            return self.stats

        if self.source == "best":
            for slug in self.best_slugs:
                if self.stats.saved >= self.item_limit:
                    break
                self._crawl_best_catalog(slug)
            log_crawl_event(
                message="crawl finished",
                context=self.stats.__dict__,
            )
            return self.stats

        slugs = self.genre_slugs or sorted(GENRE_NAMES)
        for slug in slugs:
            if self.stats.saved >= self.item_limit:
                break
            self._crawl_catalog(slug)

        log_crawl_event(
            message="crawl finished",
            context=self.stats.__dict__,
        )
        return self.stats

    def _crawl_listing(self, source: str) -> None:
        catalog_key = source
        state_key = self._state_key(catalog_key)
        self.stats.catalogs += 1
        set_catalog_state(state_key, status="running")

        try:
            start_page = self._start_page(catalog_key)
            end_page = start_page + self.page_limit
            for page in range(start_page, end_page):
                if self.stats.saved >= self.item_limit:
                    break

                page_url = (
                    self.rezka.popular_page_url(page)
                    if source == "popular"
                    else self.rezka.new_page_url(page)
                )
                self._current_catalog_url = page_url
                self._report(
                    stage="listing",
                    catalog_key=catalog_key,
                    state_key=state_key,
                    source=source,
                    page=page,
                    url=page_url,
                    catalogUrl=page_url,
                    message=f"Ищу фильмы: {page_url}",
                )
                items = (
                    self.rezka.fetch_popular_page(page)
                    if source == "popular"
                    else self.rezka.fetch_new_page(page)
                )
                self.stats.pages += 1
                set_catalog_state(state_key, last_page=page, status="running")

                if not items:
                    break

                for item in items:
                    if self.stats.saved >= self.item_limit:
                        break
                    if item.url in self._seen_urls:
                        continue
                    self._seen_urls.add(item.url)
                    self.stats.seen += 1
                    self._save_item(catalog_key, item)

                self._sleep()

            set_catalog_state(state_key, status="done")
        except Exception as exc:
            self.stats.errors += 1
            self.stats.last_error = str(exc)
            set_catalog_state(state_key, status="error")
            self._report(
                stage="error",
                catalog_key=catalog_key,
                state_key=state_key,
                source=source,
                error=str(exc),
                message=f"Crawler ошибка: {exc}",
            )
            notify_exception(
                "Crawler listing failed",
                exc,
                extra={"catalog_key": catalog_key, "source": source},
            )
            log_crawl_event(
                catalog_key=catalog_key,
                level="error",
                message="catalog crawl failed",
                context={"source": source, "state_key": state_key, "error": str(exc)},
            )

    def _crawl_best_catalog(self, slug: str) -> None:
        catalog_key = f"{self.section}:best:{slug}"
        state_key = self._state_key(catalog_key)
        self.stats.catalogs += 1
        set_catalog_state(state_key, status="running")

        try:
            start_page = self._start_page(catalog_key)
            end_page = start_page + self.page_limit
            for page in range(start_page, end_page):
                if self.stats.saved >= self.item_limit:
                    break

                page_url = self.rezka.best_page_url(slug, page, self.section)
                self._current_catalog_url = page_url
                self._report(
                    stage="listing",
                    catalog_key=catalog_key,
                    state_key=state_key,
                    slug=slug,
                    page=page,
                    url=page_url,
                    catalogUrl=page_url,
                    message=f"Ищу популярное по фильтру: {page_url}",
                )
                items = self.rezka.fetch_best_page(slug, page, self.section)
                self.stats.pages += 1
                set_catalog_state(state_key, last_page=page, status="running")

                if not items:
                    break

                for item in items:
                    if self.stats.saved >= self.item_limit:
                        break
                    if item.url in self._seen_urls:
                        continue
                    self._seen_urls.add(item.url)
                    self.stats.seen += 1
                    self._save_item(catalog_key, item)

                self._sleep()

            set_catalog_state(state_key, status="done")
        except Exception as exc:
            self.stats.errors += 1
            self.stats.last_error = str(exc)
            set_catalog_state(state_key, status="error")
            self._report(
                stage="error",
                catalog_key=catalog_key,
                state_key=state_key,
                slug=slug,
                error=str(exc),
                message=f"Crawler ошибка: {exc}",
            )
            notify_exception(
                "Crawler best catalog failed",
                exc,
                extra={"catalog_key": catalog_key, "slug": slug},
            )
            log_crawl_event(
                catalog_key=catalog_key,
                level="error",
                message="best catalog crawl failed",
                context={"slug": slug, "state_key": state_key, "error": str(exc)},
            )

    def _crawl_catalog(self, slug: str) -> None:
        catalog_key = f"{self.section}:{slug}"
        state_key = self._state_key(catalog_key)
        self.stats.catalogs += 1
        set_catalog_state(state_key, status="running")

        try:
            start_page = self._start_page(catalog_key)
            end_page = start_page + self.page_limit
            for page in range(start_page, end_page):
                if self.stats.saved >= self.item_limit:
                    break

                page_url = self.rezka.catalog_page_url(slug, page, self.section)
                self._current_catalog_url = page_url
                self._report(
                    stage="listing",
                    catalog_key=catalog_key,
                    state_key=state_key,
                    slug=slug,
                    page=page,
                    url=page_url,
                    catalogUrl=page_url,
                    message=f"Ищу фильмы: {page_url}",
                )
                items = self.rezka.fetch_catalog_page(slug, page, self.section)
                self.stats.pages += 1
                set_catalog_state(state_key, last_page=page, status="running")

                if not items:
                    break

                for item in items:
                    if self.stats.saved >= self.item_limit:
                        break
                    if item.url in self._seen_urls:
                        continue
                    self._seen_urls.add(item.url)
                    self.stats.seen += 1
                    self._save_item(catalog_key, item)

                self._sleep()

            set_catalog_state(state_key, status="done")
        except Exception as exc:
            self.stats.errors += 1
            self.stats.last_error = str(exc)
            set_catalog_state(state_key, status="error")
            self._report(
                stage="error",
                catalog_key=catalog_key,
                state_key=state_key,
                slug=slug,
                error=str(exc),
                message=f"Crawler ошибка: {exc}",
            )
            notify_exception(
                "Crawler catalog failed",
                exc,
                extra={"catalog_key": catalog_key, "slug": slug},
            )
            log_crawl_event(
                catalog_key=catalog_key,
                level="error",
                message="catalog crawl failed",
                context={"slug": slug, "state_key": state_key, "error": str(exc)},
            )

    def _save_item(self, catalog_key: str, item: Any) -> None:
        existing = get_movie_by_rezka_url(item.url)
        if existing:
            self.stats.existing += 1
            self.stats.skipped += 1
            self._report(
                stage="skip_existing",
                catalog_key=catalog_key,
                url=item.url,
                title=item.title,
                message=f"Уже есть в БД, пропускаю: {item.title}",
            )
            return

        metadata: dict[str, Any] = {}
        try:
            self._report(
                stage="metadata",
                catalog_key=catalog_key,
                url=item.url,
                title=item.title,
                message=f"Читаю страницу фильма: {item.url}",
            )
            metadata = fetch_page_metadata(item.url)
            self._sleep()
        except requests.RequestException as exc:
            self.stats.errors += 1
            self.stats.last_error = str(exc)
            self._report(
                stage="metadata_error",
                catalog_key=catalog_key,
                url=item.url,
                title=item.title,
                error=str(exc),
                message=f"Не удалось прочитать страницу фильма: {item.url}",
            )
            log_crawl_event(
                catalog_key=catalog_key,
                level="warning",
                message="metadata fetch failed",
                context={"url": item.url, "error": str(exc)},
            )

        imdb_rating = metadata.get("imdbRating")
        if imdb_rating is None and self._should_fetch_imdb():
            imdb_rating = self._fetch_imdb_rating(catalog_key, item, metadata)

        movie = {
            "rezka_url": item.url,
            "title_ru": item.title,
            "title_original": metadata.get("originalTitle") or item.original_title or "",
            "year": _year_as_int(metadata.get("year") or item.year),
            "content_type": _content_type(item.category, self.section, item.url),
            "imdb_id": metadata.get("imdbId") or None,
            "imdb_rating": imdb_rating,
            "imdb_match_confidence": None,
            "poster_url": metadata.get("image") or item.image or "",
            "description": metadata.get("description") or item.description or "",
            "source_catalog": catalog_key,
            "genres": metadata.get("genres") or item.genres or item.seed_genres,
            "countries": metadata.get("countries") or item.countries,
        }
        if not self._matches_filters(movie):
            self.stats.skipped += 1
            return

        movie_id = upsert_movie_with_relations(movie)
        self.stats.saved += 1
        self._report(
            stage="saved",
            catalog_key=catalog_key,
            url=item.url,
            title=item.title,
            message=f"Сохранено: {item.title}",
        )
        set_catalog_state(
            self._state_key(catalog_key),
            last_movie_url=item.url,
            status="running",
        )
        log_crawl_event(
            catalog_key=catalog_key,
            movie_id=movie_id,
            message="movie saved",
            context={"url": item.url, "title": item.title},
        )

    def _should_fetch_imdb(self) -> bool:
        return self.imdb_enabled and self.stats.imdb_checked < self.imdb_item_limit

    def _fetch_imdb_rating(self, catalog_key: str, item: Any, metadata: dict[str, Any]) -> float | None:
        self.stats.imdb_checked += 1
        titles = [
            str(metadata.get("originalTitle") or ""),
            str(item.original_title or ""),
            str(item.title or ""),
        ]
        year = str(metadata.get("year") or item.year or "")
        try:
            rating = self.imdb.fetch_first_rating(titles, year)
            self._sleep()
            return rating
        except requests.RequestException as exc:
            self.stats.errors += 1
            self.stats.last_error = str(exc)
            self._report(
                stage="imdb_error",
                catalog_key=catalog_key,
                url=item.url,
                title=item.title,
                error=str(exc),
                message=f"Не удалось получить IMDb-рейтинг: {item.title}",
            )
            log_crawl_event(
                catalog_key=catalog_key,
                level="warning",
                message="imdb rating fetch failed",
                context={"url": item.url, "title": item.title, "error": str(exc)},
            )
            return None

    def _sleep(self) -> None:
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)

    def _report(self, **payload: Any) -> None:
        if not self.progress_callback:
            return
        payload["stats"] = self.stats.__dict__.copy()
        if self._current_catalog_url and "catalogUrl" not in payload:
            payload["catalogUrl"] = self._current_catalog_url
        self.progress_callback(**payload)

    def _start_page(self, catalog_key: str) -> int:
        if not self.resume:
            return 1
        state = get_catalog_state(self._state_key(catalog_key))
        if not state:
            return 1
        try:
            last_page = int(state.get("last_page") or 0)
        except (TypeError, ValueError):
            return 1
        if last_page <= 0 and state.get("last_movie_url"):
            return 2
        return max(1, last_page + 1)

    def _state_key(self, catalog_key: str) -> str:
        if not self.state_scope:
            return catalog_key
        return f"{self.state_scope}:{catalog_key}"

    def _matches_filters(self, movie: dict[str, Any]) -> bool:
        if self.filters.content_type and movie["content_type"] != self.filters.content_type:
            return False

        genres = _normalized_set(movie.get("genres") or [])
        countries = _normalized_set(movie.get("countries") or [])

        include_genres = _normalized_set(_canonical_genres(self.filters.include_genres))
        if include_genres and not include_genres.issubset(genres):
            return False

        ban_genres = _normalized_set(_canonical_genres(self.filters.ban_genres))
        if ban_genres and genres.intersection(ban_genres):
            return False

        include_countries = _normalized_set(self.filters.include_countries)
        if include_countries and not include_countries.issubset(countries):
            return False

        ban_countries = _normalized_set(self.filters.ban_countries)
        if ban_countries and countries.intersection(ban_countries):
            return False

        imdb_rating = movie.get("imdb_rating")
        if self.filters.min_imdb is not None:
            if imdb_rating is None or float(imdb_rating) < self.filters.min_imdb:
                return False
        if self.filters.max_imdb is not None:
            if imdb_rating is None or float(imdb_rating) > self.filters.max_imdb:
                return False

        return True


def _year_as_int(value: Any) -> int | None:
    year = parse_year(str(value or ""))
    return int(year) if year else None


def _content_type(category: str, section: str = "", url: str = "") -> str:
    parsed_section = _section_from_url(url)
    if parsed_section:
        return parsed_section

    clean = normalize(str(category or ""))
    if "сериал" in clean or "serial" in clean or "series" in clean:
        return "series"
    if "аниме" in clean or "anime" in clean:
        return "anime"
    if "мульт" in clean or "mult" in clean or "cartoon" in clean:
        return "cartoon"

    if section == "animation":
        return "anime"
    if section == "cartoons":
        return "cartoon"
    if section == "series":
        return "series"
    return "film"


def _section_from_url(url: str) -> str:
    path = urlparse(str(url or "")).path
    if path.startswith("/animation/"):
        return "anime"
    if path.startswith("/cartoons/"):
        return "cartoon"
    if path.startswith("/series/"):
        return "series"
    if path.startswith("/films/"):
        return "film"
    return ""


def _normalized_set(values: list[str]) -> set[str]:
    return {normalize(value) for value in values if str(value).strip()}


def _canonical_genres(values: list[str]) -> list[str]:
    return [GENRE_ALIASES.get(normalize(value), value.strip()) for value in values if value.strip()]


def filters_from_params(params: dict[str, str]) -> CrawlFilters:
    include_genres = _canonical_genres(split_csv(params.get("include_genres", "")))
    if not include_genres:
        include_genres = _genres_from_query(params.get("query", params.get("q", "")))
    return CrawlFilters(
        include_genres=include_genres,
        ban_genres=_canonical_genres(split_csv(params.get("ban_genres", ""))),
        include_countries=split_csv(params.get("include_countries", "")),
        ban_countries=split_csv(params.get("ban_countries", "")),
        content_type=_content_type_filter(params.get("content_type", "")),
        min_imdb=parse_rating(params.get("min_imdb", params.get("min_rating", ""))),
        max_imdb=parse_rating(params.get("max_imdb", params.get("max_rating", ""))),
    )


def build_crawl_state_scope(
    params: dict[str, str],
    *,
    source: str,
    section: str,
    genre_slugs: list[str],
    best_slugs: list[str],
) -> str:
    payload: dict[str, Any] = {
        "source": source,
        "requested_source": str(params.get("crawl_source", "auto")).strip().lower() or "auto",
        "section": section,
        "genre_slugs": sorted({normalize(slug) for slug in genre_slugs if str(slug).strip()}),
        "best_slugs": sorted({normalize(slug) for slug in best_slugs if str(slug).strip()}),
        "filters": {},
    }
    filters = payload["filters"]
    for field_name in CRAWL_STATE_FILTER_FIELDS:
        value = params.get(field_name, "")
        if field_name in {"include_genres", "ban_genres", "include_countries", "ban_countries"}:
            filters[field_name] = sorted({normalize(item) for item in split_csv(str(value or ""))})
        else:
            filters[field_name] = normalize(str(value or ""))

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"ui:{source}:{section}:{digest}"


def genre_slugs_from_params(params: dict[str, str]) -> list[str]:
    client = RezkaClient()
    include_genres = split_csv(params.get("include_genres", ""))
    if include_genres:
        return client.genre_slugs(",".join(include_genres))
    query = params.get("query", params.get("q", "")).strip()
    return client.genre_slugs(query)


def best_slugs_from_params(params: dict[str, str]) -> list[str]:
    return genre_slugs_from_params(params)


def _genres_from_query(query: str) -> list[str]:
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


def section_from_params(params: dict[str, str]) -> str:
    content_type = _content_type_filter(params.get("content_type", ""))
    if content_type == "series":
        return "series"
    if content_type == "cartoon":
        return "cartoons"
    if content_type == "anime":
        return "animation"
    return "films"


def _content_type_filter(value: str) -> str:
    clean = str(value or "").strip().lower()
    if clean in {"", "all", "any"}:
        return ""
    return clean


def normalize_state_scope(value: str) -> str:
    clean = str(value or "").strip().lower()
    allowed = []
    for char in clean:
        if char.isalnum() or char in {":", "-", "_"}:
            allowed.append(char)
        else:
            allowed.append("-")
    return "".join(allowed).strip("-")


def run_crawler(args: argparse.Namespace) -> None:
    crawler = RezkaCrawler(
        page_limit=args.page_limit,
        item_limit=args.item_limit,
        sleep_seconds=args.sleep_seconds,
        source=args.source,
        imdb_enabled=not args.no_imdb,
        imdb_item_limit=args.imdb_item_limit,
        resume=args.resume,
        genre_slugs=split_csv(args.genre_slugs),
        best_slugs=split_csv(args.best_slugs),
        section=args.section,
    )
    stats = crawler.run()
    print(
        "Crawl finished: "
        f"source={args.source} catalogs={stats.catalogs} pages={stats.pages} seen={stats.seen} "
        f"saved={stats.saved} imdb_checked={stats.imdb_checked} errors={stats.errors}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl Rezka catalog pages into PostgreSQL.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run the crawler")
    run_parser.add_argument("--page-limit", type=int, default=CRAWLER_PAGE_LIMIT)
    run_parser.add_argument("--item-limit", type=int, default=CRAWLER_ITEM_LIMIT)
    run_parser.add_argument("--sleep-seconds", type=float, default=CRAWLER_SLEEP_SECONDS)
    run_parser.add_argument("--source", choices=["new", "popular", "genres", "best"], default=CRAWLER_SOURCE)
    run_parser.add_argument("--genre-slugs", default="")
    run_parser.add_argument("--best-slugs", default="")
    run_parser.add_argument("--section", choices=sorted(REZKA_SECTIONS), default="films")
    run_parser.add_argument("--imdb-item-limit", type=int, default=CRAWLER_IMDB_ITEM_LIMIT)
    run_parser.add_argument("--no-imdb", action="store_true", default=not CRAWLER_IMDB_ENABLED)
    run_parser.add_argument("--resume", action="store_true")
    run_parser.set_defaults(func=run_crawler)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
