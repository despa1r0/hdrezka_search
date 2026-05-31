from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchItem:
    title: str
    url: str
    original_title: str = ""
    image: str = ""
    category: str = ""
    source_rating: float | None = None
    imdb_rating: float | None = None
    rating: float | None = None
    rating_source: str = ""
    genres: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    seed_genres: list[str] = field(default_factory=list)
    year: str = ""
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "originalTitle": self.original_title,
            "image": self.image,
            "category": self.category,
            "sourceRating": self.source_rating,
            "imdbRating": self.imdb_rating,
            "rating": self.rating,
            "ratingSource": self.rating_source,
            "genres": self.genres,
            "countries": self.countries,
            "year": self.year,
            "description": self.description,
        }
