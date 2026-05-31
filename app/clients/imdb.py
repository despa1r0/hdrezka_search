from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT, USER_AGENT
from app.utils.text import normalize, parse_rating, transliterate


class ImdbClient:
    def fetch_first_rating(self, titles: list[str], year: str = "") -> float | None:
        seen: set[str] = set()
        for title in self._title_variants(titles):
            normalized = normalize(title)
            if not normalized or normalized in seen:
                continue

            seen.add(normalized)
            try:
                rating = self.fetch_rating(title, year)
            except requests.RequestException:
                rating = None

            if rating is not None:
                return rating

        return None

    @lru_cache(maxsize=256)
    def fetch_rating(self, title: str, year: str = "") -> float | None:
        slug = self._build_slug(title)
        if not slug:
            return None

        imdb_id = self._find_imdb_id(slug, title, year)
        if not imdb_id:
            return None

        return self._fetch_rating_from_api(imdb_id) or self._fetch_rating_from_imdb_page(imdb_id)

    def _build_slug(self, title: str) -> str:
        title = transliterate(title)
        return re.sub(r"[^a-zA-Z0-9_ -]", "", title).strip().replace(" ", "_")

    def _title_variants(self, titles: list[str]) -> list[str]:
        variants: list[str] = []
        for title in titles:
            for part in re.split(r"\s*/\s*|\s+\|\s+", title):
                clean = part.strip()
                if clean and clean not in variants:
                    variants.append(clean)
        return variants

    def _find_imdb_id(self, slug: str, original_title: str, year: str = "") -> str:
        url = f"https://v3.sg.media-imdb.com/suggestion/{slug[0].lower()}/{quote(slug)}.json"
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        candidates = response.json().get("d", [])
        if not candidates:
            return ""

        wanted_year = int(year) if year.isdigit() else None
        wanted_title = normalize(transliterate(original_title))

        def score(candidate: dict) -> int:
            value = 0
            candidate_title = normalize(candidate.get("l", ""))
            similarity = SequenceMatcher(None, wanted_title, candidate_title).ratio()
            value += int(similarity * 100)
            if candidate.get("qid") in {"movie", "tvSeries", "tvMiniSeries"}:
                value += 20
            if wanted_year and candidate.get("y") == wanted_year:
                value += 40
            return value

        return str(max(candidates, key=score).get("id") or "")

    def _fetch_rating_from_api(self, imdb_id: str) -> float | None:
        response = requests.get(
            f"https://api.imdbapi.dev/titles/{imdb_id}",
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if not response.ok:
            return None

        rating = response.json().get("rating", {}).get("aggregateRating")
        return parse_rating(rating)

    def _fetch_rating_from_imdb_page(self, imdb_id: str) -> float | None:
        response = requests.get(
            f"https://www.imdb.com/title/{imdb_id}/",
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
            except json.JSONDecodeError:
                continue

            parsed = parse_rating(data.get("aggregateRating", {}).get("ratingValue"))
            if parsed is not None:
                return parsed

        match = re.search(r'"ratingValue"\s*:\s*"?(?P<rating>\d+(?:\.\d+)?)', response.text)
        return parse_rating(match.group("rating")) if match else None
