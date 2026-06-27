from __future__ import annotations

import base64
import atexit
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
from threading import Lock, get_ident, local
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.config import (
    REQUEST_TIMEOUT,
    REZKA_ACCEPT_LANGUAGE,
    REZKA_BASE_URL,
    REZKA_FETCH_MODE,
    REZKA_PLAYWRIGHT_BROWSER,
    REZKA_PLAYWRIGHT_HEADLESS,
    REZKA_PLAYWRIGHT_PROFILE_DIR,
    REZKA_PLAYWRIGHT_PROXY,
    REZKA_PLAYWRIGHT_TIMEOUT_MS,
    ROOT_DIR,
    get_rezka_cookie,
    USER_AGENT,
)
from app.models import SearchItem
from app.utils.text import normalize, parse_rating, parse_year, split_csv


GENRE_PATHS = {
    "\u0444\u0430\u043d\u0442\u0430\u0441\u0442\u0438\u043a\u0430": "fiction",
    "\u0444\u0430\u043d\u0442\u0430\u0441\u0442\u0438\u043a\u0438": "fiction",
    "sci-fi": "fiction",
    "scifi": "fiction",
    "\u0434\u0435\u0442\u0435\u043a\u0442\u0438\u0432": "detective",
    "\u0434\u0435\u0442\u0435\u043a\u0442\u0438\u0432\u044b": "detective",
    "\u0443\u0436\u0430\u0441\u044b": "horror",
    "\u0445\u043e\u0440\u0440\u043e\u0440": "horror",
    "\u0431\u043e\u0435\u0432\u0438\u043a": "action",
    "\u0431\u043e\u0435\u0432\u0438\u043a\u0438": "action",
    "\u043a\u043e\u043c\u0435\u0434\u0438\u044f": "comedy",
    "\u043a\u043e\u043c\u0435\u0434\u0438\u0438": "comedy",
    "\u0434\u0440\u0430\u043c\u0430": "drama",
    "\u0434\u0440\u0430\u043c\u044b": "drama",
    "\u043c\u0435\u043b\u043e\u0434\u0440\u0430\u043c\u0430": "romance",
    "\u043c\u0435\u043b\u043e\u0434\u0440\u0430\u043c\u044b": "romance",
    "\u0442\u0440\u0438\u043b\u043b\u0435\u0440": "thriller",
    "\u0442\u0440\u0438\u043b\u043b\u0435\u0440\u044b": "thriller",
    "\u043a\u0440\u0438\u043c\u0438\u043d\u0430\u043b": "crime",
    "\u0444\u044d\u043d\u0442\u0435\u0437\u0438": "fantasy",
    "\u043f\u0440\u0438\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f": "adventures",
    "\u0438\u0441\u0442\u043e\u0440\u0438\u044f": "historical",
    "\u0438\u0441\u0442\u043e\u0440\u0438\u0447\u0435\u0441\u043a\u0438\u0435": "historical",
}

GENRE_NAMES = {
    "fiction": "\u0424\u0430\u043d\u0442\u0430\u0441\u0442\u0438\u043a\u0430",
    "detective": "\u0414\u0435\u0442\u0435\u043a\u0442\u0438\u0432\u044b",
    "horror": "\u0423\u0436\u0430\u0441\u044b",
    "action": "\u0411\u043e\u0435\u0432\u0438\u043a\u0438",
    "comedy": "\u041a\u043e\u043c\u0435\u0434\u0438\u0438",
    "drama": "\u0414\u0440\u0430\u043c\u044b",
    "romance": "\u041c\u0435\u043b\u043e\u0434\u0440\u0430\u043c\u044b",
    "thriller": "\u0422\u0440\u0438\u043b\u043b\u0435\u0440\u044b",
    "crime": "\u041a\u0440\u0438\u043c\u0438\u043d\u0430\u043b",
    "fantasy": "\u0424\u044d\u043d\u0442\u0435\u0437\u0438",
    "adventures": "\u041f\u0440\u0438\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f",
    "historical": "\u0418\u0441\u0442\u043e\u0440\u0438\u0447\u0435\u0441\u043a\u0438\u0435",
}

