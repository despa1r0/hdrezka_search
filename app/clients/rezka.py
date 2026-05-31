from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests
from bs4 import BeautifulSoup
from HdRezkaApi.search import HdRezkaSearch

from app.config import DEFAULT_RESULT_LIMIT, REQUEST_TIMEOUT, REZKA_BASE_URL, USER_AGENT
from app.models import SearchItem
from app.utils.text import get_attr, normalize, parse_rating, parse_year, split_csv


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


class RezkaClient:
    def __init__(self, base_url: str = REZKA_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self._search = HdRezkaSearch(base_url)

    def search(self, query: str, limit: int = DEFAULT_RESULT_LIMIT) -> list[SearchItem]:
        genre_items = self._search_films_by_genre(query, limit)
        if genre_items:
            return genre_items

        return self._advanced_search(query, limit)

    def _advanced_search(self, query: str, limit: int) -> list[SearchItem]:
        result = self._search(query, find_all=True)
        items: list[SearchItem] = []
        seen_urls: set[str] = set()
        page = 1

        while len(items) < limit:
            page_items = result.get_page(page)
            if not page_items:
                break

            for raw in page_items:
                item = self._item_from_raw(raw)
                if item and item.url not in seen_urls:
                    seen_urls.add(item.url)
                    items.append(item)
                if len(items) >= limit:
                    break

            page += 1

        return items

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

    def _catalog_page_url(self, slug: str, page: int) -> str:
        if page == 1:
            return f"{self.base_url}/films/{slug}/"
        return f"{self.base_url}/films/{slug}/page/{page}/"

    def _fetch_catalog_page(self, url: str, slug: str = "") -> list[SearchItem]:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        items: list[SearchItem] = []
        for node in soup.select(".b-content__inline_item"):
            link = node.select_one(".b-content__inline_item-link a")
            cover = node.select_one(".b-content__inline_item-cover img")
            if not link:
                continue

            title = link.get_text(" ", strip=True)
            item_url = str(link.get("href") or "")
            if not title or not item_url:
                continue

            items.append(
                SearchItem(
                    title=title,
                    url=item_url,
                    image=str(cover.get("src") if cover else ""),
                    category="films",
                    genres=[GENRE_NAMES[slug]] if slug in GENRE_NAMES else [],
                    seed_genres=[GENRE_NAMES[slug]] if slug in GENRE_NAMES else [],
                    year=parse_year(title),
                )
            )

        return items

    def _item_from_raw(self, raw: Any) -> SearchItem | None:
        title = str(get_attr(raw, "title", "") or "")
        url = str(get_attr(raw, "url", "") or "")
        if not title or not url:
            return None

        source_rating = parse_rating(get_attr(raw, "rating", None))
        category = str(get_attr(raw, "category", "") or "")
        return SearchItem(
            title=title,
            url=url,
            image=str(get_attr(raw, "image", "") or ""),
            category=category,
            source_rating=source_rating,
            year=parse_year(title, category),
        )


@lru_cache(maxsize=512)
def fetch_page_metadata(url: str) -> dict[str, Any]:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    metadata: dict[str, Any] = {
        "genres": [],
        "countries": [],
        "year": "",
        "description": "",
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
        metadata["image"] = poster.get("src", "")

    description = soup.select_one(".b-post__description_text")
    if description:
        metadata["description"] = normalize(description.get_text(" "))

    rating = soup.select_one(".b-post__rating .num")
    if rating:
        metadata["rezkaRating"] = parse_rating(rating.get_text(" "))

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

    imdb_rating = soup.select_one('[itemprop="ratingValue"]')
    if imdb_rating:
        metadata["imdbRating"] = parse_rating(imdb_rating.get_text(" "))

    return metadata
