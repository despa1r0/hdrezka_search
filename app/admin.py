from __future__ import annotations

import argparse

from app.config import APP_USERS, ROOT_DIR
from app.database import execute
from app.repositories.user_repository import replace_app_users


def init_empty_db(_: argparse.Namespace) -> None:
    migration_path = ROOT_DIR / "migrations" / "001_init.sql"
    execute(migration_path.read_text(encoding="utf-8"))
    clear_runtime_data()
    replace_app_users()
    print(f"Initialized empty database with APP_USERS={APP_USERS}")


def clear_runtime_data() -> None:
    for table in (
        "shown_items",
        "user_movie_state",
        "movie_genres",
        "movie_countries",
        "crawl_log",
        "catalog_crawl_state",
        "movies",
    ):
        execute(f"DELETE FROM {table}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Administrative database commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init-empty-db",
        help="Apply migrations, clear movies/states/logs, and recreate APP_USERS.",
    )
    init_parser.set_defaults(func=init_empty_db)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
