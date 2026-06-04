from __future__ import annotations

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database import execute
from app.repositories.user_repository import ensure_test_users


def main() -> None:
    execute("DELETE FROM shown_items")
    execute("DELETE FROM user_movie_state")
    execute("DELETE FROM movie_genres")
    execute("DELETE FROM movie_countries")
    execute("DELETE FROM movies")
    ensure_test_users()
    print("Reset movie/state/shown data. Kept test users.")


if __name__ == "__main__":
    main()
