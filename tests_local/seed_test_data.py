from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.repositories.movie_repository import upsert_movie_with_relations
from app.repositories.user_repository import ensure_test_users


MOVIES = [
    {
        "rezka_url": "local://movie/fantasy-a",
        "title_ru": "Фантастика A",
        "title_original": "Science Fiction A",
        "year": 2011,
        "content_type": "film",
        "imdb_rating": 9.0,
        "poster_url": "",
        "description": "Тестовый фантастический фильм A.",
        "source_catalog": "tests_local",
        "genres": ["Фантастика", "Драмы"],
        "countries": ["США"],
    },
    {
        "rezka_url": "local://movie/fantasy-b",
        "title_ru": "Фантастика B",
        "title_original": "Science Fiction B",
        "year": 2012,
        "content_type": "film",
        "imdb_rating": 8.8,
        "poster_url": "",
        "description": "Тестовый фантастический фильм B.",
        "source_catalog": "tests_local",
        "genres": ["Фантастика", "Триллеры"],
        "countries": ["США", "Канада"],
    },
    {
        "rezka_url": "local://movie/fantasy-c",
        "title_ru": "Фантастика C",
        "title_original": "Science Fiction C",
        "year": 2013,
        "content_type": "film",
        "imdb_rating": 8.5,
        "poster_url": "",
        "description": "Тестовый фантастический фильм C.",
        "source_catalog": "tests_local",
        "genres": ["Фантастика", "Приключения"],
        "countries": ["Великобритания"],
    },
    {
        "rezka_url": "local://movie/fantasy-d",
        "title_ru": "Фантастика D",
        "title_original": "Science Fiction D",
        "year": 2014,
        "content_type": "film",
        "imdb_rating": 8.2,
        "poster_url": "",
        "description": "Тестовый фантастический фильм D.",
        "source_catalog": "tests_local",
        "genres": ["Фантастика", "Детективы"],
        "countries": ["США", "Великобритания"],
    },
    {
        "rezka_url": "local://movie/fantasy-e",
        "title_ru": "Фантастика E",
        "title_original": "Science Fiction E",
        "year": 2015,
        "content_type": "film",
        "imdb_rating": 7.9,
        "poster_url": "",
        "description": "Тестовый фантастический фильм E.",
        "source_catalog": "tests_local",
        "genres": ["Фантастика", "Комедии"],
        "countries": ["Франция"],
    },
    {
        "rezka_url": "local://movie/fantasy-f",
        "title_ru": "Фантастика F",
        "title_original": "Science Fiction F",
        "year": 2016,
        "content_type": "film",
        "imdb_rating": 7.5,
        "poster_url": "",
        "description": "Тестовый фантастический фильм F.",
        "source_catalog": "tests_local",
        "genres": ["Фантастика", "Ужасы"],
        "countries": ["США"],
    },
    {
        "rezka_url": "local://movie/detective-a",
        "title_ru": "Детектив A",
        "title_original": "Detective A",
        "year": 2017,
        "content_type": "film",
        "imdb_rating": 8.6,
        "poster_url": "",
        "description": "Тестовый детектив.",
        "source_catalog": "tests_local",
        "genres": ["Детективы", "Триллеры"],
        "countries": ["США"],
    },
    {
        "rezka_url": "local://movie/detective-b",
        "title_ru": "Детектив B",
        "title_original": "Detective B",
        "year": 2018,
        "content_type": "series",
        "imdb_rating": 7.7,
        "poster_url": "",
        "description": "Тестовый детективный сериал.",
        "source_catalog": "tests_local",
        "genres": ["Детективы", "Криминал"],
        "countries": ["Великобритания"],
    },
    {
        "rezka_url": "local://movie/anime-a",
        "title_ru": "Аниме A",
        "title_original": "Anime A",
        "year": 2019,
        "content_type": "anime",
        "imdb_rating": 8.1,
        "poster_url": "",
        "description": "Тестовое аниме.",
        "source_catalog": "tests_local",
        "genres": ["Аниме", "Фэнтези"],
        "countries": ["Япония"],
    },
    {
        "rezka_url": "local://movie/no-rating",
        "title_ru": "Без рейтинга",
        "title_original": "No Rating",
        "year": 2020,
        "content_type": "film",
        "imdb_rating": None,
        "poster_url": "",
        "description": "Тестовый фильм без рейтинга.",
        "source_catalog": "tests_local",
        "genres": ["Драмы"],
        "countries": ["США"],
    },
]


def main() -> None:
    ensure_test_users()
    for movie in MOVIES:
        upsert_movie_with_relations(movie)
    print(f"Seeded {len(MOVIES)} movies.")


if __name__ == "__main__":
    main()
