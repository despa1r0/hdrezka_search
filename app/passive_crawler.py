from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass

from app.clients.rezka import GENRE_NAMES
from app.config import (
    PASSIVE_CRAWLER_BAN_COUNTRIES,
    PASSIVE_CRAWLER_ENABLED,
    PASSIVE_CRAWLER_GENRE_SLUGS,
    PASSIVE_CRAWLER_IMDB_ITEM_LIMIT,
    PASSIVE_CRAWLER_INITIAL_DELAY_SECONDS,
    PASSIVE_CRAWLER_INTERVAL_SECONDS,
    PASSIVE_CRAWLER_ITEM_LIMIT,
    PASSIVE_CRAWLER_PAGE_LIMIT,
    PASSIVE_CRAWLER_SECTIONS,
    PASSIVE_CRAWLER_SLEEP_SECONDS,
    PASSIVE_CRAWLER_STATE_SCOPE,
)
from app.crawler import CrawlFilters, RezkaCrawler, normalize_state_scope
from app.notifier import notify_exception
from app.repositories.crawl_repository import get_catalog_state, log_crawl_event, set_catalog_state
from app.utils.text import split_csv

_scheduler_started = False
_run_lock = threading.Lock()


@dataclass(frozen=True)
class PassiveCatalog:
    source: str
    section: str = "films"
    slug: str = ""

    @property
    def catalog_key(self) -> str:
        if self.source == "new":
            return "new"
        if self.source == "popular":
            return "popular"
        if self.source == "best":
            return f"{self.section}:best:{self.slug}"
        return f"{self.section}:{self.slug}"


def start_passive_crawler_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started or not PASSIVE_CRAWLER_ENABLED:
        return

    _scheduler_started = True
    thread = threading.Thread(target=_scheduler_loop, name="passive-crawler", daemon=True)
    thread.start()


def _scheduler_loop() -> None:
    delay = max(0, PASSIVE_CRAWLER_INITIAL_DELAY_SECONDS)
    if delay:
        time.sleep(delay)

    while True:
        try:
            run_passive_crawl_once()
        except Exception as exc:
            notify_exception("Passive crawler failed", exc)
            log_crawl_event(
                catalog_key="passive",
                level="error",
                message="passive crawler failed",
                context={"error": str(exc)},
            )
        time.sleep(max(60, PASSIVE_CRAWLER_INTERVAL_SECONDS))


def run_passive_crawl_once() -> None:
    if not _run_lock.acquire(blocking=False):
        return
    try:
        catalog = _pick_next_catalog()
        filters = CrawlFilters(ban_countries=split_csv(PASSIVE_CRAWLER_BAN_COUNTRIES))
        crawler = RezkaCrawler(
            page_limit=PASSIVE_CRAWLER_PAGE_LIMIT,
            item_limit=PASSIVE_CRAWLER_ITEM_LIMIT,
            sleep_seconds=PASSIVE_CRAWLER_SLEEP_SECONDS,
            source=catalog.source,
            resume=True,
            genre_slugs=[catalog.slug] if catalog.source == "genres" and catalog.slug else [],
            best_slugs=[catalog.slug] if catalog.source == "best" and catalog.slug else [],
            section=catalog.section,
            filters=filters,
            imdb_enabled=PASSIVE_CRAWLER_IMDB_ITEM_LIMIT > 0,
            imdb_item_limit=PASSIVE_CRAWLER_IMDB_ITEM_LIMIT,
            state_scope=normalize_state_scope(PASSIVE_CRAWLER_STATE_SCOPE),
        )
        stats = crawler.run()
        state_key = f"{normalize_state_scope(PASSIVE_CRAWLER_STATE_SCOPE)}:{catalog.catalog_key}"
        if stats.pages > 0 and stats.seen == 0:
            set_catalog_state(state_key, status="exhausted")
        log_crawl_event(
            catalog_key=state_key,
            message="passive crawl finished",
            context={
                "catalog": catalog.__dict__,
                "stats": stats.__dict__,
                "ban_countries": filters.ban_countries,
            },
        )
    finally:
        _run_lock.release()


def _pick_next_catalog() -> PassiveCatalog:
    catalogs = _passive_catalogs()
    if not catalogs:
        return PassiveCatalog(source="new")

    scope = normalize_state_scope(PASSIVE_CRAWLER_STATE_SCOPE)

    def sort_key(catalog: PassiveCatalog) -> tuple[int, str]:
        state = get_catalog_state(f"{scope}:{catalog.catalog_key}")
        if not state:
            return (0, catalog.catalog_key)
        if state.get("status") == "exhausted":
            return (1_000_000_000, catalog.catalog_key)
        try:
            last_page = int(state.get("last_page") or 0)
        except (TypeError, ValueError):
            last_page = 0
        return (last_page, str(state.get("updated_at") or ""))

    return min(catalogs, key=sort_key)


def _passive_catalogs() -> list[PassiveCatalog]:
    sections = _configured_sections()
    slugs = _configured_slugs()
    catalogs: list[PassiveCatalog] = [PassiveCatalog(source="new"), PassiveCatalog(source="popular")]
    for section in sections:
        for slug in slugs:
            catalogs.append(PassiveCatalog(source="genres", section=section, slug=slug))
            catalogs.append(PassiveCatalog(source="best", section=section, slug=slug))
    return catalogs


def _configured_sections() -> list[str]:
    allowed = {"films", "series", "cartoons", "animation"}
    values = [value for value in split_csv(PASSIVE_CRAWLER_SECTIONS) if value in allowed]
    return values or ["films", "series", "cartoons", "animation"]


def _configured_slugs() -> list[str]:
    values = split_csv(PASSIVE_CRAWLER_GENRE_SLUGS)
    known = set(GENRE_NAMES)
    slugs = [value for value in values if value in known]
    return slugs or sorted(GENRE_NAMES)


def run_once_command(_: argparse.Namespace) -> None:
    run_passive_crawl_once()
    print("Passive crawl cycle finished")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run passive crawler maintenance tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_once_parser = subparsers.add_parser("run-once", help="Run one passive crawler cycle")
    run_once_parser.set_defaults(func=run_once_command)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