_playwright_fetcher_lock = Lock()
_playwright_fetchers: list[PlaywrightHtmlFetcher] = []
_playwright_fetcher_local = local()


class RezkaClient:
    def __init__(self, base_url: str = REZKA_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def _search_films_by_genre(self, query: str, limit: int) -> list[SearchItem]:
        slugs = self.genre_slugs(query)
        if not slugs:
            return []

        items: list[SearchItem] = []
        seen_urls: set[str] = set()
        page = 1

        while len(items) < limit:
            page_items: list[SearchItem] = []
            for slug in slugs:
                page_items.extend(self._fetch_catalog_page(self._catalog_page_url(slug, page), slug))

            if not page_items:
                break

            for item in page_items:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    items.append(item)
                if len(items) >= limit:
                    break

            page += 1

        return items

    def genre_slugs(self, query: str) -> list[str]:
        slugs: list[str] = []
        for part in split_csv(query):
            slug = GENRE_PATHS.get(normalize(part))
            if slug and slug not in slugs:
                slugs.append(slug)
        return slugs

    def _catalog_page_url(self, slug: str, page: int, section: str = "films") -> str:
        if page == 1:
            return f"{self.base_url}/{section}/{slug}/"
        return f"{self.base_url}/{section}/{slug}/page/{page}/"

    def _best_page_url(self, slug: str, page: int, section: str = "films") -> str:
        if page == 1:
            return f"{self.base_url}/{section}/best/{slug}/"
        return f"{self.base_url}/{section}/best/{slug}/page/{page}/"

    def new_page_url(self, page: int) -> str:
        if page == 1:
            return f"{self.base_url}/new/"
        return f"{self.base_url}/new/page/{page}/"

    def popular_page_url(self, page: int) -> str:
        if page == 1:
            return f"{self.base_url}/new/?filter=popular"
        return f"{self.base_url}/new/page/{page}/?filter=popular"

    def catalog_page_url(self, slug: str, page: int, section: str = "films") -> str:
        return self._catalog_page_url(slug, page, section)

    def best_page_url(self, slug: str, page: int, section: str = "films") -> str:
        return self._best_page_url(slug, page, section)

    def fetch_catalog_page(self, slug: str, page: int, section: str = "films") -> list[SearchItem]:
        return self._fetch_catalog_page(self._catalog_page_url(slug, page, section), slug)

    def fetch_best_page(self, slug: str, page: int, section: str = "films") -> list[SearchItem]:
        return self._fetch_catalog_page(self._best_page_url(slug, page, section), slug)

    def fetch_new_page(self, page: int) -> list[SearchItem]:
        return self._fetch_catalog_page(self.new_page_url(page))

    def fetch_popular_page(self, page: int) -> list[SearchItem]:
        return self._fetch_catalog_page(self.popular_page_url(page))

    def _fetch_catalog_page(self, url: str, slug: str = "") -> list[SearchItem]:
        html = fetch_rezka_html(
            url,
            referer=self.base_url + "/",
            wait_selector=".b-content__inline_item",
        )
        soup = BeautifulSoup(html, "html.parser")

        items: list[SearchItem] = []
        for node in soup.select(".b-content__inline_item"):
            link = node.select_one(".b-content__inline_item-link a")
            cover = node.select_one(".b-content__inline_item-cover img")
            category_node = node.select_one(".b-content__inline_item-cover .cat .entity")
            if not link:
                continue

            title = link.get_text(" ", strip=True)
            item_url = urljoin(self.base_url + "/", str(link.get("href") or ""))
            if not title or not item_url:
                continue
            image_url = ""
            if cover:
                image_url = urljoin(
                    self.base_url + "/",
                    str(cover.get("src") or cover.get("data-src") or ""),
                )

            items.append(
                SearchItem(
                    title=title,
                    url=item_url,
                    image=image_url,
                    category=category_node.get_text(" ", strip=True) if category_node else "",
                    genres=[GENRE_NAMES[slug]] if slug in GENRE_NAMES else [],
                    seed_genres=[GENRE_NAMES[slug]] if slug in GENRE_NAMES else [],
                    year=parse_year(title),
                )
            )

        return items


@lru_cache(maxsize=512)
def fetch_page_metadata(url: str) -> dict[str, Any]:
    html = fetch_rezka_html(
        url,
        referer=REZKA_BASE_URL,
        wait_selector=".b-post__info, .b-post__description_text",
    )
    soup = BeautifulSoup(html, "html.parser")

    metadata: dict[str, Any] = {
        "genres": [],
        "countries": [],
        "year": "",
        "description": "",
        "imdbId": "",
        "imdbRating": None,
        "image": "",
        "originalTitle": "",
        "rezkaRating": None,
    }

    original_title = soup.select_one(".b-post__origtitle")
    if original_title:
        metadata["originalTitle"] = original_title.get_text(" ", strip=True)

    poster = soup.select_one(".b-sidecover img, .b-post__poster img")
    if poster:
        metadata["image"] = urljoin(REZKA_BASE_URL, str(poster.get("src") or poster.get("data-src") or ""))

    description = soup.select_one(".b-post__description_text")
    if description:
        metadata["description"] = normalize(description.get_text(" "))

    rating = soup.select_one(".b-post__rating .num")
    if rating:
        metadata["rezkaRating"] = parse_rating(rating.get_text(" "))

    imdb_rating = soup.select_one(".b-post__info_rates.imdb .bold")
    if imdb_rating:
        metadata["imdbRating"] = parse_rating(imdb_rating.get_text(" "))

    imdb_link = soup.select_one(".b-post__info_rates.imdb a[href]")
    if imdb_link:
        metadata["imdbId"] = _imdb_id_from_rezka_help_url(str(imdb_link.get("href") or ""))

    info = soup.select_one(".b-post__info")
    if info:
        metadata["year"] = parse_year(info.get_text("\n", strip=True))

    for row in soup.select(".b-post__info tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        key = normalize(cells[0].get_text(" "))
        value = cells[1].get_text(" ", strip=True)

        if "\u0436\u0430\u043d\u0440" in key:
            metadata["genres"] = split_csv(value)
        elif "\u0441\u0442\u0440\u0430\u043d" in key:
            metadata["countries"] = split_csv(value)
        elif "\u0433\u043e\u0434" in key and not metadata["year"]:
            metadata["year"] = parse_year(value)
        elif "\u043e\u0440\u0438\u0433\u0438\u043d" in key:
            metadata["originalTitle"] = metadata["originalTitle"] or value

    if metadata["imdbRating"] is None:
        imdb_rating = soup.select_one('[itemprop="ratingValue"]')
        if imdb_rating:
            metadata["imdbRating"] = parse_rating(imdb_rating.get_text(" "))

    return metadata


def _imdb_id_from_rezka_help_url(value: str) -> str:
    path = urlparse(value).path.strip("/")
    if not path.startswith("help/"):
        return ""
    encoded = path.removeprefix("help/").strip("/")
    try:
        decoded = unquote(base64.b64decode(encoded).decode("utf-8", errors="ignore"))
    except Exception:
        return ""
    parsed = urlparse(decoded)
    parts = [part for part in parsed.path.split("/") if part]
    for index, part in enumerate(parts):
        if part == "title" and index + 1 < len(parts):
            return parts[index + 1]
    return ""


def build_rezka_headers(referer: str = "") -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": REZKA_ACCEPT_LANGUAGE,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i",
    }
    if referer:
        headers["Referer"] = referer
    cookie = get_rezka_cookie()
    if cookie:
        headers["Cookie"] = cookie
    return headers


def fetch_rezka_html(url: str, *, referer: str = "", wait_selector: str = "") -> str:
    if REZKA_FETCH_MODE == "playwright":
        return _get_playwright_fetcher().fetch(url, referer=referer, wait_selector=wait_selector)

    response = requests.get(
        url,
        headers=build_rezka_headers(referer=referer),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


class PlaywrightHtmlFetcher:
    def __init__(self) -> None:
        self._lock = Lock()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    def fetch(self, url: str, *, referer: str = "", wait_selector: str = "") -> str:
        with self._lock:
            context = self._ensure_context()
            page = context.new_page()
            try:
                response = page.goto(
                    url,
                    referer=referer or None,
                    wait_until="domcontentloaded",
                    timeout=REZKA_PLAYWRIGHT_TIMEOUT_MS,
                )
                status = response.status if response else 0
                if status >= 400:
                    try:
                        reason = HTTPStatus(status).phrase
                    except ValueError:
                        reason = "HTTP Error"
                    raise requests.HTTPError(f"{status} Client Error: {reason} for url: {url}")
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=min(10000, REZKA_PLAYWRIGHT_TIMEOUT_MS))
                    except Exception:
                        pass
                return page.content()
            finally:
                page.close()

    def close(self) -> None:
        with self._lock:
            if self._context is not None:
                self._context.close()
                self._context = None
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None

    def _ensure_context(self) -> Any:
        if self._context is not None:
            return self._context

        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        browser_type = getattr(self._playwright, _browser_name(), self._playwright.firefox)
        launch_kwargs = _playwright_launch_kwargs()
        context_kwargs = _playwright_context_kwargs()

        profile_dir = Path(REZKA_PLAYWRIGHT_PROFILE_DIR)
        if not profile_dir.is_absolute():
            profile_dir = ROOT_DIR / profile_dir
        profile_dir = profile_dir / f"thread-{get_ident()}"
        profile_dir.parent.mkdir(parents=True, exist_ok=True)
        self._context = browser_type.launch_persistent_context(
            str(profile_dir),
            **launch_kwargs,
            **context_kwargs,
        )
        _add_cookie_header_to_context(self._context)
        return self._context


def _get_playwright_fetcher() -> PlaywrightHtmlFetcher:
    fetcher = getattr(_playwright_fetcher_local, "fetcher", None)
    if fetcher is not None:
        return fetcher

    with _playwright_fetcher_lock:
        fetcher = getattr(_playwright_fetcher_local, "fetcher", None)
        if fetcher is None:
            fetcher = PlaywrightHtmlFetcher()
            _playwright_fetcher_local.fetcher = fetcher
            _playwright_fetchers.append(fetcher)
            if len(_playwright_fetchers) == 1:
                atexit.register(_close_playwright_fetchers)
        return fetcher


def _close_playwright_fetchers() -> None:
    for fetcher in list(_playwright_fetchers):
        fetcher.close()


def _browser_name() -> str:
    if REZKA_PLAYWRIGHT_BROWSER in {"chromium", "firefox", "webkit"}:
        return REZKA_PLAYWRIGHT_BROWSER
    return "firefox"


def _playwright_launch_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {"headless": REZKA_PLAYWRIGHT_HEADLESS}
    proxy = _playwright_proxy_config()
    if proxy:
        kwargs["proxy"] = proxy
    return kwargs


def _playwright_context_kwargs() -> dict[str, Any]:
    return {
        "user_agent": USER_AGENT,
        "locale": _locale_from_accept_language(REZKA_ACCEPT_LANGUAGE),
        "extra_http_headers": {"Accept-Language": REZKA_ACCEPT_LANGUAGE},
    }


def _playwright_proxy_config() -> dict[str, str]:
    if not REZKA_PLAYWRIGHT_PROXY:
        return {}
    parsed = urlparse(REZKA_PLAYWRIGHT_PROXY)
    if not parsed.scheme or not parsed.hostname:
        return {"server": REZKA_PLAYWRIGHT_PROXY}

    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    config = {"server": server}
    if parsed.username:
        config["username"] = unquote(parsed.username)
    if parsed.password:
        config["password"] = unquote(parsed.password)
    return config


def _locale_from_accept_language(value: str) -> str:
    return value.split(",", 1)[0].strip() or "en-US"


def _add_cookie_header_to_context(context: Any) -> None:
    cookie_header = get_rezka_cookie()
    if not cookie_header:
        return

    parsed_base = urlparse(REZKA_BASE_URL)
    domain = parsed_base.hostname or "rezka.ag"
    cookies = []
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value.strip(),
                "domain": domain,
                "path": "/",
            }
        )
    if cookies:
        context.add_cookies(cookies)
