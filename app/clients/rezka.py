from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests
from bs4 import BeautifulSoup
from HdRezkaApi.search import HdRezkaSearch

from app.config import MAX_RESULTS, REQUEST_TIMEOUT, REZKA_BASE_URL, USER_AGENT
from app.models import SearchItem
from app.utils.text import get_attr, normalize, parse_rating, parse_year, split_csv


class RezkaClient:
    def __init__(self, base_url: str = REZKA_BASE_URL) -> None:
        self.base_url = base_url
        self._search = HdRezkaSearch(base_url)

    def search(self, query: str) -> list[SearchItem]:
        raw_items = self._search(query)
        items: list[SearchItem] = []

        for raw in raw_items[:MAX_RESULTS]:
            title = str(get_attr(raw, "title", "") or "")
            url = str(get_attr(raw, "url", "") or "")
            if not title or not url:
                continue

            source_rating = parse_rating(get_attr(raw, "rating", None))
            category = str(get_attr(raw, "category", "") or "")
            items.append(
                SearchItem(
                    title=title,
                    url=url,
                    image=str(get_attr(raw, "image", "") or ""),
                    category=category,
                    source_rating=source_rating,
                    rating=source_rating,
                    rating_source="Rezka" if source_rating is not None else "",
                    year=parse_year(title, category),
                )
            )

        return items


@lru_cache(maxsize=256)
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

    info = soup.select_one(".b-post__info")
    if info:
        metadata["year"] = parse_year(info.get_text("\n", strip=True))

    for row in soup.select(".b-post__info tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        key = normalize(cells[0].get_text(" "))
        value = cells[1].get_text(" ", strip=True)

        if "жанр" in key:
            metadata["genres"] = split_csv(value)
        elif "стран" in key:
            metadata["countries"] = split_csv(value)
        elif "год" in key and not metadata["year"]:
            metadata["year"] = parse_year(value)
        elif "оригин" in key:
            metadata["originalTitle"] = metadata["originalTitle"] or value

    imdb_rating = soup.select_one('[itemprop="ratingValue"]')
    if imdb_rating:
        metadata["imdbRating"] = parse_rating(imdb_rating.get_text(" "))

    return metadata
